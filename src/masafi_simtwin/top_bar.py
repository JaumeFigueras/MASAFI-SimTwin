"""The single row of chrome that runs across the top of the main window.

The bar carries, from left to right: the application logo, the hamburger button
that stands in for the menu bar, and the project button whose drop-down lists
the recently opened projects.  Pushed to the right edge sit the simulation
controls, then a separator and the search button, then a separator and the
settings button.

The hamburger does not open a pop-up.  Clicking it *replaces* the button with
the real ``QMenuBar``, laid out in the same place; the menu bar disappears and
the button comes back as soon as an item is triggered or the user clicks
elsewhere.  The project button steps aside with it, so the menu titles keep the
left of the bar to themselves and nothing shifts sideways as menus are opened.  That is the behaviour of the compact main menu in PyCharm, and it is
why the menu bar lives in this widget rather than in the window's own menu bar
slot — that slot is taken by this bar.
"""

from __future__ import annotations

from importlib import resources

from PyQt6.QtCore import QEvent, QObject, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QMouseEvent
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QMenu,
    QMenuBar,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from masafi_simtwin import icons
from masafi_simtwin.menus import clear_menu

#: Side, in pixels, of the logo drawn at the far left of the bar.
LOGO_SIZE = 24

#: The presses that count as the user turning away from the expanded menu bar.
#: The non-client one is the window's own title bar and frame.
_PRESS_EVENTS = frozenset(
    {
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.NonClientAreaMouseButtonPress,
    }
)


def _load_logo(parent: QWidget | None = None) -> QSvgWidget:
    """Build the logo widget from the SVG shipped in ``resources``.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.

    Returns
    -------
    PyQt6.QtSvgWidgets.QSvgWidget
        A fixed size widget rendering ``resources/logo.svg``.
    """

    path = resources.files('masafi_simtwin.resources') / 'logo.svg'
    with resources.as_file(path) as svg_path:
        widget = QSvgWidget(str(svg_path), parent)
    widget.setFixedSize(QSize(LOGO_SIZE, LOGO_SIZE))
    widget.setObjectName('Logo')
    return widget


def _separator(parent: QWidget | None = None) -> QFrame:
    """Build one of the thin vertical rules that group the right hand buttons.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.

    Returns
    -------
    PyQt6.QtWidgets.QFrame
        A one pixel wide vertical line.
    """

    line = QFrame(parent)
    line.setObjectName('TopBarSeparator')
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFrameShadow(QFrame.Shadow.Plain)
    line.setFixedWidth(1)
    line.setFixedHeight(18)
    return line


