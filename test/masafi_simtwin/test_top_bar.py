"""Tests for the top bar."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenuBar, QWidget

from masafi_simtwin.top_bar import TopBar


@pytest.fixture
def top_bar(qtbot):
    """Build a top bar with throw-away actions.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    masafi_simtwin.top_bar.TopBar
        A top bar, shown and ready for interaction.
    """

    menu_bar = QMenuBar()
    menu_bar.addMenu('&File')
    menu_bar.addMenu('&Edit')

    controls = [QAction(name) for name in ('Run', 'Stop', 'Fast Forward', 'Reset')]
    bar = TopBar(
        menu_bar=menu_bar,
        control_actions=controls,
        open_project_action=QAction('Open Project…'),
        clear_recent_projects_action=QAction('Clear Recent Projects'),
        search_action=QAction('Search'),
        settings_action=QAction('Settings'),
    )
    qtbot.addWidget(bar)
    bar.show()
    qtbot.waitExposed(bar)
    return bar


def test_starts_with_the_hamburger_and_no_menu_bar(top_bar):
    """The bar opens showing the buttons, not the menu bar."""

    assert not top_bar.menu_bar_visible
    assert top_bar._hamburger_button.isVisible()
    assert top_bar._project_button.isVisible()


def test_hamburger_swaps_itself_for_the_menu_bar(top_bar, qtbot):
    """Clicking the hamburger replaces it with the menu bar in the same place."""

    qtbot.mouseClick(top_bar._hamburger_button, Qt.MouseButton.LeftButton)

    assert top_bar.menu_bar_visible
    assert not top_bar._hamburger_button.isVisible()


def test_the_menu_bar_takes_the_place_of_the_project_button(top_bar, qtbot):
    """The project name steps aside for as long as the menu titles are up."""

    qtbot.mouseClick(top_bar._hamburger_button, Qt.MouseButton.LeftButton)
    assert not top_bar._project_button.isVisible()

    qtbot.mouseClick(top_bar, Qt.MouseButton.LeftButton, pos=QPoint(400, 10))

    assert not top_bar.menu_bar_visible
    assert top_bar._project_button.isVisible()


def test_triggering_a_menu_item_brings_the_buttons_back(top_bar, qtbot):
    """The menu bar folds away as soon as an item is triggered."""

    qtbot.mouseClick(top_bar._hamburger_button, Qt.MouseButton.LeftButton)
    file_menu = top_bar._menu_bar.actions()[0].menu()
    action = file_menu.addAction('Quit')
    action.trigger()

    assert not top_bar.menu_bar_visible
    assert top_bar._hamburger_button.isVisible()
    assert top_bar._project_button.isVisible()


def test_losing_focus_brings_the_button_back(top_bar, qtbot):
    """Moving the keyboard focus away folds the menu bar away."""

    qtbot.mouseClick(top_bar._hamburger_button, Qt.MouseButton.LeftButton)
    top_bar._menu_bar.clearFocus()
    qtbot.waitUntil(lambda: not top_bar.menu_bar_visible, timeout=1000)

    assert top_bar._hamburger_button.isVisible()
    assert top_bar._project_button.isVisible()


def test_clicking_the_bar_itself_brings_the_button_back(top_bar, qtbot):
    """A press on the empty stretch of the top bar counts as clicking elsewhere."""

    qtbot.mouseClick(top_bar._hamburger_button, Qt.MouseButton.LeftButton)
    assert top_bar.menu_bar_visible

    qtbot.mouseClick(top_bar, Qt.MouseButton.LeftButton, pos=QPoint(400, 10))

    assert not top_bar.menu_bar_visible
    assert top_bar._hamburger_button.isVisible()


def test_clicking_another_widget_brings_the_button_back(top_bar, qtbot):
    """A press anywhere else in the application folds the menu bar away.

    Nothing routes this click to the top bar and the widget pressed never takes
    the focus, so only the application wide filter can catch it.
    """

    elsewhere = QWidget()
    qtbot.addWidget(elsewhere)
    elsewhere.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    elsewhere.show()
    qtbot.waitExposed(elsewhere)

    qtbot.mouseClick(top_bar._hamburger_button, Qt.MouseButton.LeftButton)
    assert top_bar.menu_bar_visible

    qtbot.mouseClick(elsewhere, Qt.MouseButton.LeftButton)

    assert not top_bar.menu_bar_visible
    assert top_bar._hamburger_button.isVisible()


def test_clicking_inside_the_menu_bar_keeps_it_open(top_bar, qtbot):
    """Pressing a menu title opens it instead of folding the bar away."""

    qtbot.mouseClick(top_bar._hamburger_button, Qt.MouseButton.LeftButton)
    file_action = top_bar._menu_bar.actions()[0]
    file_action.menu().addAction('Quit')

    qtbot.mouseClick(
        top_bar._menu_bar,
        Qt.MouseButton.LeftButton,
        pos=top_bar._menu_bar.actionGeometry(file_action).center(),
    )
    try:
        assert top_bar.menu_bar_visible
    finally:
        file_action.menu().close()


def test_the_filter_is_removed_once_the_menu_bar_is_hidden(top_bar, qtbot):
    """A collapsed bar stops watching the application, and can be reopened."""

    qtbot.mouseClick(top_bar._hamburger_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(top_bar, Qt.MouseButton.LeftButton, pos=QPoint(400, 10))
    qtbot.mouseClick(top_bar, Qt.MouseButton.LeftButton, pos=QPoint(400, 10))

    assert not top_bar.menu_bar_visible

    qtbot.mouseClick(top_bar._hamburger_button, Qt.MouseButton.LeftButton)

    assert top_bar.menu_bar_visible


def test_project_menu_offers_open_project_first(top_bar):
    """With no history the drop-down is Open Project and a disabled placeholder."""

    entries = top_bar._project_button.menu().actions()

    assert entries[0].text() == 'Open Project…'
    assert entries[1].isSeparator()
    assert not entries[2].isEnabled()


def test_project_menu_lists_recent_projects(top_bar):
    """Recent projects follow Open Project, in the order given."""

    top_bar.set_recent_projects(['/home/jaume/codi/one', '/home/jaume/codi/two'])
    entries = top_bar._project_button.menu().actions()

    assert [entry.text() for entry in entries[2:-2]] == [
        '/home/jaume/codi/one',
        '/home/jaume/codi/two',
    ]


def test_the_menu_ends_with_a_separator_and_the_clear_entry(top_bar):
    """Whatever the history holds, so the menu keeps one shape."""

    for history in ([], ['/home/jaume/codi/one']):
        top_bar.set_recent_projects(history)
        entries = top_bar._project_button.menu().actions()

        assert entries[-2].isSeparator()
        assert entries[-1] is top_bar._clear_recent_projects_action


def test_the_clear_entry_is_the_action_the_bar_was_given(top_bar):
    """The bar shows the window's action rather than one of its own."""

    top_bar.set_recent_projects(['/home/jaume/codi/one'])
    last = top_bar._project_button.menu().actions()[-1]

    assert last.text() == 'Clear Recent Projects'
    assert last is top_bar._clear_recent_projects_action


