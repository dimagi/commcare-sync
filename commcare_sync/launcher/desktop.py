"""
The desktop UI.
"""

import html
import os
import webbrowser
from pathlib import Path

from commcare_sync.launcher.env import OPEN_PAGE_FILENAME


def open_in_browser(data_dir: Path, url: str) -> None:
    """
    By way of a page in the data directory, which other accounts cannot
    read, rather than as an argument: ``ps`` shows every account the
    command line of the browser, and the URL may carry the setup token.
    """
    page = data_dir / OPEN_PAGE_FILENAME
    fd = os.open(page, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as file:
        file.write(
            '<meta http-equiv="refresh" content="0; '
            f'url={html.escape(url, quote=True)}">'
        )
    webbrowser.open(page.as_uri())
