"""What one edit of a drawn net is, and how it is undone and replayed.

An **operation** is the smallest change a person can make to a net: a place
dropped, a node moved, an arc's weight set.  A **change** is what one gesture
does, which is often more than one operation — deleting a place takes its arcs
with it, moving a selection moves each of its items — and it is what goes on the
undo stack and what is written to the journal, one line at a time.

Every operation knows its :meth:`Operation.inverse`, so undoing a change is
applying its operations backwards, and every operation can be **applied to a
description** with no Qt anywhere near it.  That is what makes this module the
right place for them: the journal is replayed onto the last saved file before any
editor exists, and an editor applies the very same operations to what is on its
sheet.  The two are tested against each other — the description the editor gives
after applying an operation is the description :func:`Change.apply` gives — so
the two ways of meaning one edit cannot drift apart.

**Applying returns a new description.**  A :class:`~simtwin_core.petri_net.NetDocument`
is a value and is checked as it is made, so an operation that would break the net
— an arc to a node that is not there, two arcs of one kind the same way round —
raises :class:`~simtwin_core.petri_net.InvalidNet` where it is applied.  A journal
that has been damaged is refused rather than half replayed.

**What an operation carries is everything needed to put it back.**  A node
removed is carried whole, so undoing gives back the same node with the same UUID
and the same name, and the arcs that hung on it come back in the same change.
Nothing is looked up from the net at the time it is undone, because by then the
net is not what it was.

An arc's ``route`` is not carried: it is derived from the arc's points, the
editor is the only thing that can work it out, and it takes no part in comparing
two descriptions.

**A whole net is written as the same plain data** — :func:`encode_net` and
:func:`decode_net` — because it is the same nodes and the same arcs written by
the same helpers, and because what a piece of a net *is* has one answer here
rather than one for the journal and another for whatever else carries one.  The
clipboard is the other thing that carries one: what is copied off a sheet is a
:class:`~simtwin_core.petri_net.NetDocument` of a few nodes and the arcs between
them, and it is read back by whichever sheet it is pasted onto.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from simtwin_core.petri_net import (
    ArcData,
    GuideData,
    NetDocument,
    PlaceData,
    Point,
    TransitionData,
)

#: A node of a net, whichever kind it is.
Node = PlaceData | TransitionData


class Operation:
    """One smallest change to a drawn net.

    A subclass is a frozen dataclass carrying everything needed to make the
    change and to put it back, and says two things: what it does to a
    description, and what its inverse is.
    """

    #: What the operation is called in a journal.
    NAME: str = ''

    def apply(self, document: NetDocument) -> NetDocument:
        """Give the description this operation makes of another.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            What the net is now.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            What it becomes.

        Raises
        ------
        NotImplementedError
            Always.  What an operation does is what a subclass is.
        """

        raise NotImplementedError

    def inverse(self) -> Operation:
        """Give the operation that puts this one back.

        Returns
        -------
        Operation
            The inverse.

        Raises
        ------
        NotImplementedError
            Always.
        """

        raise NotImplementedError


# ----------------------------------------------------------------------
# The nodes of a net
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class AddNode(Operation):
    """Put a place or a transition on the sheet.

    Attributes
    ----------
    node : PlaceData or TransitionData
        The node, whole: undoing and redoing give back the same UUID and the
        same name rather than a new node that looks like it.
    """

    NAME = 'add-node'

    node: Node

    def apply(self, document: NetDocument) -> NetDocument:
        """Add the node.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net with the node on it.
        """

        if isinstance(self.node, PlaceData):
            return replace(document, places=(*document.places, self.node))
        return replace(document, transitions=(*document.transitions, self.node))

    def inverse(self) -> Operation:
        """Give the removal of the node.

        Returns
        -------
        RemoveNode
            The inverse.
        """

        return RemoveNode(self.node)


@dataclass(frozen=True)
class RemoveNode(Operation):
    """Take a place or a transition off the sheet.

    The arcs that hung on it are not this operation's business: they are removed
    by operations of their own, in the same change, so that undoing the change
    brings back the node and its arcs together.

    Attributes
    ----------
    node : PlaceData or TransitionData
        The node, whole, so that undoing gives back what was there.
    """

    NAME = 'remove-node'

    node: Node

    def apply(self, document: NetDocument) -> NetDocument:
        """Take the node out.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net without it.
        """

        return replace(
            document,
            places=tuple(node for node in document.places if node.uuid != self.node.uuid),
            transitions=tuple(
                node for node in document.transitions if node.uuid != self.node.uuid
            ),
        )

    def inverse(self) -> Operation:
        """Give the addition of the node.

        Returns
        -------
        AddNode
            The inverse.
        """

        return AddNode(self.node)


@dataclass(frozen=True)
class MoveNode(Operation):
    """Move a place or a transition on the sheet.

    Attributes
    ----------
    node : str
        The UUID of the node.
    before, after : tuple of float
        Where its centre was and where it goes, in millimetres.
    """

    NAME = 'move-node'

    node: str
    before: Point
    after: Point

    def apply(self, document: NetDocument) -> NetDocument:
        """Put the node where it goes.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net with the node moved.
        """

        return replace(
            document,
            places=_moved(document.places, self.node, self.after),
            transitions=_moved(document.transitions, self.node, self.after),
        )

    def inverse(self) -> Operation:
        """Give the move back.

        Returns
        -------
        MoveNode
            The inverse.
        """

        return MoveNode(self.node, self.after, self.before)


@dataclass(frozen=True)
class SetNodeName(Operation):
    """Call a place or a transition something else.

    A name is what a backend knows a node by, so a name another node already has
    is refused where the operation is applied, as
    :class:`~simtwin_core.petri_net.NetDocument` refuses two nodes of one name.
    Whether a name is one a person may give at all is decided before an
    operation is made, not here.

    Attributes
    ----------
    node : str
        The UUID of the node.
    before, after : str
        What it was called and what it is called.
    """

    NAME = 'set-node-name'

    node: str
    before: str
    after: str

    def apply(self, document: NetDocument) -> NetDocument:
        """Rename the node.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net with the node renamed.
        """

        return _changed_node(document, self.node, name=self.after)

    def inverse(self) -> Operation:
        """Give the name back.

        Returns
        -------
        SetNodeName
            The inverse.
        """

        return SetNodeName(self.node, self.after, self.before)


@dataclass(frozen=True)
class SetTokens(Operation):
    """Set how many tokens a place holds before the net is run.

    A transition holds no tokens, so a transition of that UUID is left as it is.

    Attributes
    ----------
    node : str
        The UUID of the place.
    before, after : int
        The tokens it held and the tokens it holds.
    """

    NAME = 'set-tokens'

    node: str
    before: int
    after: int

    def apply(self, document: NetDocument) -> NetDocument:
        """Set the tokens.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net with the place's tokens set.
        """

        return _changed_node(document, self.node, tokens=self.after)

    def inverse(self) -> Operation:
        """Give the tokens back.

        Returns
        -------
        SetTokens
            The inverse.
        """

        return SetTokens(self.node, self.after, self.before)


@dataclass(frozen=True)
class SetDescription(Operation):
    """Describe a place or a transition in other words.

    Attributes
    ----------
    node : str
        The UUID of the node.
    before, after : str
        The description it had and the one it has.
    """

    NAME = 'set-node-description'

    node: str
    before: str
    after: str

    def apply(self, document: NetDocument) -> NetDocument:
        """Set the description.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net with the node described anew.
        """

        return _changed_node(document, self.node, description=self.after)

    def inverse(self) -> Operation:
        """Give the description back.

        Returns
        -------
        SetDescription
            The inverse.
        """

        return SetDescription(self.node, self.after, self.before)


@dataclass(frozen=True)
class SetVertical(Operation):
    """Stand a transition up the sheet, or lay it back across it.

    A place is round and is the same thing whichever way it is turned, so a
    place of that UUID is left as it is.

    Attributes
    ----------
    node : str
        The UUID of the transition.
    before, after : bool
        Which way round it was drawn and which way round it is drawn.
    """

    NAME = 'set-vertical'

    node: str
    before: bool
    after: bool

    def apply(self, document: NetDocument) -> NetDocument:
        """Turn the transition.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net with the transition drawn the other way round.
        """

        return _changed_node(document, self.node, vertical=self.after)

    def inverse(self) -> Operation:
        """Turn it back.

        Returns
        -------
        SetVertical
            The inverse.
        """

        return SetVertical(self.node, self.after, self.before)


# ----------------------------------------------------------------------
# The arcs
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class AddArc(Operation):
    """Draw an arc between two nodes.

    Attributes
    ----------
    arc : ArcData
        The arc, whole: its identity, its ends, its connecting points, its
        weight, its kind, its shape and its bends.
    """

    NAME = 'add-arc'

    arc: ArcData

    def apply(self, document: NetDocument) -> NetDocument:
        """Add the arc.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net with the arc in it.
        """

        return replace(document, arcs=(*document.arcs, self.arc))

    def inverse(self) -> Operation:
        """Give the removal of the arc.

        Returns
        -------
        RemoveArc
            The inverse.
        """

        return RemoveArc(self.arc)


@dataclass(frozen=True)
class RemoveArc(Operation):
    """Take an arc off the sheet.

    Attributes
    ----------
    arc : ArcData
        The arc, whole, so that undoing gives back the line that was drawn
        rather than a straight one between the same two nodes.
    """

    NAME = 'remove-arc'

    arc: ArcData

    def apply(self, document: NetDocument) -> NetDocument:
        """Take the arc out.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net without it.
        """

        return replace(
            document, arcs=tuple(arc for arc in document.arcs if arc.uuid != self.arc.uuid)
        )

    def inverse(self) -> Operation:
        """Give the drawing of the arc.

        Returns
        -------
        AddArc
            The inverse.
        """

        return AddArc(self.arc)


@dataclass(frozen=True)
class MoveArcEnd(Operation):
    """Put one end of an arc on another connecting point, of the same node or
    of another.

    Attributes
    ----------
    arc : str
        The UUID of the arc.
    end : str
        ``source`` or ``target``.
    before_node, after_node : str
        The UUID of the node that end was on and of the one it goes to.
    before_port, after_port : int, optional
        Which connecting point of each.
    """

    NAME = 'move-arc-end'

    arc: str
    end: str
    before_node: str
    before_port: int | None
    after_node: str
    after_port: int | None

    def apply(self, document: NetDocument) -> NetDocument:
        """Move the end.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net with the arc moved.
        """

        if self.end == 'source':
            changes = {'source': self.after_node, 'source_port': self.after_port}
        else:
            changes = {'target': self.after_node, 'target_port': self.after_port}
        return _changed_arc(document, self.arc, **changes)

    def inverse(self) -> Operation:
        """Give the move back.

        Returns
        -------
        MoveArcEnd
            The inverse.
        """

        return MoveArcEnd(
            self.arc, self.end, self.after_node, self.after_port, self.before_node, self.before_port
        )


@dataclass(frozen=True)
class SetArcShape(Operation):
    """Draw an arc in another shape.

    The points a shape is led through are not touched here: an arc given its
    shape's defaults changes both, and that is two operations in one change, so
    that each of them is exactly what it says.

    Attributes
    ----------
    arc : str
        The UUID of the arc.
    before, after : str
        The shape it was drawn in and the one it is drawn in now.
    """

    NAME = 'set-arc-shape'

    arc: str
    before: str
    after: str

    def apply(self, document: NetDocument) -> NetDocument:
        """Set the shape.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net with the arc reshaped.
        """

        return _changed_arc(document, self.arc, shape=self.after)

    def inverse(self) -> Operation:
        """Give the shape back.

        Returns
        -------
        SetArcShape
            The inverse.
        """

        return SetArcShape(self.arc, self.after, self.before)


@dataclass(frozen=True)
class SetArcKind(Operation):
    """Make an arc a kind of arc.

    Attributes
    ----------
    arc : str
        The UUID of the arc.
    before, after : str
        The kind it was and the kind it is.
    """

    NAME = 'set-arc-kind'

    arc: str
    before: str
    after: str

    def apply(self, document: NetDocument) -> NetDocument:
        """Set the kind.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net with the arc changed.
        """

        return _changed_arc(document, self.arc, kind=self.after)

    def inverse(self) -> Operation:
        """Give the kind back.

        Returns
        -------
        SetArcKind
            The inverse.
        """

        return SetArcKind(self.arc, self.after, self.before)


@dataclass(frozen=True)
class SetArcWeight(Operation):
    """Set how many tokens an arc carries.

    Attributes
    ----------
    arc : str
        The UUID of the arc.
    before, after : int
        The weight it carried and the weight it carries.
    """

    NAME = 'set-arc-weight'

    arc: str
    before: int
    after: int

    def apply(self, document: NetDocument) -> NetDocument:
        """Set the weight.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net with the arc changed.
        """

        return _changed_arc(document, self.arc, weight=self.after)

    def inverse(self) -> Operation:
        """Give the weight back.

        Returns
        -------
        SetArcWeight
            The inverse.
        """

        return SetArcWeight(self.arc, self.after, self.before)


@dataclass(frozen=True)
class SetArcBends(Operation):
    """Shape an arc: its control points, the points it is led through, or both.

    One operation for all three gestures — dragging a handle, putting a point
    in, taking one out — because all three say the same thing about the arc:
    *this is how it bends now*.  Each is the whole of what the arc keeps, so
    undoing is exact rather than approximate.

    Attributes
    ----------
    arc : str
        The UUID of the arc.
    before_controls, after_controls : tuple, optional
        The two control points, in the chord's frame, before and after.
    before_points, after_points : tuple, optional
        The points it is led through, likewise.
    """

    NAME = 'set-arc-bends'

    arc: str
    before_controls: tuple[Point, Point] | None
    before_points: tuple[Point, ...] | None
    after_controls: tuple[Point, Point] | None
    after_points: tuple[Point, ...] | None

    def apply(self, document: NetDocument) -> NetDocument:
        """Shape the arc.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net with the arc shaped.
        """

        return _changed_arc(
            document, self.arc, controls=self.after_controls, points=self.after_points
        )

    def inverse(self) -> Operation:
        """Give the shape back.

        Returns
        -------
        SetArcBends
            The inverse.
        """

        return SetArcBends(
            self.arc,
            self.after_controls,
            self.after_points,
            self.before_controls,
            self.before_points,
        )


# ----------------------------------------------------------------------
# The guides
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class AddGuide(Operation):
    """Put a guide on the sheet.

    Attributes
    ----------
    guide : GuideData
        The guide.
    """

    NAME = 'add-guide'

    guide: GuideData

    def apply(self, document: NetDocument) -> NetDocument:
        """Add the guide.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net with the guide across it.
        """

        return replace(document, guides=(*document.guides, self.guide))

    def inverse(self) -> Operation:
        """Give the removal of the guide.

        Returns
        -------
        RemoveGuide
            The inverse.
        """

        return RemoveGuide(self.guide)


@dataclass(frozen=True)
class RemoveGuide(Operation):
    """Take a guide off the sheet.

    A guide has no identity of its own — it is a way round and a place — so the
    first guide equal to this one is the one taken off.  Two guides that are
    equal are the same guide to anybody looking at the sheet.

    Attributes
    ----------
    guide : GuideData
        The guide.
    """

    NAME = 'remove-guide'

    guide: GuideData

    def apply(self, document: NetDocument) -> NetDocument:
        """Take the guide out.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net without it.
        """

        return replace(document, guides=_without(document.guides, self.guide))

    def inverse(self) -> Operation:
        """Give the guide back.

        Returns
        -------
        AddGuide
            The inverse.
        """

        return AddGuide(self.guide)


@dataclass(frozen=True)
class MoveGuide(Operation):
    """Move a guide across the sheet.

    Attributes
    ----------
    before, after : GuideData
        The guide as it was and as it is.
    """

    NAME = 'move-guide'

    before: GuideData
    after: GuideData

    def apply(self, document: NetDocument) -> NetDocument:
        """Move the guide.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            The net.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net with the guide moved.
        """

        return replace(
            document, guides=(*_without(document.guides, self.before), self.after)
        )

    def inverse(self) -> Operation:
        """Give the move back.

        Returns
        -------
        MoveGuide
            The inverse.
        """

        return MoveGuide(self.after, self.before)


# ----------------------------------------------------------------------
# What one gesture does
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Change:
    """What one gesture does to a net: one or more operations, under a name.

    This is what the undo stack holds and what the journal writes, one to a
    line.  A gesture is often more than one operation — deleting a place takes
    its arcs with it, moving a selection moves each of its items, choosing a
    shape for an arc that has no points gives it the shape's own — and undoing
    has to put all of it back or none of it.

    Attributes
    ----------
    name : str
        What the gesture was, for the *Undo* entry that offers to put it back.
        A key rather than a sentence: the words belong to the application, which
        has the translations.
    operations : tuple of Operation
        What it did, in the order it did it.
    """

    name: str
    operations: tuple[Operation, ...] = ()

    def apply(self, document: NetDocument) -> NetDocument:
        """Give the description this change makes of another.

        Parameters
        ----------
        document : simtwin_core.petri_net.NetDocument
            What the net is now.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            What it becomes, each operation applied in turn.

        Raises
        ------
        simtwin_core.petri_net.InvalidNet
            When the net it would make is not one that can be drawn — a
            journal that has been damaged is refused rather than half replayed.
        """

        for operation in self.operations:
            document = operation.apply(document)
        return document

    def inverse(self) -> Change:
        """Give the change that puts this one back.

        Returns
        -------
        Change
            The operations inverted **and in reverse order**: a place is put
            back before the arcs that hang on it.
        """

        return Change(
            self.name, tuple(operation.inverse() for operation in reversed(self.operations))
        )


# ----------------------------------------------------------------------
# A change as a line of a journal
# ----------------------------------------------------------------------

#: Every operation there is, by the name it is written under.  A journal holding
#: a name that is not here was written by another version, and is refused rather
#: than passed over: half a change replayed is a net nobody drew.
OPERATIONS: dict[str, type[Operation]] = {
    operation.NAME: operation
    for operation in (
        AddNode,
        RemoveNode,
        MoveNode,
        SetNodeName,
        SetTokens,
        SetDescription,
        SetVertical,
        AddArc,
        RemoveArc,
        MoveArcEnd,
        SetArcShape,
        SetArcKind,
        SetArcWeight,
        SetArcBends,
        AddGuide,
        RemoveGuide,
        MoveGuide,
    )
}


def encode(change: Change) -> dict:
    """Write a change as the plain data a journal line holds.

    Parameters
    ----------
    change : Change
        The change.

    Returns
    -------
    dict
        Its name and its operations, in JSON's own types.
    """

    return {
        'change': change.name,
        'operations': [_encode_operation(operation) for operation in change.operations],
    }


def decode(data: dict) -> Change:
    """Read a change back from what a journal line holds.

    Parameters
    ----------
    data : dict
        What :func:`encode` wrote.

    Returns
    -------
    Change
        The change.

    Raises
    ------
    ValueError
        When the line is not a change, or names an operation this version does
        not have.
    """

    if not isinstance(data, dict) or 'operations' not in data:
        raise ValueError(f'not a change: {data!r}')
    return Change(
        str(data.get('change', '')),
        tuple(_decode_operation(operation) for operation in data['operations']),
    )


def encode_net(document: NetDocument) -> dict:
    """Write a net, or a piece of one, as the plain data JSON holds.

    Parameters
    ----------
    document : simtwin_core.petri_net.NetDocument
        The net.

    Returns
    -------
    dict
        Its model, its nodes, its arcs and its guides.  An arc's ``route`` is
        left out, as it is everywhere else here: whatever draws the net works
        it out from the arc's points.
    """

    return {
        'model': document.model_uuid,
        'places': [_node_data(place) for place in document.places],
        'transitions': [_node_data(transition) for transition in document.transitions],
        'arcs': [_arc_data(arc) for arc in document.arcs],
        'guides': [_guide_data(guide) for guide in document.guides],
    }


def decode_net(data: dict) -> NetDocument:
    """Read a net back from what :func:`encode_net` wrote.

    Parameters
    ----------
    data : dict
        The plain data.

    Returns
    -------
    simtwin_core.petri_net.NetDocument
        The net.

    Raises
    ------
    ValueError
        When it is not a net written this way.  A
        :class:`~simtwin_core.petri_net.InvalidNet` is one of these, a document
        being checked as it is made: something that is not a net that could be
        drawn is refused here rather than reaching a sheet.
    """

    if not isinstance(data, dict):
        raise ValueError(f'not a net: {data!r}')
    try:
        nodes = [_read_node(node) for node in (*data['places'], *data['transitions'])]
        return NetDocument(
            model_uuid=str(data.get('model', '')),
            places=tuple(node for node in nodes if isinstance(node, PlaceData)),
            transitions=tuple(node for node in nodes if isinstance(node, TransitionData)),
            arcs=tuple(_read_arc(arc) for arc in data['arcs']),
            guides=tuple(_read_guide(guide) for guide in data.get('guides', ())),
        )
    except (KeyError, TypeError) as error:
        raise ValueError(f'a net is not written as it should be: {error}') from error


def _encode_operation(operation: Operation) -> dict:
    """Write one operation as plain data.

    An arc's ``route`` is left out: it is worked out from the arc's points by
    whatever draws it, and carrying it would be carrying the same thing twice.

    Parameters
    ----------
    operation : Operation
        The operation.

    Returns
    -------
    dict
        Its name and its fields.
    """

    data: dict = {'op': operation.NAME}
    if isinstance(operation, (AddNode, RemoveNode)):
        data['node'] = _node_data(operation.node)
    elif isinstance(operation, MoveNode):
        data.update(node=operation.node, before=list(operation.before), after=list(operation.after))
    elif isinstance(operation, (SetNodeName, SetTokens, SetDescription, SetVertical)):
        data.update(node=operation.node, before=operation.before, after=operation.after)
    elif isinstance(operation, (AddArc, RemoveArc)):
        data['arc'] = _arc_data(operation.arc)
    elif isinstance(operation, MoveArcEnd):
        data.update(
            arc=operation.arc,
            end=operation.end,
            before_node=operation.before_node,
            before_port=operation.before_port,
            after_node=operation.after_node,
            after_port=operation.after_port,
        )
    elif isinstance(operation, (SetArcShape, SetArcKind, SetArcWeight)):
        data.update(arc=operation.arc, before=operation.before, after=operation.after)
    elif isinstance(operation, SetArcBends):
        data.update(
            arc=operation.arc,
            before_controls=_frames(operation.before_controls),
            before_points=_frames(operation.before_points),
            after_controls=_frames(operation.after_controls),
            after_points=_frames(operation.after_points),
        )
    elif isinstance(operation, (AddGuide, RemoveGuide)):
        data['guide'] = _guide_data(operation.guide)
    elif isinstance(operation, MoveGuide):
        data.update(before=_guide_data(operation.before), after=_guide_data(operation.after))
    else:  # pragma: no cover - every operation of OPERATIONS is above
        raise ValueError(f'{operation!r} cannot be written to a journal')
    return data


def _decode_operation(data: dict) -> Operation:
    """Read one operation back from plain data.

    Parameters
    ----------
    data : dict
        What :func:`_encode_operation` wrote.

    Returns
    -------
    Operation
        The operation.

    Raises
    ------
    ValueError
        When it names no operation this version has, or is missing what that
        operation is made of.
    """

    if not isinstance(data, dict):
        raise ValueError(f'not an operation: {data!r}')
    name = data.get('op')
    operation = OPERATIONS.get(name)
    if operation is None:
        raise ValueError(f'no operation is called {name!r}')

    try:
        if operation in (AddNode, RemoveNode):
            return operation(_read_node(data['node']))
        if operation is MoveNode:
            return MoveNode(data['node'], tuple(data['before']), tuple(data['after']))
        if operation in (SetNodeName, SetTokens, SetDescription, SetVertical):
            return operation(data['node'], data['before'], data['after'])
        if operation in (AddArc, RemoveArc):
            return operation(_read_arc(data['arc']))
        if operation is MoveArcEnd:
            return MoveArcEnd(
                data['arc'],
                data['end'],
                data['before_node'],
                data['before_port'],
                data['after_node'],
                data['after_port'],
            )
        if operation in (SetArcShape, SetArcKind, SetArcWeight):
            return operation(data['arc'], data['before'], data['after'])
        if operation is SetArcBends:
            return SetArcBends(
                data['arc'],
                _read_frames(data['before_controls']),
                _read_frames(data['before_points']),
                _read_frames(data['after_controls']),
                _read_frames(data['after_points']),
            )
        if operation in (AddGuide, RemoveGuide):
            return operation(_read_guide(data['guide']))
        return MoveGuide(_read_guide(data['before']), _read_guide(data['after']))
    except (KeyError, TypeError) as error:
        raise ValueError(f'{name} is not written as it should be: {error}') from error


def _node_data(node: Node) -> dict:
    """Write a place or a transition as plain data.

    Parameters
    ----------
    node : PlaceData or TransitionData
        The node.

    Returns
    -------
    dict
        Which kind it is, and what it is.
    """

    data = {
        'kind': 'place' if isinstance(node, PlaceData) else 'transition',
        'uuid': node.uuid,
        'name': node.name,
        'position': list(node.position),
    }
    if isinstance(node, PlaceData):
        data['tokens'] = node.tokens
    else:
        data['vertical'] = node.vertical
    data['description'] = node.description
    return data


def _read_node(data: dict) -> Node:
    """Read a place or a transition back.

    Parameters
    ----------
    data : dict
        What :func:`_node_data` wrote.  A line written before nodes had tokens,
        descriptions or a way round has none of them, and reads as a node with
        none and a transition lying across the sheet.

    Returns
    -------
    PlaceData or TransitionData
        The node.
    """

    description = data.get('description', '')
    if data['kind'] == 'place':
        return PlaceData(
            data['uuid'],
            data['name'],
            tuple(data['position']),
            data.get('tokens', 0),
            description,
        )
    return TransitionData(
        data['uuid'],
        data['name'],
        tuple(data['position']),
        description,
        data.get('vertical', False),
    )


def _arc_data(arc: ArcData) -> dict:
    """Write an arc as plain data, its route left out.

    Parameters
    ----------
    arc : ArcData
        The arc.

    Returns
    -------
    dict
        Everything the arc is, apart from where its points fall on the sheet.
    """

    return {
        'uuid': arc.uuid,
        'source': arc.source,
        'target': arc.target,
        'source_port': arc.source_port,
        'target_port': arc.target_port,
        'weight': arc.weight,
        'kind': arc.kind,
        'shape': arc.shape,
        'controls': _frames(arc.controls),
        'points': _frames(arc.points),
    }


def _read_arc(data: dict) -> ArcData:
    """Read an arc back.

    Parameters
    ----------
    data : dict
        What :func:`_arc_data` wrote.

    Returns
    -------
    ArcData
        The arc, with no route: whatever draws it works that out.
    """

    return ArcData(
        data['uuid'],
        data['source'],
        data['target'],
        data['source_port'],
        data['target_port'],
        data['weight'],
        data['kind'],
        data['shape'],
        _read_frames(data['controls']),
        _read_frames(data['points']),
    )


def _guide_data(guide: GuideData) -> dict:
    """Write a guide as plain data.

    Parameters
    ----------
    guide : GuideData
        The guide.

    Returns
    -------
    dict
        Which way it lies and where it is.
    """

    return {'orientation': guide.orientation, 'position': guide.position}


def _read_guide(data: dict) -> GuideData:
    """Read a guide back.

    Parameters
    ----------
    data : dict
        What :func:`_guide_data` wrote.

    Returns
    -------
    GuideData
        The guide.
    """

    return GuideData(data['orientation'], data['position'])


def _frames(frames) -> list | None:
    """Write some places in a chord's frame as plain data.

    Parameters
    ----------
    frames : tuple, optional
        The places, or ``None`` for *untouched*.

    Returns
    -------
    list, optional
        Them as lists, or ``None``, which is the difference between an arc that
        was never shaped and one whose every point was taken out.
    """

    return None if frames is None else [list(frame) for frame in frames]


def _read_frames(frames) -> tuple | None:
    """Read them back.

    Parameters
    ----------
    frames : list, optional
        What :func:`_frames` wrote.

    Returns
    -------
    tuple, optional
        The places, or ``None``.
    """

    return None if frames is None else tuple(tuple(frame) for frame in frames)


# ----------------------------------------------------------------------
# What the net is made of, changed
# ----------------------------------------------------------------------


def _moved(nodes: tuple, uuid: str, position: Point) -> tuple:
    """Give some nodes with one of them moved.

    Parameters
    ----------
    nodes : tuple
        The places or the transitions.
    uuid : str
        Which of them.
    position : tuple of float
        Where it goes.

    Returns
    -------
    tuple
        The nodes, in the order they were in.
    """

    return tuple(
        replace(node, position=position) if node.uuid == uuid else node for node in nodes
    )


def _changed_node(document: NetDocument, uuid: str, **fields) -> NetDocument:
    """Give a description with one node changed.

    Only a node that has every field named is changed, so tokens set on a
    transition — which has none — leave it as it is.

    Parameters
    ----------
    document : simtwin_core.petri_net.NetDocument
        The net.
    uuid : str
        Which node.
    **fields
        What to change about it.

    Returns
    -------
    simtwin_core.petri_net.NetDocument
        The net, with the node in the place it was in.
    """

    def changed(nodes: tuple) -> tuple:
        return tuple(
            replace(node, **fields)
            if node.uuid == uuid and all(hasattr(node, name) for name in fields)
            else node
            for node in nodes
        )

    return replace(
        document, places=changed(document.places), transitions=changed(document.transitions)
    )


def _changed_arc(document: NetDocument, uuid: str, **fields) -> NetDocument:
    """Give a description with one arc changed.

    Parameters
    ----------
    document : simtwin_core.petri_net.NetDocument
        The net.
    uuid : str
        Which arc.
    **fields
        What to change about it.

    Returns
    -------
    simtwin_core.petri_net.NetDocument
        The net, with the arc in the place it was in.
    """

    return replace(
        document,
        arcs=tuple(
            replace(arc, **fields) if arc.uuid == uuid else arc for arc in document.arcs
        ),
    )


def _without(guides: tuple, guide: GuideData) -> tuple:
    """Give some guides without the first one equal to another.

    Parameters
    ----------
    guides : tuple
        The guides.
    guide : GuideData
        The one to leave out.

    Returns
    -------
    tuple
        The rest, in the order they were in.
    """

    kept = list(guides)
    if guide in kept:
        kept.remove(guide)
    return tuple(kept)
