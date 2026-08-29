"""Tests for the assembly of the main window."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QSizeF, Qt
from PyQt6.QtWidgets import QDialog, QDockWidget, QMessageBox, QTabBar

from masafi_simtwin import APPLICATION_NAME, paper, project
from masafi_simtwin.documents import PetriNetEditor
from masafi_simtwin.main_window import MAX_RECENT_PROJECTS, MainWindow
from masafi_simtwin.preferences import install_id
from masafi_simtwin.project_tree import NodeKind
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

    assert titles == ['&File', '&Edit', '&View', '&Project', '&Window', '&Help']


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

    assert opened == ['&File', '&Edit', '&View', '&Project', '&Window', '&Help']
    assert closed == ['&File', '&Help']


def test_the_file_menu_opens_with_new_open_and_recent(window):
    """*File* leads with the three ways into a project, then close and exit."""

    file_menu = window.top_bar._menu_bar.actions()[0].menu()
    entries = [action for action in file_menu.actions() if not action.isSeparator()]

    assert entries[0] is window.new_project_action
    assert entries[1] is window.open_project_action
    assert entries[2] is window._recent_menu.menuAction()
    assert entries[3] is window.close_project_action
    assert entries[4] is window.settings_action
    assert entries[5] is window.quit_action
    assert not window.close_project_action.isEnabled()


def test_the_simulation_controls_live_on_the_top_bar_alone(window):
    """There is no *Run* menu while there is no run control behind it.

    The actions are still the window's own and still carry their icons, so they
    are ready for whatever menu they end up in.
    """

    titles = [action.text() for action in window.top_bar._menu_bar.actions()]
    assert '&Run' not in titles

    for action in (
        window.run_action,
        window.stop_action,
        window.fast_forward_action,
        window.reset_action,
    ):
        assert not action.icon().isNull()


def test_the_project_menu_offers_what_can_be_done_to_a_project(window, make_project):
    """*New Model*, *New Simulation*, a separator, and the project's settings."""

    window.open_project_path(make_project('Bottling Line'))
    project_menu = window.top_bar._menu_bar.actions()[3].menu()

    assert project_menu.title() == '&Project'
    assert project_menu.actions() == [
        window.new_model_action,
        window.new_simulation_action,
        project_menu.actions()[2],
        window.project_settings_action,
    ]
    assert project_menu.actions()[2].isSeparator()


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


# ----------------------------------------------------------------------
# The project pane
# ----------------------------------------------------------------------


def test_opening_a_project_shows_the_project_pane(window, make_project, qtbot):
    """The pane comes out with the project, whether or not it was open."""

    window.show()
    qtbot.waitExposed(window)
    assert not window.tool_pane('project').isVisible()

    window.open_project_path(make_project('Bottling Line'))

    assert window.tool_pane('project').isVisible()
    assert window._side_bar.pane_action('project').isChecked()


def test_a_pane_already_open_is_left_alone(window, make_project, qtbot):
    """Showing an open pane must not toggle it shut."""

    window.show()
    qtbot.waitExposed(window)
    window.show_pane('project')
    window.open_project_path(make_project('Bottling Line'))

    assert window.tool_pane('project').isVisible()


def test_the_pane_holds_the_tree_of_the_open_project(window, make_project):
    """The name of the project is the root, with its three parts under it."""

    window.open_project_path(make_project('Bottling Line'))
    root = window._project_tree.root()

    assert root.text(0) == 'Bottling Line'
    assert [root.child(i).text(0) for i in range(root.childCount())] == [
        'Models',
        'Simulations',
        'Statistics',
    ]


def test_closing_a_project_empties_the_tree(window, make_project):
    """There is no project, so there is nothing for the tree to show."""

    window.open_project_path(make_project('Bottling Line'))
    window.close_project()

    assert window._project_tree.topLevelItemCount() == 0
    assert window._project_tree.root() is None


def test_closing_a_project_closes_the_project_pane(window, make_project, qtbot):
    """The pane holds nothing but the project, so it goes with it."""

    window.show()
    qtbot.waitExposed(window)
    window.open_project_path(make_project('Bottling Line'))
    assert window.tool_pane('project').isVisible()

    window.close_project()

    assert not window.tool_pane('project').isVisible()
    assert not window._side_bar.pane_action('project').isChecked()


def test_closing_a_project_leaves_the_other_panes_alone(window, make_project, qtbot):
    """Only the Project pane is tied to the project."""

    window.show()
    qtbot.waitExposed(window)
    window.open_project_path(make_project('Bottling Line'))
    window.show_pane('python')

    window.close_project()

    assert window.tool_pane('python').isVisible()


