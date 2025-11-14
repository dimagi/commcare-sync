import sys
from fabric import task


@task
def deploy(c):
    """
    Deploy code to remote host by checking out the latest via git.
    """
    if 'CODE_ROOT' not in c.config:
        print('Project config not found! Did you forget to pass in "-f deploy/environments/<env>.yml"')
        sys.exit(1)
    if 'VIRTUALENV_ROOT' in c.config:
        print('Note: VIRTUALENV_ROOT is deprecated. uv will create .venv in the project directory.')
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
    Update external dependencies on remote host using uv. Assumes you've done a code update.
    """
    with c.cd(c.config.CODE_ROOT):
        c.run('curl -LsSf https://astral.sh/uv/install.sh | sh || true')
        c.run('uv sync --frozen --extra prod')


def django_stuff(c):
    """
    staticfiles, migrate, etc.
    """
    env = {'DJANGO_SETTINGS_MODULE': c.config.DJANGO_SETTINGS_MODULE}
    with c.cd(c.config.CODE_ROOT):
        with c.prefix(f'export DJANGO_SETTINGS_MODULE={c.config.DJANGO_SETTINGS_MODULE}'):
            c.run('uv run manage.py migrate', env=env)
            c.run('uv run manage.py collectstatic --noinput', env=env)


def services_restart(c):
    c.sudo(f'sudo supervisorctl restart {c.config.DJANGO_PROCESS}')
    c.sudo(f'sudo supervisorctl restart {c.config.CELERY_PROCESS}')
