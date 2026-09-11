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
:mod:`~masafi_simtwin.documents.arc_toolbar`.  Only the kinds of arc that are
built can be chosen there: an inhibitor arc is greyed out until MASAFI-sim-petri
has them.

Every place and transition is given a **name** as it is put on the sheet —
``P1``, ``T1`` — invented until there is somewhere to type one, and unique in the
net, since that is what MASAFI-sim-petri knows a node by.  Nor may two arcs of
one kind run the same way between the same two items; see
:func:`~masafi_simtwin.documents.arc.arc_between`.

The net goes out of the editor and back into it as a
:class:`~simtwin_core.petri_net.NetDocument` — :meth:`PetriNetEditor.to_document`
and :meth:`PetriNetEditor.load_document` — which is everything that decides what
the drawing looks like and nothing of Qt.  That is what is saved, and what an
adapter reads; the editor never sees a file.

The sheet is measured in millimetres like every other document of the
application.  A Petri net has no distance unit of its own, its places having no
position that means anything to the simulation, but the *drawing* of one has a
size — which is what the rulers show and what a printed sheet would be.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtWidgets import QDialog, QGraphicsItem, QWidget

from masafi_simtwin.dialogs.arc import ArcDialog
from masafi_simtwin.documents.arc import (
    IMPLEMENTED_ARC_KINDS,
    Arc,
    ArcKind,
    ArcShape,
    arc_between,
)
from masafi_simtwin.documents.arc_toolbar import ArcToolBar
from masafi_simtwin.documents.canvas import Canvas
from masafi_simtwin.documents.net_item import NetItem
from masafi_simtwin.documents.place import Place
from masafi_simtwin.documents.ruler import MILLIMETRES, RulerUnit
from masafi_simtwin.documents.transition import Transition
from simtwin_core.petri_net import (
    ArcData,
    GuideData,
    NetDocument,
    PlaceData,
    TransitionData,
)

#: What each element of the Libraries pane becomes on this sheet, by the library
#: it was taken from and its own key — an element is named by both together,
#: never by its key alone, a place in a timed net not being a place in a plain
#: one.  The factory is given what a scene item needs from the canvas: what to
#: snap a position to, and where it may be.
ELEMENTS: dict[tuple[str, str], Callable[..., QGraphicsItem]] = {
    ('pt-petri-net', 'place'): Place,
    ('pt-petri-net', 'transition'): Transition,
}

#: What each kind of node of a document is drawn as.
NODE_ITEMS: dict[type, type[NetItem]] = {
    PlaceData: Place,
    TransitionData: Transition,
}

#: What a guide's orientation is called in a document, which is text.
GUIDE_ORIENTATIONS: dict[Qt.Orientation, str] = {
    Qt.Orientation.Horizontal: 'horizontal',
    Qt.Orientation.Vertical: 'vertical',
}


def drawn_route(arc: Arc) -> tuple:
    """Give where the points an arc is led through are on the sheet.

    For a reader that knows nothing of the chord frame the points are kept in —
    PNML's own ``graphics`` — so it can draw the route too.  A straight arc and a
    single bow are led through nothing, whatever points they may be keeping for
    when they are made an S or an L again.

    Parameters
    ----------
    arc : masafi_simtwin.documents.arc.Arc
        The arc.

    Returns
    -------
    tuple
        The points, in millimetres and in order from the source, or nothing.
    """

    if not arc.shape_kind.led_through_points:
        return ()
    return tuple((point.x(), point.y()) for point in arc.curve_points())


def held_port(index: int | None, item: NetItem) -> int | None:
    """Hold a connecting point read from a document to the ones a node has.

    Parameters
    ----------
    index : int, optional
        The point, or ``None`` for the one facing the other end.
    item : masafi_simtwin.documents.net_item.NetItem
        The node it belongs to.

    Returns
    -------
    int, optional
        The index, no further than the node's last point; ``None`` stays
        ``None``, for the arc to work out.
    """

    return None if index is None else min(index, len(item.ports()) - 1)


