"""The arc of a Petri net: what joins a place to a transition.

An arc is not a shape put somewhere.  It is a **relation between two items**,
and everything about how it is drawn follows from where those two items are: it
has no position of its own, it is never dragged, and moving either end moves it.
That is why it is not dragged out of the Libraries pane the way a place is — a
place dropped on blank paper means something and an arc does not — and why it is
drawn instead from one item's connecting points to another's.

**Which points it uses is settled when it is drawn and never changes again.**
An arc keeps the *index* of a connecting point at each end, not a position, so
dragging a place about moves the arc's end with it and does not move it round to
another point: an arc drawn once is drawn the same way for ever, and a net laid
out by hand stays laid out.  **Both ends are aimed at.**  The near end is
the point that was pressed and the far end is the point it was let go nearest,
so an arc is attached where a person put it at both ends rather than at one.
Both items show their connecting points while the arc is being drawn and the
line being dragged ends on the point it would bind to, so moving the pointer
about the far item picks the point and the binding is settled by eye before the
button is let go.

An end **nobody** aimed at — one an arc is given without a point, which is what a
document being read back and a test do — takes the point facing the other end
that has no arc on it yet, so that a place and a transition joined both ways,
which is ordinary in a net, comes out as two lines rather than one drawn twice.
A point that *was* aimed at is taken whether it is free or not: choosing one is
choosing it.

The arc works in **scene coordinates**: its position stays at the origin and its
geometry is where its ends are.  An item that never moves has nothing to gain
from a local coordinate system, and a line whose two ends belong to two other
items has nothing natural to measure from.

An arc is drawn **straight, curved or S-curved**, which is :class:`ArcShape` and
is chosen from its context menu.  A curve is a cubic Bézier with a control point
at each end, and it is **shaped by hand**: selecting a curved arc brings out
three handles, in the manner of a Bézier in DIA.

Handles are drawn the way the connecting points are — a hairline of the accent
around the colour of the paper — and are told apart from them by their shape
alone: a handle is square, a connecting point is round.

``middle``
    On the curve at its half-way point.  Dragging it moves the whole bow — both
    control points together — so the plain gesture keeps the curve a single bow
    and cannot make an S of it by accident.
``source_control`` and ``target_control``
    The two control points, each joined to the end it belongs to by a **dashed**
    line, which is what says where the curve sets off from that end and where it
    comes in at the other.  Dragging them apart is what an S is; that is what
    the handles are for, and it is the person's to do rather than the code's to
    prevent.

An **S** is the other way of shaping a line, and the simpler one to use.  It is
led through as many **points** as it is given — two to begin with, one bowed
each way, which is what makes it an S — and each point is *on* the curve rather
than off it, so a point is at once where the line goes and the handle that moves
it.  The curve through them is a Catmull-Rom spline drawn as cubic Béziers, one
segment between each pair of knots (see :func:`catmull_rom`), so it is smooth
without anybody having to place a control point.  A point is put in and taken
out from the arc's context menu: *Add Point* puts one on the line where the
pointer is, *Delete Point* over a point takes that one out.  That is what lets
an arc be led **round** something rather than merely leaned away from it, which
a single bow cannot do.

A **selected arc of any shape** also carries a handle at each of its two
ends, ``source`` and ``target``, sitting on the connecting point it is attached
to.  Dragging one puts that end on another connecting point — of the same item,
or of another item the arc may be joined to, which moves the arc rather than
merely reshaping it.  That gesture is not run here: it is the same one that
draws an arc, started from an end rather than from an item, so
:class:`~masafi_simtwin.documents.canvas.CanvasView` runs it and
:meth:`Arc.reattach` is what it calls.  What is here is where the handles are
and how they are drawn.

**A control point is kept in the chord's own frame** — how far along the two
ends it lies and how far across, as fractions of the distance between them — not
as a place on the sheet.  So a curve shaped by hand keeps exactly that shape
when either of its items is dragged: the whole picture turns and scales with the
chord instead of coming apart.  Until a handle is touched the two are
:data:`DEFAULT_CONTROLS`, which draws the same single bow of :data:`CURVE_BOW`
that the shape had before there were handles at all — the cubic that is
identical to that quadratic.

Which way an untouched curve bows follows the arc's own direction, so a pair
drawn both ways between one place and one transition bows apart of its own
accord.

The **weight** is how many tokens the arc carries, one by default.  It is drawn
beside the line only when it is not one, which is the convention of every drawn
Petri net: an arc without a number is an arc of weight one, and writing the one
in would put a number on nearly every arc of nearly every net.

Colours are the palette's, by :func:`~masafi_simtwin.documents.net_item.ink_colour`
— ``Text``, or ``Link`` when the arc is selected — the same rule the items
follow, so a net reads as one drawing in either scheme.
"""

from __future__ import annotations

import math

from collections.abc import Callable
from enum import Enum

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QFont, QPainterPath, QPainterPathStroker, QPen, QTransform
from PyQt6.QtWidgets import QGraphicsItem

from masafi_simtwin.documents.net_item import (
    ARC_Z,
    ITEM_PEN,
    ITEM_PEN_SELECTED,
    NetItem,
    ink_colour,
    paper_colour,
)

