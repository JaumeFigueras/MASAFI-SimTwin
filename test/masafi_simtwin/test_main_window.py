"""Tests for the assembly of the main window."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDockWidget

from masafi_simtwin import APPLICATION_NAME, project
from masafi_simtwin.main_window import MAX_RECENT_PROJECTS, MainWindow
from masafi_simtwin.top_bar import TopBar


@pytest.fixture
def make_project(tmp_path):
    """Give a maker of real project files.

    A project is a ``.mfstz`` archive now, and the window reads its manifest to
    learn what it is called, so the history cannot be exercised with names that
    are not files.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary directory pytest made.

    Returns
    -------
    collections.abc.Callable
        A function taking a name and returning the path of a project of that
        name, as a string.
    """

    def make(name: str) -> str:
        return str(project.create(project.path_for(tmp_path, name), name))

    return make


@pytest.fixture
def window(qtbot):
    """Build the main window.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    masafi_simtwin.main_window.MainWindow
        A window with no project open.
    """

    main_window = MainWindow()
    qtbot.addWidget(main_window)
    return main_window


def test_top_bar_occupies_the_menu_widget_slot(window):
    """The top bar runs the full width where the menu bar would normally sit."""

    assert isinstance(window.menuWidget(), TopBar)
    assert window.menuWidget() is window.top_bar


def test_side_bar_is_in_the_left_toolbar_area(window):
    """The tool stripe is a left toolbar, which leaves the dock area free."""

    assert window.toolBarArea(window.side_bar) == Qt.ToolBarArea.LeftToolBarArea
    assert not window.side_bar.isMovable()


def test_side_bar_carries_the_four_panes(window):
    """Project and libraries sit at the top, the console and problems at the bottom."""

    actions = window.side_bar.actions()
    spacer = actions.index(window.side_bar._spacer_action)
    positions = {
        key: actions.index(window.side_bar.pane_action(key))
        for key in ('project', 'libraries', 'python', 'problems')
    }

    assert positions['project'] < positions['libraries'] < spacer
    assert spacer < positions['python'] < positions['problems']


def test_document_area_is_central(window):
    """The documents fill the centre of the window."""

    assert window.centralWidget() is window.document_area


def test_status_bar_is_present(window):
    """The window closes with a status bar showing the ready message."""

    assert window.statusBar() is not None
    assert window.statusBar().currentMessage() == 'Ready'


def test_menu_bar_has_the_classic_menus(window):
    """The hamburger hides a classic File, Edit, View… menu bar."""

    titles = [action.text() for action in window.top_bar._menu_bar.actions()]

    assert titles == ['&File', '&Edit', '&View', '&Navigate', '&Run', '&Tools', '&Window', '&Help']


def test_only_file_and_help_are_shown_without_a_project(window):
    """With nothing open there is nothing to edit, view, navigate or run."""

    titles = [
        action.text() for action in window.top_bar._menu_bar.actions() if action.isVisible()
    ]

    assert titles == ['&File', '&Help']


def test_the_other_menus_follow_the_open_project(window, make_project):
    """The rest of the menu bar appears with a project and leaves with it."""

    window.open_project_path(make_project('Bottling Line'))
    opened = [
        action.text() for action in window.top_bar._menu_bar.actions() if action.isVisible()
    ]

    window.close_project()
    closed = [
        action.text() for action in window.top_bar._menu_bar.actions() if action.isVisible()
    ]

    assert opened == ['&File', '&Edit', '&View', '&Navigate', '&Run', '&Tools', '&Window', '&Help']
    assert closed == ['&File', '&Help']


def test_the_file_menu_opens_with_new_open_and_recent(window):
    """*File* leads with the three ways into a project, then close and exit."""

    file_menu = window.top_bar._menu_bar.actions()[0].menu()
    entries = [action for action in file_menu.actions() if not action.isSeparator()]

    assert entries[0] is window.new_project_action
    assert entries[1] is window.open_project_action
    assert entries[2] is window._recent_menu.menuAction()
    assert entries[3] is window.close_project_action
    assert entries[4] is window.quit_action
    assert not window.close_project_action.isEnabled()


def test_simulation_controls_are_shared_with_the_run_menu(window):
    """The top bar buttons and the Run menu are two views of the same actions."""

    run_menu = window.top_bar._menu_bar.actions()[4].menu()
    entries = [action for action in run_menu.actions() if not action.isSeparator()]

    assert entries == [
        window.run_action,
        window.stop_action,
        window.fast_forward_action,
        window.reset_action,
    ]
    for action in entries:
        assert not action.icon().isNull()


def test_running_updates_the_status_bar(window):
    """A simulation control reports the state it asked for."""

    window.run_action.trigger()

    assert window._state_label.text() == 'Running'
    assert window.statusBar().currentMessage() == 'Running'


def test_opening_a_project_updates_the_chrome(window, make_project):
    """Opening a project names it on the button, in the title and in the history.

    The name comes out of the manifest rather than off the file name, which is
    what makes a renamed file still show the project it holds.
    """

    path = make_project('Bottling Line')
    window.open_project_path(path)

    assert window.top_bar._project_button.text() == 'Bottling Line'
    assert window.windowTitle() == f'Bottling Line — {APPLICATION_NAME}'
    assert window.close_project_action.isEnabled()
    assert window._recent_projects[0] == path


def test_closing_a_project_restores_the_empty_chrome(window, make_project):
    """Closing the project puts the button and the title back."""

    window.open_project_path(make_project('Bottling Line'))
    window.close_project()

    assert window.top_bar._project_button.text() == 'No Project'
    assert window.windowTitle() == APPLICATION_NAME
    assert not window.close_project_action.isEnabled()


def test_reopening_a_project_moves_it_to_the_head(window, make_project):
    """A project opened again rises to the top of the history without duplicating."""

    one, two = make_project('One'), make_project('Two')
    window.open_project_path(one)
    window.open_project_path(two)
    window.open_project_path(one)

    assert window._recent_projects == [one, two]


def test_history_is_capped(window, make_project):
    """The history keeps only the most recent projects."""

    last = ''
    for number in range(MAX_RECENT_PROJECTS + 5):
        last = make_project(f'Project {number}')
        window.open_project_path(last)

    assert len(window._recent_projects) == MAX_RECENT_PROJECTS
    assert window._recent_projects[0] == last




# ----------------------------------------------------------------------------
# Tool panes
# ----------------------------------------------------------------------------

LEFT = Qt.DockWidgetArea.LeftDockWidgetArea
BOTTOM = Qt.DockWidgetArea.BottomDockWidgetArea

PANES = [
    ('project', 'Project', LEFT),
    ('libraries', 'Libraries', LEFT),
    ('python', 'Python Console', BOTTOM),
    ('problems', 'Problems', BOTTOM),
]

GROUPS = [('project', 'libraries'), ('python', 'problems')]

PAIRS = [pair for first, second in GROUPS for pair in ((first, second), (second, first))]


@pytest.fixture
def shown_window(window, qtbot):
    """Show the window, so that the panes report their visibility and geometry for real.

    Parameters
    ----------
    window : masafi_simtwin.main_window.MainWindow
        The window under test.
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    masafi_simtwin.main_window.MainWindow
        The same window, on screen.
    """

    window.show()
    qtbot.waitExposed(window)
    return window


def test_panes_start_closed(shown_window):
    """No pane is open before a stripe button is pressed."""

    for key, _title, _area in PANES:
        assert not shown_window.tool_pane(key).isVisible()
        assert not shown_window.side_bar.pane_action(key).isChecked()


@pytest.mark.parametrize(('key', 'title', 'area'), PANES)
def test_a_button_opens_its_pane(shown_window, key, title, area):
    """Pressing a stripe button opens the pane it stands for, under its title."""

    shown_window.side_bar.pane_action(key).setChecked(True)
    pane = shown_window.tool_pane(key)

    assert pane.isVisible()
    assert pane.title == title
    assert shown_window.dockWidgetArea(pane) == area


@pytest.mark.parametrize('key', [key for key, _title, _area in PANES])
def test_pressing_the_button_again_closes_the_pane(shown_window, key):
    """The button of the pane already open closes it and leaves nothing pressed."""

    action = shown_window.side_bar.pane_action(key)
    action.setChecked(True)
    action.trigger()

    assert not shown_window.tool_pane(key).isVisible()
    assert not action.isChecked()


@pytest.mark.parametrize(('opened', 'other'), PAIRS)
def test_the_panes_of_a_group_replace_each_other(shown_window, opened, other):
    """Opening one pane closes the other of its group, in either direction."""

    shown_window.side_bar.pane_action(opened).setChecked(True)
    shown_window.side_bar.pane_action(other).setChecked(True)

    assert shown_window.tool_pane(other).isVisible()
    assert not shown_window.tool_pane(opened).isVisible()
    assert shown_window.side_bar.pane_action(other).isChecked()
    assert not shown_window.side_bar.pane_action(opened).isChecked()


def test_the_two_groups_open_together(shown_window):
    """A pane at the side and one at the bottom are open at the same time."""

    shown_window.side_bar.pane_action('project').setChecked(True)
    shown_window.side_bar.pane_action('problems').setChecked(True)

    assert shown_window.tool_pane('project').isVisible()
    assert shown_window.tool_pane('problems').isVisible()


def test_the_bottom_pane_runs_under_the_side_pane(shown_window):
    """The bottom pane takes the whole width and shortens the pane at the side."""

    shown_window.side_bar.pane_action('project').setChecked(True)
    project = shown_window.tool_pane('project')
    tall = project.height()

    shown_window.side_bar.pane_action('python').setChecked(True)
    python = shown_window.tool_pane('python')

    assert python.x() <= project.x()
    assert python.width() > project.width()
    assert project.height() < tall
    assert project.geometry().bottom() <= python.y()


@pytest.mark.parametrize('corner', [Qt.Corner.BottomLeftCorner, Qt.Corner.BottomRightCorner])
def test_the_bottom_corners_belong_to_the_bottom_area(window, corner):
    """The corner assignment is what lets the bottom pane span the window."""

    assert window.corner(corner) == Qt.DockWidgetArea.BottomDockWidgetArea


@pytest.mark.parametrize('key', [key for key, _title, _area in PANES])
def test_closing_a_pane_releases_its_button(shown_window, key):
    """A pane closed from its own header lets the stripe button go."""

    shown_window.side_bar.pane_action(key).setChecked(True)
    shown_window.tool_pane(key).close()

    assert not shown_window.side_bar.pane_action(key).isChecked()


@pytest.mark.parametrize('key', [key for key, _title, _area in PANES])
def test_panes_cannot_be_torn_off(shown_window, key):
    """A pane can be closed and resized, but not dragged out into a window."""

    features = shown_window.tool_pane(key).features()

    assert features == QDockWidget.DockWidgetFeature.DockWidgetClosable


def test_the_about_action_opens_the_about_dialog(window, monkeypatch):
    """The action builds the dialog over the window instead of writing a message.

    The dialog is modal, so it is stubbed rather than executed: what is worth
    asserting is that the action reaches it and parents it on the window.
    """

    opened = []

    class StubAboutDialog:
        def __init__(self, parent=None):
            opened.append(parent)

        def exec(self):
            return 0

    monkeypatch.setattr('masafi_simtwin.main_window.AboutDialog', StubAboutDialog)
    window.about_action.trigger()
    assert opened == [window]


def stub_settings(monkeypatch, result, written=()):
    """Put a settings dialog that neither draws nor blocks in the window's way.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The patcher.
    result : int
        What ``exec`` should return, an accepted or a rejected dialog.
    written : tuple of str, optional
        The keys the stub claims to have written.

    Returns
    -------
    list
        The parents the dialog was built with, one entry per opening.
    """

    opened = []

    class StubSettingsDialog:
        def __init__(self, parent=None):
            opened.append(parent)
            self.written = written

        def exec(self):
            return result

    monkeypatch.setattr('masafi_simtwin.main_window.SettingsDialog', StubSettingsDialog)
    return opened


def stub_restart(monkeypatch, answer):
    """Answer the restart question without asking it.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The patcher.
    answer : bool
        What the user is to be taken to have answered.

    Returns
    -------
    list
        The parents the question was asked with, one entry per asking.
    """

    asked = []

    def ask(parent=None):
        asked.append(parent)
        return answer

    monkeypatch.setattr('masafi_simtwin.main_window.ask_to_restart', ask)
    return asked


def test_the_settings_action_opens_the_settings_dialog(window, monkeypatch):
    """The action reaches the dialog instead of writing a message.

    The dialog is modal, so it is stubbed rather than executed, as the About
    one is.
    """

    opened = stub_settings(monkeypatch, QDialog.DialogCode.Rejected)
    window.settings_action.trigger()
    assert opened == [window]


def test_a_cancelled_settings_dialog_asks_nothing(window, monkeypatch):
    """Nothing was written, so there is nothing to restart for."""

    stub_settings(monkeypatch, QDialog.DialogCode.Rejected, ('appearance/theme',))
    asked = stub_restart(monkeypatch, False)
    window.settings_action.trigger()
    assert asked == []


def test_a_setting_that_takes_effect_at_once_asks_nothing(window, monkeypatch):
    """Only the preferences declared as needing a restart raise the question."""

    stub_settings(monkeypatch, QDialog.DialogCode.Accepted, ('units/time',))
    asked = stub_restart(monkeypatch, False)
    window.settings_action.trigger()
    assert asked == []


def test_a_setting_that_needs_a_restart_asks_after_the_dialog_closes(window, monkeypatch):
    """The question the dialog told the user to expect."""

    stub_settings(monkeypatch, QDialog.DialogCode.Accepted, ('appearance/theme',))
    asked = stub_restart(monkeypatch, False)
    window.settings_action.trigger()
    assert asked == [window]


def test_answering_later_leaves_the_application_running(window, monkeypatch, qapp):
    """Later means later: the settings are stored, nothing else happens."""

    stub_settings(monkeypatch, QDialog.DialogCode.Accepted, ('appearance/theme',))
    stub_restart(monkeypatch, False)
    restarted = []
    monkeypatch.setattr(type(qapp), 'restart', lambda self: restarted.append(self))

    window.settings_action.trigger()
    assert restarted == []


def test_answering_now_restarts_the_application(window, monkeypatch, qapp):
    """Now means the application starts again."""

    stub_settings(monkeypatch, QDialog.DialogCode.Accepted, ('appearance/theme',))
    stub_restart(monkeypatch, True)
    restarted = []
    monkeypatch.setattr(type(qapp), 'restart', lambda self: restarted.append(self))

    window.settings_action.trigger()
    assert restarted == [qapp]


# ----------------------------------------------------------------------
# Creating a project
# ----------------------------------------------------------------------


def stub_new_project(monkeypatch, result, path=None, name='Bottling Line'):
    """Put a New Project dialog that neither draws nor blocks in the window's way.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The patcher.
    result : int
        What ``exec`` should return.
    path : pathlib.Path, optional
        The path the dialog settles on.
    name : str, optional
        The name it was given.

    Returns
    -------
    list
        The locations the dialog was opened at, one entry per opening.
    """

    opened = []

    class StubNewProjectDialog:
        def __init__(self, parent=None, location=None):
            opened.append(location)
            self.project_path = path
            self.name = name

        def exec(self):
            return result

    monkeypatch.setattr('masafi_simtwin.main_window.NewProjectDialog', StubNewProjectDialog)
    return opened


def test_the_new_project_action_writes_and_opens_the_project(window, monkeypatch, tmp_path):
    """The whole way from the menu entry to a project on disk."""

    target = project.path_for(tmp_path, 'Bottling Line')
    stub_new_project(monkeypatch, QDialog.DialogCode.Accepted, target)

    window.new_project_action.trigger()

    assert target.exists()
    assert project.name_of(target) == 'Bottling Line'
    assert window.windowTitle() == f'Bottling Line — {APPLICATION_NAME}'
    assert window._recent_projects[0] == str(target)


def test_a_cancelled_new_project_writes_nothing(window, monkeypatch, tmp_path):
    """Nothing is created until the dialog is accepted."""

    target = project.path_for(tmp_path, 'Bottling Line')
    stub_new_project(monkeypatch, QDialog.DialogCode.Rejected, target)

    window.new_project_action.trigger()

    assert not target.exists()
    assert window.windowTitle() == APPLICATION_NAME


def test_a_project_that_cannot_be_written_is_reported(window, monkeypatch, tmp_path):
    """The failure reaches the user rather than the traceback."""

    target = tmp_path / 'nowhere' / f'Bottling Line{project.PROJECT_SUFFIX}'
    stub_new_project(monkeypatch, QDialog.DialogCode.Accepted, target)
    shown = []
    monkeypatch.setattr(
        'masafi_simtwin.main_window.QMessageBox.critical',
        lambda parent, title, text: shown.append((title, text)),
    )

    window.new_project_action.trigger()

    assert len(shown) == 1
    assert window.windowTitle() == APPLICATION_NAME


def test_a_file_that_is_not_a_project_is_reported(window, monkeypatch, tmp_path):
    """A stale entry in the recent list, or the wrong file chosen by hand."""

    path = tmp_path / f'not-a-project{project.PROJECT_SUFFIX}'
    path.write_bytes(b'hello')
    shown = []
    monkeypatch.setattr(
        'masafi_simtwin.main_window.QMessageBox.critical',
        lambda parent, title, text: shown.append((title, text)),
    )

    window.open_project_path(str(path))

    assert len(shown) == 1
    assert window.windowTitle() == APPLICATION_NAME
    assert window._recent_projects == []


def test_a_new_project_is_offered_beside_the_last_one(window, monkeypatch, make_project):
    """The dialog opens where the user was working, not in their documents."""

    opened_project = make_project('Earlier')
    window.open_project_path(opened_project)

    opened = stub_new_project(monkeypatch, QDialog.DialogCode.Rejected)
    window.new_project_action.trigger()

    assert opened == [str(Path(opened_project).parent)]