def test_closing_a_pane_that_is_already_closed_does_nothing(window, qtbot):
    """Hiding a closed pane must not toggle it open."""

    window.show()
    qtbot.waitExposed(window)
    window.hide_pane('project')

    assert not window.tool_pane('project').isVisible()


def test_the_tree_and_the_project_menu_offer_the_same_actions(window, make_project):
    """Which is the point of `project_entries`: one list, two views."""

    window.open_project_path(make_project('Bottling Line'))
    tree = window._project_tree
    menu = tree.menu_for(tree.root())

    assert [action for action in menu.actions() if not action.isSeparator()] == [
        window.new_model_action,
        window.new_simulation_action,
        window.project_settings_action,
    ]


@pytest.mark.parametrize(
    ('kind', 'expected'),
    [
        (NodeKind.MODELS, 'new_model_action'),
        (NodeKind.SIMULATIONS, 'new_simulation_action'),
    ],
)
def test_a_branch_offers_only_what_can_be_added_to_it(window, make_project, kind, expected):
    """One entry each, and it is the window's own action."""

    window.open_project_path(make_project('Bottling Line'))
    tree = window._project_tree
    menu = tree.menu_for(tree.node(kind))

    assert menu.actions() == [getattr(window, expected)]


def test_the_statistics_branch_offers_nothing(window, make_project):
    """Nothing is added to it by hand."""

    window.open_project_path(make_project('Bottling Line'))
    tree = window._project_tree

    assert tree.menu_for(tree.node(NodeKind.STATISTICS)) is None


@pytest.mark.parametrize('action', ['new_simulation_action', 'project_settings_action'])
def test_the_project_actions_say_they_are_not_written_yet(window, action):
    """They are wired and reachable; what they will do is the next step."""

    getattr(window, action).trigger()

    assert 'not implemented yet' in window.statusBar().currentMessage()


def test_adding_a_model_needs_a_project(window):
    """The action is only reachable with one open, but it says so anyway."""

    window.new_model_action.trigger()

    assert window._project_path is None


# ----------------------------------------------------------------------
# Clearing the history
# ----------------------------------------------------------------------


def drop_down(window):
    """List what the project drop-down of the top bar offers.

    Parameters
    ----------
    window : masafi_simtwin.main_window.MainWindow
        The window.

    Returns
    -------
    list of str
        The titles, with ``'---'`` for a separator.
    """

    return [
        '---' if action.isSeparator() else action.text()
        for action in window.top_bar._project_button.menu().actions()
    ]


def open_recent(window):
    """List what *File → Open Recent* offers.

    Parameters
    ----------
    window : masafi_simtwin.main_window.MainWindow
        The window.

    Returns
    -------
    list of str
        The titles, with ``'---'`` for a separator.
    """

    return [
        '---' if action.isSeparator() else action.text()
        for action in window._recent_menu.actions()
    ]


def test_the_drop_down_ends_with_a_separator_and_the_clear_entry(window, make_project):
    """Below *Open Project*, the history, then the way to be rid of it."""

    window.open_project_path(make_project('Bottling Line'))
    entries = drop_down(window)

    assert entries[0] == window.open_project_action.text()
    assert entries[1] == '---'
    assert entries[-2] == '---'
    assert entries[-1] == window.clear_recent_projects_action.text()


def test_the_clear_entry_is_the_windows_own_action(window):
    """Not a copy, so it is the same entry wherever it is put."""

    menu = window.top_bar._project_button.menu()

    assert menu.actions()[-1] is window.clear_recent_projects_action


def test_the_drop_down_keeps_its_shape_with_no_history(window):
    """The entry is always there, disabled when there is nothing to clear."""

    assert drop_down(window) == [
        window.open_project_action.text(),
        '---',
        'No Recent Projects',
        '---',
        window.clear_recent_projects_action.text(),
    ]
    assert not window.clear_recent_projects_action.isEnabled()


def test_the_clear_entry_comes_alive_with_the_first_project(window, make_project):
    """There is something to clear only once something has been opened."""

    assert not window.clear_recent_projects_action.isEnabled()
    window.open_project_path(make_project('Bottling Line'))
    assert window.clear_recent_projects_action.isEnabled()


def test_clearing_empties_the_history_everywhere_at_once(window, make_project):
    """The drop-down, the *File* menu and the stored list all follow."""

    window.open_project_path(make_project('One'))
    window.open_project_path(make_project('Two'))

    window.clear_recent_projects_action.trigger()

    assert window._recent_projects == []
    assert 'No Recent Projects' in drop_down(window)
    assert open_recent(window) == [
        'No Recent Projects',
        '---',
        window.clear_recent_projects_action.text(),
    ]
    assert not window.clear_recent_projects_action.isEnabled()