def test_selecting_a_recent_project_is_reported(top_bar, qtbot):
    """Picking a project from the drop-down emits its path."""

    top_bar.set_recent_projects(['/home/jaume/codi/one'])
    entry = top_bar._project_button.menu().actions()[2]

    with qtbot.waitSignal(top_bar.recent_project_selected, timeout=1000) as blocker:
        entry.trigger()

    assert blocker.args == ['/home/jaume/codi/one']


def test_project_name_is_shown_on_the_button(top_bar):
    """The button carries the project name and repeats it as a tool tip."""

    top_bar.set_project_name('MASAFI-SimTwin')

    assert top_bar._project_button.text() == 'MASAFI-SimTwin'
    assert top_bar._project_button.toolTip() == 'MASAFI-SimTwin'


def test_clicking_outside_an_open_menu_brings_the_button_back(top_bar, qtbot):
    """A click outside an open pop-up dismisses the menu and folds the bar away.

    The pop-up grabs the mouse, so this press is delivered to the menu and not
    to whatever is under the cursor; it is only the position that tells it apart
    from a click on an entry.
    """

    qtbot.mouseClick(top_bar._hamburger_button, Qt.MouseButton.LeftButton)
    file_menu = top_bar._menu_bar.actions()[0].menu()
    file_menu.addAction('Quit')
    file_menu.popup(top_bar.mapToGlobal(QPoint(0, 40)))
    qtbot.waitExposed(file_menu)

    qtbot.mouseClick(
        file_menu,
        Qt.MouseButton.LeftButton,
        pos=QPoint(file_menu.width() + 50, file_menu.height() + 50),
    )

    assert not top_bar.menu_bar_visible
    assert top_bar._hamburger_button.isVisible()
