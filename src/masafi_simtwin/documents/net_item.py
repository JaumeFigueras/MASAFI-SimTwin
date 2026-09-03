"""What every item of a net has in common.

A place is a circle and a transition is a bar, and apart from those two facts
they are the same thing: something of a fixed size in millimetres, dropped on
the sheet, moved about it a millimetre at a time, held inside the paper, and
carrying **connecting points** for the arcs that will join them.  That is
:class:`NetItem`, and it was written when there were two items to write it
against rather than one — a base class over a sample of one is a guess.

A subclass says three things and nothing else:

``ports()``
    Where an arc may be attached, in the item's own coordinates.
``boundingRect()`` and ``shape()``
    How big it is, and what can be taken hold of.
``paint_item(painter, option)``
    How it is drawn.  The connecting points are drawn over it by
    :meth:`NetItem.paint`, so a subclass never draws them itself.

**Where the connecting points are is the shape's own business.**  A circle is
even the whole way round, so a place puts one every thirty degrees; a bar is
not, so a transition puts one in the middle of each of its four edges and
spreads the rest along the two long ones.  One rule for both would be good for
neither — angles that spread evenly round a circle crowd into the middle of a
bar sixteen millimetres long and two high, which is what the first attempt at
this did.  What the base holds is everything *around* them: how big they are
drawn, that they are drawn over the item rather than under it, finding the one
under a position, and when they are seen at all.

They are **not drawn by default** — a net is read by its circles and its bars,
not by the dots each of them could be joined at — and what reveals them is
:attr:`NetItem.ports_visible`, one property, so an arc tool that wants them up
for the whole of a drag has one thing to set.

A point is drawn as a **ring**: a hairline of the accent around the colour of
the paper.  A solid dot is a mark on the drawing, and a connecting point is not
part of the drawing — it is somewhere to aim at, shown while it is being aimed
at.  The ring is filled rather than left open because the fill is what makes one
legible on a transition, which is solid ink: an open ring on a bar is a rim
around the bar's own black, which reads as a dot again.  The pen is width nought
— Qt's cosmetic hairline, one pixel at every zoom — so the ring is a line rather
than a band that thickens as the sheet is come closer to.

An item carries a **uuid**, which is what an arc names its two ends by.  It is
generated when the item is made and is meant to be the identity the model
document keeps, so an item read back out of a project is given the one it had
rather than a new one.

An arc, once drawn, keeps the **index** of the connecting point it was drawn to
at each end, not the point itself: the index does not change when the item is
dragged about, and :meth:`NetItem.scene_port` turns it back into a place on the
sheet.  That is what makes an arc stay where it was put — it moves with its ends
without ever choosing different ones.

Which items may be joined to which is declared here as well, by two class
attributes rather than by asking what class a thing is: :attr:`NetItem.GROUP`
says what an item counts as, and :attr:`NetItem.CONNECTS_TO` says what it may be
joined to.  A Petri net is bipartite — a place joins a transition and nothing
else — and a timed transition is a transition for this purpose however it is
drawn, which is a fact about the net rather than about the class hierarchy.

Nothing here knows about the *model*.  An item on the sheet is a drawing of one,
and what a place or a transition is in a Petri net belongs to the document layer
that is still to come; when it arrives these items are given one rather than
being one.

**The colours are the palette's, never constants.**  The sheet is painted rather
than styled, so one rule has to read on both schemes: ``Text`` is the ink,
``Link`` is the accent — where
:data:`~masafi_simtwin.theme.ThemeColors.accent` is kept, ``Highlight`` being
the pale wash behind selected text — and ``Base`` is the colour of the paper.
What each item makes of them is its own; see :mod:`~masafi_simtwin.documents.place`
and :mod:`~masafi_simtwin.documents.transition`.
"""

from __future__ import annotations

import math

from collections.abc import Callable
from uuid import uuid4

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainterPath, QPalette, QPen
from PyQt6.QtWidgets import QGraphicsItem

#: How big a connecting point is drawn, in millimetres of radius.  Small, and
#: smaller than what it takes to aim at one: a connecting point is not part of
#: the drawing but somewhere to aim at, shown only while it is being aimed at,
#: so it is drawn as a mark rather than as a bead.
PORT_RADIUS = 0.35