def test_clearing_survives_a_new_window(window, make_project, qtbot):
    """The history is stored, so forgetting it has to be stored too."""

    window.open_project_path(make_project('Bottling Line'))
    window.clear_recent_projects_action.trigger()

    reopened = MainWindow()
    qtbot.addWidget(reopened)

    assert reopened._recent_projects == []
    assert not reopened.clear_recent_projects_action.isEnabled()


def test_clearing_leaves_the_open_project_alone(window, make_project):
    """Only the history goes; the project stays open and its file untouched."""

    path = make_project('Bottling Line')
    window.open_project_path(path)
    window.clear_recent_projects_action.trigger()

    assert window.windowTitle() == f'Bottling Line — {APPLICATION_NAME}'
    assert Path(path).exists()
    assert window.close_project_action.isEnabled()


def test_clearing_says_so(window, make_project):
    """A menu entry that appears to do nothing has to report that it did."""

    window.open_project_path(make_project('Bottling Line'))
    window.clear_recent_projects_action.trigger()

    assert 'cleared' in window.statusBar().currentMessage()


def test_open_recent_lists_the_history_then_the_way_to_be_rid_of_it(window, make_project):
    """*File → Open Recent* is the drop-down without its *Open Project* entry."""

    window.open_project_path(make_project('One'))
    window.open_project_path(make_project('Two'))

    assert open_recent(window) == [
        'Two',
        'One',
        '---',
        window.clear_recent_projects_action.text(),
    ]


def test_open_recent_holds_the_same_clear_action_as_the_drop_down(window):
    """One action in two menus, so it can never be enabled in only one of them."""

    from_menu = window._recent_menu.actions()[-1]
    from_bar = window.top_bar._project_button.menu().actions()[-1]

    assert from_menu is window.clear_recent_projects_action
    assert from_bar is window.clear_recent_projects_action


def test_open_recent_keeps_its_shape_with_no_history(window):
    """The placeholder, a separator, and the disabled way to clear nothing."""

    assert open_recent(window) == [
        'No Recent Projects',
        '---',
        window.clear_recent_projects_action.text(),
    ]


def test_clearing_from_open_recent_works_as_from_the_drop_down(window, make_project):
    """It is the same action, so it had better."""

    window.open_project_path(make_project('Bottling Line'))
    window._recent_menu.actions()[-1].trigger()

    assert window._recent_projects == []


def test_a_stored_history_reaches_both_menus_when_the_window_opens(window, make_project, qtbot):
    """The list is read back before either menu exists, so it has to be pushed.

    A window built with a history showed it in the drop-down but left the
    *File* submenu empty until the next project was opened.
    """

    path = make_project('Bottling Line')
    window.open_project_path(path)

    reopened = MainWindow()
    qtbot.addWidget(reopened)

    assert reopened._recent_projects == [path]
    assert open_recent(reopened) == [
        'Bottling Line',
        '---',
        reopened.clear_recent_projects_action.text(),
    ]
    assert reopened.clear_recent_projects_action.isEnabled()


# ----------------------------------------------------------------------
# How the history is shown
# ----------------------------------------------------------------------


def test_a_project_is_listed_by_its_manifest_name(window, make_project):
    """Not by its path, in either menu."""

    path = make_project('Bottling Line')
    window.open_project_path(path)

    assert open_recent(window)[0] == 'Bottling Line'
    assert drop_down(window)[2] == 'Bottling Line'


def test_a_renamed_file_keeps_the_name_of_the_project_inside_it(window, make_project):
    """Which is what reading the manifest buys."""

    path = Path(make_project('Bottling Line'))
    renamed = path.with_name(f'moved{project.PROJECT_SUFFIX}')
    path.rename(renamed)
    window.open_project_path(str(renamed))

    assert open_recent(window)[0] == 'Bottling Line'


def test_projects_sharing_a_name_are_told_apart_by_their_path(window, tmp_path):
    """In both menus, and only the ones that clash."""

    here, there = tmp_path / 'here', tmp_path / 'there'
    here.mkdir()
    there.mkdir()
    first = str(project.create(project.path_for(here, 'Line'), 'Line'))
    second = str(project.create(project.path_for(there, 'Line'), 'Line'))
    other = str(project.create(project.path_for(here, 'Other'), 'Other'))

    for path in (first, second, other):
        window.open_project_path(path)

    assert open_recent(window)[:3] == [
        'Other',
        f'Line ({second})',
        f'Line ({first})',
    ]
    assert drop_down(window)[2:5] == open_recent(window)[:3]


