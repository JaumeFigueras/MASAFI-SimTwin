"""The vertical stripe of tool window buttons down the left edge.

One stripe holds two groups: the buttons added with :meth:`SideBar.add_top_pane`
sit under the top bar, the ones added with :meth:`SideBar.add_bottom_pane` are
pushed down against the status bar by a spacer that eats the room in between.
That is one toolbar, not two, because Qt stacks two toolbars in the same dock
area head to tail — the only way to pin a group to the bottom edge is to put a
stretch in front of it.

Each group is exclusive but optional: at most one of its buttons is pressed at a
time, so opening a pane closes the one that was open, and pressing the button of
the pane already open closes it and leaves the group empty.  The stripe only
reports the change through :attr:`SideBar.pane_toggled`; which pane a key stands
for is the window's business, not the stripe's.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import QSizePolicy, QToolBar, QWidget

from masafi_simtwin import icons


class SideBar(QToolBar):
    """A vertical tool stripe with a top and a bottom group of icon buttons.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.

    Attributes
    ----------
    pane_toggled : PyQt6.QtCore.pyqtSignal
        Emitted with the key of the pane and its new checked state whenever one
        of the buttons is toggled.
    """

    pane_toggled = pyqtSignal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('SideBar')
        self.setMovable(False)
        self.setFloatable(False)
        self.setIconSize(QSize(icons.CHROME_ICON_SIZE, icons.CHROME_ICON_SIZE))

        self._actions: dict[str, QAction] = {}
        self._top_group = self._build_group()
        self._bottom_group = self._build_group()

        spacer = QWidget(self)
        spacer.setObjectName('SideBarSpacer')
        spacer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._spacer_action = self.addWidget(spacer)

    def add_top_pane(self, key: str, icon_name: str, text: str) -> QAction:
        """Add a button to the group anchored at the top of the stripe.

        Parameters
        ----------
        key : str
            Identifier reported by :attr:`pane_toggled`.
        icon_name : str
            Name of the Material Symbol to draw on the button.
        text : str
            Translated name of the pane, used as the tool tip.

        Returns
        -------
        PyQt6.QtGui.QAction
            The checkable action backing the button.
        """

        action = self._build_action(key, icon_name, text, self._top_group)
        self.insertAction(self._spacer_action, action)
        return action

    def add_bottom_pane(self, key: str, icon_name: str, text: str) -> QAction:
        """Add a button to the group anchored at the bottom of the stripe.

        Parameters
        ----------
        key : str
            Identifier reported by :attr:`pane_toggled`.
        icon_name : str
            Name of the Material Symbol to draw on the button.
        text : str
            Translated name of the pane, used as the tool tip.

        Returns
        -------
        PyQt6.QtGui.QAction
            The checkable action backing the button.
        """

        action = self._build_action(key, icon_name, text, self._bottom_group)
        self.addAction(action)
        return action

    def pane_action(self, key: str) -> QAction | None:
        """Return the action of a pane.

        Parameters
        ----------
        key : str
            Identifier the pane was added with.

        Returns
        -------
        PyQt6.QtGui.QAction or None
            The action, or ``None`` when no pane was added under that key.
        """

        return self._actions.get(key)

    def _build_group(self) -> QActionGroup:
        """Build one exclusive but optional group of stripe actions.

        Returns
        -------
        PyQt6.QtGui.QActionGroup
            A group in which checking a button unchecks the others, and in which
            the checked button can be unchecked by pressing it again.  The plain
            exclusive policy would refuse that second press, which is exactly
            how a pane is closed from the stripe.
        """

        group = QActionGroup(self)
        group.setExclusionPolicy(QActionGroup.ExclusionPolicy.ExclusiveOptional)
        return group

    def _build_action(self, key: str, icon_name: str, text: str, group: QActionGroup) -> QAction:
        """Build one checkable stripe action.

        Parameters
        ----------
        key : str
            Identifier reported by :attr:`pane_toggled`.
        icon_name : str
            Name of the Material Symbol to draw on the button.
        text : str
            Translated name of the pane.
        group : PyQt6.QtGui.QActionGroup
            The group the action competes in.

        Returns
        -------
        PyQt6.QtGui.QAction
            The action, registered and connected.
        """

        action = QAction(text, self)
        action.setCheckable(True)
        action.setToolTip(text)
        icons.set_icon(action, icon_name)
        group.addAction(action)
        action.toggled.connect(lambda checked, name=key: self.pane_toggled.emit(name, checked))
        self._actions[key] = action
        return action