def reading_order(name: str) -> list:
    """Give the key a name sorts by, numbers counted as numbers.

    ``P2`` comes before ``P10``, which is the order a person reads a net in, and
    the order a document holds its nodes in — so a file written twice from the
    same net comes out the same, and a change to a net is a small change to its
    file.

    Parameters
    ----------
    name : str
        The name.

    Returns
    -------
    list
        Its runs of letters and of digits, the digits as integers.  Splitting on
        the digits always alternates text and number, starting with text, so two
        keys compare element by element without mixing the two.
    """

    return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', name)]


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
        item.name = self.next_name(item.NAME_PREFIX)
        self.scene().addItem(item)
        item.setPos(position)
        return item

    @property
    def names(self) -> list[str]:
        """list: The names of the places and transitions on the sheet."""

        return [item.name for item in self.items_of(NetItem) if item.name]

    def next_name(self, prefix: str) -> str:
        """Invent a name for a new place or transition.

        The prefix and the number after the **highest** already in use — ``P1``,
        ``P2`` for places, ``T1``, ``T2`` for transitions — so a name deleted
        from the middle of a net is not quietly handed out again.  Invented only
        until there is somewhere to type a name, and made to keep the rules
        names will be held to: unique in the net, and a Python identifier with no
        digit first.  A place and a transition cannot clash, their prefixes
        being different.

        Parameters
        ----------
        prefix : str
            What the name begins with, the item's
            :attr:`~masafi_simtwin.documents.net_item.NetItem.NAME_PREFIX`.

        Returns
        -------
        str
            The name.
        """

        pattern = re.compile(rf'{re.escape(prefix)}(\d+)')
        numbers = [
            int(found.group(1))
            for name in self.names
            if (found := pattern.fullmatch(name)) is not None
        ]
        return f'{prefix}{max(numbers, default=0) + 1}'

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
            inhibitor arc runs from a place to a transition, and no two arcs of
            one kind run the same way between the same two items.
        """

        if (
            not source.may_connect_to(target)
            or not ArcKind(kind).permits(source, target)
            or arc_between(source, target, kind) is not None
        ):
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

        A kind that is not built yet —
        :data:`~masafi_simtwin.documents.arc.IMPLEMENTED_ARC_KINDS` — is greyed
        out in both cases.
        """

        bar = self.arc_tool_bar
        arcs = self.selected_arcs
        bar.show_target(len(arcs))
        if not arcs:
            bar.show_choice(self.view.new_arc_shape, self.view.new_arc_kind)
            for kind in ArcKind:
                bar.allow_kind(kind, kind in IMPLEMENTED_ARC_KINDS)
            return

        shapes = {arc.shape_kind for arc in arcs}
        kinds = {arc.kind for arc in arcs}
        bar.show_choice(
            next(iter(shapes)) if len(shapes) == 1 else None,
            next(iter(kinds)) if len(kinds) == 1 else None,
        )
        for kind in ArcKind:
            bar.allow_kind(
                kind, kind in IMPLEMENTED_ARC_KINDS and all(arc.can_be(kind) for arc in arcs)
            )

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

    # ------------------------------------------------------------------
    # The net as a document
    # ------------------------------------------------------------------

    def to_document(self) -> NetDocument:
        """Describe the net on the sheet, and nothing of how it is shown.

        Everything that decides what the drawing looks like is in it — where
        every node is, which connecting points every arc is attached to, and
        how every arc bends, as the arc itself keeps it — so that a net loaded
        from it with :meth:`load_document` is drawn exactly as this one is.  An
        arc's bends are written as they **are**, never as *untouched*, so a
        default that changes later does not reshape a net already drawn.

        The order is fixed: places and transitions by name, numbers counted as
        numbers (:func:`reading_order`), and arcs by the names of their two ends
        and then their kind.  The scene holds its items in stacking order, which
        changes as they are selected, and a file that changed with it would be a
        different file every time it was written.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net, its guides, and the model it is.
        """

        def node_order(item: NetItem) -> list:
            return reading_order(item.name)

        arcs = sorted(
            self.arcs,
            key=lambda arc: (
                reading_order(arc.source.name),
                reading_order(arc.target.name),
                arc.kind.value,
            ),
        )
        return NetDocument(
            model_uuid=self.model_id,
            places=tuple(
                PlaceData(item.uuid, item.name, (item.pos().x(), item.pos().y()))
                for item in sorted(self.places, key=node_order)
            ),
            transitions=tuple(
                TransitionData(item.uuid, item.name, (item.pos().x(), item.pos().y()))
                for item in sorted(self.transitions, key=node_order)
            ),
            arcs=tuple(
                ArcData(
                    arc.uuid,
                    arc.source.uuid,
                    arc.target.uuid,
                    arc.source_port,
                    arc.target_port,
                    arc.weight,
                    arc.kind.value,
                    arc.shape_kind.value,
                    arc.control_frames,
                    arc.point_frames,
                    drawn_route(arc),
                )
                for arc in arcs
            ),
            guides=tuple(
                GuideData(GUIDE_ORIENTATIONS[guide.orientation], guide.position)
                for guide in self.guides
            ),
        )

    def load_document(self, document: NetDocument) -> None:
        """Draw a net described by a document, in place of what is on the sheet.

        The nodes keep the UUIDs and the names they were written with, and the
        arcs their UUIDs, connecting points and bends, so the net is the one that
        was saved rather than one like it.  Invented names go on after the
        highest loaded.  The document has already kept every rule a net keeps —
        :class:`~simtwin_core.petri_net.NetDocument` refuses one that does not —
        so nothing here refuses anything.

        Two things are made to fit rather than taken as they are.  A position is
        snapped and held on the sheet, as every position of a node is, so a net
        written by another tool lands on the millimetre.  And a connecting point
        a node does not have is held to its last one, as
        :meth:`~masafi_simtwin.documents.net_item.NetItem.scene_port` holds it
        when it is drawn — so the arc that is drawn is the arc that is written
        back.  A connecting point the document leaves as ``None`` is the one
        facing the other end that no arc is on yet, as it is for an arc drawn
        without one.  An arc's ``route`` is not read at all: the arc is drawn
        from its points.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.  Its ``model_uuid`` is not checked: which model the sheet
            shows is the project's to say, not the file's.
        """

        self.clear_sheet()

        nodes: dict[str, NetItem] = {}
        for data in (*document.places, *document.transitions):
            item = NODE_ITEMS[type(data)](self.view.snap, self.view.sceneRect)
            item.uuid = data.uuid
            item.name = data.name
            self.scene().addItem(item)
            item.setPos(QPointF(*data.position))
            nodes[data.uuid] = item

        for data in document.arcs:
            source, target = nodes[data.source], nodes[data.target]
            arc = Arc(
                source,
                target,
                held_port(data.source_port, source),
                held_port(data.target_port, target),
                weight=data.weight,
                shape_kind=ArcShape(data.shape),
                kind=ArcKind(data.kind),
                snap=self.view.snap,
                uuid=data.uuid,
            )
            arc.restore_bends(data.controls, data.points)
            self.scene().addItem(arc)

        orientations = {text: orientation for orientation, text in GUIDE_ORIENTATIONS.items()}
        for data in document.guides:
            self.add_guide(orientations[data.orientation], data.position)

        self.show_arc_choice()

    def clear_sheet(self) -> None:
        """Take the whole net off the sheet, and its guides."""

        for item in self.items_of(NetItem):
            self.view.remove(item)
        for arc in self.arcs:
            self.view.remove(arc)
        self.clear_guides()

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