def test_the_entry_carries_the_path_it_opens(window, make_project):
    """The label is a name now, so the path has to be kept on the entry."""

    path = make_project('Bottling Line')
    window.open_project_path(path)
    entry = window._recent_menu.actions()[0]

    assert entry.data() == path
    assert entry.toolTip() == path


def test_a_recent_entry_still_opens_its_project(window, make_project):
    """The name shown must not get in the way of what the entry does."""

    first = make_project('One')
    window.open_project_path(first)
    window.open_project_path(make_project('Two'))

    window._recent_menu.actions()[1].trigger()

    assert window.windowTitle() == f'One — {APPLICATION_NAME}'


# ----------------------------------------------------------------------
# Projects that have gone
# ----------------------------------------------------------------------


def test_a_deleted_project_is_forgotten_silently(window, make_project, qtbot):
    """Deleted outside the application, so nothing is worth reporting."""

    gone = make_project('Gone')
    kept = make_project('Kept')
    window.open_project_path(gone)
    window.open_project_path(kept)
    Path(gone).unlink()

    reopened = MainWindow()
    qtbot.addWidget(reopened)

    assert reopened._recent_projects == [kept]
    assert open_recent(reopened)[0] == 'Kept'
    assert reopened.statusBar().currentMessage() == 'Ready'


def test_forgetting_a_project_is_stored(window, make_project, qtbot):
    """Otherwise it would come back on the next start-up."""

    gone = make_project('Gone')
    window.open_project_path(gone)
    Path(gone).unlink()

    MainWindow().close()
    reopened = MainWindow()
    qtbot.addWidget(reopened)

    assert reopened._recent_projects == []


def test_a_history_of_nothing_but_missing_projects_empties(window, make_project, qtbot):
    """And the clear entry goes back to being disabled."""

    for name in ('One', 'Two'):
        path = make_project(name)
        window.open_project_path(path)
        Path(path).unlink()

    reopened = MainWindow()
    qtbot.addWidget(reopened)

    assert reopened._recent_projects == []
    assert not reopened.clear_recent_projects_action.isEnabled()
    assert open_recent(reopened)[0] == 'No Recent Projects'


def test_a_broken_project_keeps_its_place(window, tmp_path, qtbot):
    """It is there, so it is not missing; it is shown under its file name."""

    broken = tmp_path / f'broken{project.PROJECT_SUFFIX}'
    broken.write_bytes(b'not a zip')
    window._publish_recent_projects([str(broken)])

    assert window._recent_projects == [str(broken)]
    assert open_recent(window)[0] == 'broken'


# ----------------------------------------------------------------------
# The editing sessions a project records
# ----------------------------------------------------------------------


def events(path):
    """List the events of a project's history.

    Parameters
    ----------
    path : str
        The project file.

    Returns
    -------
    list of str
        The event names, oldest first.
    """

    return [entry['event'] for entry in project.read_manifest(path)['history']]


def test_opening_a_project_records_a_session(window, make_project):
    """A session opens when the project does."""

    path = make_project('Bottling Line')
    window.open_project_path(path)

    assert events(path) == [project.EVENT_CREATED, project.EVENT_OPENED]


def test_closing_a_project_closes_its_session(window, make_project):
    """With a duration, which is what makes the shape of a history readable."""

    path = make_project('Bottling Line')
    window.open_project_path(path)
    window.close_project()

    assert events(path) == [
        project.EVENT_CREATED,
        project.EVENT_OPENED,
        project.EVENT_CLOSED,
    ]
    assert 'duration' in project.read_manifest(path)['history'][-1]


def test_opening_another_project_closes_the_first_session(window, make_project):
    """A window shows one project, so it is in one session at a time."""

    first = make_project('One')
    window.open_project_path(first)
    window.open_project_path(make_project('Two'))

    assert events(first)[-1] == project.EVENT_CLOSED


def test_closing_the_window_closes_the_session(window, make_project):
    """Quitting is a way of ending a session like any other."""

    path = make_project('Bottling Line')
    window.open_project_path(path)
    window.close()

    assert events(path)[-1] == project.EVENT_CLOSED


def test_the_history_is_chained_across_sessions(window, make_project):
    """The window writes through the same chaining as everything else."""

    path = make_project('Bottling Line')
    window.open_project_path(path)
    window.close_project()

    entries = project.read_manifest(path)['history']
    assert [entry['previous'] for entry in entries[1:]] == [
        entry['log_item_id'] for entry in entries[:-1]
    ]


