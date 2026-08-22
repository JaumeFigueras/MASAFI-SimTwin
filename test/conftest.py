"""Fixtures shared by the whole test suite."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings

from masafi_simtwin.application import SimTwinApplication


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
def isolated_settings(tmp_path_factory):
    """Keep ``QSettings`` out of the developer's real configuration.

    The main window persists its recent project list through ``QSettings``.
    Pointing the INI search path at a temporary directory means a test run
    neither reads nor overwrites what the developer has on disk.

    Parameters
    ----------
    tmp_path_factory : pytest.TempPathFactory
        Factory for the temporary directory.

    Yields
    ------
    pathlib.Path
        The directory the settings were written to.
    """

    directory = tmp_path_factory.mktemp('settings')
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(directory)
    )
    yield directory


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
