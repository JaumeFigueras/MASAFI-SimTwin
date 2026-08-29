"""Emptying a menu without pulling the ground from under Qt.

``QMenu.clear()`` **destroys** the actions the menu owns, there and then.  That
is fine when a menu is rebuilt from somewhere unrelated, and it is a crash when
the menu is rebuilt from inside the ``triggered`` handler of one of its own
actions — which is exactly what the recent projects list does: clicking a
project opens it, opening it moves it to the head of the history, and the
history is these two menus.

Qt is still inside ``QAction::activate()`` when our slot runs.  Destroying the
action under it leaves Qt holding a pointer to freed memory, and it goes on to
use it the moment the slot returns.  The result is a segmentation fault with no
Python traceback at all — the crash is in C++, in the event loop, long after the
last Python frame has gone — and it is a *silent* fault as often as not, because
freed memory only bites once something else has been put in it.  It crashed the
machine it was found on and never once crashed a driven session here, which is
why the test for it asks whether the action is still alive rather than whether
anything fell over.

So: take the actions out, and let the event loop destroy the ones the menu owns
once it has finished with them.  Anything owned by somebody else — an action
shared between two menus, which this application has several of — is removed and
left alone.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QMenu


def clear_menu(menu: QMenu) -> None:
    """Empty a menu, destroying nothing before Qt has finished with it.

    Use this rather than ``QMenu.clear()`` wherever a menu might be rebuilt from
    something the menu itself set off.

    Parameters
    ----------
    menu : PyQt6.QtWidgets.QMenu
        The menu to empty.
    """

    for action in menu.actions():
        menu.removeAction(action)
        if action.parent() is menu:
            action.deleteLater()
