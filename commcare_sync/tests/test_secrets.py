import json
import stat

from cryptography.fernet import Fernet

from commcare_sync.launcher.secrets import (
    SECRETS_FILENAME,
    bootstrap_secrets,
    load_secrets,
)


def test_creates_secrets_file_when_absent(tmp_path):
    bootstrap_secrets(tmp_path)

    secrets_path = tmp_path / SECRETS_FILENAME
    assert secrets_path.is_file()

    secrets = json.loads(secrets_path.read_text())
    assert 'SECRET_KEY' in secrets
    assert 'FERNET_KEYS' in secrets


def test_does_not_overwrite_existing_secrets_file(tmp_path):
    bootstrap_secrets(tmp_path)
    secrets_path = tmp_path / SECRETS_FILENAME
    original = secrets_path.read_text()

    bootstrap_secrets(tmp_path)

    assert secrets_path.read_text() == original


def test_secrets_file_has_owner_only_permissions(tmp_path):
    bootstrap_secrets(tmp_path)

    secrets_path = tmp_path / SECRETS_FILENAME
    mode = stat.S_IMODE(secrets_path.stat().st_mode)

    assert mode == stat.S_IRUSR | stat.S_IWUSR


def test_fernet_keys_is_single_element_list_of_valid_key(tmp_path):
    bootstrap_secrets(tmp_path)

    secrets = load_secrets(tmp_path)
    fernet_keys = secrets['FERNET_KEYS']

    assert isinstance(fernet_keys, list)
    assert len(fernet_keys) == 1

    # A valid Fernet key round-trips a token it encrypted itself.
    fernet = Fernet(fernet_keys[0].encode())
    token = fernet.encrypt(b'payload')
    assert fernet.decrypt(token) == b'payload'


def test_load_secrets_round_trips_bootstrapped_values(tmp_path):
    bootstrap_secrets(tmp_path)

    on_disk = json.loads((tmp_path / SECRETS_FILENAME).read_text())
    loaded = load_secrets(tmp_path)

    assert loaded == on_disk


def test_load_secrets_raises_when_file_missing(tmp_path):
    try:
        load_secrets(tmp_path)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError('expected FileNotFoundError')