def test_the_installation_is_recorded_with_every_session(window, make_project):
    """Two projects edited on one machine can be seen to have been."""

    path = make_project('Bottling Line')
    window.open_project_path(path)

    assert project.read_manifest(path)['history'][-1]['install'] == install_id()


def test_a_history_that_cannot_be_written_does_not_stop_the_project_opening(
    window, make_project, monkeypatch
):
    """A project on a read-only medium still opens; it says the record failed."""

    path = make_project('Bottling Line')
    monkeypatch.setattr(
        'masafi_simtwin.project.record',
        lambda *arguments, **keywords: (_ for _ in ()).throw(
            project.ProjectError('read only')
        ),
    )

    window.open_project_path(path)

    assert window.windowTitle() == f'Bottling Line — {APPLICATION_NAME}'
    assert 'history' in window.statusBar().currentMessage()


# ----------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------


def stub_model_dialog(monkeypatch, result, name='Filling Station',
                      kind=None, units=None):
    """Put a model dialog that neither draws nor blocks in the window's way.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The patcher.
    result : int
        What ``exec`` should return.
    name : str, optional
        The name the dialog settles on.
    kind : masafi_simtwin.project.ModelKind, optional
        The kind it settles on, a Petri net by default.
    units : dict, optional
        The units it settles on.

    Returns
    -------
    list
        The models the dialog was opened over, ``None`` for a new one.
    """

    opened = []

    class StubModelDialog:
        def __init__(self, parent=None, preferences=None, model=None, taken=None):
            opened.append(model)
            self.name = name
            self.kind = kind or project.ModelKind.PETRI_NET
            self._units = units or {'time': 's'}

        def units(self):
            return self._units

        def exec(self):
            return result

    monkeypatch.setattr('masafi_simtwin.main_window.ModelDialog', StubModelDialog)
    return opened


@pytest.fixture
def opened(window, make_project):
    """Open a project and give its path.

    Parameters
    ----------
    window : masafi_simtwin.main_window.MainWindow
        The window.
    make_project : collections.abc.Callable
        The project maker.

    Returns
    -------
    str
        The project file.
    """

    path = make_project('Bottling Line')
    window.open_project_path(path)
    return path


def test_a_new_model_is_written_and_shown(window, opened, monkeypatch):
    """From the menu entry to a file in the archive and a node in the tree."""

    stub_model_dialog(monkeypatch, QDialog.DialogCode.Accepted)
    window.new_model_action.trigger()

    models = project.models_of(opened)
    assert [model['name'] for model in models] == ['Filling Station']
    assert models[0]['file'] == 'models/Filling_Station.mfst'
    assert [item.text(0) for item in window._project_tree.model_items()] == [
        'Filling Station'
    ]


def test_a_cancelled_model_dialog_writes_nothing(window, opened, monkeypatch):
    """Nothing is added until the dialog is accepted."""

    stub_model_dialog(monkeypatch, QDialog.DialogCode.Rejected)
    window.new_model_action.trigger()

    assert project.models_of(opened) == []
    assert window._project_tree.model_items() == []


def test_a_model_is_offered_the_names_it_may_not_reuse(window, opened, monkeypatch):
    """So the dialog can refuse a duplicate before anything is written."""

    stub_model_dialog(monkeypatch, QDialog.DialogCode.Accepted)
    window.new_model_action.trigger()

    taken = []

    class Recording:
        def __init__(self, parent=None, preferences=None, model=None, taken_=None, **kw):
            taken.append(kw.get('taken'))
            self.name, self.kind = 'Other', project.ModelKind.PETRI_NET

        def units(self):
            return {'time': 's'}

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr('masafi_simtwin.main_window.ModelDialog', Recording)
    window.new_model_action.trigger()

    assert taken == [['Filling Station']]


def test_changing_a_model_updates_the_tree(window, opened, monkeypatch):
    """The pane follows the manifest, which is the one source of truth."""

    stub_model_dialog(monkeypatch, QDialog.DialogCode.Accepted)
    window.new_model_action.trigger()
    window._project_tree.setCurrentItem(window._project_tree.model_items()[0])

    stub_model_dialog(monkeypatch, QDialog.DialogCode.Accepted, name='Filling')
    window.model_properties_action.trigger()

    assert [item.text(0) for item in window._project_tree.model_items()] == ['Filling']
    assert project.models_of(opened)[0]['name'] == 'Filling'


def test_the_properties_dialog_is_opened_over_the_selected_model(
    window, opened, monkeypatch
):
    """Which is what makes it a properties dialog rather than a new-model one."""

    stub_model_dialog(monkeypatch, QDialog.DialogCode.Accepted)
    window.new_model_action.trigger()
    window._project_tree.setCurrentItem(window._project_tree.model_items()[0])

    over = stub_model_dialog(monkeypatch, QDialog.DialogCode.Rejected)
    window.model_properties_action.trigger()

    assert over[0]['name'] == 'Filling Station'