#: How far from the line, in millimetres, the pointer may be and still take hold
#: of it.  A line a third of a millimetre wide is a line nobody can click on.
ARC_GRAB = 1.5

#: How long the arrowhead is, in millimetres, and how wide across its base.
ARROW_LENGTH = 2.4
ARROW_WIDTH = 1.8

#: How tall the weight is drawn, in millimetres, and how far off the line.
WEIGHT_HEIGHT = 3.0
WEIGHT_OFFSET = 1.2

#: The weight an arc carries unless it is told otherwise, and the one that is
#: not drawn: an arc without a number is an arc of weight one.
DEFAULT_WEIGHT = 1

#: How far a curved arc bows away from its chord, as a fraction of the distance
#: between its two ends.  A fraction rather than a length, so that a long arc
#: and a short one bow by the same amount *to the eye*.
CURVE_BOW = 0.18

#: Where the two control points of an untouched curve sit, in the chord's own
#: frame: how far along the chord, and how far across it, as fractions of its
#: length.  These are the cubic that draws exactly the quadratic bow of
#: :data:`CURVE_BOW` — a quadratic with control ``Q`` is the cubic with controls
#: two thirds of the way from each end towards ``Q``.
DEFAULT_CONTROLS = (
    (1.0 / 3.0, CURVE_BOW * 2.0 / 3.0),
    (2.0 / 3.0, CURVE_BOW * 2.0 / 3.0),
)

#: How big a handle is drawn, in millimetres of side.  A square, so that a
#: handle is never mistaken for a connecting point, which is a ring; and as
#: small as a connecting point is, because both are marks put on the drawing to
#: be aimed at rather than parts of the drawing itself.
HANDLE_SIZE = 0.7

#: How far from a handle, in millimetres, the pointer may be and still take hold
#: of it.  Well beyond the square it is drawn as: a handle is aimed at, and a
#: handle that has to be hit exactly is a handle nobody can use.  Drawing it
#: smaller is a change to the picture and not to the aiming, which is why the
#: two are separate numbers.
HANDLE_GRAB = 1.3

#: Where the points of an untouched S sit, in the chord's own frame: one bowed
#: :data:`CURVE_BOW` to the left a third of the way along and one the same to
#: the right two thirds of the way, which is an S rather than a description of
#: one.  A shape named after what it looks like should look like it as soon as
#: it is chosen.
DEFAULT_S_POINTS = (
    (1.0 / 3.0, CURVE_BOW),
    (2.0 / 3.0, -CURVE_BOW),
)

#: How many places along a segment are looked at when the nearest place on the
#: curve is wanted — for putting a new point on the line where the pointer is,
#: which is the only thing that asks.  A curve is not a thing to solve exactly
#: when the answer is snapped to the millimetre afterwards.
SEGMENT_SAMPLES = 24

#: What the name of a point handle begins with, the rest of it being which
#: point.  An S carries as many handles as it has points, so they are named
#: rather than listed.
POINT_PREFIX = 'point:'

#: The handles that shape a single bow, in the order they are searched.  The
#: middle one is first, being the one that is aimed at most and the one that
#: overlaps the others when a curve is pulled flat.  Only a curved arc has them,
#: and the arc drags them itself; an S has its points instead, which is what
#: :meth:`Arc.shape_handles` answers.
SHAPE_HANDLES = ('middle', 'source_control', 'target_control')

#: The handles at an arc's two ends, which every selected arc has whatever shape
#: it is.  Dragging one puts that end on another connecting point, and that is
#: the canvas's gesture rather than the arc's — it is the one that draws an arc,
#: started from an end.
END_HANDLES = ('source', 'target')


class ArcShape(Enum):
    """How an arc is drawn between its two ends.

    Attributes
    ----------
    STRAIGHT
        One segment from end to end, which is what a Petri net arc is in most
        drawings and what an arc is until it is told otherwise.
    CURVED
        One cubic Bézier bowing :data:`CURVE_BOW` of its own length off the
        straight, on the left of the way it is going, shaped by its two control
        points.  One bow: an S can be pulled out of it by hand, but it cannot be
        made to go *round* anything, having nowhere to put a second bend.
    S_CURVED
        A curve through as many **points** as it is given, each of them on the
        line rather than off it, drawn as one smooth path.  It starts as an S —
        :data:`DEFAULT_S_POINTS` — and a point is put in or taken out from the
        arc's context menu, so an arc can be led round whatever is in its way.
    """

    STRAIGHT = 'straight'
    CURVED = 'curved'
    S_CURVED = 's-curved'


def point_handle(index: int) -> str:
    """Give the name of the handle on one point of an S.

    Parameters
    ----------
    index : int
        Which point, counting from the source.

    Returns
    -------
    str
        The name, which is :data:`POINT_PREFIX` and the index.
    """

    return f'{POINT_PREFIX}{index}'


def point_of_handle(name: str | None) -> int | None:
    """Give which point a handle is on, when it is on one.

    Parameters
    ----------
    name : str, optional
        The name of a handle, or ``None``.

    Returns
    -------
    int, optional
        The index of the point, or ``None`` when the handle is not one of them.
    """

    if not name or not name.startswith(POINT_PREFIX):
        return None
    return int(name[len(POINT_PREFIX) :])