#: How far from a connecting point's centre, in millimetres, the pointer may be
#: and still take hold of it.  Wider than the ring is drawn, exactly as
#: :data:`masafi_simtwin.documents.arc.HANDLE_GRAB` is wider than
#: :data:`masafi_simtwin.documents.arc.HANDLE_SIZE`: shrinking a mark should
#: not make what it marks harder to hit, and the nearest point within reach is
#: the one taken, so reaches that overlap still pick the one aimed at.
PORT_GRAB = 0.7

#: How thick an outline is, in millimetres.  A real stroke rather than Qt's
#: cosmetic hairline: these are things drawn on paper, so an outline grows with
#: the zoom the way the shape it draws does.
ITEM_PEN = 0.3

#: How thick it is while the item is selected.
ITEM_PEN_SELECTED = 0.6

#: The net sits on the sheet, under the guides the sheet is lined up against.
ITEM_Z = 10.0

#: The arcs go under the items they join, so that a line runs behind a place
#: rather than across it and an arrowhead meets a boundary cleanly.
ARC_Z = 5.0


def ink_colour(selected: bool, option) -> QColor:
    """Give the colour a thing of the net is drawn in.

    ``Text`` is the ink of the sheet and ``Link`` is the accent — where
    :data:`~masafi_simtwin.theme.ThemeColors.accent` is kept, ``Highlight`` being
    the pale wash behind selected text — so a selected thing is drawn in the
    accent.  It is one rule for the items and the arcs alike, which is why it is
    a function here rather than a method of either.

    Parameters
    ----------
    selected : bool
        Whether the thing is selected.
    option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
        What the view knows about drawing it, its palette included.  An item has
        no widget to take a palette from, so this is where the palette comes
        from.

    Returns
    -------
    PyQt6.QtGui.QColor
        The colour.
    """

    role = QPalette.ColorRole.Link if selected else QPalette.ColorRole.Text
    return option.palette.color(role)


def paper_colour(option) -> QColor:
    """Give the colour of the sheet a thing of the net is drawn on.

    ``Base`` is what :meth:`CanvasView.drawBackground` fills the sheet with, so
    this is what a thing is filled with to read as a hole in whatever it is
    over — a connecting point on a transition, a handle on a curve — and what a
    place is filled with to be the colour of the paper it sits on.

    Parameters
    ----------
    option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
        What the view knows about drawing it, its palette included.

    Returns
    -------
    PyQt6.QtGui.QColor
        The colour.
    """

    return option.palette.color(QPalette.ColorRole.Base)


