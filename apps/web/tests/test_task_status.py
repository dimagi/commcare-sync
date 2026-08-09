import uuid
from datetime import timedelta

from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django_q.models import Task
from unmagic import use

from tests.fixtures import authed_client


@use(authed_client)
class TestTaskStatus:
    def _create_task(self, name, success, result):
        # Django Q2's Task.get_task only queries by ID when the ID looks
        # like a UUID; anything shorter falls back to a lookup by
        # `name`.
        task_id = uuid.uuid4().hex
        now = timezone.now()
        Task.objects.create(
            id=task_id,
            name=name,
            func='apps.exports.tasks.run_export_task',
            started=now - timedelta(seconds=10),
            stopped=now,
            success=success,
            result=result,
        )
        return task_id

    def _get_status(self, task_id):
        return authed_client().get(reverse('web:task_status', args=[task_id]))

    def test_pending_task_reports_incomplete(self):
        unknown_id = uuid.uuid4().hex
        response = self._get_status(unknown_id)
        assert response.status_code == 200
        assert response.json() == {
            'complete': False,
            'success': None,
            'result': None,
        }

    def test_successful_task_reports_result(self):
        task_id = self._create_task(
            name='export-task-1',
            success=True,
            result={'status': 'success'},
        )
        response = self._get_status(task_id)
        assert response.json() == {
            'complete': True,
            'success': True,
            'result': {'status': 'success'},
        }

    def test_failed_task_hides_traceback_result(self):
        task_id = self._create_task(
            name='export-task-2',
            success=False,
            result='Traceback (most recent call last): ...',
        )
        response = self._get_status(task_id)
        assert response.json() == {
            'complete': True,
            'success': False,
            'result': None,
        }


def test_task_status_requires_login():
    response = Client().get(reverse('web:task_status', args=['x']))
    assert response.status_code == 302
