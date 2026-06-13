# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024  Your Name
"""
Shared pytest fixtures for the Masafi-SimTwin test suite.
"""

import pytest

from src.masafi_simtwin.app import MasafiSimTwinApplication


@pytest.fixture(scope="session")
def qapp(qapp_args: list[str]):
    """
    Provide a ``MasafiSimTwinApplication`` for the whole test session.

    Overrides the default ``qapp`` fixture supplied by *pytest-qt* so
    that the Fusion style and dark/light theme logic are exercised.

    Parameters
    ----------
    qapp_args : list[str]
        Command-line arguments injected by pytest-qt.

    Yields
    ------
    MasafiSimTwinApplication
        The application singleton.
    """
    app = MasafiSimTwinApplication(qapp_args)
    yield app