class NetItem(QGraphicsItem):
    """One item of a net, drawn on the sheet.

    The item's ``pos`` is the **centre** of the shape, not a corner of it: the
    centre is what the connecting points are measured from, it is what a drop
    puts under the pointer, and it is the one point of a circle that means
    anything.

    Parameters
    ----------
    snap : collections.abc.Callable, optional
        What to round a coordinate to as the item moves.  The canvas passes
        :meth:`~masafi_simtwin.documents.canvas.CanvasView.snap`, which is the
        millimetre at every zoom; without one an item goes where it is put.
    bounds : collections.abc.Callable, optional
        Where the item may be, as something returning a
        :class:`~PyQt6.QtCore.QRectF` in scene coordinates.  The canvas passes
        the scene rectangle, so an item cannot be dragged off the sheet — the
        whole of it is held inside, not merely its centre.  The rectangle is
        asked for at every move rather than kept, because the sheet is ruled
        again whenever the page changes under it.
    parent : PyQt6.QtWidgets.QGraphicsItem, optional
        Parent item.

    Attributes
    ----------
    uuid : str
        What an arc names this item by.  Generated when the item is made; a
        document read back out of a project assigns the one it was saved under.
    GROUP : str
        What this item counts as when it is joined to another.  A subclass says
        it; two items of the same group are two of the same kind of thing
        however differently they are drawn.
    CONNECTS_TO : tuple of str
        The groups this item may be joined to.  A Petri net is bipartite, so a
        place names the transition and a transition names the place, and
        everything else — including joining a thing to itself — is refused.
    """

    #: What this item counts as when it is joined to another.
    GROUP: str = ''

    #: The groups it may be joined to.
    CONNECTS_TO: tuple[str, ...] = ()

    def __init__(
        self,
        snap: Callable[[float], float] | None = None,
        bounds: Callable[[], QRectF] | None = None,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._snap = snap
        self._bounds = bounds
        self._ports_visible = False
        self._arcs: list = []
        self.uuid = str(uuid4())

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(ITEM_Z)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    # ------------------------------------------------------------------
    # The connecting points
    # ------------------------------------------------------------------

    @property
    def ports_visible(self) -> bool:
        """bool: Whether the connecting points are drawn.

        They are not, to begin with.  Pointing at the item turns them on and
        taking the pointer away turns them off again; an arc tool that wants
        them up for the whole of a drag sets this itself.
        """

        return self._ports_visible

    @ports_visible.setter
    def ports_visible(self, visible: bool) -> None:
        """Show or hide the connecting points.

        Parameters
        ----------
        visible : bool
            Whether to draw them.
        """

        visible = bool(visible)
        if visible != self._ports_visible:
            self._ports_visible = visible
            self.update()

    def ports(self) -> list[QPointF]:
        """Give every connecting point, in the item's own coordinates.

        Returns
        -------
        list of PyQt6.QtCore.QPointF
            The points an arc may be attached at.

        Raises
        ------
        NotImplementedError
            Always.  Where they are is a fact about the shape, and the shape is
            what a subclass is.
        """

        raise NotImplementedError

    def scene_ports(self) -> list[QPointF]:
        """Give every connecting point where it is on the sheet.

        Returns
        -------
        list of PyQt6.QtCore.QPointF
            The points, in scene millimetres.
        """

        return [self.mapToScene(point) for point in self.ports()]

    def scene_port(self, index: int) -> QPointF:
        """Give one connecting point where it is on the sheet.

        This is what an arc asks: it keeps the *index* of the point it was drawn
        to, and the index does not change when the item moves — the point's
        place on the sheet does, which is exactly what an arc has to follow.

        Parameters
        ----------
        index : int
            Which of :meth:`ports`, in that order.  One past the end is held to
            the last, so a document naming a point this version does not have
            still opens.

        Returns
        -------
        PyQt6.QtCore.QPointF
            The point, in scene millimetres.
        """

        points = self.ports()
        return self.mapToScene(points[min(max(index, 0), len(points) - 1)])

    def port_index_at(self, position: QPointF) -> int | None:
        """Find which connecting point a scene position falls on.

        Within :data:`PORT_GRAB` rather than within the ring's own radius: a
        connecting point is aimed at rather than hit, and what is drawn is the
        smaller of the two.  The **nearest** one rather than the first: on a
        transition the points along a long edge are less than two reaches
        apart, and taking whichever came first in the list would hand back a
        neighbour of the one that was aimed at.  That did not matter while an
        arc chose its own points; it matters now that a press decides where an
        arc leaves for good.

        Parameters
        ----------
        position : QPointF
            Where to look, in scene millimetres.

        Returns
        -------
        int, optional
            The index, or ``None`` when the position is on none of them.
        """

        within = [
            (math.hypot(position.x() - point.x(), position.y() - point.y()), index)
            for index, point in enumerate(self.scene_ports())
        ]
        near = [pair for pair in within if pair[0] <= PORT_GRAB]
        return min(near)[1] if near else None

    def port_at(self, position: QPointF) -> QPointF | None:
        """Find the connecting point a scene position falls on.

        Parameters
        ----------
        position : PyQt6.QtCore.QPointF
            Where to look, in scene millimetres.

        Returns
        -------
        PyQt6.QtCore.QPointF, optional
            The connecting point, in scene millimetres, or ``None`` when the
            position is not on one of them.
        """

        index = self.port_index_at(position)
        return None if index is None else self.scene_port(index)

    # ------------------------------------------------------------------
    # The arcs that touch it
    # ------------------------------------------------------------------

    @property
    def arcs(self) -> list:
        """list: The arcs joined to this item, in the order they were drawn."""

        return list(self._arcs)

    def attach(self, arc) -> None:
        """Take note of an arc that has just been joined to this item.

        An arc is drawn from its two ends rather than from a position of its
        own, so an item has to be able to tell its arcs that it has moved.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc
            The arc.  Attaching one twice does nothing, which is what an arc
            whose two ends are the same item would otherwise do.
        """

        if arc not in self._arcs:
            self._arcs.append(arc)

    def detach(self, arc) -> None:
        """Forget an arc that no longer joins this item.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc
            The arc.  One that was never attached is ignored, so a half-built
            arc can be taken apart without knowing how far it got.
        """

        if arc in self._arcs:
            self._arcs.remove(arc)

    def may_connect_to(self, other) -> bool:
        """Say whether an arc may be drawn from this item to another.

        Parameters
        ----------
        other : NetItem
            What it would be joined to.

        Returns
        -------
        bool
            Whether :attr:`CONNECTS_TO` names the other's :attr:`GROUP`.  An
            item is never in its own ``CONNECTS_TO``, so a thing cannot be
            joined to itself and a place cannot be joined to a place.
        """

        return isinstance(other, NetItem) and other.GROUP in self.CONNECTS_TO

    def used_ports(self) -> set[int]:
        """Give the connecting points that already have an arc on them.

        Returns
        -------
        set of int
            The indices, at this end of each of this item's arcs.
        """

        return {arc.port_of(self) for arc in self._arcs}

    def port_index_towards(self, point: QPointF, skip=()) -> int:
        """Give the connecting point that faces a place on the sheet.

        Parameters
        ----------
        point : PyQt6.QtCore.QPointF
            What to face, in scene millimetres.
        skip : collections.abc.Container, optional
            Indices to pass over.  A point already carrying an arc is passed
            over so that two arcs do not land on top of one another; if every
            point is taken the nearest is given anyway, an item having a fixed
            number of points and no fixed number of arcs.

        Returns
        -------
        int
            The index of the point.
        """

        ranked = sorted(
            range(len(self.ports())),
            key=lambda index: (
                (point.x() - self.scene_port(index).x()) ** 2
                + (point.y() - self.scene_port(index).y()) ** 2
            ),
        )
        for index in ranked:
            if index not in skip:
                return index
        return ranked[0]

    def free_port_towards(self, point: QPointF) -> int:
        """Give the nearest connecting point that no arc is on yet.

        This is how the far end of an arc is chosen when it is drawn: the near
        end is the point that was pressed, and the far end is whichever point
        faces it and is still free.  Both are then **kept**, so an arc drawn
        once is drawn the same way for ever.

        Parameters
        ----------
        point : PyQt6.QtCore.QPointF
            What to face, in scene millimetres.

        Returns
        -------
        int
            The index of the point.
        """

        return self.port_index_towards(point, self.used_ports())

    def port_towards(self, point: QPointF) -> QPointF:
        """Give the connecting point facing a place on the sheet.

        Parameters
        ----------
        point : PyQt6.QtCore.QPointF
            What to face, in scene millimetres.

        Returns
        -------
        PyQt6.QtCore.QPointF
            The point, in scene millimetres.
        """

        return self.scene_port(self.port_index_towards(point))

    # ------------------------------------------------------------------
    # Where the item may go
    # ------------------------------------------------------------------

    def itemChange(self, change, value):  # noqa: N802  (Qt naming)
        """Snap a moving item to the millimetre and hold it to the sheet.

        This is the one place a position is decided, so an item dropped from the
        library and one dragged by the hand land under the same rule.

        Parameters
        ----------
        change : PyQt6.QtWidgets.QGraphicsItem.GraphicsItemChange
            What is being changed.
        value : object
            What it is being changed to.

        Returns
        -------
        object
            What it is changed to instead.
        """

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            x, y = value.x(), value.y()
            if self._snap is not None:
                x, y = self._snap(x), self._snap(y)
            if self._bounds is not None:
                x, y = self._inside(x, y, self._bounds())
            return QPointF(x, y)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for arc in self._arcs:
                arc.route()
        return super().itemChange(change, value)

    def _inside(self, x: float, y: float, area: QRectF) -> tuple[float, float]:
        """Hold a centre far enough inside an area for the whole item to fit.

        The centre is what is moved, but it is the shape that has to stay on the
        sheet, so the room the item takes is taken off each edge first.  An area
        too small to hold it at all is left alone rather than pinning the item to
        a corner of a sheet it does not fit on.

        Parameters
        ----------
        x : float
            Where the centre is going, across the sheet.
        y : float
            Where it is going, down it.
        area : PyQt6.QtCore.QRectF
            Where the item may be, in scene millimetres.

        Returns
        -------
        tuple of float
            The centre, held inside the area.
        """

        room = self.boundingRect()
        left = area.left() - room.left()
        right = area.right() - room.right()
        top = area.top() - room.top()
        bottom = area.bottom() - room.bottom()
        if left <= right:
            x = min(max(x, left), right)
        if top <= bottom:
            y = min(max(y, top), bottom)
        return x, y

    # ------------------------------------------------------------------
    # Pointing at it
    # ------------------------------------------------------------------

    def hoverEnterEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Show the connecting points while the pointer is over the item.

        Parameters
        ----------
        event : PyQt6.QtWidgets.QGraphicsSceneHoverEvent
            The hover event.
        """

        self.ports_visible = True
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Hide them again when the pointer goes.

        Parameters
        ----------
        event : PyQt6.QtWidgets.QGraphicsSceneHoverEvent
            The hover event.
        """

        self.ports_visible = False
        super().hoverLeaveEvent(event)

    # ------------------------------------------------------------------
    # How it is drawn
    # ------------------------------------------------------------------

    def outline_colour(self, option) -> QColor:
        """Give the colour the item is drawn in.

        Parameters
        ----------
        option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
            What the view knows about drawing this item, its palette included.

        Returns
        -------
        PyQt6.QtGui.QColor
            The colour, by the one rule :func:`ink_colour` holds for the items
            and the arcs alike.
        """

        return ink_colour(self.isSelected(), option)

    def outline_width(self) -> float:
        """Give how thick the outline is, which says whether it is selected.

        Returns
        -------
        float
            Millimetres.
        """

        return ITEM_PEN_SELECTED if self.isSelected() else ITEM_PEN

    def pen(self, option) -> QPen:
        """Build the pen an item is outlined with.

        The join is **mitered**, which is what takes a corner to a point.  Qt's
        default is a bevel, and a bevel chamfers every corner by the width of
        the pen — on a bar two millimetres high drawn with a stroke of
        :data:`ITEM_PEN` that is a visible cut across each corner, and a
        transition is a rectangle rather than a rectangle with its corners taken
        off.  A circle has no joins, so this costs a place nothing.

        Parameters
        ----------
        option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
            What the view knows about drawing this item, its palette included.

        Returns
        -------
        PyQt6.QtGui.QPen
            The pen: :meth:`outline_colour` at :meth:`outline_width`, mitered.
        """

        pen = QPen(self.outline_colour(option), self.outline_width())
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        return pen

    def paint_item(self, painter, option) -> None:
        """Draw the shape itself, without its connecting points.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the view.
        option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
            What the view knows about drawing this item.

        Raises
        ------
        NotImplementedError
            Always.  How an item is drawn is what a subclass is.
        """

        raise NotImplementedError

    def paint(self, painter, option, widget=None) -> None:
        """Draw the item, and its connecting points when they are shown.

        The points are drawn here rather than by each subclass, so that they are
        the same rings in the same colour on every item of a net however it is
        shaped, and so that they are always on top of what they belong to.

        A ring is the accent at width nought — Qt's cosmetic hairline, one pixel
        at every zoom — filled with ``Base``, the colour of the paper.  The fill
        is what makes one legible over a transition, which is solid ink.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the view.
        option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
            What the view knows about drawing this item, its palette included.
        widget : PyQt6.QtWidgets.QWidget, optional
            The widget being painted on.
        """

        self.paint_item(painter, option)
        if not self._ports_visible:
            return

        painter.setPen(QPen(option.palette.color(QPalette.ColorRole.Link), 0.0))
        painter.setBrush(paper_colour(option))
        for point in self.ports():
            painter.drawEllipse(point, PORT_RADIUS, PORT_RADIUS)

    def shape(self) -> QPainterPath:
        """Give what can be taken hold of.

        Returns
        -------
        PyQt6.QtGui.QPainterPath
            The shape itself, out to the middle of its outline.

        Raises
        ------
        NotImplementedError
            Always.  A subclass says how big it is.
        """

        raise NotImplementedError
