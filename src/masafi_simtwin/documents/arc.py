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

An arc is drawn **straight or curved**, which is
:class:`ArcShape` and is chosen from its context menu.  A curve is a cubic
Bézier with a control point at each end, and it is **shaped by hand**: selecting
a curved arc brings out three handles, in the manner of a Bézier in DIA.

Handles are drawn the way the connecting points are — a hairline of the accent
around the colour of the paper — and are told apart from them by their shape
alone: a handle is square, a connecting point is round.

``middle``
    On the curve at its half-way point.  Dragging it moves the whole bow — both
    control points together — so the plain gesture keeps the curve a single bow
    and cannot make an S of it by accident.
``start`` and ``end``
    The two control points, each joined to the end it belongs to by a **dashed**
    line, which is what says where the curve sets off from that end and where it
    comes in at the other.  Dragging them apart is what an S is; that is what
    the handles are for, and it is the person's to do rather than the code's to
    prevent.

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
#: handle is never mistaken for a connecting point, which is a ring.
HANDLE_SIZE = 1.4

#: How far from a handle, in millimetres, the pointer may be and still take hold
#: of it.  More than half its side: a handle is aimed at, and a handle that has
#: to be hit exactly is a handle nobody can use.
HANDLE_GRAB = 1.3

#: The handles a curved arc carries, in the order they are drawn and searched.
#: The middle one is first, being the one that is aimed at most and the one that
#: overlaps the others when a curve is pulled flat.
HANDLES = ('middle', 'start', 'end')


class ArcShape(Enum):
    """How an arc is drawn between its two ends.

    Attributes
    ----------
    STRAIGHT
        One segment from end to end, which is what a Petri net arc is in most
        drawings and what an arc is until it is told otherwise.
    CURVED
        A single quadratic Bézier bowing :data:`CURVE_BOW` of its own length off
        the straight, on the left of the way it is going.  One control point and
        no S: the shapes with more than one bend are a later piece of work, and
        this enumeration is where they go.
    """

    STRAIGHT = 'straight'
    CURVED = 'curved'


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
        """bool: Whether the arc bows, which is the whole of what a menu asks."""

        return self._shape_kind is ArcShape.CURVED

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
    # The handles a curve is shaped by
    # ------------------------------------------------------------------

    def handles(self) -> dict:
        """Give the handles a curved arc is shaped by, and where they are.

        There are none on a straight arc and none on one that is not selected: a
        sheet showing a handle for every arc on it is a sheet nobody can read,
        and selecting a thing is how a person says which one they mean.

        Returns
        -------
        dict
            ``middle``, on the curve half way along; ``start`` and ``end``, the
            two control points.  Empty when there is nothing to shape.
        """

        if self._shape_kind is not ArcShape.CURVED or not self.isSelected():
            return {}

        first, second = self.control_points()
        return {'middle': self.curve_middle(), 'start': first, 'end': second}

    def handle_at(self, point: QPointF) -> str | None:
        """Find the handle a scene position takes hold of.

        Parameters
        ----------
        point : PyQt6.QtCore.QPointF
            Where to look, in scene millimetres.

        Returns
        -------
        str, optional
            Which handle, in the order of :data:`HANDLES` so that the middle one
            wins where they overlap, or ``None`` for none of them.
        """

        found = self.handles()
        for name in HANDLES:
            where = found.get(name)
            if where is None:
                continue
            if math.hypot(point.x() - where.x(), point.y() - where.y()) <= HANDLE_GRAB:
                return name
        return None

    def move_handle(self, name: str, point: QPointF) -> None:
        """Put one handle where the pointer is, and reshape the curve.

        The **middle** handle moves the whole bow: both control points shift by
        the same amount, so the curve keeps its shape and only its depth and its
        lean change.  A cubic's half-way point moves three quarters as far as
        its controls do, so the controls are moved four thirds of the way — the
        handle then lands under the pointer rather than short of it.

        The other two are the control points themselves, and moving them apart
        is what makes an S.  That is what they are for.

        Parameters
        ----------
        name : str
            Which handle, one of :data:`HANDLES`.
        point : PyQt6.QtCore.QPointF
            Where to put it, in scene millimetres.
        """

        if self._shape_kind is not ArcShape.CURVED:
            return
        if self._snap is not None:
            point = QPointF(self._snap(point.x()), self._snap(point.y()))

        self.prepareGeometryChange()
        if name == 'middle':
            was = self.chord_frame(self.curve_middle())
            wants = self.chord_frame(point)
            shift = ((wants[0] - was[0]) * 4.0 / 3.0, (wants[1] - was[1]) * 4.0 / 3.0)
            for control in self._controls:
                control[0] += shift[0]
                control[1] += shift[1]
        elif name in ('start', 'end'):
            self._controls[0 if name == 'start' else 1] = list(self.chord_frame(point))
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
        to its end.

        Returns
        -------
        PyQt6.QtCore.QPointF
            The direction, of unit length.
        """

        if self._shape_kind is ArcShape.CURVED:
            reach = QLineF(self.control_points()[1], self._line.p2())
        else:
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
        if self._shape_kind is ArcShape.CURVED:
            first, second = self.control_points()
            path.cubicTo(first, second, self._line.p2())
        else:
            path.lineTo(self._line.p2())
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
        """Take hold of a handle, or leave the press to the scene.

        Parameters
        ----------
        event : PyQt6.QtWidgets.QGraphicsSceneMouseEvent
            The mouse event.
        """

        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = self.handle_at(event.scenePos())
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
        painter.drawLine(QLineF(self._line.p1(), found['start']))
        painter.drawLine(QLineF(self._line.p2(), found['end']))

        painter.setPen(QPen(accent, 0.0))
        painter.setBrush(paper_colour(option))
        for name in HANDLES:
            painter.drawRect(self.handle_rect(found[name]))