def test_deleting_a_model_asks_first(window, opened, monkeypatch):
    """The one thing here that cannot be undone is the one thing that asks."""

    stub_model_dialog(monkeypatch, QDialog.DialogCode.Accepted)
    window.new_model_action.trigger()
    window._project_tree.setCurrentItem(window._project_tree.model_items()[0])

    asked = []
    monkeypatch.setattr(
        'masafi_simtwin.main_window.QMessageBox.question',
        lambda *arguments, **keywords: asked.append(arguments[1])
        or QMessageBox.StandardButton.No,
    )
    window.delete_model_action.trigger()

    assert len(asked) == 1
    assert len(project.models_of(opened)) == 1


def test_deleting_a_model_removes_it_when_confirmed(window, opened, monkeypatch):
    """From the manifest, the archive and the tree."""

    stub_model_dialog(monkeypatch, QDialog.DialogCode.Accepted)
    window.new_model_action.trigger()
    window._project_tree.setCurrentItem(window._project_tree.model_items()[0])

    monkeypatch.setattr(
        'masafi_simtwin.main_window.QMessageBox.question',
        lambda *arguments, **keywords: QMessageBox.StandardButton.Yes,
    )
    window.delete_model_action.trigger()

    assert project.models_of(opened) == []
    assert window._project_tree.model_items() == []


def test_a_model_node_offers_properties_and_delete(window, opened, monkeypatch):
    """The two things that can be done to a model."""

    stub_model_dialog(monkeypatch, QDialog.DialogCode.Accepted)
    window.new_model_action.trigger()
    tree = window._project_tree
    menu = tree.menu_for(tree.model_items()[0])

    assert [action for action in menu.actions() if not action.isSeparator()] == [
        window.model_properties_action,
        window.delete_model_action,
    ]


def test_reopening_a_project_shows_its_models(window, opened, monkeypatch, qtbot):
    """The tree is built from the manifest, so a model outlives the session."""

    stub_model_dialog(monkeypatch, QDialog.DialogCode.Accepted)
    window.new_model_action.trigger()
    window.close_project()

    reopened = MainWindow()
    qtbot.addWidget(reopened)
    reopened.open_project_path(opened)

    assert [item.text(0) for item in reopened._project_tree.model_items()] == [
        'Filling Station'
    ]


def test_a_project_open_elsewhere_is_refused(window, make_project, monkeypatch, qtbot):
    """Never the same project twice: two writers lose each other's work."""

    path = make_project('Shared')
    window.open_project_path(path)

    warned = []
    monkeypatch.setattr(
        'masafi_simtwin.main_window.QMessageBox.warning',
        lambda parent, title, text: warned.append(title),
    )
    second = MainWindow()
    qtbot.addWidget(second)
    second.open_project_path(path)

    assert len(warned) == 1
    assert second._project_name == ''
    assert second._project_path is None


def test_closing_a_project_frees_it_for_another_window(window, make_project, qtbot):
    """The lock goes with the session."""

    path = make_project('Shared')
    window.open_project_path(path)
    window.close_project()

    second = MainWindow()
    qtbot.addWidget(second)
    second.open_project_path(path)

    assert second._project_name == 'Shared'


def test_opening_the_project_already_open_does_nothing(window, make_project):
    """It is already open here, so there is nothing to do and nothing to refuse."""

    path = make_project('Shared')
    window.open_project_path(path)
    before = len(project.read_manifest(path)['history'])

    window.open_project_path(path)

    assert window._project_name == 'Shared'
    assert len(project.read_manifest(path)['history']) == before


def test_the_lock_is_freed_when_the_window_closes(window, make_project):
    """Quitting frees the project as closing it does."""

    path = make_project('Shared')
    window.open_project_path(path)
    window.close()

    assert project.holder_of(path) is None


# ----------------------------------------------------------------------
# Documents
# ----------------------------------------------------------------------


def add_model(window, monkeypatch, name: str = 'Filling Station') -> dict:
    """Add a model to the open project through the window's own action.

    Parameters
    ----------
    window : masafi_simtwin.main_window.MainWindow
        The window, with a project open.
    monkeypatch : pytest.MonkeyPatch
        The patcher, for the model dialog.
    name : str, optional
        What the model is called.

    Returns
    -------
    dict
        The model's entry in the manifest.
    """

    stub_model_dialog(monkeypatch, QDialog.DialogCode.Accepted, name=name)
    window.new_model_action.trigger()
    return [
        model
        for model in project.models_of(window._project_path)
        if model['name'] == name
    ][0]


