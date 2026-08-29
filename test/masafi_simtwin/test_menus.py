"""Tests for emptying a menu without destroying what Qt is still using."""

from __future__ import annotations

import pytest
from PyQt6 import sip
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu, QWidget

from masafi_simtwin.menus import clear_menu


@pytest.fixture
def menu(qtbot):
    """Build a menu with one action of its own and one belonging elsewhere.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    tuple
        The owner of both, the menu, the action it owns, and the action it does
        not.  The owner is handed back so that it outlives the fixture: dropping
        it would destroy the menu with it.
    """

    owner = QWidget()
    qtbot.addWidget(owner)
    widget = QMenu(owner)
    mine = widget.addAction('Mine')
    shared = QAction('Shared', owner)
    widget.addAction(shared)
    return owner, widget, mine, shared


def test_a_menu_is_emptied(menu):
    """Which is what it was asked to do."""

    _owner, widget, _mine, _shared = menu
    clear_menu(widget)

    assert widget.actions() == []


def test_nothing_is_destroyed_while_qt_may_still_be_using_it(menu, qtbot):
    """``QMenu.clear()`` destroys what the menu owns *there and then*.

    These menus are rebuilt from inside the ``triggered`` handler of one of
    their own actions — click a recent project and it moves to the head of the
    history, which is the menu.  Qt is still inside ``QAction::activate()``
    then, and an action destroyed under it leaves Qt using freed memory: a
    segmentation fault with no Python traceback, and only sometimes, which is
    the worst way for a bug to behave.
    """

    _owner, widget, mine, _shared = menu
    clear_menu(widget)

    assert not sip.isdeleted(mine)


def test_what_the_menu_owns_is_destroyed_in_the_end(menu, qtbot):
    """Deferred, not leaked: the loop clears them once it is safe to."""

    _owner, widget, mine, _shared = menu
    clear_menu(widget)
    qtbot.wait(50)

    assert sip.isdeleted(mine)


def test_an_action_belonging_elsewhere_is_only_taken_out(menu, qtbot):
    """This application shares actions between two menus; one may not delete them."""

    _owner, widget, _mine, shared = menu
    clear_menu(widget)
    qtbot.wait(50)

    assert not sip.isdeleted(shared)
    assert shared.text() == 'Shared'
