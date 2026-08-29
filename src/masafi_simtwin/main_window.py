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

import time
from pathlib import Path

from PyQt6.QtCore import QSettings, QSize, Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QStatusBar,
    QWidget,
)

from masafi_simtwin import APPLICATION_NAME, documents, icons, project
from masafi_simtwin.dialogs import (
    AboutDialog,
    ModelDialog,
    NewProjectDialog,
    SettingsDialog,
    ask_to_restart,
)
from masafi_simtwin.preferences import install_id, needs_restart
from masafi_simtwin.project_tree import NodeKind, ProjectTree
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
        self._project_path: str | None = None
        self._session_started: float = 0.0
        self._recent_projects: list[str] = self._load_recent_projects()

        self._create_actions()
        self._create_top_bar()
        self._create_side_bar()
        self._create_tool_panes()
        self._create_document_area()
        self._create_status_bar()

        self._show_recent_projects()
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
        self.new_project_action.triggered.connect(self.new_project)

        self.open_project_action = QAction(self.tr('Open Project…'), self)
        self.open_project_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_project_action.triggered.connect(self.open_project)

        self.clear_recent_projects_action = QAction(self.tr('Clear Recent Projects'), self)
        self.clear_recent_projects_action.triggered.connect(self.clear_recent_projects)

        self.close_project_action = QAction(self.tr('Close Project'), self)
        self.close_project_action.setEnabled(False)
        self.close_project_action.triggered.connect(self.close_project)

        self.new_model_action = QAction(self.tr('New Model…'), self)
        self.new_model_action.triggered.connect(self.new_model)

        self.new_simulation_action = QAction(self.tr('New Simulation…'), self)
        self.new_simulation_action.triggered.connect(
            lambda: self._report(self.tr('Creating a simulation is not implemented yet'))
        )

        self.model_properties_action = QAction(self.tr('Model Properties…'), self)
        self.model_properties_action.triggered.connect(self.edit_model)

        self.delete_model_action = QAction(self.tr('Delete Model'), self)
        self.delete_model_action.triggered.connect(self.delete_model)

        self.project_settings_action = QAction(self.tr('Project Settings…'), self)
        self.project_settings_action.triggered.connect(
            lambda: self._report(self.tr('The project settings are not implemented yet'))
        )

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
        self.settings_action.triggered.connect(self.show_settings)

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

            The application's own *Settings* sits in *File*, as it does in the
            IDE this window is modelled on, and the simulation controls live on
            the top bar alone until there is a run control behind them.
        """

        menu_bar = QMenuBar(self)

        file_menu = menu_bar.addMenu(self.tr('&File'))
        file_menu.addAction(self.new_project_action)
        file_menu.addAction(self.open_project_action)
        self._recent_menu = file_menu.addMenu(self.tr('Open Recent'))
        file_menu.addSeparator()
        file_menu.addAction(self.close_project_action)
        file_menu.addSeparator()
        file_menu.addAction(self.settings_action)
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

        project_menu = menu_bar.addMenu(self.tr('&Project'))
        for entry in self.project_entries():
            if entry is None:
                project_menu.addSeparator()
            else:
                project_menu.addAction(entry)

        window_menu = menu_bar.addMenu(self.tr('&Window'))
        self._add_placeholder_actions(window_menu, [self.tr('Next Tab'), self.tr('Previous Tab')])

        help_menu = menu_bar.addMenu(self.tr('&Help'))
        self._add_placeholder_actions(help_menu, [self.tr('Documentation')])
        help_menu.addSeparator()
        help_menu.addAction(self.about_action)

        self._project_menus = [edit_menu, view_menu, project_menu, window_menu]
        self._update_menus_for_project()

        return menu_bar

    def project_entries(self) -> list[QAction | None]:
        """Give what can be done to the open project.

        The *Project* menu and the context menu of the project in the tree are
        two views of this one list, so an entry cannot be added to one and
        forgotten in the other.

        Returns
        -------
        list of (PyQt6.QtGui.QAction or None)
            The actions, with ``None`` where a separator goes.
        """

        return [
            self.new_model_action,
            self.new_simulation_action,
            None,
            self.project_settings_action,
        ]

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

        With no project open there is nothing to edit, view or do to a project,
        so the menu bar keeps *File* and *Help* alone; the rest appear once a
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
            clear_recent_projects_action=self.clear_recent_projects_action,
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

        self._project_tree = ProjectTree(
            {
                NodeKind.ROOT: self.project_entries(),
                NodeKind.MODELS: [self.new_model_action],
                NodeKind.MODEL: [
                    self.model_properties_action,
                    None,
                    self.delete_model_action,
                ],
                NodeKind.SIMULATIONS: [self.new_simulation_action],
            },
            self,
        )
        self._project_tree.model_activated.connect(self.open_model)
        contents: dict[str, QWidget] = {'project': self._project_tree}

        self._tool_panes: dict[str, ToolPane] = {}
        for group in groups:
            panes = []
            for key, title, area in group:
                pane = ToolPane(title, contents.get(key), area=area, key=key, parent=self)
                self.addDockWidget(area, pane)
                pane.hide()
                pane.pane_visibility_changed.connect(self._on_pane_visibility_changed)
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

    def new_project(self) -> None:
        """Ask where a new project goes, write it, and open it.

        The dialog settles on a path and nothing more; the writing happens here,
        where a failure has a window to be reported on.
        """

        dialog = NewProjectDialog(self, self._last_location())
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.project_path is None:
            return
        try:
            created = project.create(
                dialog.project_path, dialog.name, install=install_id()
            )
        except project.ProjectError as error:
            QMessageBox.critical(
                self,
                self.tr('The project could not be created'),
                str(error),
            )
            return
        self.open_project_path(str(created))

    def open_project(self) -> None:
        """Ask for a project file and open it."""

        path, _filter = QFileDialog.getOpenFileName(
            self,
            self.tr('Open Project'),
            self._last_location(),
            self.tr('MASAFI-SimTwin projects (*{0})').format(project.PROJECT_SUFFIX),
        )
        if path:
            self.open_project_path(path)

    def open_project_path(self, path: str) -> None:
        """Open a project by path.

        There is no project model yet, so this reads the name out of the
        manifest, takes the project's lock, records the project as open, moves
        it to the head of the recent list and updates the chrome.

        A project already open in this window is left alone, and one open in
        another is refused: nothing may hold the same project twice, because
        two writers of one archive silently lose each other's work.

        Parameters
        ----------
        path : str
            The ``.mfstz`` file of the project.
        """

        try:
            name = project.name_of(path)
        except project.ProjectError as error:
            QMessageBox.critical(self, self.tr('The project could not be opened'), str(error))
            return

        if path == self._project_path:
            return

        try:
            project.acquire(path)
        except project.ProjectLocked as error:
            QMessageBox.warning(
                self,
                self.tr('The project is already open'),
                self.tr('{0} is open in another window, as {1}.').format(
                    name, error.holder.get('user') or self.tr('another user')
                ),
            )
            return
        except project.ProjectError as error:
            QMessageBox.critical(self, self.tr('The project could not be opened'), str(error))
            return

        self._end_session()
        self._document_area.close_all_documents()
        self._project_path = path
        self._session_started = time.monotonic()
        self._record(path, project.EVENT_OPENED)

        self._project_name = name
        self._top_bar.set_project_name(self._project_name)
        self.setWindowTitle(f'{self._project_name} — {APPLICATION_NAME}')
        self.close_project_action.setEnabled(True)
        self._update_menus_for_project()
        self._project_tree.set_project(name, project.models_of(path))
        self.show_pane('project')
        self._remember_project(path)
        self.statusBar().showMessage(self.tr('Opened {0}').format(path), 4000)

    def _last_location(self) -> str:
        """Give the directory to offer first in a project dialog.

        Returns
        -------
        str
            The directory of the most recently opened project, and an empty
            string when there is none, which leaves the choice to the dialog.
        """

        for path in self._recent_projects:
            parent = Path(path).parent
            if parent.is_dir():
                return str(parent)
        return ''

    def close_project(self) -> None:
        """Close the open project and put the chrome back to its empty state.

        The Project pane goes with the project it was opened for: it holds
        nothing else, so leaving it behind would leave an empty panel taking up
        the side of the window.
        """

        self._end_session()
        self._document_area.close_all_documents()

        self._project_name = ''
        self._top_bar.set_project_name(self.tr('No Project'))
        self.setWindowTitle(APPLICATION_NAME)
        self.close_project_action.setEnabled(False)
        self._update_menus_for_project()
        self._project_tree.clear()
        self.hide_pane('project')
        self.statusBar().showMessage(self.tr('Project closed'), 4000)

    def _remember_project(self, path: str) -> None:
        """Move a project to the head of the recent list and persist it.

        Parameters
        ----------
        path : str
            Directory of the project.
        """

        recent = [path] + [other for other in self._recent_projects if other != path]
        self._publish_recent_projects(recent[:MAX_RECENT_PROJECTS])

    def clear_recent_projects(self) -> None:
        """Forget every project in the history.

        Only the history goes; the projects themselves are untouched, which is
        why this is not worth a confirmation.
        """

        self._publish_recent_projects([])
        self._report(self.tr('The list of recent projects was cleared'))

    def _publish_recent_projects(self, paths: list[str]) -> None:
        """Store the recent project list and show it everywhere it appears.

        Storing it and showing it are one step, so that a history cannot be
        written and left unshown.

        Parameters
        ----------
        paths : list of str
            The history, most recent first.
        """

        self._recent_projects = paths
        self._settings.setValue('recent_projects', self._recent_projects)
        self._show_recent_projects()

    def _show_recent_projects(self) -> None:
        """Show the history in all three places it appears.

        The drop-down on the top bar, the *File → Open Recent* menu and the
        state of :attr:`clear_recent_projects_action` come from here, so they
        cannot disagree about what the history holds.  This runs when the
        window is built as well as whenever the history changes: the list is
        read back from the settings before either menu exists, so without it a
        stored history would reach the drop-down and never the menu.

        A project is shown by the name in its manifest rather than by its path,
        and projects whose files have gone are forgotten first, which is why
        start-up is the right moment for this as well.
        """

        self._forget_missing_projects()
        projects = project.labels_for(self._recent_projects)
        self.clear_recent_projects_action.setEnabled(bool(projects))
        self._top_bar.set_recent_projects(projects)
        self._rebuild_recent_menu(projects)

    def _end_session(self) -> None:
        """Close the editing session of the open project, if there is one.

        A session is a pair of entries rather than one written at the end, so
        that a run cut short by a crash still leaves its opening behind — an
        unclosed session is itself worth seeing.  The project's lock goes with
        the session, so closing one frees it for another window.
        """

        if self._project_path is None:
            return
        duration = int(time.monotonic() - self._session_started)
        self._record(self._project_path, project.EVENT_CLOSED, duration)
        project.release(self._project_path)
        self._project_path = None

    def _record(self, path: str, event: str, duration: int | None = None) -> None:
        """Add an entry to a project's history, saying so if it cannot be added.

        A history that cannot be written is not a reason to refuse to open a
        project — a project on a read-only medium still opens — but it is worth
        saying, because the record is the point.

        Parameters
        ----------
        path : str
            The project file.
        event : str
            What happened, one of the ``EVENT_*`` names of
            :mod:`masafi_simtwin.project`.
        duration : int, optional
            Seconds the session lasted, on a closing entry.
        """

        try:
            project.record(path, event, project.current_user(), install_id(), duration)
        except project.ProjectError:
            self._report(self.tr('The project history could not be written'))

    def closeEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Close the open project's session before the window goes.

        Parameters
        ----------
        event : PyQt6.QtGui.QCloseEvent
            The close event, always accepted.
        """

        self._end_session()
        super().closeEvent(event)

    def _forget_missing_projects(self) -> None:
        """Drop from the history the projects whose files have gone.

        Silently: a project deleted or moved outside the application is not
        something the user needs telling about, and an entry that cannot lead
        anywhere is worse than no entry.
        """

        existing = [path for path in self._recent_projects if Path(path).is_file()]
        if existing != self._recent_projects:
            self._recent_projects = existing
            self._settings.setValue('recent_projects', existing)

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

    def _rebuild_recent_menu(self, projects: list[tuple[str, str]]) -> None:
        """Mirror the recent project list into the *File → Open Recent* menu.

        The menu is the drop-down on the top bar without its *Open Project*
        entry, which *File* already carries directly above this submenu: the
        history, then a separator, then *Clear Recent Projects*.  The last entry
        is always there, disabled when there is nothing to clear, so that the
        menu keeps the same shape whatever the history holds.

        Parameters
        ----------
        projects : list of tuple of str
            The history as ``(label, path)`` pairs, most recent first.
        """

        self._recent_menu.clear()
        if not projects:
            empty = self._recent_menu.addAction(self.tr('No Recent Projects'))
            empty.setEnabled(False)
        else:
            for label, path in projects:
                action = self._recent_menu.addAction(label)
                action.setData(path)
                action.setToolTip(path)
                action.triggered.connect(
                    lambda _checked=False, selected=path: self.open_project_path(selected)
                )

        self._recent_menu.addSeparator()
        self._recent_menu.addAction(self.clear_recent_projects_action)

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------

    def new_model(self) -> None:
        """Ask what model to add to the open project, and add it."""

        if self._project_path is None:
            return
        dialog = ModelDialog(self, taken=self._model_names())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        model = self._change_models(
            lambda path: project.add_model(
                path,
                dialog.name,
                dialog.kind,
                dialog.units(),
                project.current_user(),
                install_id(),
            ),
            self.tr('The model could not be added'),
        )
        if model is not None:
            self.open_model(model['uuid'])

    def edit_model(self) -> None:
        """Change the name or the units of the model selected in the tree."""

        model = self._selected_model()
        if model is None or self._project_path is None:
            return
        dialog = ModelDialog(
            self,
            model=model,
            taken=[
                name for name in self._model_names() if name != model.get('name')
            ],
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        changed = self._change_models(
            lambda path: project.update_model(
                path,
                model['uuid'],
                dialog.name,
                dialog.units(),
                project.current_user(),
                install_id(),
            ),
            self.tr('The model could not be changed'),
        )
        if changed is not None:
            self._retitle_document(changed)

    def delete_model(self) -> None:
        """Remove the model selected in the tree, having asked first.

        Deleting is the one thing here that cannot be undone, so it is the one
        thing that asks.
        """

        model = self._selected_model()
        if model is None or self._project_path is None:
            return
        answer = QMessageBox.question(
            self,
            self.tr('Delete the model?'),
            self.tr('{0} and everything in it will be removed from the project.').format(
                model.get('name', '')
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        removed = self._change_models(
            lambda path: project.remove_model(
                path, model['uuid'], project.current_user(), install_id()
            ),
            self.tr('The model could not be removed'),
        )
        if removed is not None:
            self._document_area.close_document_for(removed['uuid'])

    def _change_models(self, change, failure: str) -> dict | None:
        """Apply a change to the project's models and show the result.

        Every change is written to the project as it is made — there is no save
        step — so a failure to write is the only thing that can go wrong, and it
        is reported rather than raised.

        Parameters
        ----------
        change : collections.abc.Callable
            What to do to the project, given its path.
        failure : str
            Translated sentence to show when it cannot be done.

        Returns
        -------
        dict, optional
            The model entry the change worked on, so that the caller can open,
            retitle or close its tab, and ``None`` when nothing was changed.
        """

        try:
            model = change(self._project_path)
        except project.ProjectError as error:
            QMessageBox.critical(self, failure, str(error))
            return None
        self._project_tree.set_models(project.models_of(self._project_path))
        return model

    def _model_names(self) -> list[str]:
        """List the names of the open project's models.

        Returns
        -------
        list of str
            The names, so that a dialog can refuse to reuse one.
        """

        if self._project_path is None:
            return []
        return [model.get('name', '') for model in project.models_of(self._project_path)]

    def _selected_model(self) -> dict | None:
        """Give the model the tree is on, if it is on one.

        Returns
        -------
        dict, optional
            Its entry in the manifest, or ``None`` when no model is selected.
        """

        return self._model(self._project_tree.model_of(self._project_tree.currentItem()))

    def _model(self, identifier: str | None) -> dict | None:
        """Find a model of the open project by its UUID.

        Parameters
        ----------
        identifier : str, optional
            The model's UUID.

        Returns
        -------
        dict, optional
            Its entry in the manifest, or ``None`` when the project holds no
            such model — which is what a tree left behind by a change made
            elsewhere would ask for.
        """

        if not identifier or self._project_path is None:
            return None
        return next(
            (
                model
                for model in project.models_of(self._project_path)
                if model.get('uuid') == identifier
            ),
            None,
        )

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    def open_model(self, identifier: str) -> None:
        """Open a model in the document area, or raise the tab it is already in.

        A model is one document however often it is asked for: opening it twice
        would be two views of one file, each unaware of the other's edits.  The
        tab is keyed by the model's UUID rather than by its name, so a model
        renamed while it is open keeps the tab it is in.

        Parameters
        ----------
        identifier : str
            The model's UUID.
        """

        if self._document_area.show_document(identifier):
            return

        model = self._model(identifier)
        if model is None:
            return

        editor = documents.editor_for(model)
        if editor is None:
            self._report(
                self.tr('{0} cannot be opened yet: that kind of model is not built.').format(
                    model.get('name', '')
                )
            )
            return

        self._document_area.add_document(
            editor,
            model.get('name', ''),
            key=identifier,
            tool_tip=model.get('file', ''),
        )

    def _retitle_document(self, model: dict) -> None:
        """Put a model's new name on its tab, if it is open.

        Parameters
        ----------
        model : dict
            The model's entry in the manifest, as it now stands.
        """

        self._document_area.set_document_title(
            model.get('uuid', ''), model.get('name', ''), model.get('file', '')
        )

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------

    def show_about(self) -> None:
        """Open the About dialog, modal over the window."""

        AboutDialog(self).exec()

    def show_settings(self) -> None:
        """Open the Settings dialog, and offer the restart it may have earned.

        The question comes after the dialog has closed, which is what the
        dialog told the user to expect when the preference was changed.
        """

        dialog = SettingsDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if needs_restart(dialog.written) and ask_to_restart(self):
            application = QApplication.instance()
            if application is not None:
                application.restart()

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

    def show_pane(self, key: str) -> None:
        """Open a tool pane if it is not open already.

        Parameters
        ----------
        key : str
            Identifier of the pane.
        """

        self._set_pane_open(key, True)

    def hide_pane(self, key: str) -> None:
        """Close a tool pane if it is open.

        Parameters
        ----------
        key : str
            Identifier of the pane.
        """

        self._set_pane_open(key, False)

    def _set_pane_open(self, key: str, open_: bool) -> None:
        """Open or close a tool pane.

        The stripe button is what is pressed rather than the pane shown or
        hidden, so that the button, the pane and the exclusivity of its group
        stay in step.  A button already in the wanted state is left alone, so
        that showing an open pane does not toggle it shut.

        Parameters
        ----------
        key : str
            Identifier of the pane.
        open_ : bool
            Whether the pane should end up open.
        """

        action = self._side_bar.pane_action(key)
        if action is not None and action.isChecked() != open_:
            action.setChecked(open_)

    def _report(self, message: str) -> None:
        """Say something in the status bar for a few seconds.

        Each caller passes a whole translated sentence rather than a noun to
        drop into one: a sentence built from a fragment cannot be translated
        into a language whose grammar does not agree with English's.

        Parameters
        ----------
        message : str
            The translated sentence to show.
        """

        self.statusBar().showMessage(message, 4000)

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
