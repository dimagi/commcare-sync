"""
The bundle's entry point. ``freeze_support()`` lets the cluster child,
and multiprocessing's helpers, start as copies of this executable.
"""

import multiprocessing
import sys

from commcare_sync.launcher.cli import main

if __name__ == '__main__':
    multiprocessing.freeze_support()
    sys.exit(main())
