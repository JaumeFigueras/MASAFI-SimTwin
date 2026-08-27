"""Tests for the light and dark themes."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QPalette

from masafi_simtwin.theme import (
    APPEARANCE_NAMESPACE,
    CARD_RADIUS,
    COLOR_SCHEME_KEY,
    COLORS,
    PANE_GAP,
    PORTAL_SCHEMES,
    SEPARATOR_WIDTH,
    ColorScheme,
    ThemeManager,
    _portal_value,
    build_palette,
    build_stylesheet,
    detect_color_scheme,
    portal_color_scheme,
    portal_settings,
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


def test_an_override_is_applied_at_once(qapp):
    """Setting it is what the theme preference does at start-up.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    """

    manager = ThemeManager(qapp)
    manager.override = ColorScheme.DARK
    assert manager.scheme == ColorScheme.DARK

    manager.override = ColorScheme.LIGHT
    assert manager.scheme == ColorScheme.LIGHT


def test_the_desktop_does_not_overrule_an_override(qapp):
    """A user who asked for dark keeps dark when the desktop turns light.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    """

    manager = ThemeManager(qapp)
    manager.override = ColorScheme.DARK
    manager._on_system_scheme_changed(Qt.ColorScheme.Light)
    assert manager.scheme == ColorScheme.DARK


def test_clearing_the_override_follows_the_desktop_again(qapp):
    """Choosing the system default goes back to what the machine says.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    """

    manager = ThemeManager(qapp)
    manager.override = ColorScheme.DARK
    manager.override = None
    assert manager.override is None
    assert manager.scheme == detect_color_scheme()


# ----------------------------------------------------------------------
# Where the scheme is read from
# ----------------------------------------------------------------------


def test_the_portal_values_are_the_ones_the_specification_gives():
    """``0`` means no preference and is deliberately not mapped."""

    assert PORTAL_SCHEMES == {1: ColorScheme.DARK, 2: ColorScheme.LIGHT}
    assert 0 not in PORTAL_SCHEMES


def test_the_desktops_own_answer_wins_over_qt(monkeypatch):
    """The bug this exists for: Qt says light on a desktop set to dark."""

    monkeypatch.setattr('masafi_simtwin.theme.portal_color_scheme', lambda: ColorScheme.DARK)
    assert detect_color_scheme() == ColorScheme.DARK

    monkeypatch.setattr('masafi_simtwin.theme.portal_color_scheme', lambda: ColorScheme.LIGHT)
    assert detect_color_scheme() == ColorScheme.LIGHT


def test_no_portal_falls_back_to_qt(qapp, monkeypatch):
    """What Windows, macOS and a Linux box without a portal reach.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    monkeypatch : pytest.MonkeyPatch
        The patcher.
    """

    monkeypatch.setattr('masafi_simtwin.theme.portal_color_scheme', lambda: None)
    hints = QGuiApplication.styleHints()
    expected = (
        ColorScheme.DARK
        if hints is not None and hints.colorScheme() == Qt.ColorScheme.Dark
        else ColorScheme.LIGHT
    )
    assert detect_color_scheme() == expected


def test_without_qtdbus_there_is_no_portal(monkeypatch):
    """The import is guarded, so a Qt built without QtDBus still runs."""

    monkeypatch.setattr('masafi_simtwin.theme._portal_settings', None)
    monkeypatch.setattr('masafi_simtwin.theme.QDBusConnection', None)
    assert portal_settings() is None
    assert portal_color_scheme() is None


def test_a_scheme_is_still_decided_without_a_portal(monkeypatch):
    """Falling back must never leave the application with no scheme at all."""

    monkeypatch.setattr('masafi_simtwin.theme._portal_settings', None)
    monkeypatch.setattr('masafi_simtwin.theme.QDBusConnection', None)
    assert detect_color_scheme() in (ColorScheme.LIGHT, ColorScheme.DARK)


@pytest.mark.parametrize(
    ('arguments', 'expected'),
    [
        ([], None),
        ([1], 1),
        ([2], 2),
        (['dark'], None),
        ([None], None),
    ],
)
def test_the_reply_of_the_portal_is_read_defensively(arguments, expected):
    """A portal answering with something unexpected must not raise."""

    assert _portal_value(arguments) == expected


# ----------------------------------------------------------------------
# Following the desktop through the portal
# ----------------------------------------------------------------------


def test_the_portal_is_listened_to_when_there_is_one(qapp):
    """Qt's own signal is not enough where Qt reads the scheme wrongly.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    """

    manager = ThemeManager(qapp)
    assert manager.watching_portal is (portal_settings() is not None)


def test_nothing_is_listened_to_without_qtdbus(qapp, monkeypatch):
    """Which is the ordinary state of affairs on Windows and macOS.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    monkeypatch : pytest.MonkeyPatch
        The patcher.
    """

    monkeypatch.setattr('masafi_simtwin.theme.QDBusConnection', None)
    assert ThemeManager(qapp).watching_portal is False


def test_a_change_of_colour_scheme_reapplies_the_theme(qapp, monkeypatch):
    """The signal the fix is for.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    monkeypatch : pytest.MonkeyPatch
        The patcher.
    """

    manager = ThemeManager(qapp)
    applied = []
    monkeypatch.setattr(manager, 'apply', lambda scheme=None: applied.append(scheme))

    manager._on_portal_setting_changed(APPEARANCE_NAMESPACE, COLOR_SCHEME_KEY, None)
    assert applied == [None]


@pytest.mark.parametrize(
    ('namespace', 'key'),
    [
        ('org.gnome.desktop.interface', COLOR_SCHEME_KEY),
        (APPEARANCE_NAMESPACE, 'accent-color'),
    ],
)
def test_the_other_settings_of_the_portal_are_ignored(qapp, monkeypatch, namespace, key):
    """The portal signals everything it holds, not only the colour scheme.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    monkeypatch : pytest.MonkeyPatch
        The patcher.
    namespace : str
        The namespace of the setting that changed.
    key : str
        The key within it.
    """

    manager = ThemeManager(qapp)
    applied = []
    monkeypatch.setattr(manager, 'apply', lambda scheme=None: applied.append(scheme))

    manager._on_portal_setting_changed(namespace, key, None)
    assert applied == []


def test_the_portal_does_not_overrule_an_override(qapp):
    """As the desktop's own signal does not, and for the same reason.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.
    """

    manager = ThemeManager(qapp)
    manager.override = ColorScheme.LIGHT
    manager._on_portal_setting_changed(APPEARANCE_NAMESPACE, COLOR_SCHEME_KEY, None)
    assert manager.scheme == ColorScheme.LIGHT
