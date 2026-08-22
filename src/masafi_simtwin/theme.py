"""Light and dark themes that follow the operating system setting.

The application never hard codes a colour.  Every widget takes its colours from
the :class:`ThemeColors` record of the active scheme, which is turned into a
``QPalette`` and a style sheet by :func:`build_palette` and
:func:`build_stylesheet` and applied by :class:`ThemeManager`.

The scheme itself is decided by the desktop.  Qt reports it through
``QStyleHints.colorScheme()`` and signals every change with
``colorSchemeChanged``, so switching the desktop between light and dark repaints
the running application without a restart and without a manual toggle.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPalette
from PyQt6.QtWidgets import QApplication


class ColorScheme(Enum):
    """The two schemes the application knows how to paint."""

    LIGHT = 'light'
    DARK = 'dark'


@dataclass(frozen=True)
class ThemeColors:
    """The colour tokens of one scheme.

    Attributes
    ----------
    window : str
        Background of ordinary dialogs and of the window itself.
    surface : str
        Background of the chrome: top bar, tool stripes, status bar, tool panes.
    editor : str
        Background of the document area, the largest surface on screen.
    border : str
        Hairline that separates the chrome from the document area.
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
    window='#f7f8fa',
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
    window='#2b2d30',
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


def detect_color_scheme() -> ColorScheme:
    """Return the scheme the desktop is currently asking for.

    Returns
    -------
    ColorScheme
        The scheme reported by Qt.  A desktop that does not express a
        preference, or a platform plugin that cannot read one, is treated as
        light.
    """

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
        background: {colors.surface};
        border-bottom: 1px solid {colors.border};
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
        background: {colors.surface};
        border: none;
        border-right: 1px solid {colors.border};
        padding: 6px 4px;
        spacing: 4px;
    }}

    QToolBar#SideBar QToolButton {{
        min-width: 24px;
        min-height: 24px;
    }}

    QMainWindow::separator {{
        background: {colors.border};
        width: 1px;
        height: 1px;
    }}

    QDockWidget {{
        color: {colors.text};
        titlebar-close-icon: none;
        titlebar-normal-icon: none;
    }}

    QWidget#ToolPaneHeader {{
        background: {colors.surface};
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
        background: {colors.surface};
    }}

    QLabel#ToolPanePlaceholder {{
        color: {colors.text_muted};
        padding: 12px;
    }}

    QWidget#DocumentArea,
    QLabel#DocumentPlaceholder {{
        background: {colors.editor};
    }}

    QLabel#DocumentPlaceholder {{
        color: {colors.text_muted};
    }}

    QTabWidget#DocumentTabs::pane {{
        border: none;
        border-top: 1px solid {colors.border};
        background: {colors.editor};
    }}

    QTabWidget#DocumentTabs QTabBar {{
        background: {colors.surface};
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
        background: {colors.surface};
        border-top: 1px solid {colors.border};
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
        self._scheme = detect_color_scheme()

        hints = QGuiApplication.styleHints()
        if hints is not None:
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    @property
    def scheme(self) -> ColorScheme:
        """ColorScheme: The scheme currently applied."""

        return self._scheme

    @property
    def colors(self) -> ThemeColors:
        """ThemeColors: The colour tokens currently applied."""

        return COLORS[self._scheme]

    def apply(self, scheme: ColorScheme | None = None) -> None:
        """Apply a scheme to the application.

        Parameters
        ----------
        scheme : ColorScheme, optional
            The scheme to apply.  When omitted the scheme is read from the
            desktop again.
        """

        self._scheme = scheme if scheme is not None else detect_color_scheme()
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
            ``Unknown`` maps to light in one single place.
        """

        self.apply()
