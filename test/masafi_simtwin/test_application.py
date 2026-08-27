"""Tests for the application object itself."""

from __future__ import annotations

import sys

import pytest
from PyQt6.QtCore import QLocale, QSettings

from masafi_simtwin import ORGANISATION_NAME
from masafi_simtwin.preferences import SYSTEM_LANGUAGE, SYSTEM_THEME, Preferences
from masafi_simtwin.theme import ColorScheme


def test_the_settings_are_an_ini_file_on_every_platform(qapp):
    """One readable file everywhere, rather than the registry or a plist.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    """

    assert QSettings.defaultFormat() == QSettings.Format.IniFormat
    assert QSettings().fileName().endswith('.ini')


def test_the_application_names_itself_so_qsettings_can_find_its_file(qapp, isolated_settings):
    """``QSettings()`` with no arguments only works because of the names.

    Only the organisation is asserted: pytest-qt renames the application after
    it is built, so the file is named after the test run rather than after
    :data:`~masafi_simtwin.APPLICATION_NAME` here.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    isolated_settings : str
        The directory the suite's settings were redirected to.
    """

    assert qapp.organizationName() == ORGANISATION_NAME
    assert QSettings().fileName().startswith(isolated_settings)
    assert ORGANISATION_NAME in QSettings().fileName()


def test_the_application_carries_its_preferences(qapp):
    """They are read while it is built, so they hang off it.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    """

    assert isinstance(qapp.preferences, Preferences)
    assert qapp.preferences.value('appearance/language') == SYSTEM_LANGUAGE


def test_an_unset_language_follows_the_desktop(qapp):
    """The application keeps following the machine until the user chooses.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    """

    assert qapp.locale_of_choice().name() == QLocale.system().name()


@pytest.mark.parametrize('language', ['en', 'ca'])
def test_a_chosen_language_wins_over_the_desktop(qapp, language):
    """The preference is what the catalogues are loaded for at start-up.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    language : str
        The language to choose.
    """

    qapp.preferences.set_value('appearance/language', language)
    assert qapp.locale_of_choice().language() == QLocale(language).language()


def test_a_chosen_scheme_is_applied_over_the_desktop(qapp):
    """A user who asked for dark gets dark, whatever the desktop says.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    """

    qapp.preferences.set_value('appearance/theme', 'dark')
    assert qapp.scheme_of_choice() == ColorScheme.DARK

    qapp.preferences.set_value('appearance/theme', SYSTEM_THEME)
    assert qapp.scheme_of_choice() is None


def test_restarting_flushes_the_settings_before_replacing_the_process(qapp, monkeypatch):
    """The preference that was restarted for must survive the restart.

    ``os.execv`` skips every destructor, so an unwritten ``QSettings`` would be
    lost; the order of the two is what this checks.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    monkeypatch : pytest.MonkeyPatch
        The patcher.
    """

    events = []
    monkeypatch.setattr(
        type(qapp.preferences.settings),
        'sync',
        lambda self: events.append('sync'),
    )
    monkeypatch.setattr(
        'masafi_simtwin.application.os.execv',
        lambda path, argv: events.append(('execv', path, tuple(argv))),
    )

    qapp.restart()

    assert events[0] == 'sync'
    assert events[-1][0] == 'execv'
    assert events[-1][1] == sys.executable
    assert events[-1][2][0] == sys.executable