def catmull_rom(knots: list[QPointF]) -> list[tuple[QPointF, QPointF, QPointF]]:
    """Draw a smooth curve **through** a run of points, as cubic Béziers.

    A Bézier's control points are off the curve, which is what makes a Bézier
    hard to explain and hard to aim: a person putting a point on a line means
    *the line goes here*.  A Catmull-Rom spline is the curve that does that —
    it passes through every knot it is given — and each of its segments is
    exactly one cubic Bézier, so what is drawn is still the one thing
    :meth:`Arc.path` knows how to draw.

    The control points of the segment from ``P[i]`` to ``P[i + 1]`` are a sixth
    of the way along the chords ``P[i - 1] → P[i + 1]`` and ``P[i] → P[i + 2]``,
    which is the uniform spline; the run's own ends are doubled, there being no
    point beyond them to take a direction from.

    Parameters
    ----------
    knots : list of PyQt6.QtCore.QPointF
        The points the curve passes through, in order, at least two of them.

    Returns
    -------
    list of tuple
        One ``(first control, second control, end)`` for each segment, which is
        what a ``cubicTo`` takes.
    """

    segments = []
    count = len(knots)
    for index in range(count - 1):
        before = knots[max(index - 1, 0)]
        start = knots[index]
        end = knots[index + 1]
        after = knots[min(index + 2, count - 1)]
        segments.append(
            (
                QPointF(
                    start.x() + (end.x() - before.x()) / 6.0,
                    start.y() + (end.y() - before.y()) / 6.0,
                ),
                QPointF(
                    end.x() - (after.x() - start.x()) / 6.0,
                    end.y() - (after.y() - start.y()) / 6.0,
                ),
                QPointF(end),
            )
        )
    return segments


