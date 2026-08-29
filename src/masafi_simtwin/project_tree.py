"""The tree of the open project, shown in the Project tool pane.

The tree is the project's own shape: the project at the root, and under it the
three things a project is made of — its models, the simulations run over them,
and the statistics those produced.

The tree owns no actions.  The window owns every action of the application, and
hands this widget the ones each kind of node offers, so that an entry of the
*Project* menu and the same entry in a context menu are one action rather than
two that have to be kept in step.  Which node offers what is
:data:`ProjectTree.menus`, given when the tree is built.

What the tree does say is that a model was asked for: a double click on a model
is how one is opened, and :attr:`ProjectTree.model_activated` reports it.  That
is a fact about the tree rather than an action of it — what opening a model
means is the window's to decide.
"""

from __future__ import annotations

from enum import Enum

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu, QTreeWidget, QTreeWidgetItem, QWidget


class NodeKind(Enum):
    """What a node of the tree stands for."""

    ROOT = 'root'
    MODELS = 'models'
    MODEL = 'model'
    SIMULATIONS = 'simulations'
    STATISTICS = 'statistics'


#: Where the :class:`NodeKind` of an item is kept, on the item itself.
KIND_ROLE = Qt.ItemDataRole.UserRole

#: Where the UUID of the model a node stands for is kept.
MODEL_ROLE = Qt.ItemDataRole.UserRole + 1