def test_a_new_model_opens_in_a_tab(window, opened, monkeypatch):
    """A model made is a model being worked on, so it opens where it is edited."""

    model = add_model(window, monkeypatch)
    area = window.document_area

    assert area.document_count == 1
    assert area.tabs.tabText(0) == 'Filling Station'
    assert area.document(model['uuid']) is not None


def test_a_model_opens_on_its_own_canvas(window, opened, monkeypatch):
    """A Petri net opens on the Petri net editor, not on a placeholder."""

    model = add_model(window, monkeypatch)

    assert isinstance(window.document_area.document(model['uuid']), PetriNetEditor)


def test_a_tab_is_closed_by_its_own_button(window, opened, monkeypatch):
    """Every document carries one, which is the only way one is closed by hand."""

    add_model(window, monkeypatch)
    area = window.document_area
    button = area.tabs.tabBar().tabButton(0, QTabBar.ButtonPosition.RightSide)
    button.click()

    assert area.document_count == 0
    assert area.showing_placeholder


def test_double_clicking_a_model_opens_it_again(window, opened, monkeypatch):
    """The project pane is where a closed model is reached from."""

    model = add_model(window, monkeypatch)
    tree = window._project_tree
    window.document_area.close_all_documents()

    tree.itemDoubleClicked.emit(tree.model_items()[0], 0)

    assert window.document_area.document_count == 1
    assert window.document_area.document(model['uuid']) is not None


def test_a_model_already_open_is_raised_rather_than_opened_twice(
    window, opened, monkeypatch
):
    """Two tabs of one model would be two views of one file, unaware of each other."""

    first = add_model(window, monkeypatch, 'Filling Station')
    add_model(window, monkeypatch, 'Capping')
    area = window.document_area
    editor = area.document(first['uuid'])

    window.open_model(first['uuid'])

    assert area.document_count == 2
    assert area.document(first['uuid']) is editor
    assert area.tabs.currentWidget() is editor


def test_renaming_a_model_retitles_its_tab(window, opened, monkeypatch):
    """A model's identity is its UUID, so the tab it is in survives the rename."""

    model = add_model(window, monkeypatch)
    editor = window.document_area.document(model['uuid'])
    window._project_tree.setCurrentItem(window._project_tree.model_items()[0])

    stub_model_dialog(monkeypatch, QDialog.DialogCode.Accepted, name='Filling')
    window.model_properties_action.trigger()

    assert window.document_area.tabs.tabText(0) == 'Filling'
    assert window.document_area.document(model['uuid']) is editor


def test_deleting_a_model_closes_its_tab(window, opened, monkeypatch):
    """A document of something that no longer exists cannot be left open."""

    add_model(window, monkeypatch)
    window._project_tree.setCurrentItem(window._project_tree.model_items()[0])

    monkeypatch.setattr(
        'masafi_simtwin.main_window.QMessageBox.question',
        lambda *arguments, **keywords: QMessageBox.StandardButton.Yes,
    )
    window.delete_model_action.trigger()

    assert window.document_area.document_count == 0


def test_closing_a_project_closes_its_documents(window, opened, monkeypatch):
    """The documents belong to the project, as the project pane does."""

    add_model(window, monkeypatch)
    window.close_project()

    assert window.document_area.document_count == 0
    assert window.document_area.showing_placeholder


def test_opening_another_project_closes_the_documents_of_the_first(
    window, opened, make_project, monkeypatch
):
    """Otherwise a tab would outlive the project whose file it is written in."""

    add_model(window, monkeypatch)
    window.open_project_path(make_project('Packing Line'))

    assert window.document_area.document_count == 0


def test_a_model_of_a_kind_that_is_not_built_is_not_opened(window, opened):
    """It is reported instead, which is what an unimplemented kind deserves."""

    model = project.add_model(
        opened, 'Flow', project.ModelKind.PROCESS_FLOW, {'time': 's'}
    )
    window.open_model(model['uuid'])

    assert window.document_area.document_count == 0
    assert 'Flow' in window.statusBar().currentMessage()


def test_opening_a_model_the_project_does_not_hold_does_nothing(window, opened):
    """A tree left behind by a change made elsewhere asks for exactly that."""

    window.open_model('no-such-model')

    assert window.document_area.document_count == 0


# ----------------------------------------------------------------------
# Teardown
# ----------------------------------------------------------------------

