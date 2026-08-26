"""Run the application with ``python -m masafi_simtwin``."""

from __future__ import annotations

import sys

from masafi_simtwin.application import main

if __name__ == '__main__':  # pragme no cover
    sys.exit(main(sys.argv))
