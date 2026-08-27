"""Light and dark themes that follow the operating system setting.

The application never hard codes a colour.  Every widget takes its colours from
the :class:`ThemeColors` record of the active scheme, which is turned into a
``QPalette`` and a style sheet by :func:`build_palette` and
:func:`build_stylesheet` and applied by :class:`ThemeManager`.

Three of those colours carry the layout.  ``window`` is the ground the whole
application is laid on and the colour that shows through the gaps; ``surface``
is the card a tool pane is drawn as; ``editor`` is the card the documents are
drawn as.  Cards are inset by :data:`PANE_GAP` and their corners rounded by
:data:`CARD_RADIUS`, which is what makes them read as floating on the ground
rather than as regions of one flat window.

The scheme itself is decided by the desktop, and where the answer comes from is
not the same on every platform.  On Windows and macOS Qt reads it natively and
``QStyleHints.colorScheme()`` is right.  On Linux it is read by whichever
platform theme plugin Qt happened to load, and that answer cannot be trusted:
GNOME 42 and later publish dark mode through the ``color-scheme`` setting alone,
while Qt's ``gtk3`` plugin still decides from the GTK theme name — so a desktop
set to dark with the plain ``Adwaita`` theme is reported as light.

The desktop's own answer is the ``color-scheme`` key of the
``org.freedesktop.appearance`` namespace, published over D-Bus by the
XDG desktop portal.  :func:`detect_color_scheme` asks the portal first and falls
back to ``QStyleHints`` — which is what Windows and macOS reach, since there is
no session bus for the first step to find, and what a Linux box without a portal
reaches too.  :class:`ThemeManager` listens to the portal's ``SettingChanged``
alongside ``colorSchemeChanged`` for the same reason: on a desktop where Qt gets
the scheme wrong it never reports a change either.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import QObject, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QGuiApplication, QPalette
from PyQt6.QtWidgets import QApplication

try:
    from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusVariant
except ImportError:  # pragma: no cover - QtDBus is not built on every platform
    QDBusConnection = None
    QDBusInterface = None
    QDBusVariant = None


#: Ground, in pixels, left around every card.
PANE_GAP = 3

#: Radius, in pixels, of the corners of a card.
CARD_RADIUS = 8

#: Width, in pixels, of the handle a pane is resized by.  It sits between two
#: cards that are already inset, so the gap the user sees is wider than this.
SEPARATOR_WIDTH = 4

#: The bus name of the XDG desktop portal.
PORTAL_SERVICE = 'org.freedesktop.portal.Desktop'

#: The object the portal's settings live on.
PORTAL_PATH = '/org/freedesktop/portal/desktop'

#: The portal interface the appearance settings are read through.
PORTAL_SETTINGS = 'org.freedesktop.portal.Settings'

#: The namespace the desktop publishes its appearance under.
APPEARANCE_NAMESPACE = 'org.freedesktop.appearance'

#: The key holding the light or dark preference of the desktop.
COLOR_SCHEME_KEY = 'color-scheme'

#: The signal the portal emits when one of its settings is changed.
SETTING_CHANGED = 'SettingChanged'



class ColorScheme(Enum):
    """The two schemes the application knows how to paint."""

    LIGHT = 'light'
    DARK = 'dark'


#: What the portal's ``color-scheme`` values mean.  ``0`` is "no preference",
#: which is deliberately absent: it means the desktop has nothing to say and the
#: question falls through to Qt.
PORTAL_SCHEMES = {1: ColorScheme.DARK, 2: ColorScheme.LIGHT}

#: The portal interface, once it has been reached; see :func:`portal_settings`.
_portal_settings: QDBusInterface | None = None


@dataclass(frozen=True)
class ThemeColors:
    """The colour tokens of one scheme.

    Attributes
    ----------
    window : str
        The ground everything is laid on: the chrome — top bar, tool stripes,
        status bar — and the gaps between the cards.
    surface : str
        Background of a tool pane card.
    editor : str
        Background of the document card, the largest surface on screen.
    border : str
        Hairline drawn inside a card, under a pane header.
    text : str
        Foreground of ordinary text.
    text_muted : str
        Foreground of secondary text, such as status bar hints.
    disabled_text : str
        Foreground of a disabled widget.
    accent : str
        Colour of the active tab underline, focus rings and checked buttons.
    hover : str
        Background of a hovered flat button.
    pressed : str
        Background of a pressed or checked flat button.
    selection : str
        Background of a selected item.
    selection_text : str
        Foreground of a selected item.
    error : str
        Foreground used to report a problem.
    """

    window: str
    surface: str
    editor: str
    border: str
    text: str
    text_muted: str
    disabled_text: str
    accent: str
    hover: str
    pressed: str
    selection: str
    selection_text: str
    error: str


LIGHT_COLORS = ThemeColors(
    window='#e4e6ea',
    surface='#f7f8fa',
    editor='#ffffff',
    border='#d3d5db',
    text='#1e1f22',
    text_muted='#818594',
    disabled_text='#a8adbd',
    accent='#3574f0',
    hover='#dfe1e5',
    pressed='#ced0d6',
    selection='#d4e2ff',
    selection_text='#1e1f22',
    error='#db3b4b',
)

DARK_COLORS = ThemeColors(
    window='#131417',
    surface='#2b2d30',
    editor='#1e1f22',
    border='#393b40',
    text='#dfe1e5',
    text_muted='#868a91',
    disabled_text='#6f737a',
    accent='#548af7',
    hover='#393b40',
    pressed='#43454a',
    selection='#2e436e',
    selection_text='#dfe1e5',
    error='#f75462',
)

COLORS: dict[ColorScheme, ThemeColors] = {
    ColorScheme.LIGHT: LIGHT_COLORS,
    ColorScheme.DARK: DARK_COLORS,
}


def portal_settings() -> QDBusInterface | None:
    """Return the portal's settings interface, or ``None`` when there is none.

    The interface is kept once it has been reached, because
    :func:`detect_color_scheme` runs on every :meth:`ThemeManager.apply`.
    Failure is not kept: a machine with no session bus — Windows and macOS, and
    a Linux box running without one — pays only the ``isConnected`` check.

    Returns
    -------
    PyQt6.QtDBus.QDBusInterface, optional
        The interface, or ``None`` when QtDBus was not built, there is no
        session bus, or no portal is answering on it.
    """

    global _portal_settings

    if _portal_settings is not None:
        return _portal_settings
    if QDBusConnection is None:
        return None
    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return None
    interface = QDBusInterface(PORTAL_SERVICE, PORTAL_PATH, PORTAL_SETTINGS, bus)
    if not interface.isValid():
        return None
    _portal_settings = interface
    return _portal_settings


def portal_color_scheme() -> ColorScheme | None:
    """Return the scheme the desktop publishes over the portal.

    ``ReadOne`` is version 2 of the portal's settings interface; ``Read`` is
    the deprecated call that older portals answer instead, so both are tried.

    Returns
    -------
    ColorScheme, optional
        The scheme, or ``None`` when there is no portal, when it will not
        answer, or when the desktop expresses no preference.
    """

    interface = portal_settings()
    if interface is None:
        return None
    for method in ('ReadOne', 'Read'):
        reply = interface.call(method, APPEARANCE_NAMESPACE, COLOR_SCHEME_KEY)
        if reply.errorName():
            continue
        return PORTAL_SCHEMES.get(_portal_value(reply.arguments()))
    return None


def _portal_value(arguments: list) -> int | None:
    """Take the number out of a portal reply.

    Parameters
    ----------
    arguments : list
        The arguments of the reply.  The portal answers with a variant, which
        PyQt unwraps for the reply of a call but not for the payload of a
        signal, so both shapes are accepted.

    Returns
    -------
    int, optional
        The value, or ``None`` when the reply held something else.
    """

    if not arguments:
        return None
    value = arguments[0]
    if QDBusVariant is not None and isinstance(value, QDBusVariant):
        value = value.variant()
    return value if isinstance(value, int) else None


def detect_color_scheme() -> ColorScheme:
    """Return the scheme the desktop is currently asking for.

    The desktop portal is asked first, because on Linux it is the desktop's own
    answer while ``QStyleHints`` is a platform theme plugin's guess at it, and
    the guess is wrong on a GNOME session with a theme whose name does not say
    "dark".  Everywhere the portal cannot be reached — Windows and macOS above
    all — the question falls through to Qt, which reads those two natively.

    Returns
    -------
    ColorScheme
        The scheme the desktop asks for.  A desktop that expresses no
        preference, or a platform that cannot report one, is treated as light.
    """

    scheme = portal_color_scheme()
    if scheme is not None:
        return scheme

    hints = QGuiApplication.styleHints()
    if hints is not None and hints.colorScheme() == Qt.ColorScheme.Dark:
        return ColorScheme.DARK
    return ColorScheme.LIGHT


def build_palette(colors: ThemeColors) -> QPalette:
    """Build the ``QPalette`` of a scheme.

    The palette matters beyond the widgets that read it directly: the icons of
    :mod:`masafi_simtwin.icons` are tinted with its ``WindowText`` colour, so a
    palette that does not match the style sheet produces icons that do not match
    the chrome.

    Parameters
    ----------
    colors : ThemeColors
        Colour tokens of the scheme to build.

    Returns
    -------
    PyQt6.QtGui.QPalette
        A palette with every group filled in, disabled entries included.
    """

    role = QPalette.ColorRole
    group = QPalette.ColorGroup

    palette = QPalette()
    palette.setColor(role.Window, QColor(colors.window))
    palette.setColor(role.WindowText, QColor(colors.text))
    palette.setColor(role.Base, QColor(colors.editor))
    palette.setColor(role.AlternateBase, QColor(colors.surface))
    palette.setColor(role.Text, QColor(colors.text))
    palette.setColor(role.Button, QColor(colors.surface))
    palette.setColor(role.ButtonText, QColor(colors.text))
    palette.setColor(role.BrightText, QColor(colors.error))
    palette.setColor(role.ToolTipBase, QColor(colors.surface))
    palette.setColor(role.ToolTipText, QColor(colors.text))
    palette.setColor(role.PlaceholderText, QColor(colors.text_muted))
    palette.setColor(role.Highlight, QColor(colors.selection))
    palette.setColor(role.HighlightedText, QColor(colors.selection_text))
    palette.setColor(role.Link, QColor(colors.accent))
    palette.setColor(role.LinkVisited, QColor(colors.accent))
    palette.setColor(role.Light, QColor(colors.hover))
    palette.setColor(role.Mid, QColor(colors.border))
    palette.setColor(role.Dark, QColor(colors.border))
    palette.setColor(role.Shadow, QColor(colors.border))

    for disabled_role in (role.WindowText, role.Text, role.ButtonText):
        palette.setColor(group.Disabled, disabled_role, QColor(colors.disabled_text))

    return palette


def build_stylesheet(colors: ThemeColors) -> str:
    """Build the application style sheet of a scheme.

    Parameters
    ----------
    colors : ThemeColors
        Colour tokens of the scheme to build.

    Returns
    -------
    str
        A style sheet meant for ``QApplication.setStyleSheet``.
    """

    return f"""
    QWidget#TopBar {{
        background: {colors.window};
    }}

    QWidget#TopBar QToolButton,
    QToolBar#SideBar QToolButton {{
        border: none;
        border-radius: 6px;
        padding: 4px;
        background: transparent;
        color: {colors.text};
    }}

    QWidget#TopBar QToolButton:hover,
    QToolBar#SideBar QToolButton:hover {{
        background: {colors.hover};
    }}

    QWidget#TopBar QToolButton:pressed,
    QWidget#TopBar QToolButton:checked,
    QToolBar#SideBar QToolButton:pressed,
    QToolBar#SideBar QToolButton:checked {{
        background: {colors.pressed};
    }}

    QWidget#TopBar QToolButton:disabled {{
        color: {colors.disabled_text};
    }}

    QToolButton#ProjectButton {{
        padding: 4px 10px 4px 8px;
    }}

    QWidget#TopBar QMenuBar {{
        background: transparent;
        color: {colors.text};
        padding: 0px;
    }}

    QWidget#TopBar QMenuBar::item {{
        background: transparent;
        padding: 4px 8px;
        border-radius: 6px;
    }}

    QWidget#TopBar QMenuBar::item:selected {{
        background: {colors.hover};
    }}

    QMenu {{
        background: {colors.surface};
        color: {colors.text};
        border: 1px solid {colors.border};
        padding: 4px;
    }}

    QMenu::item {{
        padding: 4px 24px 4px 24px;
        border-radius: 4px;
    }}

    QMenu::item:selected {{
        background: {colors.selection};
        color: {colors.selection_text};
    }}

    QMenu::item:disabled {{
        color: {colors.disabled_text};
    }}

    QMenu::separator {{
        height: 1px;
        background: {colors.border};
        margin: 4px 8px;
    }}

    QFrame#TopBarSeparator {{
        background: {colors.border};
        border: none;
    }}

    QToolBar#SideBar {{
        background: {colors.window};
        border: none;
        padding: 6px 4px;
        spacing: 4px;
    }}

    QToolBar#SideBar QToolButton {{
        min-width: 24px;
        min-height: 24px;
    }}

    QMainWindow::separator {{
        background: {colors.window};
        width: {SEPARATOR_WIDTH}px;
        height: {SEPARATOR_WIDTH}px;
    }}

    QMainWindow::separator:hover {{
        background: {colors.accent};
    }}

    QDockWidget {{
        color: {colors.text};
        titlebar-close-icon: none;
        titlebar-normal-icon: none;
    }}

    QFrame#ToolPaneCard {{
        background: {colors.surface};
        border: none;
        border-radius: {CARD_RADIUS}px;
    }}

    QWidget#ToolPaneHeader {{
        background: transparent;
        border-bottom: 1px solid {colors.border};
    }}

    QLabel#ToolPaneTitle {{
        color: {colors.text};
        font-weight: 600;
    }}

    QToolButton#ToolPaneClose {{
        border: none;
        border-radius: 4px;
        padding: 0px;
        background: transparent;
    }}

    QToolButton#ToolPaneClose:hover {{
        background: {colors.pressed};
    }}

    QWidget#ToolPaneContent {{
        background: transparent;
    }}

    QLabel#ToolPanePlaceholder {{
        color: {colors.text_muted};
        padding: 12px;
    }}

    QLabel[placeholder="true"] {{
        color: {colors.text_muted};
    }}

    QLabel[error="true"] {{
        color: {colors.error};
    }}

    QWidget#DocumentArea,
    QLabel#DocumentPlaceholder {{
        background: transparent;
    }}

    QFrame#DocumentCard {{
        background: {colors.editor};
        border: none;
        border-radius: {CARD_RADIUS}px;
    }}

    QLabel#DocumentPlaceholder {{
        color: {colors.text_muted};
    }}

    QTabWidget#DocumentTabs::pane {{
        border: none;
        border-top: 1px solid {colors.border};
        background: transparent;
    }}

    QTabWidget#DocumentTabs QTabBar {{
        background: transparent;
    }}

    QTabWidget#DocumentTabs QTabBar::tab {{
        background: transparent;
        color: {colors.text_muted};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 6px 12px;
        margin: 0px;
    }}

    QTabWidget#DocumentTabs QTabBar::tab:hover {{
        background: {colors.hover};
    }}

    QTabWidget#DocumentTabs QTabBar::tab:selected {{
        color: {colors.text};
        border-bottom: 2px solid {colors.accent};
    }}

    QToolButton#TabCloseButton {{
        border: none;
        border-radius: 4px;
        padding: 0px;
        background: transparent;
    }}

    QToolButton#TabCloseButton:hover {{
        background: {colors.pressed};
    }}

    QStatusBar#StatusBar {{
        background: {colors.window};
        color: {colors.text_muted};
    }}

    QStatusBar#StatusBar::item {{
        border: none;
    }}

    QStatusBar#StatusBar QLabel {{
        color: {colors.text_muted};
        padding: 0px 6px;
    }}
    """


class ThemeManager(QObject):
    """Applies a scheme to the application and follows the desktop.

    The desktop is followed until an :attr:`override` is set, which is what the
    ``appearance/theme`` preference does when the user asks for light or dark
    outright; clearing it goes back to following the desktop.

    Parameters
    ----------
    application : PyQt6.QtWidgets.QApplication
        The application the palette and style sheet are applied to.
    parent : PyQt6.QtCore.QObject, optional
        Parent object, by default the application itself.

    Attributes
    ----------
    scheme_changed : PyQt6.QtCore.pyqtSignal
        Emitted with the new :class:`ColorScheme` after the palette and the
        style sheet have been applied, so that anything holding pre-rendered
        colours — the icons above all — can rebuild itself.
    """

    scheme_changed = pyqtSignal(ColorScheme)

    def __init__(self, application: QApplication, parent: QObject | None = None) -> None:
        super().__init__(parent if parent is not None else application)
        self._application = application
        self._override: ColorScheme | None = None
        self._scheme = detect_color_scheme()

        hints = QGuiApplication.styleHints()
        if hints is not None:
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

        #: Whether the portal is being listened to as well as Qt.
        self.watching_portal = self._watch_portal()

    @property
    def scheme(self) -> ColorScheme:
        """ColorScheme: The scheme currently applied."""

        return self._scheme

    @property
    def colors(self) -> ThemeColors:
        """ThemeColors: The colour tokens currently applied."""

        return COLORS[self._scheme]

    @property
    def override(self) -> ColorScheme | None:
        """ColorScheme, optional: The scheme forced on the application.

        ``None`` while the desktop is being followed.  Setting it applies the
        scheme at once and stops the desktop from changing it again; setting it
        back to ``None`` applies whatever the desktop is asking for now.
        """

        return self._override

    @override.setter
    def override(self, scheme: ColorScheme | None) -> None:
        self._override = scheme
        self.apply()

    def apply(self, scheme: ColorScheme | None = None) -> None:
        """Apply a scheme to the application.

        Parameters
        ----------
        scheme : ColorScheme, optional
            The scheme to apply.  When omitted the scheme is the
            :attr:`override` if one is set, and what the desktop asks for
            otherwise.
        """

        if scheme is None:
            scheme = self._override if self._override is not None else detect_color_scheme()
        self._scheme = scheme
        colors = COLORS[self._scheme]
        self._application.setPalette(build_palette(colors))
        self._application.setStyleSheet(build_stylesheet(colors))
        self.scheme_changed.emit(self._scheme)

    def _on_system_scheme_changed(self, _scheme: Qt.ColorScheme) -> None:
        """Re-apply the theme when the desktop switches between light and dark.

        Parameters
        ----------
        _scheme : PyQt6.QtCore.Qt.ColorScheme
            The scheme reported by Qt.  It is read back through
            :func:`detect_color_scheme` instead of being trusted here, so that
            ``Unknown`` maps to light in one single place.  A user who asked
            for light or dark outright is not overruled by the desktop, so this
            does nothing while an :attr:`override` is set.
        """

        if self._override is None:
            self.apply()

    def _watch_portal(self) -> bool:
        """Listen for the desktop changing its appearance over the portal.

        ``colorSchemeChanged`` is not enough on a desktop where Qt reads the
        scheme wrongly to begin with: it is fed from the same place, so it
        never reports the change either.

        Returns
        -------
        bool
            Whether the portal is being listened to.  ``False`` is the ordinary
            answer on Windows, on macOS, and on a Linux box with no portal; the
            application then follows Qt alone, as it did before.
        """

        if QDBusConnection is None:
            return False
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            return False
        return bus.connect(
            PORTAL_SERVICE,
            PORTAL_PATH,
            PORTAL_SETTINGS,
            SETTING_CHANGED,
            self._on_portal_setting_changed,
        )

    @pyqtSlot(str, str, 'QDBusVariant')
    def _on_portal_setting_changed(self, namespace: str, key: str, value: object) -> None:
        """Re-apply the theme when the desktop publishes a new appearance.

        The portal signals every setting it holds, so all but the colour scheme
        are dropped.  The new value is read back through
        :func:`detect_color_scheme` rather than taken from the signal, so that
        "no preference" is resolved in the one place that knows how.

        Parameters
        ----------
        namespace : str
            The namespace of the setting that changed.
        key : str
            The key within it.
        value : object
            What it changed to, which is not used.
        """

        if namespace != APPEARANCE_NAMESPACE or key != COLOR_SCHEME_KEY:
            return
        if self._override is None:
            self.apply()
