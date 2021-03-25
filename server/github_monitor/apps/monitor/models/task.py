import os
from django.db import models
from importlib import import_module
from github_monitor.apps.monitor.processors.factory import AbstractTaskProcessor


def get_processor_choices() -> list:
    choices = []
    module = import_module(f"github_monitor.apps.monitor.processors.backends")
    for root, dirs, files in os.walk(module.__path__[0]):
        if root == module.__path__[0]:
            for file in files:
                if file.endswith(".py"):
                    processor_name = file.rsplit('.')[0]
                    m = import_module(f"github_monitor.apps.monitor.processors.backends.{processor_name}")
                    if getattr(m, 'TaskProcessor', None) and issubclass(getattr(m, 'TaskProcessor'), AbstractTaskProcessor):
                        choices.append((processor_name, m.TaskProcessor.name()))
            break
    return choices


class Task(models.Model):
    statusItemChoices = (
        (0, '等待中'),
        (1, '运行中'),
        (2, '完成')
    )
    matchMethodChoices = (
        (0, '模糊匹配'),
        (1, '精确匹配'),
        (2, '单词匹配')
    )

    name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name=u'任务名'
    )
    keywords = models.TextField(null=False, blank=False, verbose_name='关键词')
    match_method = models.IntegerField(choices=matchMethodChoices, default=0)
    pages = models.IntegerField(default=5, null=False, verbose_name='爬取页数')
    interval = models.IntegerField(default=60, null=False, verbose_name='爬取间隔(分钟)')
    ignore_org = models.TextField(null=True, default='', verbose_name='忽略指定组织或账号下的代码')
    ignore_repo = models.TextField(null=True, default='', verbose_name='忽略某类仓库下的代码, 如 github.io')
    status = models.IntegerField(choices=statusItemChoices, default=0)
    start_time = models.DateTimeField(null=True)
    finished_time = models.DateTimeField(null=True)
    mail = models.TextField(null=True, default='', verbose_name='通知邮箱列表')
    processor = models.CharField('processor', max_length=16, choices=get_processor_choices(), default='github')
