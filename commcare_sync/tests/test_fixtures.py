import logging
import os

from unmagic import fixture, use

from commcare_sync.launcher.env import (
    DATA_DIR_ENV_VAR,
    MODE_ENV_VAR,
    PORT_ENV_VAR,
)
from commcare_sync.tests.fixtures import (
    restore_launcher_process_state,
    unset_env_var,
)

_tmp_path = fixture('tmp_path')

VAR = 'COMMCARE_SYNC_TEST_ONLY'


def test_unset_env_var_restores_an_absent_variable():
    os.environ.pop(VAR, None)
    with unset_env_var(VAR):
        os.environ[VAR] = 'leaked'
    assert VAR not in os.environ


def test_unset_env_var_hides_and_restores_a_set_variable():
    os.environ[VAR] = 'before'
    try:
        with unset_env_var(VAR):
            assert VAR not in os.environ
        assert os.environ[VAR] == 'before'
    finally:
        del os.environ[VAR]


@use(_tmp_path)
def test_restore_launcher_process_state_undoes_what_main_does():
    cwd = os.getcwd()
    umask = os.umask(0o022)
    launcher_logger = logging.getLogger('commcare_sync.launcher')
    handlers_before = list(launcher_logger.handlers)
    with restore_launcher_process_state():
        os.chdir(_tmp_path())
        os.umask(0o077)
        for name in (DATA_DIR_ENV_VAR, MODE_ENV_VAR, PORT_ENV_VAR):
            os.environ[name] = 'leaked'
        launcher_logger.addHandler(logging.NullHandler())
        launcher_logger.propagate = False
        launcher_logger.setLevel(logging.INFO)
    assert os.getcwd() == cwd
    assert os.umask(umask) == 0o022
    for name in (DATA_DIR_ENV_VAR, MODE_ENV_VAR, PORT_ENV_VAR):
        assert name not in os.environ
    assert launcher_logger.handlers == handlers_before
    assert launcher_logger.propagate is True
    assert launcher_logger.level == logging.NOTSET
