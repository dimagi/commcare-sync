import posixpath

import sys
from fabric import task


@task
def deploy(c):
    """
    Deploy code to remote host by checking out the latest via git.
    """
    if 'VIRTUALENV_ROOT' not in c.config:
        print('Project config not found! Did you forget to pass in "-f deploy/environments/<env>.yml"')
        sys.exit(1)
    update_code(c)
    update_virtualenv(c)
    django_stuff(c)
    services_restart(c)


def update_code(c):
    with c.cd(c.config.CODE_ROOT):
        c.run('git fetch')
        c.run('git checkout master')
        c.run('git reset --hard origin/master')
        c.run("find . -name '*.pyc' -delete")


def update_virtualenv(c):
    """
    Update external dependencies on remote host. Assumes you've done a code update.
    """
    files = (
        posixpath.join(c.config.CODE_ROOT, 'requirements.txt'),
        posixpath.join(c.config.CODE_ROOT, 'requirements', 'prod-requirements.txt'),
    )
    with c.prefix('source {}/bin/activate'.format(c.config.VIRTUALENV_ROOT)):
        for req_file in files:
            c.run('pip install -r {}'.format(req_file))


def django_stuff(c):
    """
    staticfiles, migrate, etc.
    """
    env = {'DJANGO_SETTINGS_MODULE': c.config.DJANGO_SETTINGS_MODULE}
    with c.cd(c.config.CODE_ROOT):
        with c.prefix(f'export DJANGO_SETTINGS_MODULE={c.config.DJANGO_SETTINGS_MODULE}'):
            c.run('{}/bin/python manage.py migrate'.format(c.config.VIRTUALENV_ROOT), env=env)
            c.run('{}/bin/python manage.py collectstatic --noinput'.format(c.config.VIRTUALENV_ROOT), env=env)


def services_restart(c):
    c.sudo(f'sudo supervisorctl restart {c.config.DJANGO_PROCESS}')
    c.sudo(f'sudo supervisorctl restart {c.config.CELERY_PROCESS}')
