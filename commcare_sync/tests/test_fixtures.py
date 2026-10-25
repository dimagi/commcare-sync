import os

from commcare_sync.tests.fixtures import unset_env_var

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