class Arc(QGraphicsItem):
    """One arc of a Petri net, from a place to a transition or back.

    Parameters
    ----------
    source : masafi_simtwin.documents.net_item.NetItem
        The item the arc leaves.
    target : masafi_simtwin.documents.net_item.NetItem
        The item it enters, which is where the arrowhead is.
    source_port : int, optional
        Which of the source's connecting points the arc leaves by.  The point
        that was pressed, when a person drew it; the point facing the target and
        free of arcs when it is left out.
    target_port : int, optional
        Which of the target's it enters by.  The point it was let go nearest,
        when a person drew it; the point facing the source and free of arcs when
        it is left out.
    weight : int, optional
        How many tokens it carries.  One by default, which is the weight that is
        not drawn.
    shape_kind : ArcShape, optional
        Whether it is drawn straight or curved.  Straight by default.
    snap : collections.abc.Callable, optional
        What to round a handle to as it is dragged.  The canvas passes its own,
        which is the millimetre at every zoom; without one a handle goes where
        it is put.
    parent : PyQt6.QtWidgets.QGraphicsItem, optional
        Parent item.

    Attributes
    ----------
    source, target : masafi_simtwin.documents.net_item.NetItem
        The two ends.  They are items rather than positions: an arc is a
        relation, and where it is drawn is worked out from them.
    source_port, target_port : int
        Which connecting point of each end it is attached to.  Settled when the
        arc is drawn and never changed by anything moving.
    """

    def __init__(
        self,
        source: NetItem,
        target: NetItem,
        source_port: int | None = None,
        target_port: int | None = None,
        weight: int = DEFAULT_WEIGHT,
        shape_kind: ArcShape = ArcShape.STRAIGHT,
        snap: Callable[[float], float] | None = None,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self.source = source
        self.target = target
        self._weight = int(weight)
        self._shape_kind = ArcShape(shape_kind)
        self._snap = snap
        self._controls = [list(control) for control in DEFAULT_CONTROLS]
        self._points = [list(point) for point in DEFAULT_S_POINTS]
        self._dragging: str | None = None
        self._line = QLineF()

        if source_port is None:
            source_port = source.free_port_towards(target.scenePos())
        self.source_port = int(source_port)
        if target_port is None:
            target_port = target.free_port_towards(source.scene_port(self.source_port))
        self.target_port = int(target_port)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(ARC_Z)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.source.attach(self)
        self.target.attach(self)
        self.route()

    # ------------------------------------------------------------------
    # What it joins
    # ------------------------------------------------------------------

    def joins(self, one: NetItem, other: NetItem) -> bool:
        """Say whether this arc runs between two items, either way round.

        Parameters
        ----------
        one, other : masafi_simtwin.documents.net_item.NetItem
            The pair to ask about.

        Returns
        -------
        bool
            Whether they are this arc's two ends, in either direction — the
            direction being what tells two arcs of a pair apart rather than what
            makes them a different pair.
        """

        return {id(self.source), id(self.target)} == {id(one), id(other)}

    def port_of(self, item: NetItem) -> int:
        """Give which connecting point of one of its ends the arc is on.

        Parameters
        ----------
        item : masafi_simtwin.documents.net_item.NetItem
            One of the two ends.

        Returns
        -------
        int
            The index of the point, the source's for anything that is not the
            target — an arc has two ends and is asked by one of them.
        """

        return self.target_port if item is self.target else self.source_port

    def detach(self) -> None:
        """Take the arc off both of its ends.

        Called when it is removed from the sheet.  Without it an item would go
        on telling an arc that is no longer there that it has moved, which is a
        line drawn to somewhere nothing is.
        """

        self.source.detach(self)
        self.target.detach(self)

    # ------------------------------------------------------------------
    # Where it runs
    # ------------------------------------------------------------------

    @property
    def line(self) -> QLineF:
        """PyQt6.QtCore.QLineF: Where the arc runs, in scene millimetres."""

        return QLineF(self._line)

    def route(self) -> None:
        """Work out where the arc runs, its two ends having moved.

        Nothing is **chosen** here: the connecting points were settled when the
        arc was drawn, and this only asks where those two points now are.  That
        is what makes an arc keep its shape as a net is laid out — an item drags
        its end of the arc along with it rather than passing it round to another
        point.

        The scene has to be told the geometry is changing before it changes, or
        it goes on looking for the arc where the arc no longer is.
        """

        self.prepareGeometryChange()
        self._line = QLineF(
            self.source.scene_port(self.source_port),
            self.target.scene_port(self.target_port),
        )
        self.update()

    # ------------------------------------------------------------------
    # Straight or curved
    # ------------------------------------------------------------------

    @property
    def shape_kind(self) -> ArcShape:
        """ArcShape: Whether the arc is drawn straight or curved.

        Not ``shape``: :meth:`QGraphicsItem.shape` is what a scene hit-tests
        against, and an item may not have both.
        """

        return self._shape_kind

    @shape_kind.setter
    def shape_kind(self, value: ArcShape) -> None:
        """Draw the arc straight or curved from now on.

        Parameters
        ----------
        value : ArcShape
            Which of them.
        """

        value = ArcShape(value)
        if value != self._shape_kind:
            self.prepareGeometryChange()
            self._shape_kind = value
            self.update()

    @property
    def curved(self) -> bool:
        """bool: Whether the arc bows rather than running straight from end to
        end, which is either of the two curved shapes."""

        return self._shape_kind is not ArcShape.STRAIGHT

    def chord_point(self, along: float, across: float) -> QPointF:
        """Turn a place in the chord's own frame into a place on the sheet.

        The frame is the arc's two ends: ``along`` runs from nought at the
        source to one at the target, and ``across`` is at right angles to it, to
        the **left of the way the arc is going**.  Both are fractions of the
        distance between the ends, so a shape kept in this frame turns and
        scales with the arc rather than coming apart when an item is dragged.

        Parameters
        ----------
        along : float
            How far along, as a fraction.
        across : float
            How far across, as a fraction.

        Returns
        -------
        PyQt6.QtCore.QPointF
            The place, in scene millimetres.
        """

        length = self._line.length()
        origin = self._line.p1()
        if not length:
            return QPointF(origin)

        forward = QPointF(self._line.dx() / length, self._line.dy() / length)
        sideways = QPointF(-forward.y(), forward.x())
        return QPointF(
            origin.x() + (forward.x() * along + sideways.x() * across) * length,
            origin.y() + (forward.y() * along + sideways.y() * across) * length,
        )

    def chord_frame(self, point: QPointF) -> tuple[float, float]:
        """Turn a place on the sheet into a place in the chord's own frame.

        The other half of :meth:`chord_point`, and what a dragged handle is
        stored as.

        Parameters
        ----------
        point : PyQt6.QtCore.QPointF
            The place, in scene millimetres.

        Returns
        -------
        tuple of float
            How far along and how far across, as fractions of the chord.
        """

        length = self._line.length()
        if not length:
            return 0.0, 0.0

        forward = QPointF(self._line.dx() / length, self._line.dy() / length)
        sideways = QPointF(-forward.y(), forward.x())
        reach = point - self._line.p1()
        return (
            (reach.x() * forward.x() + reach.y() * forward.y()) / length,
            (reach.x() * sideways.x() + reach.y() * sideways.y()) / length,
        )

    def control_points(self) -> list[QPointF]:
        """Give the two points that bend a curved arc.

        Returns
        -------
        list of PyQt6.QtCore.QPointF
            The one that says where the curve leaves the source and the one that
            says where it comes in at the target, in scene millimetres.
        """

        return [self.chord_point(along, across) for along, across in self._controls]

    def curve_middle(self) -> QPointF:
        """Give the half-way point of the arc as it is drawn.

        Returns
        -------
        PyQt6.QtCore.QPointF
            Where the middle handle sits, in scene millimetres — on the curve
            itself rather than off it, which is what makes it a thing to take
            hold of rather than a thing to interpret.
        """

        path = self.path()
        if not path.length():
            return self._line.center()
        return path.pointAtPercent(0.5)

    # ------------------------------------------------------------------
    # The points an S is led through
    # ------------------------------------------------------------------

    def curve_points(self) -> list[QPointF]:
        """Give the points an S is led through, on the sheet.

        Returns
        -------
        list of PyQt6.QtCore.QPointF
            Them, in order from the source, in scene millimetres.  They are kept
            in the chord's own frame, as the control points are, so an S shaped
            by hand keeps its shape when either of its items is dragged.
        """

        return [self.chord_point(along, across) for along, across in self._points]

    def segments(self) -> list[tuple[QPointF, QPointF, QPointF]]:
        """Give the curve as cubic segments, which is what is drawn.

        One segment for a single bow, one for every gap between the knots of an
        S — its two ends and the points it is led through — and none at all for
        a straight arc, which has no curve to cut up.

        Returns
        -------
        list of tuple
            One ``(first control, second control, end)`` for each, in scene
            millimetres.
        """

        if self._shape_kind is ArcShape.CURVED:
            first, second = self.control_points()
            return [(first, second, self._line.p2())]
        if self._shape_kind is ArcShape.S_CURVED:
            knots = [self._line.p1(), *self.curve_points(), self._line.p2()]
            return catmull_rom(knots)
        return []

    def segment_paths(self) -> list[QPainterPath]:
        """Give each segment of the curve as a path of its own.

        Which is what says *where along the arc* a place is: the whole path
        answers how near, and only the segments answer between which two points.

        Returns
        -------
        list of PyQt6.QtGui.QPainterPath
            One path per segment, in the order they are drawn.
        """

        start = self._line.p1()
        paths = []
        for first, second, end in self.segments():
            one = QPainterPath(start)
            one.cubicTo(first, second, end)
            paths.append(one)
            start = end
        return paths

    def nearest_on_curve(self, point: QPointF) -> tuple[int, QPointF]:
        """Find the place on the drawn arc nearest a place on the sheet.

        Sampled rather than solved: the answer is snapped to the millimetre
        afterwards, so an exact root of a cubic would be thrown away.

        Parameters
        ----------
        point : PyQt6.QtCore.QPointF
            Where to look from, in scene millimetres.

        Returns
        -------
        tuple
            Which segment it fell on and where on it, in scene millimetres.  The
            segment is what says where a new point belongs in the run: the one
            between the knots the pointer is between.
        """

        best = None
        found = (0, self._line.center())
        for index, one in enumerate(self.segment_paths()):
            for step in range(SEGMENT_SAMPLES + 1):
                where = one.pointAtPercent(step / SEGMENT_SAMPLES)
                gap = math.hypot(point.x() - where.x(), point.y() - where.y())
                if best is None or gap < best:
                    best = gap
                    found = (index, where)
        return found

    def insert_point(self, at: QPointF) -> int | None:
        """Put another point into the curve, where the pointer is.

        **On the line rather than under the pointer.**  A point is put in to be
        dragged somewhere, and a curve that jumped as the point went in would
        have to be put back before it could be shaped: the new point goes on the
        nearest place on the curve, so the picture does not change and the
        handle comes out where the person aimed.

        Parameters
        ----------
        at : PyQt6.QtCore.QPointF
            Where the arc was aimed at, in scene millimetres.

        Returns
        -------
        int, optional
            Which point it became, or ``None`` when the arc is not one that is
            led through points.
        """

        if self._shape_kind is not ArcShape.S_CURVED:
            return None

        index, where = self.nearest_on_curve(at)
        if self._snap is not None:
            where = QPointF(self._snap(where.x()), self._snap(where.y()))

        self.prepareGeometryChange()
        self._points.insert(index, list(self.chord_frame(where)))
        self.update()
        return index

    def remove_point(self, index: int) -> bool:
        """Take one point out of the curve again.

        Taking the last one out is allowed: an S led through no points is a
        straight line, and it is still an S — the points can be put back.  A
        gesture that refuses on the last of something is a gesture a person has
        to count before using.

        Parameters
        ----------
        index : int
            Which point, counting from the source.

        Returns
        -------
        bool
            Whether there was one there to take out.
        """

        if not 0 <= index < len(self._points):
            return False

        self.prepareGeometryChange()
        del self._points[index]
        self.update()
        return True

    def point_at(self, position: QPointF) -> int | None:
        """Find which point of an S a scene position falls on.

        The **nearest** one within :data:`HANDLE_GRAB`, which is the rule the
        connecting points follow.  Asked of the arc's geometry rather than of
        its handles, because a menu asking *is there a point here?* is asking
        about the arc and not about what is drawn on it: an arc that is not
        selected has no handles at all.  An arc of another shape has no points
        on it whatever it may be keeping for when it is made an S again.

        Parameters
        ----------
        position : PyQt6.QtCore.QPointF
            Where to look, in scene millimetres.

        Returns
        -------
        int, optional
            The index of the point, or ``None`` for none of them.
        """

        if self._shape_kind is not ArcShape.S_CURVED:
            return None

        best = None
        found = None
        for index, where in enumerate(self.curve_points()):
            gap = math.hypot(position.x() - where.x(), position.y() - where.y())
            if gap <= HANDLE_GRAB and (best is None or gap < best):
                best = gap
                found = index
        return found

    def point_handles(self) -> tuple:
        """Give the names of the handles on the points of an S.

        Returns
        -------
        tuple of str
            One per point, in order, and none at all on an arc of another shape.
        """

        if self._shape_kind is not ArcShape.S_CURVED:
            return ()
        return tuple(point_handle(index) for index in range(len(self._points)))

    # ------------------------------------------------------------------
    # The handles a curve is shaped by
    # ------------------------------------------------------------------

    def handles(self) -> dict:
        """Give the handles the arc carries, and where they are.

        There are none on an arc that is not selected: a sheet showing a handle
        for every arc on it is a sheet nobody can read, and selecting a thing is
        how a person says which one they mean.

        Returns
        -------
        dict
            ``source`` and ``target``, on the connecting points the two ends are
            attached to, on any selected arc; on a curved one ``middle``, on the
            curve half way along, with ``source_control`` and ``target_control``,
            the two control points; and on an S one handle per point it is led
            through, named by :func:`point_handle`.  Empty when the arc is not
            selected.
        """

        if not self.isSelected():
            return {}

        found = {'source': self._line.p1(), 'target': self._line.p2()}
        if self._shape_kind is ArcShape.CURVED:
            first, second = self.control_points()
            found['middle'] = self.curve_middle()
            found['source_control'] = first
            found['target_control'] = second
        elif self._shape_kind is ArcShape.S_CURVED:
            for index, where in enumerate(self.curve_points()):
                found[point_handle(index)] = where
        return found

    def shape_handles(self) -> tuple:
        """Give the handles the arc shapes itself by, in the order they are
        searched.

        Which they are is the shape's own business: the three of a single bow,
        one per point of an S, and none at all on a straight arc.  The two at
        the ends are not among them — they are dragged by the canvas, that being
        the gesture which draws an arc.

        Returns
        -------
        tuple of str
            Their names.
        """

        if self._shape_kind is ArcShape.CURVED:
            return SHAPE_HANDLES
        return self.point_handles()

    def handle_order(self) -> tuple:
        """Give every handle the arc carries, in the order they are searched.

        Returns
        -------
        tuple of str
            The shaping handles first, the ends after them: a handle sitting on
            an end is the one a person means when the two are on top of one
            another.
        """

        return self.shape_handles() + END_HANDLES

    def handle_at(self, point: QPointF, among=None) -> str | None:
        """Find the handle a scene position takes hold of.

        Parameters
        ----------
        point : PyQt6.QtCore.QPointF
            Where to look, in scene millimetres.
        among : collections.abc.Iterable, optional
            Which handles to look at, in the order they are tried, so that the
            arc can ask for the ones it drags itself and the canvas for the ones
            it drags.  Every one this arc carries by default, which depends on
            the shape it is drawn as — see :meth:`handle_order`.

        Returns
        -------
        str, optional
            Which handle, the first of ``among`` within reach, or ``None`` for
            none of them.
        """

        found = self.handles()
        for name in self.handle_order() if among is None else among:
            where = found.get(name)
            if where is None:
                continue
            if math.hypot(point.x() - where.x(), point.y() - where.y()) <= HANDLE_GRAB:
                return name
        return None

    def reattach(self, end: str, item: NetItem, port: int) -> bool:
        """Put one end of the arc on another connecting point.

        The point may belong to the item that end is already on, which only
        moves it round; or to another item, which moves the arc itself.  The two
        are one gesture because they are one question — *where does this end
        go?* — and telling them apart would mean a person had to know which they
        were doing before they started.

        Parameters
        ----------
        end : str
            ``source`` or ``target``.
        item : masafi_simtwin.documents.net_item.NetItem
            What that end is to be attached to.
        port : int
            Which of its connecting points.

        Returns
        -------
        bool
            Whether the arc was changed.  It is not when the end would be put
            where it already is, nor when the two ends would become the same
            item — an arc from a thing to itself is not an arc.
        """

        if end not in END_HANDLES:
            return False

        other = self.target if end == 'source' else self.source
        if item is other:
            return False

        was = self.source if end == 'source' else self.target
        was_port = self.source_port if end == 'source' else self.target_port
        if item is was and port == was_port:
            return False

        if item is not was:
            was.detach(self)
            item.attach(self)
            if end == 'source':
                self.source = item
            else:
                self.target = item

        if end == 'source':
            self.source_port = int(port)
        else:
            self.target_port = int(port)

        self.route()
        return True

    def move_handle(self, name: str, point: QPointF) -> None:
        """Put one handle where the pointer is, and reshape the curve.

        The **middle** handle moves the whole bow: both control points shift by
        the same amount, so the curve keeps its shape and only its depth and its
        lean change.  A cubic's half-way point moves three quarters as far as
        its controls do, so the controls are moved four thirds of the way — the
        handle then lands under the pointer rather than short of it.

        The other two are the control points themselves, and moving them apart
        is what makes an S out of a single bow.  That is what they are for.

        A handle on a **point of an S** is simpler than either, the point being
        on the line: it goes where it is put, and the curve follows it.

        Parameters
        ----------
        name : str
            Which handle, one this arc carries — see :meth:`shape_handles`.
        point : PyQt6.QtCore.QPointF
            Where to put it, in scene millimetres.
        """

        if self._snap is not None:
            point = QPointF(self._snap(point.x()), self._snap(point.y()))

        index = point_of_handle(name)
        if index is not None:
            if self._shape_kind is ArcShape.S_CURVED and 0 <= index < len(self._points):
                self.prepareGeometryChange()
                self._points[index] = list(self.chord_frame(point))
                self.update()
            return

        if self._shape_kind is not ArcShape.CURVED:
            return

        self.prepareGeometryChange()
        if name == 'middle':
            was = self.chord_frame(self.curve_middle())
            wants = self.chord_frame(point)
            shift = ((wants[0] - was[0]) * 4.0 / 3.0, (wants[1] - was[1]) * 4.0 / 3.0)
            for control in self._controls:
                control[0] += shift[0]
                control[1] += shift[1]
        elif name in ('source_control', 'target_control'):
            index = 0 if name == 'source_control' else 1
            self._controls[index] = list(self.chord_frame(point))
        self.update()

    def handle_rect(self, at: QPointF) -> QRectF:
        """Give the square a handle is drawn as.

        Parameters
        ----------
        at : PyQt6.QtCore.QPointF
            Where the handle is, in scene millimetres.

        Returns
        -------
        PyQt6.QtCore.QRectF
            The square, centred there.
        """

        half = HANDLE_SIZE / 2.0
        return QRectF(at.x() - half, at.y() - half, HANDLE_SIZE, HANDLE_SIZE)

    # ------------------------------------------------------------------
    # The weight
    # ------------------------------------------------------------------

    @property
    def weight(self) -> int:
        """int: How many tokens the arc carries, one by default."""

        return self._weight

    @weight.setter
    def weight(self, value: int) -> None:
        """Set how many tokens it carries.

        Parameters
        ----------
        value : int
            The weight.  Below one is not a weight, so it is held at one.
        """

        value = max(int(value), 1)
        if value != self._weight:
            self.prepareGeometryChange()
            self._weight = value
            self.update()

    def weight_path(self) -> QPainterPath | None:
        """Build the number beside the line, when there is one to draw.

        The number is a **path** rather than text drawn with a font, because the
        scene is measured in millimetres and a font is measured in points: a
        path can be scaled to a height in millimetres, so the number is the same
        size on the paper at every zoom and on every machine, and it is painted
        with the same brush as the rest of the arc.

        Returns
        -------
        PyQt6.QtGui.QPainterPath, optional
            The digits, centred beside the middle of the line, or ``None`` when
            the weight is one and nothing is drawn.
        """

        if self._weight == DEFAULT_WEIGHT:
            return None

        glyphs = QPainterPath()
        glyphs.addText(0.0, 0.0, QFont(), str(self._weight))
        drawn = glyphs.boundingRect()
        if drawn.isEmpty():
            return None

        glyphs.translate(-drawn.center().x(), -drawn.center().y())
        scale = WEIGHT_HEIGHT / drawn.height()
        middle, away = self._halfway()
        reach = WEIGHT_OFFSET + WEIGHT_HEIGHT / 2.0

        placed = QTransform().scale(scale, scale).map(glyphs)
        placed.translate(
            middle.x() + away.x() * reach,
            middle.y() + away.y() * reach,
        )
        return placed

    def _halfway(self) -> tuple[QPointF, QPointF]:
        """Give the middle of the arc and the way across it there.

        The middle of the *drawn* arc rather than of the chord, so a number
        beside a curved arc sits beside the curve.  ``QPainterPath`` answers
        both halves of the question, which is what keeps one placement rule for
        every shape an arc may be given.

        Returns
        -------
        tuple
            The point, in scene millimetres, and the unit vector across the arc
            there.
        """

        path = self.path()
        if not path.length():
            return self._line.center(), self._perpendicular()

        angle = math.radians(path.angleAtPercent(0.5))
        along = QPointF(math.cos(angle), -math.sin(angle))
        return path.pointAtPercent(0.5), QPointF(-along.y(), along.x())

    def _arriving(self) -> QPointF:
        """Give the unit vector the arc is travelling in when it arrives.

        The chord for a straight arc, and the tangent at the end for a curved
        one — which for a cubic Bézier is the way from its second control point
        to its end, taken from the **last** segment, an S having several.

        Returns
        -------
        PyQt6.QtCore.QPointF
            The direction, of unit length.
        """

        segments = self.segments()
        reach = QLineF(segments[-1][1], self._line.p2()) if segments else QLineF(self._line)
        if not reach.length():
            reach = QLineF(self._line)
        length = reach.length()
        if not length:
            return QPointF(1.0, 0.0)
        return QPointF(reach.dx() / length, reach.dy() / length)

    def _perpendicular(self) -> QPointF:
        """Give the unit vector across the line, which is where the weight sits.

        Returns
        -------
        PyQt6.QtCore.QPointF
            One millimetre across the line, or across the sheet when the arc has
            no length to be across.
        """

        length = self._line.length()
        if not length:
            return QPointF(0.0, -1.0)
        return QPointF(
            -(self._line.dy()) / length,
            self._line.dx() / length,
        )

    # ------------------------------------------------------------------
    # What it covers, and how it is drawn
    # ------------------------------------------------------------------

    def path(self) -> QPainterPath:
        """Give the arc as a path, which is what is drawn, stroked and measured.

        Everything about the arc's geometry comes through here — what is
        painted, what can be taken hold of, where the arrowhead points and where
        the weight sits — so a new :class:`ArcShape` is a new branch here and
        nothing else.

        Returns
        -------
        PyQt6.QtGui.QPainterPath
            From one end to the other, straight or bowed.
        """

        path = QPainterPath(self._line.p1())
        segments = self.segments()
        if not segments:
            path.lineTo(self._line.p2())
        for first, second, end in segments:
            path.cubicTo(first, second, end)
        return path

    def arrow(self) -> QPainterPath:
        """Build the arrowhead, at the end the arc enters.

        It points along the arc's **tangent** where it arrives, not along the
        chord, so a curved arc meets its target head on rather than at an angle
        to the line that was drawn.

        Returns
        -------
        PyQt6.QtGui.QPainterPath
            A filled triangle whose point is on the target's boundary, or an
            empty path when the arc has no length to point along.
        """

        head = QPainterPath()
        length = self._line.length()
        if not length:
            return head

        tip = self._line.p2()
        along = self._arriving()
        across = QPointF(-along.y(), along.x())
        back = QPointF(tip.x() - along.x() * ARROW_LENGTH, tip.y() - along.y() * ARROW_LENGTH)

        head.moveTo(tip)
        head.lineTo(
            back.x() + across.x() * ARROW_WIDTH / 2.0,
            back.y() + across.y() * ARROW_WIDTH / 2.0,
        )
        head.lineTo(
            back.x() - across.x() * ARROW_WIDTH / 2.0,
            back.y() - across.y() * ARROW_WIDTH / 2.0,
        )
        head.closeSubpath()
        return head

    def boundingRect(self) -> QRectF:  # noqa: N802  (Qt naming)
        """Give what the arc is drawn and clicked inside.

        Returns
        -------
        PyQt6.QtCore.QRectF
            The arc as it is drawn, the arrowhead, the number beside it, its
            handles when it has any, and the band the line can be taken hold of
            in.
        """

        area = self.path().boundingRect().normalized()
        weight = self.weight_path()
        if weight is not None:
            area = area.united(weight.boundingRect())
        for where in self.handles().values():
            area = area.united(self.handle_rect(where))
        reach = max(ARC_GRAB, ARROW_WIDTH, ITEM_PEN_SELECTED, HANDLE_GRAB)
        return area.adjusted(-reach, -reach, reach, reach)

    def shape(self) -> QPainterPath:
        """Give the band the arc can be taken hold of in.

        Returns
        -------
        PyQt6.QtGui.QPainterPath
            The line stroked to :data:`ARC_GRAB`, with the arrowhead and with a
            reach around each handle — a line a third of a millimetre wide is a
            line nobody can click on, and a handle outside the shape is a handle
            no press ever reaches, the scene sending a press to the item whose
            shape it fell in.
        """

        stroker = QPainterPathStroker()
        stroker.setWidth(ARC_GRAB * 2.0)
        band = stroker.createStroke(self.path())
        band.addPath(self.arrow())
        for where in self.handles().values():
            band.addEllipse(where, HANDLE_GRAB, HANDLE_GRAB)
        return band

    def paint(self, painter, option, widget=None) -> None:
        """Draw the arc, its arrowhead and its weight.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the view.
        option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
            What the view knows about drawing this item, its palette included.
        widget : PyQt6.QtWidgets.QWidget, optional
            The widget being painted on.
        """

        colour = ink_colour(self.isSelected(), option)
        width = ITEM_PEN_SELECTED if self.isSelected() else ITEM_PEN

        pen = QPen(colour, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour)
        painter.drawPath(self.arrow())

        weight = self.weight_path()
        if weight is not None:
            painter.drawPath(weight)

        self._paint_handles(painter, option)

    def mousePressEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Take hold of a shaping handle, or leave the press to the scene.

        Only the handles that shape the curve: the two at the ends are dragged
        by the canvas, which is where the gesture that draws an arc lives, and
        the canvas takes those presses before the scene ever sees them.

        Parameters
        ----------
        event : PyQt6.QtWidgets.QGraphicsSceneMouseEvent
            The mouse event.
        """

        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = self.handle_at(event.scenePos(), self.shape_handles())
            if self._dragging is not None:
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Drag whichever handle was taken hold of.

        Parameters
        ----------
        event : PyQt6.QtWidgets.QGraphicsSceneMouseEvent
            The mouse event.
        """

        if self._dragging is not None:
            self.move_handle(self._dragging, event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Let go of the handle.

        Parameters
        ----------
        event : PyQt6.QtWidgets.QGraphicsSceneMouseEvent
            The mouse event.
        """

        if self._dragging is not None:
            self._dragging = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _paint_handles(self, painter, option) -> None:
        """Draw the handles a selected curve is shaped by.

        A handle is drawn the way a connecting point is: a **hairline** of the
        accent — one pixel at every zoom — around the colour of the paper.  It
        is a thing to take hold of rather than a mark on the drawing, and the
        two are told apart by their shape alone, a handle being square and a
        connecting point round.  The fill is what makes a handle legible over
        the curve it sits on, exactly as it makes a connecting point legible
        over a transition.

        Each control point is joined to the end it belongs to by a **dashed**
        line, which is what says that it is that end's — the line is not part of
        the arc and is not something the arc goes along, so it is drawn the way
        a guide is drawn rather than the way an arc is.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the view.
        option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
            What the view knows about drawing this item, its palette included.
        """

        found = self.handles()
        if not found:
            return

        accent = ink_colour(True, option)
        lead = QPen(accent, 0.0)
        lead.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(lead)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if 'source_control' in found:
            painter.drawLine(QLineF(self._line.p1(), found['source_control']))
            painter.drawLine(QLineF(self._line.p2(), found['target_control']))

        painter.setPen(QPen(accent, 0.0))
        painter.setBrush(paper_colour(option))
        for where in found.values():
            painter.drawRect(self.handle_rect(where))
