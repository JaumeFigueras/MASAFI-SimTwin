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

An arc is drawn from a connecting point, and **what it is drawn as is chosen on
the arc tool bar** along the top of the sheet — its shape and its kind.  With
arcs selected the bar shows theirs and a press changes them; with none it shows
what the next arc will be; and a press sets the next arc in both cases.  See
:mod:`~masafi_simtwin.documents.arc_toolbar`.

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
from masafi_simtwin.documents.arc import Arc, ArcKind, ArcShape
from masafi_simtwin.documents.arc_toolbar import ArcToolBar
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
    arc_tool_bar : masafi_simtwin.documents.arc_toolbar.ArcToolBar
        The bar the shape and the kind of an arc are chosen on.
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

        self.arc_tool_bar = ArcToolBar(self)
        self.add_tool_bar(self.arc_tool_bar)

        self.view.element_dropped.connect(self._on_element_dropped)
        self.view.connection_drawn.connect(self._on_connection_drawn)
        self.view.item_activated.connect(self._on_item_activated)
        self.view.arc_reshaped.connect(self._on_arc_reshaped)
        self.arc_tool_bar.shape_chosen.connect(self._on_shape_chosen)
        self.arc_tool_bar.kind_chosen.connect(self._on_kind_chosen)
        self.scene().selectionChanged.connect(self._on_selection_changed)
        self.show_arc_choice()

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
        shape_kind: ArcShape = ArcShape.STRAIGHT,
        kind: ArcKind = ArcKind.NORMAL,
        points: list[QPointF] | None = None,
    ) -> Arc | None:
        """Join two items of the net with an arc.

        The shape and the kind are given rather than read off the tool bar: this
        is also how a net read back out of a document is put on the sheet, and
        that must not depend on which button happens to be pressed.  The
        gesture that draws an arc is what reads the bar.

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
        shape_kind : masafi_simtwin.documents.arc.ArcShape, optional
            How it is drawn, straight by default.
        kind : masafi_simtwin.documents.arc.ArcKind, optional
            Whether it is normal or inhibitor, normal by default.
        points : list of PyQt6.QtCore.QPointF, optional
            Points to lead it through, in scene millimetres.

        Returns
        -------
        masafi_simtwin.documents.arc.Arc, optional
            The arc, already on the scene, or ``None`` when the two may not be
            joined — a Petri net is bipartite, so a place joins a transition and
            nothing else, itself included — or not by an arc of that kind: an
            inhibitor arc runs from a place to a transition.
        """

        if not source.may_connect_to(target) or not ArcKind(kind).permits(source, target):
            return None

        arc = Arc(
            source,
            target,
            source_port,
            target_port,
            shape_kind=shape_kind,
            kind=kind,
            points=points,
            snap=self.view.snap,
        )
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
        self, source, target, source_port: int, target_port: int, points: list
    ) -> None:
        """Join what has been drawn between, as the tool bar says to.

        The arc is of the view's :attr:`~masafi_simtwin.documents.canvas.CanvasView.new_arc_shape`
        and :attr:`~masafi_simtwin.documents.canvas.CanvasView.new_arc_kind`,
        which are what the tool bar set and what the preview was drawn as.  When
        points were laid for it on the way it is **led through them**, in the
        shape a route of that shape is — :attr:`~masafi_simtwin.documents.arc.ArcShape.routed`:
        straight lines between them for a straight arc, a curve through them for
        a curved one.

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
        points : list of PyQt6.QtCore.QPointF
            The points laid on the bare sheet on the way, in scene millimetres.
        """

        shape = self.view.new_arc_shape
        if points:
            shape = shape.routed
        self.add_arc(
            source, target, source_port, target_port, shape, self.view.new_arc_kind, points
        )

    # ------------------------------------------------------------------
    # The arc tool bar
    # ------------------------------------------------------------------

    @property
    def selected_arcs(self) -> list[Arc]:
        """list: The arcs that are selected, whatever else is selected with them."""

        return [item for item in self.scene().selectedItems() if isinstance(item, Arc)]

    def choose_arc_shape(self, shape: ArcShape) -> None:
        """Draw arcs in a shape: the selected ones now, and the next one drawn.

        Parameters
        ----------
        shape : masafi_simtwin.documents.arc.ArcShape
            The shape.
        """

        self.view.new_arc_shape = shape
        for arc in self.selected_arcs:
            self.view.set_arc_shape(arc, shape)
        self.show_arc_choice()

    def choose_arc_kind(self, kind: ArcKind) -> None:
        """Make arcs of a kind: the selected ones now, and the next one drawn.

        A selected arc that may not be of that kind is left as it is.  The
        tool bar greys out a kind that some selected arc may not be, so this is
        reached with one only when it is called directly.

        Parameters
        ----------
        kind : masafi_simtwin.documents.arc.ArcKind
            The kind.
        """

        self.view.new_arc_kind = kind
        for arc in self.selected_arcs:
            arc.set_kind(kind)
        self.show_arc_choice()

    def show_arc_choice(self) -> None:
        """Show on the tool bar what a press of it would act on.

        The bar says it in words first — *New Arc*, or how many arcs are
        selected — and then in its buttons.  The selected arcs when there are
        any: their shape and their kind, none checked where they differ, and a
        kind greyed out where one of them may not be of it.  Otherwise the next
        arc to be drawn, with every kind allowed — which way it will run is not
        known until it is drawn, and an inhibitor arc drawn out of a transition
        lights nothing up, which is the refusal made visible.
        """

        bar = self.arc_tool_bar
        arcs = self.selected_arcs
        bar.show_target(len(arcs))
        if not arcs:
            bar.show_choice(self.view.new_arc_shape, self.view.new_arc_kind)
            for kind in ArcKind:
                bar.allow_kind(kind, True)
            return

        shapes = {arc.shape_kind for arc in arcs}
        kinds = {arc.kind for arc in arcs}
        bar.show_choice(
            next(iter(shapes)) if len(shapes) == 1 else None,
            next(iter(kinds)) if len(kinds) == 1 else None,
        )
        for kind in ArcKind:
            bar.allow_kind(kind, all(arc.can_be(kind) for arc in arcs))

    def _on_shape_chosen(self, shape: ArcShape) -> None:
        """Act on a shape pressed on the tool bar.

        Connected as a bound method rather than as a lambda, for the reason
        :meth:`_on_element_dropped` is.

        Parameters
        ----------
        shape : masafi_simtwin.documents.arc.ArcShape
            The shape.
        """

        self.choose_arc_shape(shape)

    def _on_kind_chosen(self, kind: ArcKind) -> None:
        """Act on a kind pressed on the tool bar.

        Parameters
        ----------
        kind : masafi_simtwin.documents.arc.ArcKind
            The kind.
        """

        self.choose_arc_kind(kind)

    def _on_selection_changed(self) -> None:
        """Show the new selection's arcs on the tool bar."""

        self.show_arc_choice()

    def _on_arc_reshaped(self, arc: Arc) -> None:
        """Show an arc reshaped from its context menu, if it is selected.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc
            The arc.
        """

        self.show_arc_choice()

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