class ProjectTree(QTreeWidget):
    """The tree of the open project.

    Parameters
    ----------
    menus : dict, optional
        The actions each kind of node offers on a right click, by
        :class:`NodeKind`.  ``None`` in a list inserts a separator, as it does
        in the menu bar.  A kind that is absent, or whose list is empty, has no
        context menu at all.
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.

    Attributes
    ----------
    menus : dict
        The mapping the tree was built with.
    model_activated : PyQt6.QtCore.pyqtSignal
        Emitted with the UUID of a model when its node is double clicked, which
        is how a model is opened in the document area.
    """

    model_activated = pyqtSignal(str)

    def __init__(
        self,
        menus: dict[NodeKind, list[QAction | None]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.menus = menus if menus is not None else {}

        self.setObjectName('ProjectTree')
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.itemDoubleClicked.connect(self._on_item_activated)

    # ------------------------------------------------------------------
    # What the tree holds
    # ------------------------------------------------------------------

    def set_project(self, name: str, models: list[dict] | None = None) -> QTreeWidgetItem:
        """Show a project, replacing whatever was shown before.

        Parameters
        ----------
        name : str
            The name of the project, which is what the root is called.
        models : list of dict, optional
            The project's models, as the manifest holds them.

        Returns
        -------
        PyQt6.QtWidgets.QTreeWidgetItem
            The root of the tree.
        """

        self.clear()

        root = QTreeWidgetItem(self, [name])
        root.setData(0, KIND_ROLE, NodeKind.ROOT)
        for kind, title in (
            (NodeKind.MODELS, self.tr('Models')),
            (NodeKind.SIMULATIONS, self.tr('Simulations')),
            (NodeKind.STATISTICS, self.tr('Statistics')),
        ):
            child = QTreeWidgetItem(root, [title])
            child.setData(0, KIND_ROLE, kind)

        root.setExpanded(True)
        self.set_models(models or [])
        self.setCurrentItem(root)
        return root

    def set_models(self, models: list[dict]) -> None:
        """Show a project's models under the *Models* node.

        Parameters
        ----------
        models : list of dict
            The models, as the manifest holds them.  Each is shown by its name
            and remembers its UUID, which is what a context menu acts on: a
            model renamed is still the same model.
        """

        parent = self.node(NodeKind.MODELS)
        if parent is None:
            return
        parent.takeChildren()
        for model in models:
            item = QTreeWidgetItem(parent, [model.get('name', '')])
            item.setData(0, KIND_ROLE, NodeKind.MODEL)
            item.setData(0, MODEL_ROLE, model.get('uuid'))
        parent.setExpanded(bool(models))

    def model_of(self, item: QTreeWidgetItem | None) -> str | None:
        """Give the UUID of the model a node stands for.

        Parameters
        ----------
        item : PyQt6.QtWidgets.QTreeWidgetItem, optional
            The node.

        Returns
        -------
        str, optional
            The UUID, or ``None`` when the node is not a model.
        """

        return None if item is None else item.data(0, MODEL_ROLE)

    def model_items(self) -> list[QTreeWidgetItem]:
        """List the nodes standing for models.

        Returns
        -------
        list of PyQt6.QtWidgets.QTreeWidgetItem
            The children of the *Models* node, in the order they are shown.
        """

        parent = self.node(NodeKind.MODELS)
        if parent is None:
            return []
        return [parent.child(position) for position in range(parent.childCount())]

    def root(self) -> QTreeWidgetItem | None:
        """Give the root of the tree.

        Returns
        -------
        PyQt6.QtWidgets.QTreeWidgetItem, optional
            The project's node, or ``None`` while no project is shown.
        """

        return self.topLevelItem(0)

    def node(self, kind: NodeKind) -> QTreeWidgetItem | None:
        """Find the node of one kind.

        Parameters
        ----------
        kind : NodeKind
            What to look for.

        Returns
        -------
        PyQt6.QtWidgets.QTreeWidgetItem, optional
            The node, or ``None`` when the tree does not hold one.
        """

        root = self.root()
        if root is None:
            return None
        if kind is NodeKind.ROOT:
            return root
        for position in range(root.childCount()):
            child = root.child(position)
            if child.data(0, KIND_ROLE) is kind:
                return child
        return None

    @staticmethod
    def kind_of(item: QTreeWidgetItem | None) -> NodeKind | None:
        """Say what a node stands for.

        Parameters
        ----------
        item : PyQt6.QtWidgets.QTreeWidgetItem, optional
            The node.

        Returns
        -------
        NodeKind, optional
            Its kind, or ``None`` when there is no node.
        """

        return None if item is None else item.data(0, KIND_ROLE)

    # ------------------------------------------------------------------
    # The context menus
    # ------------------------------------------------------------------

    def menu_for(self, item: QTreeWidgetItem | None) -> QMenu | None:
        """Build the context menu of a node.

        Kept apart from showing it so that what a node offers can be checked
        without a menu going up and blocking on its own event loop.  The node
        under the pointer is made current before the menu goes up, so that an
        action reading the selection acts on what was right-clicked.

        Parameters
        ----------
        item : PyQt6.QtWidgets.QTreeWidgetItem, optional
            The node that was clicked.

        Returns
        -------
        PyQt6.QtWidgets.QMenu, optional
            The menu, or ``None`` when that node offers nothing.
        """

        entries = self.menus.get(self.kind_of(item)) or []
        if not entries:
            return None
        menu = QMenu(self)
        for entry in entries:
            if entry is None:
                menu.addSeparator()
            else:
                menu.addAction(entry)
        return menu

    def _on_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        """Report a double click on a model, and let every other node be.

        A double click on a group node is Qt's own way of folding it, which is
        left alone.

        Parameters
        ----------
        item : PyQt6.QtWidgets.QTreeWidgetItem
            The node that was double clicked.
        _column : int
            Which column it was, of the one this tree has.
        """

        identifier = self.model_of(item)
        if identifier:
            self.model_activated.emit(identifier)

    def _on_context_menu(self, position: QPoint) -> None:
        """Put the context menu of the node under the pointer up.

        Parameters
        ----------
        position : PyQt6.QtCore.QPoint
            Where the click landed, in the viewport's coordinates.
        """

        item = self.itemAt(position)
        if item is not None:
            self.setCurrentItem(item)
        menu = self.menu_for(item)
        if menu is not None:
            menu.exec(self.viewport().mapToGlobal(position))
