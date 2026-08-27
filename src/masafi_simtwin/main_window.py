"""The main window: top bar, left tool stripe, document area and status bar.

The window owns every action.  The menu bar behind the hamburger and the buttons
on the top bar are two views of that one set, so a control never drifts out of
step with its menu entry.

The layout follows PyCharm.  The top bar takes the window's menu widget slot and
runs the full width; the tool stripe is a toolbar in the left toolbar area, which
leaves the left dock area free for the panes those buttons will eventually open;
the documents fill the centre; the status bar closes the window at the bottom.
"""

from __future__ import annotations

from PyQt6.QtCore import QSettings, QSize, Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QStatusBar,
    QWidget,
)

from masafi_simtwin import APPLICATION_NAME, icons
from masafi_simtwin.dialogs import AboutDialog
from masafi_simtwin.document_area import DocumentArea
from masafi_simtwin.side_bar import SideBar
from masafi_simtwin.tool_pane import ToolPane
from masafi_simtwin.top_bar import TopBar

#: How many projects the drop-down remembers.
MAX_RECENT_PROJECTS = 10

#: Default size of the window the first time the application is started.
DEFAULT_WINDOW_SIZE = QSize(1440, 900)


class MainWindow(QMainWindow):
    """The application's main window.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('MainWindow')
        self.setWindowTitle(APPLICATION_NAME)
        self.resize(DEFAULT_WINDOW_SIZE)

        self._settings = QSettings()
        self._project_name: str = ''
        self._recent_projects: list[str] = self._load_recent_projects()

        self._create_actions()
        self._create_top_bar()
        self._create_side_bar()
        self._create_tool_panes()
        self._create_document_area()
        self._create_status_bar()

        self._top_bar.set_recent_projects(self._recent_projects)
        self.statusBar().showMessage(self.tr('Ready'))

    # ------------------------------------------------------------------
    # Actions and menus
    # ------------------------------------------------------------------

    def _create_actions(self) -> None:
        """Build every action of the window.

        The simulation controls are built here rather than in the top bar so
        that the *Run* menu and the top bar share one action each.
        """

        self.new_project_action = QAction(self.tr('New Project…'), self)
        self.new_project_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_project_action.triggered.connect(
            lambda: self.statusBar().showMessage(
                self.tr('Creating a project is not implemented yet'), 4000
            )
        )

        self.open_project_action = QAction(self.tr('Open Project…'), self)
        self.open_project_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_project_action.triggered.connect(self.open_project)

        self.close_project_action = QAction(self.tr('Close Project'), self)
        self.close_project_action.setEnabled(False)
        self.close_project_action.triggered.connect(self.close_project)

        self.quit_action = QAction(self.tr('Exit'), self)
        self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.setMenuRole(QAction.MenuRole.QuitRole)
        self.quit_action.triggered.connect(self.close)

        self.run_action = QAction(self.tr('Run'), self)
        self.run_action.setToolTip(self.tr('Run the simulation'))
        icons.set_icon(self.run_action, 'play_arrow')
        self.run_action.triggered.connect(lambda: self._report_control(self.tr('Running')))

        self.stop_action = QAction(self.tr('Stop'), self)
        self.stop_action.setToolTip(self.tr('Stop the simulation'))
        icons.set_icon(self.stop_action, 'stop')
        self.stop_action.triggered.connect(lambda: self._report_control(self.tr('Stopped')))

        self.fast_forward_action = QAction(self.tr('Fast Forward'), self)
        self.fast_forward_action.setToolTip(self.tr('Run the simulation without animation'))
        icons.set_icon(self.fast_forward_action, 'fast_forward')
        self.fast_forward_action.triggered.connect(
            lambda: self._report_control(self.tr('Fast forwarding'))
        )

        self.reset_action = QAction(self.tr('Reset'), self)
        self.reset_action.setToolTip(self.tr('Reset the simulation to its initial state'))
        icons.set_icon(self.reset_action, 'restart_alt')
        self.reset_action.triggered.connect(lambda: self._report_control(self.tr('Idle')))

        self.search_action = QAction(self.tr('Search'), self)
        self.search_action.setToolTip(self.tr('Search everywhere'))
        self.search_action.setShortcut(QKeySequence.StandardKey.Find)
        icons.set_icon(self.search_action, 'search')
        self.search_action.triggered.connect(
            lambda: self.statusBar().showMessage(self.tr('Search is not implemented yet'), 4000)
        )

        self.settings_action = QAction(self.tr('Settings'), self)
        self.settings_action.setToolTip(self.tr('Open the settings'))
        self.settings_action.setShortcut(QKeySequence.StandardKey.Preferences)
        self.settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        icons.set_icon(self.settings_action, 'settings')
        self.settings_action.triggered.connect(
            lambda: self.statusBar().showMessage(self.tr('Settings are not implemented yet'), 4000)
        )

        self.about_action = QAction(self.tr('About {0}').format(APPLICATION_NAME), self)
        self.about_action.setMenuRole(QAction.MenuRole.AboutRole)
        self.about_action.triggered.connect(self.show_about)

    def _build_menu_bar(self) -> QMenuBar:
        """Build the classic menu bar shown in place of the hamburger button.

        Returns
        -------
        PyQt6.QtWidgets.QMenuBar
            The menu bar.  Entries with no implementation behind them yet are
            present but disabled, so that the shape of the application is
            visible without pretending the feature works.  Every menu is built
            here, but only *File* and *Help* are visible while no project is
            open; see :meth:`_update_menus_for_project`.
        """

        menu_bar = QMenuBar(self)

        file_menu = menu_bar.addMenu(self.tr('&File'))
        file_menu.addAction(self.new_project_action)
        file_menu.addAction(self.open_project_action)
        self._recent_menu = file_menu.addMenu(self.tr('Open Recent'))
        file_menu.addSeparator()
        file_menu.addAction(self.close_project_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)

        edit_menu = menu_bar.addMenu(self.tr('&Edit'))
        self._add_placeholder_actions(
            edit_menu,
            [
                self.tr('Undo'),
                self.tr('Redo'),
                None,
                self.tr('Cut'),
                self.tr('Copy'),
                self.tr('Paste'),
            ],
        )

        view_menu = menu_bar.addMenu(self.tr('&View'))
        self._add_placeholder_actions(
            view_menu,
            [
                self.tr('Tool Windows'),
                self.tr('Appearance'),
                None,
                self.tr('Zoom In'),
                self.tr('Zoom Out'),
            ],
        )

        navigate_menu = menu_bar.addMenu(self.tr('&Navigate'))
        self._add_placeholder_actions(
            navigate_menu,
            [
                self.tr('Block…'),
                self.tr('Sub-model…'),
                None,
                self.tr('Back'),
                self.tr('Forward'),
            ],
        )

        run_menu = menu_bar.addMenu(self.tr('&Run'))
        run_menu.addAction(self.run_action)
        run_menu.addAction(self.stop_action)
        run_menu.addAction(self.fast_forward_action)
        run_menu.addSeparator()
        run_menu.addAction(self.reset_action)

        tools_menu = menu_bar.addMenu(self.tr('&Tools'))
        self._add_placeholder_actions(
            tools_menu, [self.tr('Block Libraries'), self.tr('Python Console')]
        )
        tools_menu.addSeparator()
        tools_menu.addAction(self.settings_action)

        window_menu = menu_bar.addMenu(self.tr('&Window'))
        self._add_placeholder_actions(window_menu, [self.tr('Next Tab'), self.tr('Previous Tab')])

        help_menu = menu_bar.addMenu(self.tr('&Help'))
        self._add_placeholder_actions(help_menu, [self.tr('Documentation')])
        help_menu.addSeparator()
        help_menu.addAction(self.about_action)

        self._project_menus = [
            edit_menu,
            view_menu,
            navigate_menu,
            run_menu,
            tools_menu,
            window_menu,
        ]
        self._update_menus_for_project()

        return menu_bar

    def _add_placeholder_actions(self, menu: QMenu, titles: list[str | None]) -> None:
        """Fill a menu with disabled entries that mark out what will live there.

        Parameters
        ----------
        menu : PyQt6.QtWidgets.QMenu
            The menu to fill.
        titles : list of (str or None)
            Translated entry titles; ``None`` inserts a separator.
        """

        for title in titles:
            if title is None:
                menu.addSeparator()
                continue
            action: QAction = menu.addAction(title)
            action.setEnabled(False)

    def _update_menus_for_project(self) -> None:
        """Show only the menus that make sense for the current project state.

        With no project open there is nothing to edit, view, navigate or run, so
        the menu bar keeps *File* and *Help* alone; the rest appear once a
        project is open and go away again when it is closed.
        """

        for menu in self._project_menus:
            menu.menuAction().setVisible(bool(self._project_name))

    # ------------------------------------------------------------------
    # Window furniture
    # ------------------------------------------------------------------

    def _create_top_bar(self) -> None:
        """Build the top bar and install it in the window's menu widget slot."""

        self._top_bar = TopBar(
            menu_bar=self._build_menu_bar(),
            control_actions=[
                self.run_action,
                self.stop_action,
                self.fast_forward_action,
                self.reset_action,
            ],
            open_project_action=self.open_project_action,
            search_action=self.search_action,
            settings_action=self.settings_action,
            parent=self,
        )
        self._top_bar.recent_project_selected.connect(self.open_project_path)
        self.setMenuWidget(self._top_bar)

    def _create_side_bar(self) -> None:
        """Build the left tool stripe and add it to the left toolbar area."""

        self._side_bar = SideBar(self)
        self._side_bar.add_top_pane('project', 'account_tree', self.tr('Project'))
        self._side_bar.add_top_pane('libraries', 'category', self.tr('Libraries'))
        self._side_bar.add_bottom_pane('python', 'terminal', self.tr('Python Console'))
        self._side_bar.add_bottom_pane('problems', 'error', self.tr('Problems'))
        self._side_bar.pane_toggled.connect(self._on_pane_toggled)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self._side_bar)

    def _create_tool_panes(self) -> None:
        """Build the panes the tool stripe opens, one dock area per stripe group.

        The panes of a group are tabified onto each other so that the group
        occupies one slot in its dock area and shares its size: a pane opened
        after the user has resized its neighbour comes back at the size the user
        chose.  Only one pane of a group is ever visible, so the tab bar Qt would
        draw for a tabified pair never appears.

        The bottom corners are handed to the bottom dock area, which is what
        makes a pane at the bottom run the full width of the window and shorten
        the pane at the side instead of being shortened by it.
        """

        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.BottomDockWidgetArea)

        left = Qt.DockWidgetArea.LeftDockWidgetArea
        bottom = Qt.DockWidgetArea.BottomDockWidgetArea
        groups = [
            [('project', self.tr('Project'), left), ('libraries', self.tr('Libraries'), left)],
            [
                ('python', self.tr('Python Console'), bottom),
                ('problems', self.tr('Problems'), bottom),
            ],
        ]

        self._tool_panes: dict[str, ToolPane] = {}
        for group in groups:
            panes = []
            for key, title, area in group:
                pane = ToolPane(title, area=area, parent=self)
                self.addDockWidget(area, pane)
                pane.hide()
                pane.visibilityChanged.connect(
                    lambda visible, name=key: self._on_pane_visibility_changed(name, visible)
                )
                self._tool_panes[key] = pane
                panes.append(pane)

            for pane in panes[1:]:
                self.tabifyDockWidget(panes[0], pane)
            self.resizeDocks(
                panes,
                [pane.default_size for pane in panes],
                panes[0].resize_orientation,
            )

    def _create_document_area(self) -> None:
        """Build the tabbed document area and make it the central widget."""

        self._document_area = DocumentArea(self)
        self._document_area.current_document_changed.connect(self._on_document_changed)
        self.setCentralWidget(self._document_area)

    def _create_status_bar(self) -> None:
        """Build the status bar, with the transient message on the left.

        The two labels on the right are permanent: the document that is current
        and the state of the simulation.
        """

        status_bar = QStatusBar(self)
        status_bar.setObjectName('StatusBar')
        status_bar.setSizeGripEnabled(True)

        self._document_label = QLabel(self.tr('No document'), status_bar)
        self._state_label = QLabel(self.tr('Idle'), status_bar)
        status_bar.addPermanentWidget(self._document_label)
        status_bar.addPermanentWidget(self._state_label)

        self.setStatusBar(status_bar)

    # ------------------------------------------------------------------
    # Accessors, for the tests and for the panes to come
    # ------------------------------------------------------------------

    @property
    def top_bar(self) -> TopBar:
        """masafi_simtwin.top_bar.TopBar: The top bar."""

        return self._top_bar

    @property
    def side_bar(self) -> SideBar:
        """masafi_simtwin.side_bar.SideBar: The left tool stripe."""

        return self._side_bar

    def tool_pane(self, key: str) -> ToolPane | None:
        """Return the pane a stripe button opens.

        Parameters
        ----------
        key : str
            Identifier the stripe button was added with.

        Returns
        -------
        masafi_simtwin.tool_pane.ToolPane or None
            The pane, or ``None`` when no pane has been written for that button.
        """

        return self._tool_panes.get(key)

    @property
    def document_area(self) -> DocumentArea:
        """masafi_simtwin.document_area.DocumentArea: The tabbed document area."""

        return self._document_area

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def open_project(self) -> None:
        """Ask for a project directory and open it."""

        directory = QFileDialog.getExistingDirectory(self, self.tr('Open Project'))
        if directory:
            self.open_project_path(directory)

    def open_project_path(self, path: str) -> None:
        """Open a project by path.

        There is no project model yet, so this records the project as open,
        moves it to the head of the recent list and updates the chrome.

        Parameters
        ----------
        path : str
            Directory of the project.
        """

        self._project_name = path.rstrip('/').rpartition('/')[2] or path
        self._top_bar.set_project_name(self._project_name)
        self.setWindowTitle(f'{self._project_name} — {APPLICATION_NAME}')
        self.close_project_action.setEnabled(True)
        self._update_menus_for_project()
        self._remember_project(path)
        self.statusBar().showMessage(self.tr('Opened {0}').format(path), 4000)

    def close_project(self) -> None:
        """Close the open project and put the chrome back to its empty state."""

        self._project_name = ''
        self._top_bar.set_project_name(self.tr('No Project'))
        self.setWindowTitle(APPLICATION_NAME)
        self.close_project_action.setEnabled(False)
        self._update_menus_for_project()
        self.statusBar().showMessage(self.tr('Project closed'), 4000)

    def _remember_project(self, path: str) -> None:
        """Move a project to the head of the recent list and persist it.

        Parameters
        ----------
        path : str
            Directory of the project.
        """

        recent = [path] + [other for other in self._recent_projects if other != path]
        self._recent_projects = recent[:MAX_RECENT_PROJECTS]
        self._settings.setValue('recent_projects', self._recent_projects)
        self._top_bar.set_recent_projects(self._recent_projects)
        self._rebuild_recent_menu()

    def _load_recent_projects(self) -> list[str]:
        """Read the recent project list back from the settings.

        Returns
        -------
        list of str
            Paths, most recent first.  An empty list when nothing was stored or
            when what was stored is not a list of strings.
        """

        stored = self._settings.value('recent_projects', [])
        if isinstance(stored, str):
            return [stored]
        if isinstance(stored, list):
            return [str(path) for path in stored]
        return []

    def _rebuild_recent_menu(self) -> None:
        """Mirror the recent project list into the *File → Open Recent* menu."""

        self._recent_menu.clear()
        if not self._recent_projects:
            empty = self._recent_menu.addAction(self.tr('No Recent Projects'))
            empty.setEnabled(False)
            return
        for path in self._recent_projects:
            action = self._recent_menu.addAction(path)
            action.triggered.connect(
                lambda _checked=False, selected=path: self.open_project_path(selected)
            )

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------

    def show_about(self) -> None:
        """Open the About dialog, modal over the window."""

        AboutDialog(self).exec()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _report_control(self, state: str) -> None:
        """Show the state a simulation control asked for.

        There is no run control behind the buttons yet; this is what makes them
        visibly wired while the backend protocol is being designed.

        Parameters
        ----------
        state : str
            Translated name of the state.
        """

        self._state_label.setText(state)
        self.statusBar().showMessage(state, 4000)

    def _on_pane_toggled(self, key: str, checked: bool) -> None:
        """Open or close the pane a tool stripe button stands for.

        The stripe group already guarantees that at most one button of the group
        is pressed, so closing the pane that is leaving happens through this same
        slot, with ``checked`` false, before the one that is arriving opens.

        Parameters
        ----------
        key : str
            Identifier of the pane.
        checked : bool
            The new state of the button.
        """

        pane = self._tool_panes.get(key)
        if pane is not None:
            pane.setVisible(checked)

    def _on_pane_visibility_changed(self, key: str, visible: bool) -> None:
        """Keep the stripe button in step with the pane it opens.

        A pane can be closed from its own header, and Qt hides every dock widget
        when the window goes away; the first has to release the stripe button,
        the second must not touch it.

        Parameters
        ----------
        key : str
            Identifier of the pane.
        visible : bool
            Whether the pane is now visible.
        """

        if not self.isVisible():
            return

        action = self._side_bar.pane_action(key)
        if action is not None and action.isChecked() != visible:
            action.setChecked(visible)

    def _on_document_changed(self, title: str) -> None:
        """Show the current document in the status bar.

        Parameters
        ----------
        title : str
            Title of the current document, empty when none is open.
        """

        self._document_label.setText(title or self.tr('No document'))
