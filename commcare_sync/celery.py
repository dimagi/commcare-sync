import os
from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'commcare_sync.settings')

app = Celery('commcare_sync')

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    periodicity_in_seconds = 60 * 60 * 12  # 12 hours
    sender.add_periodic_task(periodicity_in_seconds, run_all_exports_task_wrapper.s(),
                             name='Import all pro chats.')


@app.task
def run_all_exports_task_wrapper():
    from apps.exports.tasks import run_all_exports_task
    run_all_exports_task()


# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
