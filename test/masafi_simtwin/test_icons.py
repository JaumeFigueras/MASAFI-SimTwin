"""Tests for the theme-following icons."""

from __future__ import annotations

import pytest
from PyQt6.QtGui import QAction

from masafi_simtwin import icons
from masafi_simtwin.theme import ColorScheme, ThemeManager


def test_icon_builds_a_known_symbol(qapp):
    """A Material Symbol that exists produces a non-null icon."""

    assert not icons.icon('play_arrow').isNull()


def test_set_icon_registers_for_refresh(qapp, qtbot):
    """An icon set through set_icon is repainted when the theme changes."""

    manager = ThemeManager(qapp)
    try:
        manager.apply(ColorScheme.LIGHT)
        action = QAction('Run')
        icons.set_icon(action, 'play_arrow')
        light = action.icon().pixmap(20).toImage()

        manager.apply(ColorScheme.DARK)
        icons.refresh()
        dark = action.icon().pixmap(20).toImage()

        assert light != dark
    finally:
        manager.deleteLater()


def test_refresh_drops_dead_targets(qapp):
    """Targets that have been collected are removed from the registry."""

    action = QAction('Temporary')
    icons.set_icon(action, 'stop')
    before = len(icons._registry)

    del action
    icons.refresh()

    assert len(icons._registry) < before


def test_unsupported_size_is_rejected(qapp):
    """A size with no resource bundle behind it fails with a clear message."""

    with pytest.raises(ValueError, match='available sizes'):
        icons.icon('close', size=16)
