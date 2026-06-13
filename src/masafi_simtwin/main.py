"""
Application entry point.

Run with::

    python -m masafi_simtwin.main
    # or, after ``pip install -e .``:
    masafi-simtwin
"""

import sys

from src.masafi_simtwin.app import MasafiSimTwinApplication
from src.masafi_simtwin.main_window import MainWindow


def main() -> int:
    """
    Initialise and run Masafi-SimTwin.

    Returns
    -------
    int
        Process exit code returned to the OS.
    """
    app = MasafiSimTwinApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())