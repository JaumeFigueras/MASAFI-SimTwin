"""Tests for the tree of the open project."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from masafi_simtwin.project_tree import KIND_ROLE, NodeKind, ProjectTree


@pytest.fixture
def actions(qapp):
    """Build actions to hang off the nodes.

    Parameters
    ----------
    qapp : masafi_simtwin.application.SimTwinApplication
        The application pytest-qt built.

    Returns
    -------
    dict
        Three actions, by the name they go by in the tests.
    """

    return {name: QAction(name, qapp) for name in ('model', 'simulation', 'settings')}


@pytest.fixture
def tree(qtbot, actions):
    """Build a tree with a project already in it.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.
    actions : dict
        The actions each kind of node offers.

    Returns
    -------
    masafi_simtwin.project_tree.ProjectTree
        The tree, showing a project called *Bottling Line*.
    """

    widget = ProjectTree(
        {
            NodeKind.ROOT: [actions['model'], actions['simulation'], None, actions['settings']],
            NodeKind.MODELS: [actions['model']],
            NodeKind.SIMULATIONS: [actions['simulation']],
        }
    )
    qtbot.addWidget(widget)
    widget.set_project('Bottling Line')
    return widget


# ----------------------------------------------------------------------
# What the tree shows
# ----------------------------------------------------------------------


def test_the_project_is_the_root(tree):
    """The project's name is what the tree is rooted at."""

    assert tree.topLevelItemCount() == 1
    assert tree.root().text(0) == 'Bottling Line'
    assert tree.kind_of(tree.root()) is NodeKind.ROOT


def test_the_root_holds_the_three_things_a_project_is_made_of(tree):
    """Models, the simulations run over them, and the statistics those made."""

    root = tree.root()
    children = [root.child(position) for position in range(root.childCount())]

    assert [child.text(0) for child in children] == ['Models', 'Simulations', 'Statistics']
    assert [tree.kind_of(child) for child in children] == [
        NodeKind.MODELS,
        NodeKind.SIMULATIONS,
        NodeKind.STATISTICS,
    ]


def test_the_root_opens_expanded(tree):
    """The three nodes are what the pane is for; hiding them helps nobody."""

    assert tree.root().isExpanded()
    assert tree.currentItem() is tree.root()


def test_the_header_is_hidden(tree):
    """There is one column and it needs no name."""

    assert tree.isHeaderHidden()


def test_a_node_is_found_by_its_kind(tree):
    """Which is how the window reaches one without matching on its title."""

    assert tree.node(NodeKind.MODELS).text(0) == 'Models'
    assert tree.node(NodeKind.ROOT) is tree.root()


def test_opening_another_project_replaces_the_first(tree):
    """A window shows one project, so the tree holds one root."""

    tree.set_project('Second')

    assert tree.topLevelItemCount() == 1
    assert tree.root().text(0) == 'Second'


def test_an_empty_tree_has_no_root(qtbot):
    """Which is what the pane shows while no project is open."""

    widget = ProjectTree()
    qtbot.addWidget(widget)

    assert widget.root() is None
    assert widget.node(NodeKind.MODELS) is None
    assert widget.kind_of(None) is None


def test_the_kind_is_kept_on_the_item(tree):
    """Not derived from the title, which is translated."""

    assert tree.root().data(0, KIND_ROLE) is NodeKind.ROOT
    assert KIND_ROLE == Qt.ItemDataRole.UserRole


# ----------------------------------------------------------------------
# The context menus
# ----------------------------------------------------------------------


def entries(menu):
    """List what a menu offers.

    Parameters
    ----------
    menu : PyQt6.QtWidgets.QMenu
        The menu.

    Returns
    -------
    list of str
        The titles, with ``'---'`` for a separator.
    """

    return ['---' if action.isSeparator() else action.text() for action in menu.actions()]