#: A whole session, run in a process of its own: build the window, open a
#: project in it, and let go of both it and the application at once, which is
#: what happens when ``main()`` returns.
#:
#: It cannot be done in this process.  What went wrong here did not raise, it
#: killed the interpreter — Qt hides every dock widget as the window is torn
#: down, and the pane's *visibility* signal reached a window whose C++ side had
#: already gone.  A test for that has to be able to survive it, so it watches
#: from outside and reads the exit code.
TEARDOWN_SESSION = '''
import gc, sys
from PyQt6.QtCore import QSettings, QTimer, QEventLoop
from masafi_simtwin.application import SimTwinApplication
from masafi_simtwin.main_window import MainWindow
from masafi_simtwin import project

QSettings.setDefaultFormat(QSettings.Format.IniFormat)

def session(path):
    application = SimTwinApplication([sys.argv[0]])
    window = MainWindow()
    window.show()
    loop = QEventLoop()
    QTimer.singleShot(50, loop.quit)
    loop.exec()
    window.open_project_path(path)

session(sys.argv[1])
gc.collect()
print('survived')
'''


def test_a_window_that_opened_a_project_is_torn_down_without_a_crash(tmp_path):
    """Opening a project shows a pane, and a pane shown is a pane hidden later.

    Qt hides every dock widget as the window is destroyed, so the pane reports
    it — and until the pane carried its own signal, that report was a lambda
    belonging to the dock, which Qt keeps until the *dock* goes.  By then the
    window's C++ side is gone, and calling a method on it took the interpreter
    down with it rather than raising anything a test could catch.
    """

    path = str(project.create(project.path_for(tmp_path, 'Bottling Line'), 'Bottling Line'))
    environment = dict(os.environ)
    environment['QT_QPA_PLATFORM'] = 'offscreen'
    environment['XDG_CONFIG_HOME'] = str(tmp_path / 'config')

    finished = subprocess.run(
        [sys.executable, '-c', TEARDOWN_SESSION, path],
        capture_output=True,
        text=True,
        timeout=120,
        env=environment,
    )

    assert finished.returncode == 0, finished.stderr
    assert 'survived' in finished.stdout


def test_a_new_page_reaches_the_documents_that_are_open(window, opened, monkeypatch):
    """The page is not a preference that waits for a restart.

    A sheet can be ruled again where it stands, and a setting whose effect can
    be seen at once is a setting the user can judge.
    """

    add_model(window, monkeypatch)
    editor = window.document_area.tabs.currentWidget()
    before = editor.page

    landscape = QSizeF(paper.dimensions('A3', paper.LANDSCAPE))
    monkeypatch.setattr('masafi_simtwin.main_window.preferences.page', lambda: landscape)
    window._apply_page(('appearance/page_size',))

    assert before != landscape
    assert editor.page == landscape


def test_a_settings_change_that_is_not_the_page_leaves_the_sheets_alone(
    window, opened, monkeypatch
):
    """Which is every other preference there is."""

    add_model(window, monkeypatch)
    editor = window.document_area.tabs.currentWidget()
    before = editor.page

    monkeypatch.setattr(
        'masafi_simtwin.main_window.preferences.page',
        lambda: QSizeF(paper.dimensions('A3', paper.LANDSCAPE)),
    )
    window._apply_page(('units/time',))

    assert editor.page == before


@pytest.mark.parametrize('which', ['recent menu', 'top bar'])
def test_a_recent_project_survives_being_clicked(window, make_project, which):
    """Opening a project rebuilds the very menus the click came from.

    Qt is still inside ``QAction::activate()`` while our handler runs, so an
    entry destroyed there leaves Qt using freed memory once the handler returns
    — a segmentation fault in the event loop, with no Python traceback, and only
    when the freed memory has been reused. Hence the pixel-precise assertion
    here: the entry has to still be alive when its own trigger returns.
    """

    path = make_project('Bottling Line')
    window._publish_recent_projects([path])
    menu = window._recent_menu if which == 'recent menu' else window.top_bar._project_button.menu()
    entry = next(action for action in menu.actions() if action.data() == path)

    entry.trigger()

    assert not sip.isdeleted(entry)
    assert window._project_name == 'Bottling Line'


def test_the_recent_menus_still_hold_the_project_afterwards(window, make_project, qtbot):
    """The deferred deletion empties the menus; the rebuild fills them again."""

    path = make_project('Bottling Line')
    window._publish_recent_projects([path])
    next(a for a in window._recent_menu.actions() if a.data() == path).trigger()
    qtbot.wait(50)

    for menu in (window._recent_menu, window.top_bar._project_button.menu()):
        assert [action.data() for action in menu.actions() if action.data()] == [path]
