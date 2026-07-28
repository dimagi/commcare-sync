"""Entry point for ``python -m commcare_sync.launcher``.

The launcher uses this to start its own task cluster child process, which
works in a frozen build too, where there is no console script on PATH.
"""

import sys

from commcare_sync.launcher import main

if __name__ == '__main__':
    sys.exit(main())
