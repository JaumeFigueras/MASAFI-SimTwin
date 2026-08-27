"""Fixtures shared by the whole test suite."""

from __future__ import annotations

import tempfile

import pytest
from PyQt6.QtCore import QSettings

from masafi_simtwin.application import SimTwinApplication

#: Where the suite's ``QSettings`` are kept, instead of the developer's own.
#:
#: This is done on import rather than in a fixture because the application
#: reads its preferences while it is being constructed — the language is
#: settled before the first widget exists — so the redirection has to be in
#: place before any fixture can build an application.
SETTINGS_DIRECTORY = tempfile.mkdtemp(prefix='masafi-simtwin-settings-')

QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(
    QSettings.Format.IniFormat, QSettings.Scope.UserScope, SETTINGS_DIRECTORY
)


@pytest.fixture(scope='session')
def qapp_cls():
    """Tell pytest-qt to build the application class of this project.

    Returns
    -------
    type
        :class:`masafi_simtwin.application.SimTwinApplication`, so that the
        tests exercise the real style, palette and theme manager rather than a
        bare ``QApplication``.
    """

    return SimTwinApplication


@pytest.fixture(autouse=True, scope='session')
def source_language(qapp):
    """Run the suite in the source language, whatever the desktop says.

    The application follows the locale of the machine it starts on, so on a
    Catalan desktop every assertion on an English string would fail.  Taking
    the catalogues back out leaves the ``tr()`` literals in place, which is what
    the tests of the application are written against; the catalogues themselves
    are checked by the tests marked ``i18n``.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    """

    qapp.remove_translators()
    return qapp


@pytest.fixture(scope='session')
def isolated_settings():
    """Give the directory ``QSettings`` was redirected to on import.

    The redirection itself is :data:`SETTINGS_DIRECTORY`, done when this module
    is imported; this only hands the path to the tests that want to look at the
    file.

    Returns
    -------
    str
        The directory the settings are written to.
    """

    return SETTINGS_DIRECTORY


@pytest.fixture(autouse=True)
def clean_settings(isolated_settings):
    """Start every test from an empty configuration.

    The recent project history outlives the window it was written from, so a
    test that opens projects would otherwise leak its history into the next one.

    Parameters
    ----------
    isolated_settings : pathlib.Path
        The temporary settings directory, ordered before this fixture so the
        clearing happens in the right place.
    """

    QSettings().clear()
    yield
    QSettings().clear()
