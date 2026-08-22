"""Application object and entry point.

The application forces the Fusion style.  The native styles differ too much from
one desktop to the next to be told what to paint, and the whole chrome of this
window — top bar, tool stripe, tabs — is styled by the application style sheet;
Fusion is the one style that honours it identically everywhere.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import QLibraryInfo, QLocale, QTranslator
from PyQt6.QtWidgets import QApplication

from masafi_simtwin import (
    APPLICATION_NAME,
    ORGANISATION_DOMAIN,
    ORGANISATION_NAME,
    __version__,
    icons,
)
from masafi_simtwin.main_window import MainWindow
from masafi_simtwin.theme import ThemeManager


class SimTwinApplication(QApplication):
    """The ``QApplication`` of MASAFI-SimTwin.

    Parameters
    ----------
    argv : list of str
        Command line arguments, passed through to Qt.

    Attributes
    ----------
    theme : masafi_simtwin.theme.ThemeManager
        The theme manager, already following the desktop.
    """

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setApplicationName(APPLICATION_NAME)
        self.setApplicationDisplayName(APPLICATION_NAME)
        self.setApplicationVersion(__version__)
        self.setOrganizationName(ORGANISATION_NAME)
        self.setOrganizationDomain(ORGANISATION_DOMAIN)
        self.setStyle('Fusion')

        self._translators: list[QTranslator] = []
        self._install_translators()

        self.theme = ThemeManager(self)
        self.theme.scheme_changed.connect(lambda _scheme: icons.refresh())
        self.theme.apply()

    def _install_translators(self) -> None:
        """Install the Qt translations for the current locale, if they are there.

        The application's own catalogue is not loaded yet: no ``.qm`` file is
        built, because ``lrelease`` is not installed on the development machine.
        Loading Qt's own catalogue already translates the standard dialogs, and
        this is the place the application catalogue will be added to.
        """

        locale = QLocale.system()
        translator = QTranslator(self)
        path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if translator.load(locale, 'qtbase', '_', path):
            self.installTranslator(translator)
            self._translators.append(translator)


def main(argv: list[str] | None = None) -> int:
    """Start the application.

    Parameters
    ----------
    argv : list of str, optional
        Command line arguments, ``sys.argv`` by default.

    Returns
    -------
    int
        The exit code of the Qt event loop.
    """

    application = SimTwinApplication(list(argv if argv is not None else sys.argv))
    window = MainWindow()
    window.show()
    return application.exec()
