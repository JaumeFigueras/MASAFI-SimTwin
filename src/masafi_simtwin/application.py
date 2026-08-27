"""Application object and entry point.

The application forces the Fusion style.  The native styles differ too much from
one desktop to the next to be told what to paint, and the whole chrome of this
window — top bar, tool stripe, tabs — is styled by the application style sheet;
Fusion is the one style that honours it identically everywhere.
"""

from __future__ import annotations

import os
import sys

from PyQt6.QtCore import QLibraryInfo, QLocale, QSettings, QTranslator
from PyQt6.QtWidgets import QApplication

from masafi_simtwin import (
    APPLICATION_NAME,
    ORGANISATION_DOMAIN,
    ORGANISATION_NAME,
    __version__,
    icons,
)
from masafi_simtwin.main_window import MainWindow
from masafi_simtwin.preferences import SYSTEM_THEME, Preferences
from masafi_simtwin.theme import ColorScheme, ThemeManager
from masafi_simtwin.translations import CATALOGUE_PREFIX, directory


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

        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        self.preferences = Preferences()

        self._translators: list[QTranslator] = []
        self._install_translators()

        self.theme = ThemeManager(self)
        self.theme.scheme_changed.connect(lambda _scheme: icons.refresh())
        self.theme.override = self.scheme_of_choice()
        self.theme.apply()

    def _install_translators(self) -> None:
        """Install the translations for the current locale, if they are there.

        Qt's own catalogue goes in first — it translates the standard dialogs —
        and the application's catalogue after it, so that a string the
        application translates itself wins over Qt's.
        """

        locale = self.locale_of_choice()
        self.install_qt_translator(locale)
        self.install_application_translator(locale)

    def locale_of_choice(self) -> QLocale:
        """Give the locale the catalogues should be loaded for.

        The language the user chose wins over the desktop's; an unset
        preference is what leaves the application following the machine it
        starts on.

        Returns
        -------
        PyQt6.QtCore.QLocale
            The locale to load the catalogues for.
        """

        language = self.preferences.value('appearance/language')
        return QLocale(language) if language else QLocale.system()

    def scheme_of_choice(self) -> ColorScheme | None:
        """Give the colour scheme the user asked for outright.

        Returns
        -------
        ColorScheme, optional
            The scheme stored in ``appearance/theme``, or ``None`` when it is
            left at the system default, which is what leaves the application
            following the desktop.
        """

        theme = self.preferences.value('appearance/theme')
        return ColorScheme(theme) if theme != SYSTEM_THEME else None

    def install_qt_translator(self, locale: QLocale) -> bool:
        """Install Qt's own catalogue for a locale.

        Parameters
        ----------
        locale : PyQt6.QtCore.QLocale
            The locale to load.

        Returns
        -------
        bool
            Whether a catalogue was found and installed.
        """

        translator = QTranslator(self)
        path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        return self._install(translator, translator.load(locale, 'qtbase', '_', path))

    def install_application_translator(self, locale: QLocale) -> bool:
        """Install the application's own catalogue for a locale.

        The catalogues are named after the language alone, so a locale of
        ``ca_ES`` or ``ca_AD`` both find ``masafi_simtwin_ca.qm``.

        Parameters
        ----------
        locale : PyQt6.QtCore.QLocale
            The locale to load.

        Returns
        -------
        bool
            Whether a catalogue was found and installed.  ``False`` is not an
            error: it is what an untranslated language does, and it leaves the
            source strings in place.
        """

        translator = QTranslator(self)
        return self._install(
            translator, translator.load(locale, CATALOGUE_PREFIX, '_', str(directory()))
        )

    def restart(self) -> None:
        """Start the application again, in place of this process.

        The settings are flushed first: replacing the process image skips every
        destructor, so a preference that ``QSettings`` had not written out yet
        would be lost — which would be the one the user restarted for.

        The interpreter and the arguments are the ones this run was started
        with, so a restart works the same whether the application was launched
        through ``python -m masafi_simtwin``, through the console script, or
        from an IDE.
        """

        self.preferences.settings.sync()
        self.closeAllWindows()
        os.execv(sys.executable, [sys.executable, *sys.argv])

    def remove_translators(self) -> None:
        """Take every installed catalogue back out.

        The application does not change language while it runs — that means a
        restart.  This exists so that a test can assert the source strings
        whatever the desktop of the machine it runs on says, and so that a test
        of one catalogue can put things back as they were.
        """

        for translator in self._translators:
            self.removeTranslator(translator)
        self._translators.clear()

    def _install(self, translator: QTranslator, loaded: bool) -> bool:
        """Install a translator that loaded, and keep a reference to it.

        Qt does not take ownership of an installed translator, so the
        application holds on to every one of them for as long as it lives.

        Parameters
        ----------
        translator : PyQt6.QtCore.QTranslator
            The translator.
        loaded : bool
            What :meth:`QTranslator.load` returned.

        Returns
        -------
        bool
            ``loaded``, so this can be returned straight from the caller.
        """

        if loaded:
            self.installTranslator(translator)
            self._translators.append(translator)
        return loaded


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
