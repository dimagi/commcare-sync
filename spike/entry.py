"""PyInstaller entry point for the spike bundle."""

import multiprocessing
import sys

from commcare_sync.launcher import main

if __name__ == '__main__':
    multiprocessing.freeze_support()
    sys.exit(main())
