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
from dataclasses import dataclass
from uuid import uuid4

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QUndoCommand, QUndoStack
from PyQt6.QtWidgets import QGraphicsItem, QWidget

from masafi_simtwin.documents.arc import (
    IMPLEMENTED_ARC_KINDS,
    Arc,
    ArcKind,
    ArcShape,
    arc_between,
)
from masafi_simtwin.documents.arc_toolbar import ArcToolBar
from masafi_simtwin.documents.canvas import Canvas
from masafi_simtwin.documents.guide import Guide
from masafi_simtwin.documents.net_item import NetItem
from masafi_simtwin.documents.place import Place
from masafi_simtwin.documents.ruler import MILLIMETRES, RulerUnit
from masafi_simtwin.documents.transition import Transition
from simtwin_core.operations import (
    AddArc,
    AddGuide,
    AddNode,
    Change,
    MoveArcEnd,
    MoveGuide,
    MoveNode,
    Operation,
    RemoveArc,
    RemoveGuide,
    RemoveNode,
    SetArcBends,
    SetArcKind,
    SetArcShape,
    SetArcWeight,
    SetDescription,
    SetNodeName,
    SetTokens,
)
from simtwin_core.petri_net import (
    ArcData,
    GuideData,
    NetDocument,
    PlaceData,
    TransitionData,
    name_problem,
    reading_order,
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

#: The same the other way round, for a guide read out of one.
GUIDE_WAYS: dict[str, Qt.Orientation] = {
    text: orientation for orientation, text in GUIDE_ORIENTATIONS.items()
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


def _bends(arc: Arc, before) -> list:
    """Give the operation that says how an arc bends now, when it has changed.

    Parameters
    ----------
    arc : masafi_simtwin.documents.arc.Arc
        The arc.
    before : tuple
        Its control points and its points before, in the chord's frame.

    Returns
    -------
    list
        One :class:`~simtwin_core.operations.SetArcBends`, or nothing when the
        arc bends as it did.
    """

    after = (arc.control_frames, arc.point_frames)
    if after == before:
        return []
    return [SetArcBends(arc.uuid, before[0], before[1], after[0], after[1])]


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


@dataclass(frozen=True)
class Selection:
    """What is selected on a sheet, as descriptions rather than as items.

    What the Properties pane is handed, so that it can show a place without ever
    touching the scene it is drawn on.  Guides are left out: a guide has no
    properties to show.

    Attributes
    ----------
    places : tuple of simtwin_core.petri_net.PlaceData
        The places selected, by name.
    transitions : tuple of simtwin_core.petri_net.TransitionData
        The transitions selected, by name.
    arcs : tuple of simtwin_core.petri_net.ArcData
        The arcs selected, by the names of their ends and their kind.
    names : tuple of str
        The names of every place and transition of the net, selected or not —
        what a new name is checked against, without the scene being asked.
    node_names : tuple of tuple
        Every place and transition of the net as a ``(uuid, name)`` pair, which
        is how the ends of a selected arc are named.
    """

    places: tuple = ()
    transitions: tuple = ()
    arcs: tuple = ()
    names: tuple = ()
    node_names: tuple = ()

    def __bool__(self) -> bool:
        """Say whether anything with properties is selected."""

        return bool(self.places or self.transitions or self.arcs)


def node_data(item: NetItem):
    """Describe a place or a transition as it stands on the sheet.

    Parameters
    ----------
    item : masafi_simtwin.documents.net_item.NetItem
        The item.

    Returns
    -------
    simtwin_core.petri_net.PlaceData or simtwin_core.petri_net.TransitionData
        What it is: its identity, its name, where its centre is, its
        description, and a place's tokens.
    """

    position = (item.pos().x(), item.pos().y())
    if isinstance(item, Place):
        return PlaceData(item.uuid, item.name, position, item.tokens, item.description)
    return TransitionData(item.uuid, item.name, position, item.description)


def guide_data(guide: Guide) -> GuideData:
    """Describe a guide as it lies on the sheet.

    Parameters
    ----------
    guide : masafi_simtwin.documents.guide.Guide
        The guide.

    Returns
    -------
    simtwin_core.petri_net.GuideData
        Which way it lies and where it is.
    """

    return GuideData(GUIDE_ORIENTATIONS[guide.orientation], guide.position)


def arc_data(arc: Arc) -> ArcData:
    """Describe an arc as it is drawn.

    Parameters
    ----------
    arc : masafi_simtwin.documents.arc.Arc
        The arc.

    Returns
    -------
    simtwin_core.petri_net.ArcData
        What it is, bends and all — never *untouched*, because an arc on a
        sheet is always drawn some way, and an operation must say which.
    """

    return ArcData(
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


class EditCommand(QUndoCommand):
    """One change of a net, on a sheet's undo stack.

    Parameters
    ----------
    editor : PetriNetEditor
        The document whose sheet the change is made on.
    change : simtwin_core.operations.Change
        What the change is.
    text : str
        What it is called where a person reads it: *Undo Draw Arc*.
    applied : bool, optional
        Whether the sheet already shows the change.  It does whenever a person
        made it by hand — the item is already where it was dragged to, the arc
        already drawn — and a stack pushes a command by **doing** it, so the
        first doing is passed over rather than made twice.
    parent : PyQt6.QtGui.QUndoCommand, optional
        Parent command.
    """

    def __init__(self, editor, change: Change, text: str, applied: bool = False, parent=None):
        super().__init__(text, parent)
        self._editor = editor
        self._change = change
        self._done = applied

    @property
    def change(self) -> Change:
        """simtwin_core.operations.Change: What the command does."""

        return self._change

    def redo(self) -> None:
        """Make the change, or pass over the first time when it is already made.

        Either way it is **reported**: the sheet now shows it, whether this
        command put it there or the gesture did.
        """

        if self._done:
            self._done = False
        else:
            self._editor.apply(self._change)
        self._editor.report_change(self._change)

    def undo(self) -> None:
        """Put the change back, and report the inverse.

        An undo is not a special kind of entry in a journal: it is the change
        that undoes it, so that replaying is a straight line from the last save
        to what the sheet shows now.
        """

        self._editor.apply(self._change.inverse())
        self._editor.report_change(self._change.inverse())


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
    change_recorded : PyQt6.QtCore.pyqtSignal
        Emitted with this model's UUID and every change that reaches the sheet:
        a gesture, a change done again, and — as its **inverse** — a change
        undone.  So what it says is the stream of what the net has actually
        become, which is what a journal writes and replays.
    arc_activated : PyQt6.QtCore.pyqtSignal
        Emitted with this model's UUID and an arc's when the arc is
        double-clicked, which is how its weight is asked to be edited.
    selection_changed : PyQt6.QtCore.pyqtSignal
        Emitted with this model's UUID whenever what is selected on the sheet
        changes, so that a window can ask for :meth:`selection` without a lambda
        to tell it which document spoke.
    modified_changed : PyQt6.QtCore.pyqtSignal
        Emitted with this model's UUID, and whether the sheet now differs from
        what was last written, whenever that answer changes — which is what
        the mark on a tab shows.  The editor passes it on from its own undo
        stack, so a window listening needs no connection to a child of the
        editor, and learns which model spoke without a lambda to tell it.
    """

    change_recorded = pyqtSignal(str, object)
    modified_changed = pyqtSignal(str, bool)
    selection_changed = pyqtSignal(str)
    arc_activated = pyqtSignal(str, str)

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

        self.undo_stack = QUndoStack(self)
        self.undo_stack.cleanChanged.connect(self._on_clean_changed)
        self.arc_tool_bar = ArcToolBar(self)
        self.add_tool_bar(self.arc_tool_bar)

        self.view.element_dropped.connect(self._on_element_dropped)
        self.view.connection_drawn.connect(self._on_connection_drawn)
        self.view.item_activated.connect(self._on_item_activated)
        self.view.arc_shape_asked.connect(self._on_arc_shape_asked)
        self.view.arc_end_asked.connect(self._on_arc_end_asked)
        self.view.deletion_asked.connect(self._on_deletion_asked)
        self.view.items_moved.connect(self._on_items_moved)
        self.view.guides_moved.connect(self._on_guides_moved)
        self.view.arcs_shaped.connect(self._on_arcs_shaped)
        self.view.arc_point_asked.connect(self._on_arc_point_asked)
        self.view.arc_point_removal_asked.connect(self._on_arc_point_removal_asked)
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
        item.uuid = str(uuid4())
        self.scene().addItem(item)
        item.setPos(position)
        self.record(Change('add-element', (AddNode(node_data(item)),)))
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
        until there is somewhere to type a name, and made to keep the rule
        names are held to, :func:`~simtwin_core.petri_net.name_problem`.  Names
        are unique ignoring case, so a number is counted whatever the case of
        its prefix: beside a ``p7`` the next place is ``P8``, never a ``P7`` that
        would clash with it.  A place and a transition cannot clash, their
        prefixes being different.

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

        pattern = re.compile(rf'{re.escape(prefix)}(\d+)', re.IGNORECASE)
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
        self.record(Change('draw-arc', (AddArc(arc_data(arc)),)))
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
        self.reshape_arcs(self.selected_arcs, shape)
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
        operations = []
        for arc in self.selected_arcs:
            was = arc.kind.value
            if arc.set_kind(kind):
                operations.append(SetArcKind(arc.uuid, was, kind.value))
        self.record(Change('set-arc-kind', tuple(operations)))
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
        """Show the new selection's arcs on the tool bar, and say it changed."""

        self.show_arc_choice()
        self.selection_changed.emit(self.model_id)

    def selection(self) -> Selection:
        """Describe what is selected on the sheet.

        Returns
        -------
        Selection
            The places, transitions and arcs selected, each as the description
            :meth:`to_document` would give of it, in a fixed order.
        """

        selected = self.scene().selectedItems()
        places = [item for item in selected if isinstance(item, Place)]
        transitions = [item for item in selected if isinstance(item, Transition)]
        arcs = [item for item in selected if isinstance(item, Arc)]
        by_name = lambda item: reading_order(item.name)  # noqa: E731
        return Selection(
            names=tuple(self.names),
            node_names=tuple((item.uuid, item.name) for item in self.items_of(NetItem)),
            places=tuple(node_data(item) for item in sorted(places, key=by_name)),
            transitions=tuple(node_data(item) for item in sorted(transitions, key=by_name)),
            arcs=tuple(
                arc_data(arc)
                for arc in sorted(
                    arcs,
                    key=lambda arc: (
                        reading_order(arc.source.name),
                        reading_order(arc.target.name),
                        arc.kind.value,
                    ),
                )
            ),
        )

    def reshape_arcs(self, arcs, shape: ArcShape) -> None:
        """Draw some arcs in a shape, and record it as one change.

        Choosing a shape is a **gesture**: an arc that is led through points and
        has none is given that shape's own, so a shape named after its look
        looks like it at once.  What the change records is what the arc then
        *is* — the shape, and the points if they were seeded — so undoing gives
        back what was there rather than what a default happens to be later.

        Parameters
        ----------
        arcs : collections.abc.Iterable of masafi_simtwin.documents.arc.Arc
            The arcs.
        shape : masafi_simtwin.documents.arc.ArcShape
            The shape.
        """

        operations = []
        for arc in arcs:
            was_shape = arc.shape_kind.value
            bends = (arc.control_frames, arc.point_frames)
            arc.shape_kind = shape
            if arc.shape_kind.value != was_shape:
                operations.append(SetArcShape(arc.uuid, was_shape, arc.shape_kind.value))
            operations.extend(_bends(arc, bends))
        self.record(Change('set-arc-shape', tuple(operations)))

    def insert_arc_point(self, arc: Arc, at: QPointF) -> None:
        """Put another point into an arc, and record it.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc
            The arc.
        at : PyQt6.QtCore.QPointF
            Where it was aimed at, in scene millimetres.
        """

        bends = (arc.control_frames, arc.point_frames)
        arc.insert_point(at)
        self.record(Change('add-arc-point', tuple(_bends(arc, bends))))

    def take_arc_point_out(self, arc: Arc, index: int) -> None:
        """Take one point out of an arc, and record it.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc
            The arc.
        index : int
            Which of its points, counting from the source.
        """

        bends = (arc.control_frames, arc.point_frames)
        arc.remove_point(index)
        self.record(Change('remove-arc-point', tuple(_bends(arc, bends))))

    def guide_drawn(self, guide) -> None:
        """Record a guide pulled off a ruler, once it has been kept.

        Parameters
        ----------
        guide : masafi_simtwin.documents.guide.Guide
            The guide, already on the sheet.
        """

        self.record(Change('add-guide', (AddGuide(guide_data(guide)),)))

    def _on_items_moved(self, moves) -> None:
        """Record a drag of one or more items as one change.

        Parameters
        ----------
        moves : list
            ``(item, before, after)`` for each item that ended up somewhere
            else, in scene millimetres.
        """

        self.record(
            Change(
                'move-items',
                tuple(MoveNode(item.uuid, was, now) for item, was, now in moves),
            )
        )

    def _on_guides_moved(self, moves) -> None:
        """Record a drag of one or more guides as one change.

        Parameters
        ----------
        moves : list
            ``(guide, before, after)`` for each guide that moved.
        """

        self.record(
            Change(
                'move-guide',
                tuple(
                    MoveGuide(
                        GuideData(GUIDE_ORIENTATIONS[guide.orientation], was),
                        GuideData(GUIDE_ORIENTATIONS[guide.orientation], now),
                    )
                    for guide, was, now in moves
                ),
            )
        )

    def _on_arcs_shaped(self, shaped) -> None:
        """Record a drag of a shaping handle.

        Parameters
        ----------
        shaped : list
            ``(arc, before controls, before points, after controls, after
            points)`` for each arc that was shaped.
        """

        self.record(
            Change(
                'shape-arc',
                tuple(
                    SetArcBends(arc.uuid, was_controls, was_points, controls, points)
                    for arc, was_controls, was_points, controls, points in shaped
                ),
            )
        )

    def _on_arc_end_asked(self, arc: Arc, end: str, item, port: int) -> None:
        """Put one end of an arc on another connecting point, and record it.

        The change is **not** made yet — the sheet only asked — so it is pushed
        to be done, which is what does it.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc
            The arc.
        end : str
            ``source`` or ``target``.
        item : masafi_simtwin.documents.net_item.NetItem
            What that end is to be put on.
        port : int
            Which of its connecting points.
        """

        was_item = arc.source if end == 'source' else arc.target
        was_port = arc.source_port if end == 'source' else arc.target_port
        if was_item is item and was_port == port:
            return
        self.push(
            Change(
                'move-arc-end',
                (MoveArcEnd(arc.uuid, end, was_item.uuid, was_port, item.uuid, port),),
            )
        )

    def _on_deletion_asked(self, items) -> None:
        """Delete what a person asked to be rid of, and record it as one change.

        An item takes its arcs with it, and they are taken out **before** it, so
        that undoing puts the item back before the arcs that hang on it.  The
        change is not made yet, so it is pushed to be done.

        Parameters
        ----------
        items : list
            The items, arcs and guides asked about, in no particular order.
        """

        arcs: list[Arc] = []
        nodes: list[NetItem] = []
        guides: list = []
        for item in items:
            if isinstance(item, Arc):
                arcs.append(item)
            elif isinstance(item, NetItem):
                nodes.append(item)
                arcs.extend(item.arcs)
            elif isinstance(item, Guide):
                guides.append(item)

        taken: list[Arc] = []
        for arc in arcs:
            if arc not in taken:
                taken.append(arc)

        operations = [RemoveArc(arc_data(arc)) for arc in taken]
        operations += [RemoveNode(node_data(item)) for item in nodes]
        operations += [RemoveGuide(guide_data(guide)) for guide in guides]
        self.push(Change('delete', tuple(operations)))

    def _on_arc_shape_asked(self, arc: Arc, shape: ArcShape) -> None:
        """Draw an arc in the shape its context menu chose.

        Connected as a bound method rather than as a lambda, for the reason
        :meth:`_on_element_dropped` is.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc
            The arc.
        shape : masafi_simtwin.documents.arc.ArcShape
            The shape.
        """

        self.reshape_arcs([arc], shape)
        self.show_arc_choice()

    def _on_arc_point_asked(self, arc: Arc, at: QPointF) -> None:
        """Put a point into an arc, and leave the arc in hand.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc
            The arc.
        at : PyQt6.QtCore.QPointF
            Where the menu was opened, in scene millimetres.
        """

        self.insert_arc_point(arc, at)
        self.view.work_on(arc)

    def _on_arc_point_removal_asked(self, arc: Arc, index: int) -> None:
        """Take a point out of an arc, and leave the arc in hand.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc
            The arc.
        index : int
            Which point.
        """

        self.take_arc_point_out(arc, index)
        self.view.work_on(arc)

    # ------------------------------------------------------------------
    # What can be undone
    # ------------------------------------------------------------------

    def record(self, change: Change) -> None:
        """Put a change a gesture has **already made** on the undo stack.

        Every gesture does the thing and then says what it did, rather than
        saying what it is about to do: the sheet has the last word on where an
        item lands — it is snapped, and held inside the paper — so recording
        afterwards is the only way the stack cannot disagree with the drawing.

        A change of no operations is not recorded: a gesture that turned out to
        change nothing is not an entry to undo.

        Parameters
        ----------
        change : simtwin_core.operations.Change
            What was done.
        """

        self.push(change, applied=True)

    def push(self, change: Change, applied: bool = False) -> None:
        """Put a change on the undo stack, and make it unless it is already made.

        Parameters
        ----------
        change : simtwin_core.operations.Change
            The change.
        applied : bool, optional
            Whether the sheet already shows it, which is what
            :meth:`record` says of a gesture a person has just made by hand.
        """

        if not change.operations:
            return
        self.undo_stack.push(
            EditCommand(self, change, self.change_label(change.name), applied)
        )

    def report_change(self, change: Change) -> None:
        """Say that a change has reached the sheet.

        Parameters
        ----------
        change : simtwin_core.operations.Change
            What the net has become — the change itself when it was made or
            made again, its inverse when it was undone.
        """

        self.change_recorded.emit(self.model_id, change)

    def change_label(self, name: str) -> str:
        """Give what a change is called where a person reads it.

        Qt puts it after *Undo* and *Redo*, so it is the name of the gesture
        rather than a sentence.

        Parameters
        ----------
        name : str
            What the change calls itself.

        Returns
        -------
        str
            Its translated name, and the bare name for a change nobody has
            named yet.
        """

        labels = {
            'add-element': self.tr('Add Element'),
            'draw-arc': self.tr('Draw Arc'),
            'set-arc-weight': self.tr('Change Weight'),
            'set-arc-shape': self.tr('Change Arc Shape'),
            'set-arc-kind': self.tr('Change Arc Type'),
            'add-arc-point': self.tr('Add Point'),
            'remove-arc-point': self.tr('Delete Point'),
            'move-items': self.tr('Move'),
            'move-guide': self.tr('Move Guide'),
            'add-guide': self.tr('Add Guide'),
            'shape-arc': self.tr('Shape Arc'),
            'move-arc-end': self.tr('Move Arc End'),
            'delete': self.tr('Delete'),
            'rename-node': self.tr('Rename'),
            'set-tokens': self.tr('Change Tokens'),
            'set-description': self.tr('Change Description'),
        }
        return labels.get(name, name)

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

        The order is the document's own: a
        :class:`~simtwin_core.petri_net.NetDocument` holds everything by name —
        numbers counted as numbers — however it is given, so the scene's stacking
        order, which changes as items are selected, never reaches a file.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net, its guides, and the model it is.
        """

        return NetDocument(
            model_uuid=self.model_id,
            places=tuple(node_data(item) for item in self.places),
            transitions=tuple(node_data(item) for item in self.transitions),
            arcs=tuple(arc_data(arc) for arc in self.arcs),
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
        self.undo_stack.clear()

        for data in (*document.places, *document.transitions):
            self.draw_node(data)
        for data in document.arcs:
            self.draw_arc(data)
        for data in document.guides:
            self.add_guide(GUIDE_WAYS[data.orientation], data.position)

        self.show_arc_choice()

    def draw_node(self, data) -> NetItem:
        """Put a place or a transition on the sheet, as a document describes it.

        Parameters
        ----------
        data : simtwin_core.petri_net.PlaceData or simtwin_core.petri_net.TransitionData
            The node, with the UUID and the name it is to keep.

        Returns
        -------
        masafi_simtwin.documents.net_item.NetItem
            The item, already on the scene.
        """

        item = NODE_ITEMS[type(data)](self.view.snap, self.view.sceneRect)
        item.uuid = data.uuid
        item.name = data.name
        item.description = data.description
        if isinstance(data, PlaceData):
            item.tokens = data.tokens
        self.scene().addItem(item)
        item.setPos(QPointF(*data.position))
        return item

    def draw_arc(self, data: ArcData) -> Arc:
        """Draw an arc on the sheet, as a document describes it.

        Parameters
        ----------
        data : simtwin_core.petri_net.ArcData
            The arc, with the UUID, the connecting points and the bends it is to
            keep.

        Returns
        -------
        masafi_simtwin.documents.arc.Arc
            The arc, already on the scene.
        """

        source, target = self.node(data.source), self.node(data.target)
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
        return arc

    def node(self, uuid: str) -> NetItem:
        """Find a place or a transition by its UUID.

        Parameters
        ----------
        uuid : str
            Its UUID.

        Returns
        -------
        masafi_simtwin.documents.net_item.NetItem
            The item.

        Raises
        ------
        ValueError
            When the sheet holds no such node — which a change made against
            another net, or a journal that has been damaged, would ask for.
        """

        for item in self.items_of(NetItem):
            if item.uuid == uuid:
                return item
        raise ValueError(f'the sheet holds no node {uuid!r}')

    def arc(self, uuid: str) -> Arc:
        """Find an arc by its UUID.

        Parameters
        ----------
        uuid : str
            Its UUID.

        Returns
        -------
        masafi_simtwin.documents.arc.Arc
            The arc.

        Raises
        ------
        ValueError
            When the sheet holds no such arc.
        """

        for item in self.arcs:
            if item.uuid == uuid:
                return item
        raise ValueError(f'the sheet holds no arc {uuid!r}')

    def guide(self, data: GuideData):
        """Find a guide by which way it lies and where it is.

        A guide has no identity of its own, so the first one equal to this is
        the one meant — which is what the operations say too.

        Parameters
        ----------
        data : simtwin_core.petri_net.GuideData
            The guide.

        Returns
        -------
        masafi_simtwin.documents.guide.Guide
            The guide on the sheet.

        Raises
        ------
        ValueError
            When no guide of the sheet is that one.
        """

        for guide in self.guides:
            if (
                GUIDE_ORIENTATIONS[guide.orientation] == data.orientation
                and guide.position == data.position
            ):
                return guide
        raise ValueError(f'the sheet has no {data.orientation} guide at {data.position}')

    # ------------------------------------------------------------------
    # Changing the net
    # ------------------------------------------------------------------

    def apply(self, change: Change) -> None:
        """Make one change to the net on the sheet.

        The other half of :func:`simtwin_core.operations.Change.apply`, which
        makes the same change to a description.  Everything a person does to a
        net goes through here — so that it can be undone, and written to the
        journal — and a test holds that the two agree: the description of a
        sheet a change has been applied to is the description that change makes
        of the description it had.

        Nothing here is a gesture: an operation says what a thing **is**, and
        nothing is invented from a default.  Applying a change made against
        another net raises :class:`ValueError` rather than drawing something
        nobody asked for.

        Parameters
        ----------
        change : simtwin_core.operations.Change
            What one gesture did, or — inverted — what undoing it does.
        """

        for operation in change.operations:
            self.apply_operation(operation)

    def apply_operation(self, operation: Operation) -> None:
        """Make one operation of a change.

        Parameters
        ----------
        operation : simtwin_core.operations.Operation
            The operation.

        Raises
        ------
        TypeError
            When it is an operation this editor does not know how to make,
            which is one added to the core and forgotten here.
        ValueError
            When what it is about is not on the sheet.
        """

        if isinstance(operation, AddNode):
            self.draw_node(operation.node)
        elif isinstance(operation, RemoveNode):
            self.view.remove(self.node(operation.node.uuid))
        elif isinstance(operation, MoveNode):
            self.node(operation.node).setPos(QPointF(*operation.after))
        elif isinstance(operation, SetNodeName):
            self.node(operation.node).name = operation.after
        elif isinstance(operation, SetTokens):
            place = self.node(operation.node)
            if not isinstance(place, Place):
                raise ValueError(f'the sheet has no place {operation.node!r} to hold tokens')
            place.tokens = operation.after
        elif isinstance(operation, SetDescription):
            self.node(operation.node).description = operation.after
        elif isinstance(operation, AddArc):
            self.draw_arc(operation.arc)
        elif isinstance(operation, RemoveArc):
            self.view.remove(self.arc(operation.arc.uuid))
        elif isinstance(operation, MoveArcEnd):
            self.arc(operation.arc).reattach(
                operation.end, self.node(operation.after_node), operation.after_port
            )
        elif isinstance(operation, SetArcShape):
            self.arc(operation.arc).set_shape(ArcShape(operation.after))
        elif isinstance(operation, SetArcKind):
            self.arc(operation.arc).set_kind(ArcKind(operation.after))
        elif isinstance(operation, SetArcWeight):
            self.arc(operation.arc).weight = operation.after
        elif isinstance(operation, SetArcBends):
            self.arc(operation.arc).restore_bends(
                operation.after_controls, operation.after_points
            )
        elif isinstance(operation, AddGuide):
            self.add_guide(GUIDE_WAYS[operation.guide.orientation], operation.guide.position)
        elif isinstance(operation, RemoveGuide):
            self.view.remove_guide(self.guide(operation.guide))
        elif isinstance(operation, MoveGuide):
            self.guide(operation.before).position = operation.after.position
        else:
            raise TypeError(f'{operation!r} is an operation this editor cannot make')

    def clear_sheet(self) -> None:
        """Take the whole net off the sheet, and its guides."""

        for item in self.items_of(NetItem):
            self.view.remove(item)
        for arc in self.arcs:
            self.view.remove(arc)
        self.clear_guides()

    def rename_node(self, uuid: str, name: str) -> bool:
        """Call a place or a transition something else, as one recorded change.

        Parameters
        ----------
        uuid : str
            The node's UUID.
        name : str
            What it is to be called.

        Returns
        -------
        bool
            Whether it was renamed.  It is not when the name is the one it has,
            or breaks :func:`~simtwin_core.petri_net.name_problem` against the
            other nodes' names — the Properties pane checks first, and this is
            the rule held where the change is made.
        """

        node = self.node(uuid)
        if name == node.name:
            return False
        taken = [other for other in self.names if other != node.name]
        if name_problem(name, taken) is not None:
            return False
        self.push(Change('rename-node', (SetNodeName(uuid, node.name, name),)))
        return True

    def set_tokens(self, uuids, tokens: int) -> bool:
        """Give some places the same initial tokens, as one recorded change.

        Parameters
        ----------
        uuids : collections.abc.Iterable of str
            The places.  A transition among them is passed over, holding none.
        tokens : int
            How many tokens each is to hold, nought or more.

        Returns
        -------
        bool
            Whether any place changed.
        """

        if tokens < 0:
            return False
        places = [node for node in (self.node(uuid) for uuid in uuids) if isinstance(node, Place)]
        operations = tuple(
            SetTokens(place.uuid, place.tokens, tokens) for place in places if place.tokens != tokens
        )
        self.push(Change('set-tokens', operations))
        return bool(operations)

    def describe(self, uuids, description: str) -> bool:
        """Give some places or transitions the same description, as one change.

        Parameters
        ----------
        uuids : collections.abc.Iterable of str
            The nodes.
        description : str
            What they are to be described as, on one line.

        Returns
        -------
        bool
            Whether any node changed.  A description of more than one line is
            refused, as the document refuses it.
        """

        if '\n' in description or '\r' in description:
            return False
        nodes = [self.node(uuid) for uuid in uuids]
        operations = tuple(
            SetDescription(node.uuid, node.description, description)
            for node in nodes
            if node.description != description
        )
        self.push(Change('set-description', operations))
        return bool(operations)

    def set_weight(self, uuids, weight: int) -> bool:
        """Give some arcs the same weight, as one recorded change.

        Parameters
        ----------
        uuids : collections.abc.Iterable of str
            The arcs.
        weight : int
            How many tokens each is to carry, one at least.

        Returns
        -------
        bool
            Whether any arc changed.  A weight below one is refused, as the
            document refuses it.
        """

        if weight < 1:
            return False
        arcs = [self.arc(uuid) for uuid in uuids]
        operations = tuple(
            SetArcWeight(arc.uuid, arc.weight, weight) for arc in arcs if arc.weight != weight
        )
        self.push(Change('set-arc-weight', operations))
        return bool(operations)

    def _on_item_activated(self, item) -> None:
        """Say that an arc was double-clicked, so that its weight can be edited.

        The weight is edited in the Properties pane, and a double click on an arc
        is the gesture that asks for it: the document says which arc, and the
        window opens the pane on it.  The press that began the double click has
        already selected the arc, so the pane is showing it.

        Connected as a bound method rather than as a lambda, for the reason
        :meth:`_on_element_dropped` is.

        Parameters
        ----------
        item : PyQt6.QtWidgets.QGraphicsItem, optional
            What was under the pointer, or ``None`` for the bare sheet.
        """

        if isinstance(item, Arc):
            self.arc_activated.emit(self.model_id, item.uuid)

    @property
    def model_id(self) -> str:
        """str: The UUID of the model on the sheet, which is also its tab key."""

        return self.model.get('uuid', '')

    @property
    def is_modified(self) -> bool:
        """bool: Whether the sheet differs from what was last written.

        It is the undo stack's own answer: *clean* from a save until the next
        change, and clean again when the changes since are undone.
        """

        return not self.undo_stack.isClean()

    def _on_clean_changed(self, clean: bool) -> None:
        """Say that the sheet has come to differ from its file, or stopped.

        Parameters
        ----------
        clean : bool
            Whether the undo stack is now at the state last written.
        """

        self.modified_changed.emit(self.model_id, not clean)

    @property
    def model_name(self) -> str:
        """str: What the model is called, which is what its tab says."""

        return self.model.get('name', '')
