import os
import re
import time
import logging
import dateutil.parser
from github_monitor.apps.monitor.processors.factory import AbstractTaskProcessor
from django.conf import settings
from django.utils import timezone
from github import Github
from github import GithubException
from github.GithubException import UnknownObjectException
from urllib3.exceptions import ReadTimeoutError



logger = logging.getLogger(__name__)
RS = settings.RS
per_page = 50


class TaskProcessor(AbstractTaskProcessor):
    @staticmethod
    def get_available_token():
        for key in RS.keys():
            key = key.decode()
            if key.startswith('token'):
                reset = RS.hget(key, 'reset').decode()
                if not reset or float(reset) < timezone.now().timestamp():
                    return key.split(':')[1]
        return None

    def _new_session(self):
        # 返回一个可用token所创建的git session
        while True:
            token = self.get_available_token()
            if token:
                return Github(login_or_token=token, per_page=per_page), token
            time.sleep(0.5)

    def _reset_token(self, session, token):
        rate_limit = session.get_rate_limit()
        reset_time = rate_limit.search.reset.timestamp()
        RS.hset('token:%s' % token, 'reset', reset_time)
        return self._new_session()

    def search(self, keyword):
        session, _token = self._new_session()
        while True:
            try:
                response = session.search_code(keyword, sort='indexed', order='desc', highlight=True)
                # github api支持最多搜索1000条记录
                total = min(response.totalCount, 1000)
                break
            except GithubException as e:
                if 'rate limit' in e.data.get('message', ''):
                    session, _token = self._reset_token(session, _token)
                else:
                    logger.exception(e)
                continue
            # 防止由于网络原因导致的获取失败
            except ReadTimeoutError:
                continue
        # E.G. total = 50，max_page = 1; total = 51, max_page = 2
        # 需要搜索的页数为max_page和task.page中最小的值
        max_page = (total // per_page) if (not total % per_page) else (total // per_page + 1)
        pages = min(max_page, self.task.pages) if self.task.pages else max_page
        # 搜索代码
        page = 0
        while page < pages:
            try:
                page_content = response.get_page(page)
                page += 1
            except GithubException as e:
                if 'abuse-rate-limits' in e.data.get('documentation_url'):
                    session, _token = self._reset_token(session, _token)
                else:
                    logger.exception(e)
                continue
            # 防止由于网络原因导致的获取失败
            except ReadTimeoutError:
                continue
            self.process_pages(page_content, keyword)
    def process_pages(self, _contents, _keyword):
        from github_monitor.apps.monitor.models.leakage import Leakage
        def get_data(github_file):
            if not github_file.last_modified:
                try:
                    github_file.update()
                except UnknownObjectException:
                    pass
            repo = github_file.repository
            return {
                'task': self.task,
                'keyword': _keyword,
                'sha': github_file.sha,
                'fragment': format_fragments(github_file.text_matches),
                'html_url': github_file.html_url,
                'last_modified': dateutil.parser.parse(github_file.last_modified) if github_file.last_modified else None,
                'file_name': github_file.name,
                'repo_name': repo.name,
                'repo_url': repo.html_url,
                'user_avatar': repo.owner.avatar_url,
                'user_name': repo.owner.login,
                'user_url': repo.owner.html_url
            }

        def format_fragments(_text_matches):
            return ''.join([f['fragment'] for f in _text_matches])

        # 根据任务匹配模式 进行相应的操作
        def check_match_mode(_fragment):
            # 精确匹配：如果关键词不在内容中,则跳过
            if self.task.match_method == 1 and _keyword not in _fragment:
                    return True

            # 单词匹配
            if self.task.match_method == 2 and re.search(r'\b' + _keyword + r'\b', _fragment) is None:
                    return True

        for _file in _contents:

            # 根据配置的规则、忽略某些账号或仓库下的代码
            repository = _file.repository
            user = repository.owner.login
            repo_name = repository.name
            ignore = False
            for org in self.task.ignore_org.split('\n'):
                if user == org.strip(' \r\n'):
                    ignore = True
            for _repo in self.task.ignore_repo.split('\n'):
                _repo = _repo.strip(' \r\n')
                if _repo and (_repo in repo_name):
                    ignore = True
            if ignore:
                continue

            exists_leakages = Leakage.objects.filter(sha=_file.sha)
            if exists_leakages:
                if exists_leakages.filter(status=1):
                    update_data = get_data(_file)

                    # 判断匹配模式
                    if check_match_mode(update_data['fragment']):
                        continue

                    self.email_results.append(update_data)
                    update_data.update({'status': 0, 'add_time': timezone.now()})
                    exists_leakages.filter(status=1).update(**update_data)
            else:
                data = get_data(_file)

                # 判断匹配模式
                if check_match_mode(data['fragment']):
                    continue

                self.email_results.append(data)
                Leakage(**data).save()
