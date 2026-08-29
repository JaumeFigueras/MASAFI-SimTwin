"""The Libraries pane: the elements a model is built out of.

A library is a family of elements that go together — the plain place-transition
net, the timed one, the attributed timed one — and the pane is the tree of them.
It is the palette a model is drawn from: dragging an element onto a canvas is
what it is for, and that is the next piece of work.  What is here is the tree
itself, its shape and its icons.

The elements repeat across the libraries on purpose.  A *Place* in a P/T net and
a *Place* in a timed net are the same idea and are shown the same way, and which
library one was taken from is what says how it behaves — so an element is named
by its library and its key together, never by its key alone.

The names are built where the tree is, through ``tr()``, and what does not
change from one language to the next — the keys, and the Material Symbol each
element is drawn with — is declared beside them.  The icons are rebuilt when the
palette changes, the way :mod:`masafi_simtwin.icons` does for a button: a tree
item is not an icon target, having ``setIcon(column, icon)`` rather than
``setIcon(icon)``, so it cannot be registered there and looks after itself here.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QWidget

from masafi_simtwin import icons


@dataclass(frozen=True)
class Element:
    """One thing a model can be built out of.

    Attributes
    ----------
    key : str
        What it is, in ASCII and never shown: what a drag will carry.
    name : str
        Its translated name, which is what the tree says.
    icon : str
        The Material Symbol it is drawn with.
    enabled : bool
        Whether it can be used.  A placeholder saying a library is not built yet
        is shown and cannot be taken, which is how the rest of the application
        offers what is coming without pretending it works.
    """

    key: str
    name: str
    icon: str
    enabled: bool = True


@dataclass(frozen=True)
class Library:
    """A family of elements that belong together.

    Attributes
    ----------
    key : str
        What the family is, in ASCII and never shown.
    name : str
        Its translated name.
    icon : str
        The Material Symbol it is drawn with.
    elements : tuple of Element
        What it holds, in the order it is shown.
    """

    key: str
    name: str
    icon: str
    elements: tuple[Element, ...]


#: Where the key of the library a node belongs to is kept, on the item itself.
#: A library node carries its own; an element node carries its library's, which
#: is half of what names an element.
LIBRARY_ROLE = Qt.ItemDataRole.UserRole

#: Where the key of the element a node stands for is kept.  A library node has
#: none, which is what tells the two kinds of node apart.
ELEMENT_ROLE = Qt.ItemDataRole.UserRole + 1

#: Where the name of the Material Symbol a node is drawn with is kept, so that
#: every icon can be built again when the palette changes under it.
ICON_ROLE = Qt.ItemDataRole.UserRole + 2

#: Side, in pixels, of the icons in the tree.
ELEMENT_ICON_SIZE = 20


class LibraryTree(QTreeWidget):
    """The tree of libraries and the elements in them.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('LibraryTree')
        self.setHeaderHidden(True)
        self.setColumnCount(1)

        self._fill(self.libraries())

    # ------------------------------------------------------------------
    # What the libraries hold
    # ------------------------------------------------------------------

    def libraries(self) -> tuple[Library, ...]:
        """Declare the libraries and what is in them.

        The names go through ``tr()`` here rather than being declared at the top
        of the module, because that is where a translator's tools find them and
        where a ``QObject`` is to call it on.

        Returns
        -------
        tuple of Library
            The libraries, in the order they are shown.
        """

        place = Element('place', self.tr('Place'), 'radio_button_unchecked')
        transition = Element('transition', self.tr('Transition'), 'rectangle')
        timed_transition = Element(
            'timed-transition', self.tr('Timed Transition'), 'timer'
        )
        attribute = Element('attribute', self.tr('Attribute'), 'label')

        return (
            Library(
                'pt-petri-net',
                self.tr('P/T Petri Net'),
                'schema',
                (place, transition),
            ),
            Library(
                'timed-petri-net',
                self.tr('Timed Petri Net'),
                'schedule',
                (place, transition, timed_transition),
            ),
            Library(
                'attributed-timed-petri-net',
                self.tr('Attributed Timed Petri Net'),
                'data_object',
                (place, transition, timed_transition, attribute),
            ),
            Library(
                'process-flow',
                self.tr('Process Flow'),
                'conveyor_belt',
                (
                    Element(
                        'unimplemented',
                        self.tr('Unimplemented'),
                        'construction',
                        enabled=False,
                    ),
                ),
            ),
        )

    def _fill(self, libraries: tuple[Library, ...]) -> None:
        """Build the tree, replacing whatever was in it.

        Parameters
        ----------
        libraries : tuple of Library
            What to show.
        """

        self.clear()
        for library in libraries:
            parent = QTreeWidgetItem(self, [library.name])
            parent.setData(0, LIBRARY_ROLE, library.key)
            parent.setData(0, ICON_ROLE, library.icon)
            for element in library.elements:
                item = QTreeWidgetItem(parent, [element.name])
                item.setData(0, LIBRARY_ROLE, library.key)
                item.setData(0, ELEMENT_ROLE, element.key)
                item.setData(0, ICON_ROLE, element.icon)
                if not element.enabled:
                    item.setDisabled(True)
            parent.setExpanded(True)
        self._apply_icons()

    # ------------------------------------------------------------------
    # What is in the tree
    # ------------------------------------------------------------------

    def nodes(self) -> list[QTreeWidgetItem]:
        """List every node of the tree, a library before what is in it.

        Returns
        -------
        list of PyQt6.QtWidgets.QTreeWidgetItem
            The libraries and their elements, in the order they are shown.
        """

        found: list[QTreeWidgetItem] = []
        for position in range(self.topLevelItemCount()):
            parent = self.topLevelItem(position)
            found.append(parent)
            found.extend(parent.child(index) for index in range(parent.childCount()))
        return found

    def library_of(self, item: QTreeWidgetItem | None) -> str | None:
        """Give the key of the library a node belongs to.

        Parameters
        ----------
        item : PyQt6.QtWidgets.QTreeWidgetItem, optional
            The node.

        Returns
        -------
        str, optional
            The key, or ``None`` when there is no node.
        """

        return None if item is None else item.data(0, LIBRARY_ROLE)

    def element_of(self, item: QTreeWidgetItem | None) -> str | None:
        """Give the key of the element a node stands for.

        Parameters
        ----------
        item : PyQt6.QtWidgets.QTreeWidgetItem, optional
            The node.

        Returns
        -------
        str, optional
            The key, or ``None`` when the node is a library rather than an
            element — which is what tells the two apart.
        """

        return None if item is None else item.data(0, ELEMENT_ROLE)

    # ------------------------------------------------------------------
    # Following the theme
    # ------------------------------------------------------------------

    def _apply_icons(self) -> None:
        """Draw every icon of the tree against the palette in force now."""

        for item in self.nodes():
            name = item.data(0, ICON_ROLE)
            if name:
                item.setIcon(0, icons.icon(name, size=ELEMENT_ICON_SIZE))

    def changeEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Build the icons again when the theme changes under them.

        A Material Symbol is tinted with the palette at the moment it is made,
        so an icon made under the light theme stays dark grey in the dark one.
        :func:`masafi_simtwin.icons.refresh` does this for the buttons and the
        actions it was given; a tree item cannot be given to it, so the tree
        answers for its own.

        Parameters
        ----------
        event : PyQt6.QtCore.QEvent
            The event that changed the widget.
        """

        super().changeEvent(event)
        if event.type() == event.Type.PaletteChange:
            self._apply_icons()
