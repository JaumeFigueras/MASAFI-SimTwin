"""Tests for the light and dark themes."""

from __future__ import annotations

import pytest
from PyQt6.QtGui import QPalette

from masafi_simtwin.theme import (
    COLORS,
    ColorScheme,
    ThemeManager,
    build_palette,
    build_stylesheet,
    detect_color_scheme,
)


def test_every_scheme_has_colors():
    """Both schemes are defined, and with different colours."""

    assert set(COLORS) == {ColorScheme.LIGHT, ColorScheme.DARK}
    assert COLORS[ColorScheme.LIGHT] != COLORS[ColorScheme.DARK]


def test_detect_color_scheme_returns_a_known_scheme(qapp):
    """Whatever the desktop reports maps onto one of the two schemes."""

    assert detect_color_scheme() in (ColorScheme.LIGHT, ColorScheme.DARK)


@pytest.mark.parametrize('scheme', list(ColorScheme))
def test_palette_uses_the_scheme_colors(qapp, scheme):
    """The palette carries the window and text colours of its scheme."""

    colors = COLORS[scheme]
    palette = build_palette(colors)

    assert palette.color(QPalette.ColorRole.Window).name() == colors.window
    assert palette.color(QPalette.ColorRole.WindowText).name() == colors.text
    assert palette.color(QPalette.ColorRole.Base).name() == colors.editor
    disabled = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText)
    assert disabled.name() == colors.disabled_text


@pytest.mark.parametrize('scheme', list(ColorScheme))
def test_stylesheet_styles_the_chrome(qapp, scheme):
    """Every piece of chrome the window installs is addressed by the style sheet."""

    stylesheet = build_stylesheet(COLORS[scheme])

    selectors = (
        'QWidget#TopBar',
        'QToolBar#SideBar',
        'QWidget#ToolPaneHeader',
        'QTabWidget#DocumentTabs',
        'QStatusBar#StatusBar',
    )
    for selector in selectors:
        assert selector in stylesheet
    assert COLORS[scheme].surface in stylesheet


@pytest.mark.parametrize('scheme', list(ColorScheme))
def test_apply_sets_palette_and_signals(qapp, qtbot, scheme):
    """Applying a scheme repaints the application and announces the change."""

    manager = ThemeManager(qapp)
    try:
        with qtbot.waitSignal(manager.scheme_changed, timeout=1000) as blocker:
            manager.apply(scheme)

        assert blocker.args == [scheme]
        assert manager.scheme is scheme
        assert manager.colors is COLORS[scheme]
        assert qapp.palette().color(QPalette.ColorRole.Window).name() == COLORS[scheme].window
        assert COLORS[scheme].surface in qapp.styleSheet()
    finally:
        manager.deleteLater()


def test_apply_without_argument_follows_the_desktop(qapp):
    """Calling apply with no scheme reads the desktop setting again."""

    manager = ThemeManager(qapp)
    try:
        manager.apply(ColorScheme.DARK)
        manager.apply()
        assert manager.scheme is detect_color_scheme()
    finally:
        manager.deleteLater()
