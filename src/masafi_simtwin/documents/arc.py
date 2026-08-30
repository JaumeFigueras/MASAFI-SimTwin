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
:class:`ArcShape` and is chosen from its context menu.  The curve is a single
quadratic Bézier with one control point — no S, no corners, nothing to drag —
because the first thing worth having is a way of telling two arcs apart when
they run between the same two places, and one bow does that.  Which way it bows
follows the arc's own direction, so a pair drawn both ways between one place and
one transition bows apart of its own accord.  Richer shapes come later, and
:class:`ArcShape` is the one place they will be added.

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
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self.source = source
        self.target = target
        self._weight = int(weight)
        self._shape_kind = ArcShape(shape_kind)
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

    def control_point(self) -> QPointF:
        """Give the one point that bends a curved arc.

        A quadratic Bézier has a single control point, and this is it: the
        middle of the chord, moved :data:`CURVE_BOW` of the chord's length to
        the **left of the way the arc is going**.  Following the arc's own
        direction is what makes a place and a transition joined both ways bow
        apart rather than on top of one another, without either arc knowing the
        other is there.

        Returns
        -------
        PyQt6.QtCore.QPointF
            The control point, in scene millimetres.  It is on the chord itself
            for an arc with no length to bow across.
        """

        away = self._perpendicular()
        reach = self._line.length() * CURVE_BOW
        middle = self._line.center()
        return QPointF(middle.x() + away.x() * reach, middle.y() + away.y() * reach)

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
        one — which for a quadratic Bézier is the way from its control point to
        its end.

        Returns
        -------
        PyQt6.QtCore.QPointF
            The direction, of unit length.
        """

        if self._shape_kind is ArcShape.CURVED:
            reach = QLineF(self.control_point(), self._line.p2())
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
            path.quadTo(self.control_point(), self._line.p2())
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
            The arc as it is drawn, the arrowhead, the number beside it and the
            band the line can be taken hold of in.
        """

        area = self.path().boundingRect().normalized()
        weight = self.weight_path()
        if weight is not None:
            area = area.united(weight.boundingRect())
        reach = max(ARC_GRAB, ARROW_WIDTH, ITEM_PEN_SELECTED)
        return area.adjusted(-reach, -reach, reach, reach)

    def shape(self) -> QPainterPath:
        """Give the band the arc can be taken hold of in.

        Returns
        -------
        PyQt6.QtGui.QPainterPath
            The line stroked to :data:`ARC_GRAB`, with the arrowhead, because a
            line a third of a millimetre wide is a line nobody can click on.
        """

        stroker = QPainterPathStroker()
        stroker.setWidth(ARC_GRAB * 2.0)
        band = stroker.createStroke(self.path())
        band.addPath(self.arrow())
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
