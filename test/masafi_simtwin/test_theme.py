"""Tests for the light and dark themes."""

from __future__ import annotations

import pytest
from PyQt6.QtGui import QPalette

from masafi_simtwin.theme import (
    CARD_RADIUS,
    COLORS,
    PANE_GAP,
    SEPARATOR_WIDTH,
    ColorScheme,
    ThemeManager,
    build_palette,
    build_stylesheet,
    detect_color_scheme,
)


def block_of(stylesheet: str, selector: str) -> str:
    """Return the body of one rule of a style sheet.

    Parameters
    ----------
    stylesheet : str
        The style sheet to read.
    selector : str
        The selector of the rule, matched on its opening brace so that a rule
        for a descendant of the same widget is not picked up instead.

    Returns
    -------
    str
        Everything between the braces of the rule.
    """

    return stylesheet.split(f'{selector} {{', 1)[1].split('}', 1)[0]


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


@pytest.mark.parametrize('scheme', list(ColorScheme))
def test_the_cards_stand_out_from_the_ground(qapp, scheme):
    """The gaps only read as gaps if the ground differs from both cards."""

    colors = COLORS[scheme]

    assert colors.window != colors.surface
    assert colors.window != colors.editor


@pytest.mark.parametrize('scheme', list(ColorScheme))
def test_the_chrome_is_painted_on_the_ground(qapp, scheme):
    """Top bar, tool stripe and status bar share the colour that fills the gaps."""

    stylesheet = build_stylesheet(COLORS[scheme])
    ground = COLORS[scheme].window

    for selector in ('QWidget#TopBar', 'QToolBar#SideBar', 'QStatusBar#StatusBar'):
        assert f'background: {ground}' in block_of(stylesheet, selector)


@pytest.mark.parametrize('scheme', list(ColorScheme))
def test_the_cards_are_rounded(qapp, scheme):
    """Both kinds of card are drawn with the same corner radius."""

    stylesheet = build_stylesheet(COLORS[scheme])

    for selector in ('QFrame#ToolPaneCard', 'QFrame#DocumentCard'):
        assert f'border-radius: {CARD_RADIUS}px' in block_of(stylesheet, selector)


@pytest.mark.parametrize('scheme', list(ColorScheme))
def test_the_separator_is_a_gap_the_user_can_grab(qapp, scheme):
    """The handle between two cards is painted as ground and is wide enough to hit."""

    stylesheet = build_stylesheet(COLORS[scheme])
    block = block_of(stylesheet, 'QMainWindow::separator')

    assert f'background: {COLORS[scheme].window}' in block
    assert f'width: {SEPARATOR_WIDTH}px' in block
    assert SEPARATOR_WIDTH >= PANE_GAP