def test_the_project_offers_everything_the_project_menu_does(tree, actions):
    """One list, two views of it: the menu bar and this."""

    assert entries(tree.menu_for(tree.root())) == ['model', 'simulation', '---', 'settings']


def test_the_models_node_offers_a_new_model_alone(tree):
    """Nothing else applies to the models of a project as a whole."""

    assert entries(tree.menu_for(tree.node(NodeKind.MODELS))) == ['model']


def test_the_simulations_node_offers_a_new_simulation_alone(tree):
    """As the models node does for models."""

    assert entries(tree.menu_for(tree.node(NodeKind.SIMULATIONS))) == ['simulation']


def test_the_statistics_node_offers_nothing(tree):
    """Statistics are produced by simulations; none is made by hand."""

    assert tree.menu_for(tree.node(NodeKind.STATISTICS)) is None


def test_a_click_on_no_node_offers_nothing(tree):
    """The empty space below the tree is not a node."""

    assert tree.menu_for(None) is None


def test_the_context_menu_holds_the_windows_own_actions(tree, actions):
    """Not copies of them, so that enabling one enables it everywhere."""

    menu = tree.menu_for(tree.node(NodeKind.MODELS))

    assert menu.actions()[0] is actions['model']


def test_the_tree_asks_for_its_own_context_menu(tree):
    """Which is what routes a right click to :meth:`menu_for`."""

    assert tree.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


# ----------------------------------------------------------------------
# Models under the Models node
# ----------------------------------------------------------------------

MODELS = [
    {'uuid': 'u-1', 'name': 'Filling'},
    {'uuid': 'u-2', 'name': 'Capping'},
]


def test_a_project_shows_its_models(qtbot):
    """Under *Models*, in the order the manifest holds them."""

    widget = ProjectTree()
    qtbot.addWidget(widget)
    widget.set_project('Bottling Line', MODELS)

    assert [item.text(0) for item in widget.model_items()] == ['Filling', 'Capping']
    assert widget.node(NodeKind.MODELS).isExpanded()


def test_a_model_node_remembers_which_model_it_is(tree):
    """By UUID, not by name: a model renamed is still the same model."""

    tree.set_models(MODELS)

    assert [tree.model_of(item) for item in tree.model_items()] == ['u-1', 'u-2']
    assert all(tree.kind_of(item) is NodeKind.MODEL for item in tree.model_items())


def test_setting_the_models_replaces_the_ones_shown(tree):
    """The tree follows the manifest rather than accumulating."""

    tree.set_models(MODELS)
    tree.set_models([{'uuid': 'u-3', 'name': 'Only'}])

    assert [item.text(0) for item in tree.model_items()] == ['Only']


def test_a_project_with_no_models_shows_none(tree):
    """And leaves the branch closed, since there is nothing under it."""

    tree.set_models([])

    assert tree.model_items() == []
    assert not tree.node(NodeKind.MODELS).isExpanded()


def test_a_node_that_is_not_a_model_has_no_model(tree):
    """Which is what tells the window whether a selection is one."""

    assert tree.model_of(tree.root()) is None
    assert tree.model_of(tree.node(NodeKind.MODELS)) is None


def test_double_clicking_a_model_asks_for_it(tree, qtbot):
    """Which is how a model already made is opened again."""

    tree.set_models(MODELS)

    with qtbot.waitSignal(tree.model_activated, timeout=1000) as blocker:
        tree.itemDoubleClicked.emit(tree.model_items()[1], 0)

    assert blocker.args == ['u-2']


def test_double_clicking_anything_else_asks_for_nothing(tree, qtbot):
    """A double click on a group node is Qt's own way of folding it."""

    tree.set_models(MODELS)
    asked = []
    tree.model_activated.connect(asked.append)

    tree.itemDoubleClicked.emit(tree.root(), 0)
    tree.itemDoubleClicked.emit(tree.node(NodeKind.MODELS), 0)

    assert asked == []
