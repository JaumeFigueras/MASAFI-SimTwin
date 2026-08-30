"""The Petri net document: the sheet a net is drawn on.

The editor is a :class:`~masafi_simtwin.documents.canvas.Canvas` — the ruled
sheet, its grid, its zoom and its panning — and what it adds is the net: which
model it is showing, and the places, transitions, arcs and tokens on it.  The
place is the first of those; the rest are the next piece of work and are
deliberately not invented here.

An element is put on the sheet by **dragging it out of the Libraries pane**.
The canvas takes the drop and says what was dropped and where — a sheet is the
paper rather than the drawing on it, so it has no opinion about places — and
:data:`ELEMENTS` is where this editor says what an element becomes.  A pair that
is not in it is a drag of something this editor cannot draw yet, which is left
where it fell rather than reported: the pane offers four libraries and one of
them is built, the same way
:data:`~masafi_simtwin.project.IMPLEMENTED_KINDS` offers four kinds of model.

The sheet is measured in millimetres like every other document of the
application.  A Petri net has no distance unit of its own, its places having no
position that means anything to the simulation, but the *drawing* of one has a
size — which is what the rulers show and what a printed sheet would be.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QDialog, QGraphicsItem, QWidget

from masafi_simtwin.dialogs.arc import ArcDialog
from masafi_simtwin.documents.arc import Arc
from masafi_simtwin.documents.canvas import Canvas
from masafi_simtwin.documents.net_item import NetItem
from masafi_simtwin.documents.place import Place
from masafi_simtwin.documents.ruler import MILLIMETRES, RulerUnit
from masafi_simtwin.documents.transition import Transition

#: What each element of the Libraries pane becomes on this sheet, by the library
#: it was taken from and its own key — an element is named by both together,
#: never by its key alone, a place in a timed net not being a place in a plain
#: one.  The factory is given what a scene item needs from the canvas: what to
#: snap a position to, and where it may be.
ELEMENTS: dict[tuple[str, str], Callable[..., QGraphicsItem]] = {
    ('pt-petri-net', 'place'): Place,
    ('pt-petri-net', 'transition'): Transition,
}


class PetriNetEditor(Canvas):
    """The sheet one Petri net is drawn on.

    Parameters
    ----------
    model : dict, optional
        The model's entry in the project manifest — its ``uuid``, ``name``,
        ``kind`` and ``units``.  The editor keeps it so that it can say which
        model it is showing; nothing is read back out of the project.
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.
    unit : masafi_simtwin.documents.ruler.RulerUnit, optional
        What the rulers count in, millimetres by default.

    Attributes
    ----------
    model : dict
        The manifest entry the editor was opened for.
    """

    def __init__(
        self,
        model: dict | None = None,
        parent: QWidget | None = None,
        unit: RulerUnit = MILLIMETRES,
    ) -> None:
        super().__init__(unit, parent)
        self.setObjectName('PetriNetEditor')
        self.model = dict(model or {})
        self.view.empty_note = self.tr('Drag an element out of the Libraries pane')
        self.view.element_dropped.connect(self._on_element_dropped)
        self.view.connection_drawn.connect(self._on_connection_drawn)
        self.view.item_activated.connect(self._on_item_activated)

    # ------------------------------------------------------------------
    # What is on the sheet
    # ------------------------------------------------------------------

    def add_element(self, library: str, element: str, position: QPointF):
        """Put one element of a library on the sheet.

        Parameters
        ----------
        library : str
            The key of the library it was taken from.
        element : str
            The key of the element.
        position : PyQt6.QtCore.QPointF
            Where it goes, in scene millimetres.  It is the *centre* of the
            item, which is what a drop puts under the pointer, and it is snapped
            by the item itself like every other move of one.

        Returns
        -------
        PyQt6.QtWidgets.QGraphicsItem, optional
            The item, already on the scene, or ``None`` when this editor cannot
            draw that element yet.
        """

        factory = ELEMENTS.get((library, element))
        if factory is None:
            return None

        item = factory(self.view.snap, self.view.sceneRect)
        self.scene().addItem(item)
        item.setPos(position)
        return item

    @property
    def places(self) -> list[Place]:
        """list: The places on the sheet, in the order the scene holds them."""

        return self.items_of(Place)

    @property
    def transitions(self) -> list[Transition]:
        """list: The transitions on the sheet, in the order the scene holds them."""

        return self.items_of(Transition)

    @property
    def arcs(self) -> list[Arc]:
        """list: The arcs on the sheet, in the order the scene holds them."""

        return self.items_of(Arc)

    def add_arc(
        self,
        source: NetItem,
        target: NetItem,
        source_port: int | None = None,
        target_port: int | None = None,
    ) -> Arc | None:
        """Join two items of the net with an arc.

        Parameters
        ----------
        source : masafi_simtwin.documents.net_item.NetItem
            The item the arc leaves.
        target : masafi_simtwin.documents.net_item.NetItem
            The item it enters, which is where the arrowhead goes.
        source_port : int, optional
            Which connecting point of the source it leaves by — the one that was
            pressed, when a person drew it.  Left out, the one facing the target
            and free of arcs is taken.
        target_port : int, optional
            Which of the target's it enters by.  Left out, as above.

        Returns
        -------
        masafi_simtwin.documents.arc.Arc, optional
            The arc, already on the scene, or ``None`` when the two may not be
            joined — a Petri net is bipartite, so a place joins a transition and
            nothing else, itself included.
        """

        if not source.may_connect_to(target):
            return None

        arc = Arc(source, target, source_port, target_port)
        self.scene().addItem(arc)
        return arc

    def items_of(self, kind: type) -> list:
        """Give the items of one kind that are on the sheet.

        Parameters
        ----------
        kind : type
            What to look for.

        Returns
        -------
        list
            The items, in the order the scene holds them.
        """

        return [item for item in self.scene().items() if isinstance(item, kind)]

    def _on_element_dropped(self, library: str, element: str, position: QPointF) -> None:
        """Put down what was dragged out of the Libraries pane.

        Connected as a bound method rather than as a lambda: the signal belongs
        to a child of this widget, and a lambda capturing ``self`` outlives the
        widget it captured.

        Parameters
        ----------
        library : str
            The key of the library the element was taken from.
        element : str
            The key of the element.
        position : PyQt6.QtCore.QPointF
            Where it was let go, in scene millimetres, already snapped.
        """

        self.add_element(library, element, position)

    def _on_connection_drawn(
        self, source, target, source_port: int, target_port: int
    ) -> None:
        """Join what has been drawn between, if the two may be joined.

        Connected as a bound method rather than as a lambda, for the reason
        :meth:`_on_element_dropped` is.

        Parameters
        ----------
        source : masafi_simtwin.documents.net_item.NetItem
            The item the arc was drawn from.
        target : masafi_simtwin.documents.net_item.NetItem
            The item it was drawn to.
        source_port : int
            Which connecting point of the source the press landed on, which is
            the one the arc leaves by from now on.
        target_port : int
            Which of the target's it was let go nearest, which is the one it
            arrives at from now on.
        """

        self.add_arc(source, target, source_port, target_port)

    def edit_arc(self, arc: Arc) -> bool:
        """Ask what an arc carries, and set it.

        The weight is the only property a P/T arc has, and until the right-hand
        properties pane exists a double click is where it is asked for.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc
            The arc to ask about.

        Returns
        -------
        bool
            Whether the weight was changed.
        """

        dialog = ArcDialog(arc.weight, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        changed = dialog.weight != arc.weight
        arc.weight = dialog.weight
        return changed

    def _on_item_activated(self, item) -> None:
        """Open what was double-clicked, when it is something that opens.

        Connected as a bound method rather than as a lambda, for the reason
        :meth:`_on_element_dropped` is.

        Parameters
        ----------
        item : PyQt6.QtWidgets.QGraphicsItem, optional
            What was under the pointer, or ``None`` for the bare sheet.
        """

        if isinstance(item, Arc):
            self.edit_arc(item)

    @property
    def model_id(self) -> str:
        """str: The UUID of the model on the sheet, which is also its tab key."""

        return self.model.get('uuid', '')

    @property
    def model_name(self) -> str:
        """str: What the model is called, which is what its tab says."""

        return self.model.get('name', '')