class TopBar(QWidget):
    """The top bar of the main window.

    Parameters
    ----------
    menu_bar : PyQt6.QtWidgets.QMenuBar
        The application menu bar.  It is re-parented into this widget and stays
        hidden until the hamburger is clicked.
    control_actions : list of PyQt6.QtGui.QAction
        The simulation controls, in display order: run, stop, fast forward and
        reset.  They are owned by the window, so the same actions serve the
        *Run* menu and this bar.
    open_project_action : PyQt6.QtGui.QAction
        The *Open Project* action, shown at the top of the project drop-down.
    clear_recent_projects_action : PyQt6.QtGui.QAction
        The action that empties the history, shown at the foot of the drop-down.
    search_action : PyQt6.QtGui.QAction
        The action behind the search button.
    settings_action : PyQt6.QtGui.QAction
        The action behind the settings button.
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.

    Attributes
    ----------
    recent_project_selected : PyQt6.QtCore.pyqtSignal
        Emitted with the path of the project picked from the drop-down.
    """

    recent_project_selected = pyqtSignal(str)

    def __init__(
        self,
        menu_bar: QMenuBar,
        control_actions: list[QAction],
        open_project_action: QAction,
        clear_recent_projects_action: QAction,
        search_action: QAction,
        settings_action: QAction,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName('TopBar')
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self._menu_bar = menu_bar
        self._open_project_action = open_project_action
        self._clear_recent_projects_action = clear_recent_projects_action
        self._recent_projects: list[str] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        layout.addWidget(_load_logo(self))

        self._hamburger_button = self._build_hamburger_button()
        layout.addWidget(self._hamburger_button)

        self._menu_bar.setParent(self)
        self._menu_bar.setNativeMenuBar(False)
        self._menu_bar.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self._menu_bar.hide()
        layout.addWidget(self._menu_bar)

        self._project_button = self._build_project_button()
        layout.addWidget(self._project_button)

        layout.addStretch(1)

        for action in control_actions:
            layout.addWidget(self._build_action_button(action))

        layout.addWidget(_separator(self))
        layout.addWidget(self._build_action_button(search_action))
        layout.addWidget(_separator(self))
        layout.addWidget(self._build_action_button(settings_action))

        self._menu_bar.installEventFilter(self)
        self._menu_bar.triggered.connect(self._collapse_menu_bar)

        self.set_project_name(self.tr('No Project'))
        self.set_recent_projects([])

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _build_hamburger_button(self) -> QToolButton:
        """Build the button that swaps itself for the menu bar.

        Returns
        -------
        PyQt6.QtWidgets.QToolButton
            The hamburger button, already connected.
        """

        button = QToolButton(self)
        button.setObjectName('HamburgerButton')
        button.setAutoRaise(True)
        button.setIconSize(QSize(icons.CHROME_ICON_SIZE, icons.CHROME_ICON_SIZE))
        button.setToolTip(self.tr('Main Menu'))
        icons.set_icon(button, 'menu')
        button.clicked.connect(self._expand_menu_bar)
        return button

    def _build_project_button(self) -> QToolButton:
        """Build the project name button and its drop-down.

        Returns
        -------
        PyQt6.QtWidgets.QToolButton
            A button whose menu opens on a single click.
        """

        button = QToolButton(self)
        button.setObjectName('ProjectButton')
        button.setAutoRaise(True)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        button.setMenu(QMenu(button))
        return button

    def _build_action_button(self, action: QAction) -> QToolButton:
        """Wrap an action in a flat tool button.

        Parameters
        ----------
        action : PyQt6.QtGui.QAction
            The action to display.

        Returns
        -------
        PyQt6.QtWidgets.QToolButton
            A borderless, icon-only button bound to ``action``.
        """

        button = QToolButton(self)
        button.setAutoRaise(True)
        button.setDefaultAction(action)
        button.setIconSize(QSize(icons.CHROME_ICON_SIZE, icons.CHROME_ICON_SIZE))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        return button

    # ------------------------------------------------------------------
    # Project drop-down
    # ------------------------------------------------------------------

    def set_project_name(self, name: str) -> None:
        """Set the text shown on the project button.

        Parameters
        ----------
        name : str
            Name of the open project.
        """

        self._project_button.setText(name)
        self._project_button.setToolTip(name)

    def set_recent_projects(self, projects: list[tuple[str, str]]) -> None:
        """Rebuild the project drop-down.

        The menu always opens with *Open Project*; the recent projects follow it
        after a separator, most recent first; and *Clear Recent Projects* closes
        it after a separator of its own.  With no history the list is replaced by
        a disabled placeholder so that the menu is never empty.

        The last entry is always there, disabled when there is nothing to clear,
        so that the menu keeps the same shape whatever the history holds.

        A project is shown by its name; its path is on the entry as a tool tip,
        and after the name in brackets when two projects of the history share a
        name.  Naming them is the window's business, not the bar's — see
        :func:`masafi_simtwin.project.labels_for`.

        The menu is emptied with :func:`~masafi_simtwin.menus.clear_menu` rather
        than ``QMenu.clear()``, because this is reached from the ``triggered``
        handler of one of the entries it is about to remove.

        Parameters
        ----------
        projects : list of tuple of str
            The recently opened projects as ``(label, path)`` pairs, most recent
            first.
        """

        self._recent_projects = list(projects)
        menu = self._project_button.menu()
        clear_menu(menu)
        menu.addAction(self._open_project_action)
        menu.addSeparator()

        if not self._recent_projects:
            placeholder = menu.addAction(self.tr('No Recent Projects'))
            placeholder.setEnabled(False)
        else:
            for label, path in self._recent_projects:
                action = menu.addAction(label)
                action.setData(path)
                action.setToolTip(path)
                action.triggered.connect(
                    lambda _checked=False, selected=path: self.recent_project_selected.emit(
                        selected
                    )
                )

        menu.addSeparator()
        menu.addAction(self._clear_recent_projects_action)

    # ------------------------------------------------------------------
    # Hamburger behaviour
    # ------------------------------------------------------------------

    @property
    def menu_bar_visible(self) -> bool:
        """bool: Whether the menu bar currently stands in for the hamburger."""

        return self._menu_bar.isVisible()

    def _expand_menu_bar(self) -> None:
        """Replace the hamburger button with the menu bar and focus it.

        The project button is taken down for as long as the menu bar is up: the
        menu titles are what the left of the bar is for while the menu is open,
        and the project name would only be pushed about as they take the room.

        While the menu bar stands in for the button, this widget filters the
        events of the whole application, which is what lets a click anywhere
        outside the menu fold it away again.
        """

        if self._menu_bar.isVisible():
            return

        self._hamburger_button.hide()
        self._project_button.hide()
        self._menu_bar.show()
        self._menu_bar.setFocus(Qt.FocusReason.MouseFocusReason)

        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)

    def _collapse_menu_bar(self) -> None:
        """Hide the menu bar and bring the hamburger and project buttons back."""

        application = QApplication.instance()
        if application is not None:
            application.removeEventFilter(self)

        self._menu_bar.hide()
        self._hamburger_button.show()
        self._project_button.show()

    def _collapse_menu_bar_if_idle(self) -> None:
        """Collapse the menu bar unless the user is still working in it.

        Called one event loop turn after the menu bar loses focus or the window
        is deactivated, which is late enough for an opening pop-up to have
        registered itself as the active pop-up widget.  Without that delay,
        opening *File* would be read as leaving the menu and would fold the bar
        away under the user's cursor.
        """

        if not self._menu_bar.isVisible():
            return
        if QApplication.activePopupWidget() is not None:
            return
        if self._menu_bar.hasFocus() or self._menu_bar.activeAction() is not None:
            return
        self._collapse_menu_bar()

    def _is_press_inside_menu(self, obj: QObject, event: QEvent) -> bool:
        """Tell whether a mouse press landed in the menu bar or in one of its menus.

        Parameters
        ----------
        obj : PyQt6.QtCore.QObject
            The object the press was sent to.  Events sent to something that is
            not a widget — the ``QWindow`` behind a widget, above all — are
            reported as inside, because the same press is delivered again to the
            widget under the cursor and that delivery is the one that decides.
        event : PyQt6.QtCore.QEvent
            The mouse press.

        Returns
        -------
        bool
            ``True`` when the press belongs to the menu, ``False`` when it is
            the click elsewhere that folds the menu bar away.
        """

        widget = obj if isinstance(obj, QWidget) else None
        if widget is None:
            return True

        if widget.windowType() == Qt.WindowType.Popup and isinstance(event, QMouseEvent):
            #  An open pop-up grabs the mouse, so a press anywhere on screen is
            #  delivered to it.  Only the ones inside its own rectangle are
            #  really in the menu; the rest are the click that dismisses it.
            if not widget.rect().contains(event.position().toPoint()):
                return False

        while widget is not None:
            if widget is self._menu_bar:
                return True
            widget = widget.parentWidget()

        return False

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802  (Qt naming)
        """Fold the menu bar away as soon as the user turns to something else.

        Three things count as turning away: a mouse press outside the menu bar
        and its menus, the menu bar losing keyboard focus, and the window itself
        being deactivated for another application.

        Parameters
        ----------
        obj : PyQt6.QtCore.QObject
            The object the event was sent to.
        event : PyQt6.QtCore.QEvent
            The event.

        Returns
        -------
        bool
            ``False`` always: the event is observed, never consumed.
        """

        event_type = event.type()

        if obj is self._menu_bar and event_type == QEvent.Type.FocusOut:
            QTimer.singleShot(0, self._collapse_menu_bar_if_idle)
        elif self._menu_bar.isVisible():
            if event_type in _PRESS_EVENTS and not self._is_press_inside_menu(obj, event):
                self._collapse_menu_bar()
            elif event_type == QEvent.Type.WindowDeactivate and obj is self.window():
                QTimer.singleShot(0, self._collapse_menu_bar_if_idle)

        return super().eventFilter(obj, event)
