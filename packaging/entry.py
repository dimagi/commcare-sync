"""
The bundle's entry point. ``main()`` calls ``multiprocessing.freeze_support()``
first thing, so that the cluster child and multiprocessing's helpers can
start as copies of this executable.
"""

import sys

from commcare_sync.launcher.cli import main

if __name__ == '__main__':
    sys.exit(main())
