import os
import stat

from unmagic import fixture, use

from commcare_sync.launcher.desktop import open_in_browser
from commcare_sync.launcher.env import OPEN_PAGE_FILENAME

_tmp_path = fixture('tmp_path')
_monkeypatch = fixture('monkeypatch')


@use(_tmp_path, _monkeypatch)
def test_open_in_browser_hands_over_a_private_file_not_the_url():
    opened = []
    _monkeypatch().setattr('webbrowser.open', opened.append)
    url = 'http://127.0.0.1:8000/setup/?token=secret&x="y"'

    open_in_browser(_tmp_path(), url)

    page = _tmp_path() / OPEN_PAGE_FILENAME
    assert opened == [page.as_uri()]
    assert page.read_text() == (
        '<meta http-equiv="refresh" content="0; '
        'url=http://127.0.0.1:8000/setup/?token=secret&amp;x=&quot;y&quot;">'
    )
    if os.name == 'posix':
        assert stat.S_IMODE(page.stat().st_mode) == 0o600
