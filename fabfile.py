import posixpath

from fabric import task


CODE_ROOT = '/home/ubuntu/code/commcare-sync'
VIRTUALENV_ROOT = '/home/ubuntu/.virtualenvs/commcare-sync'
DJANGO_SETTINGS_MODULE = 'commcare_sync.local'


@task
def deploy(c):
    """
    Deploy code to remote host by checking out the latest via git.
    """
    update_code(c)
    update_virtualenv(c)
    django_stuff(c)
    # services_restart(c)


def update_code(c):
    with c.cd(CODE_ROOT):
        c.run('git fetch')
        c.run('git checkout master')
        c.run('git reset --hard origin/master')
        c.run("find . -name '*.pyc' -delete")


def update_virtualenv(c):
    """
    Update external dependencies on remote host. Assumes you've done a code update.
    """
    files = (
        posixpath.join(CODE_ROOT, 'requirements.txt'),
        # posixpath.join(CODE_ROOT, 'requirements', 'prod-requirements.txt'),
    )
    with c.prefix('source {}/bin/activate'.format(VIRTUALENV_ROOT)):
        for req_file in files:
            c.run('pip install -r {}'.format(req_file))


def django_stuff(c):
    """
    staticfiles, migrate, etc.
    """
    env = {'DJANGO_SETTINGS_MODULE': DJANGO_SETTINGS_MODULE}
    with c.cd(CODE_ROOT):
        with c.prefix(f'export DJANGO_SETTINGS_MODULE={DJANGO_SETTINGS_MODULE}'):
            c.run('{}/bin/python manage.py migrate'.format(VIRTUALENV_ROOT), env=env)
            c.run('{}/bin/python manage.py collectstatic --noinput'.format(VIRTUALENV_ROOT), env=env)


# todo: supervisor managed
# def services_restart(c):
#     c.sudo('sudo supervisorctl restart commcare-sync-django')
#     c.sudo('sudo supervisorctl restart commcare-sync-celery')
