import json
import sys, os, logging, time
from abc import ABC, abstractmethod
from importlib import import_module
from typing import Optional
from django.core.mail import EmailMessage
from django.conf import settings
from django.db import connection, close_old_connections
from django.template.loader import render_to_string
from django.utils import timezone
from threading import Thread

logger = logging.getLogger(__name__)


class AbstractTaskProcessor(ABC):
    def __init__(self, task):
        self.task = task
        self.email_results = []
        self.thread_pool = list()

    def render_email_html(self):
        template_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'templates', 'mail.html'
        )
        return render_to_string(template_file, {
            'results': self.email_results,
            'task': self.task
        })

    def send_email(self):
        if self.task.mail and self.email_results:
            email = EmailMessage(
                '[GITHUB安全监控]发现新的泄露信息',
                self.render_email_html(),
                settings.FROM_EMAIL,
                self.task.mail.split(';'),
            )
            email.content_subtype = "html"
            email.send()

    @classmethod
    def name(cls):
        return os.path.basename(sys.modules[cls.__module__].__file__).rsplit('.')[0]

    @abstractmethod
    def search(self, keyword):
        ...

    def _search_by_keyword_thread(self, keyword):
        self.search(keyword)
        close_old_connections()

    def process(self):
        while True:
            connection.close()
            self.email_results = []
            self.task.refresh_from_db()
            self.task.status = 1
            self.task.start_time = timezone.now()
            self.task.finished_time = None
            self.task.save()
            keyword_list = self.task.keywords.split('\n')
            for keyword in keyword_list:
                _thread = Thread(target=self._search_by_keyword_thread, args=(keyword, ))
                _thread.start()
                self.thread_pool.append(_thread)
            for th in self.thread_pool:
                th.join()
            connection.close()
            self.task.status = 2
            self.task.finished_time = timezone.now()
            self.task.save()
            try:
                self.send_email()
            except Exception as e:
                logger.exception(e)

            # sleep一个周期的时间
            time.sleep(60 * self.task.interval)


class TaskProcessor(type):
    def __new__(mcs, task, *args, **kwargs) -> Optional[AbstractTaskProcessor]:
        try:
            module = import_module(f"github_monitor.apps.monitor.processors.backends.{task.processor}")
            return module.TaskProcessor(task)
        except ImportError:
            return None
