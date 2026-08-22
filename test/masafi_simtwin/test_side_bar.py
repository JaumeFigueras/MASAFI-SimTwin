"""Tests for the left tool stripe."""

from __future__ import annotations

import pytest

from masafi_simtwin.side_bar import SideBar


@pytest.fixture
def side_bar(qtbot):
    """Build a tool stripe with one pane in each group.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    masafi_simtwin.side_bar.SideBar
        The stripe.
    """

    bar = SideBar()
    qtbot.addWidget(bar)
    bar.add_top_pane('project', 'account_tree', 'Project')
    bar.add_bottom_pane('problems', 'error', 'Problems')
    return bar


def test_top_panes_come_before_the_spacer(side_bar):
    """A top pane is inserted above the stretch that pins the bottom group."""

    actions = side_bar.actions()
    spacer = actions.index(side_bar._spacer_action)
    project = actions.index(side_bar.pane_action('project'))
    problems = actions.index(side_bar.pane_action('problems'))

    assert project < spacer < problems


def test_panes_are_checkable_and_carry_an_icon(side_bar):
    """Stripe buttons toggle and are drawn with a Material Symbol."""

    action = side_bar.pane_action('project')

    assert action.isCheckable()
    assert not action.isChecked()
    assert not action.icon().isNull()
    assert action.toolTip() == 'Project'


def test_toggling_a_pane_is_reported(side_bar, qtbot):
    """Toggling a button reports its key and its new state."""

    action = side_bar.pane_action('problems')

    with qtbot.waitSignal(side_bar.pane_toggled, timeout=1000) as blocker:
        action.setChecked(True)
    assert blocker.args == ['problems', True]

    with qtbot.waitSignal(side_bar.pane_toggled, timeout=1000) as blocker:
        action.setChecked(False)
    assert blocker.args == ['problems', False]


def test_unknown_pane_has_no_action(side_bar):
    """Asking for a pane that was never added returns nothing."""

    assert side_bar.pane_action('nowhere') is None


def test_a_group_holds_at_most_one_pressed_button(side_bar):
    """Checking a second button in the same group releases the first."""

    side_bar.add_top_pane('libraries', 'category', 'Libraries')
    project = side_bar.pane_action('project')
    libraries = side_bar.pane_action('libraries')

    project.setChecked(True)
    libraries.setChecked(True)

    assert libraries.isChecked()
    assert not project.isChecked()


def test_the_pressed_button_can_be_released(side_bar):
    """The group is optional, so the button that is pressed can be pressed again."""

    project = side_bar.pane_action('project')
    project.setChecked(True)
    project.trigger()

    assert not project.isChecked()


def test_the_two_groups_are_independent(side_bar):
    """A button at the top and one at the bottom can be pressed at the same time."""

    project = side_bar.pane_action('project')
    problems = side_bar.pane_action('problems')

    project.setChecked(True)
    problems.setChecked(True)

    assert project.isChecked()
    assert problems.isChecked()
