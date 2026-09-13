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
``item_rect()`` and ``shape()``
    How big the shape itself is, and what can be taken hold of.  The bounding
    rectangle is the base's: the shape's room and the box its name is written
    in, together.
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
and what a place or a transition is in a Petri net belongs to
:mod:`simtwin_core.petri_net`; an item is described as a
:class:`~simtwin_core.petri_net.PlaceData` or a
:class:`~simtwin_core.petri_net.TransitionData` rather than being one.

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

from PyQt6.QtCore import QPointF, QRectF, QSizeF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainterPath,
    QPalette,
    QPen,
    QTransform,
)
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


#: How tall one line of a label is, in millimetres — the font's whole line
#: height, ascender to descender and the leading between two lines, so every
#: line of every label is the same size whatever letters happen to be in it.
LABEL_LINE_HEIGHT = 2.8

#: How wide a label may grow, in millimetres, before it goes onto another line.
#: Three places across: wide enough for a few words, narrow enough that a box
#: belongs to the item under it rather than floating between two.
LABEL_WIDTH = 30.0

#: How far a label stands off the item it belongs to, in millimetres.
LABEL_GAP = 1.0

#: What goes between a node's name and its description.
LABEL_SEPARATOR = ': '


def label_lines(text: str, width: float, metrics: QFontMetricsF, scale: float) -> list[str]:
    """Break a piece of text into the lines a box that wide holds.

    Greedy and by words, which is what a person reading a label expects.  A
    **word wider than the whole box** is broken where it stops fitting rather
    than left to hang off the side: the box is measured from the item it belongs
    to, and one that grows without limit would run across the next item along.

    Parameters
    ----------
    text : str
        The text.  Runs of whitespace part the words and are not kept.
    width : float
        How wide the box may be, in millimetres.
    metrics : PyQt6.QtGui.QFontMetricsF
        The font it is laid out in.
    scale : float
        How many millimetres one unit of that font is.

    Returns
    -------
    list of str
        The lines, none of them empty, and none wider than the box but for a
        single character that is.
    """

    room = width / scale

    def fits(line: str) -> bool:
        return metrics.horizontalAdvance(line) <= room

    lines: list[str] = []
    for word in text.split():
        while not fits(word):
            broken = 1
            while broken < len(word) and fits(word[: broken + 1]):
                broken += 1
            if lines and fits(f'{lines[-1]} {word[:broken]}'):
                lines[-1] = f'{lines[-1]} {word[:broken]}'
            else:
                lines.append(word[:broken])
            word = word[broken:]
        if not word:
            continue
        if lines and fits(f'{lines[-1]} {word}'):
            lines[-1] = f'{lines[-1]} {word}'
        else:
            lines.append(word)
    return lines


def text_block(text: str, width: float, line_height: float = LABEL_LINE_HEIGHT):
    """Lay a piece of text out as a path of however many lines it needs.

    A block of text is not :func:`glyph_path`: that scales one piece of text so
    that **its own ink** is a height, which is what a single number wants and
    exactly what a block of several lines must not have — a line with a ``g`` in
    it would come out smaller than a line without one.  Here the font's own line
    height is what is scaled, once, for the whole block, so every line is the
    same size and one line below the last.

    The path is centred on the middle of the **box** rather than of the ink, so
    where a label sits does not depend on which letters are in it.

    Parameters
    ----------
    text : str
        What to write.
    width : float
        How wide it may be, in millimetres, before it goes onto another line.
    line_height : float, optional
        How tall one line is, in millimetres.

    Returns
    -------
    tuple
        The glyphs as a :class:`~PyQt6.QtGui.QPainterPath` centred on nought,
        and the size of the box they were laid out in as a
        :class:`~PyQt6.QtCore.QSizeF`.  Both are empty for text that writes
        nothing.
    """

    font = QFont()
    metrics = QFontMetricsF(font)
    if metrics.height() <= 0.0:  # pragma: no cover - a font always has a height
        return QPainterPath(), QSizeF(0.0, 0.0)

    scale = line_height / metrics.height()
    lines = label_lines(text, width, metrics, scale)
    if not lines:
        return QPainterPath(), QSizeF(0.0, 0.0)

    box = QSizeF(
        max(metrics.horizontalAdvance(line) for line in lines) * scale,
        len(lines) * line_height,
    )

    glyphs = QPainterPath()
    for row, line in enumerate(lines):
        along = (box.width() / scale - metrics.horizontalAdvance(line)) / 2.0
        glyphs.addText(along, metrics.ascent() + row * metrics.height(), font, line)
    glyphs = QTransform().scale(scale, scale).map(glyphs)
    glyphs.translate(-box.width() / 2.0, -box.height() / 2.0)
    return glyphs, box


def glyph_path(text: str, height: float, width: float | None = None) -> QPainterPath:
    """Build a piece of text as a path a height in millimetres, centred on nought.

    What is written on the sheet — an arc's weight, a place's tokens — is a
    **path** rather than text drawn with a font, because the scene is measured in
    millimetres and a font in points: a path is scaled to a height on the paper,
    so it is the same size at every zoom and on every machine, and it is filled
    with the same brush as the thing it belongs to.

    Parameters
    ----------
    text : str
        What to write.
    height : float
        How tall it is to be, in millimetres.
    width : float, optional
        How wide it may be.  Text that would be wider at that height is
        narrowed to it instead, keeping its proportions.

    Returns
    -------
    PyQt6.QtGui.QPainterPath
        The glyphs, their bounding box centred on the origin, or an empty path
        for text that draws nothing.
    """

    glyphs = QPainterPath()
    glyphs.addText(0.0, 0.0, QFont(), text)
    drawn = glyphs.boundingRect()
    if drawn.isEmpty():
        return QPainterPath()

    glyphs.translate(-drawn.center().x(), -drawn.center().y())
    scale = height / drawn.height()
    if width is not None and drawn.width() * scale > width:
        scale = width / drawn.width()
    return QTransform().scale(scale, scale).map(glyphs)


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
    name : str
        What the net calls it, unique in its net: the name MASAFI-sim-petri
        knows it by.  Empty until the editor gives it one — see
        :meth:`~masafi_simtwin.documents.petri_net.PetriNetEditor.next_name`.
        It is written on the sheet beside the item; setting it draws it again.
    description : str
        What it is for, in a person's words, on one line.  Empty until one is
        given, and never seen by a backend.  It is written after the name, in
        the same box; setting it draws it again.
    NAME_PREFIX : str
        What a name invented for one begins with.  A subclass says it, and two
        kinds of item with different prefixes cannot be given the same name.
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

    #: What a name invented for one begins with.
    NAME_PREFIX: str = ''

    #: Whether the item can be turned the other way round on the sheet.  It is
    #: declared here rather than asked of the class, the way :attr:`GROUP` and
    #: :attr:`CONNECTS_TO` are: what a context menu offers over an item is a
    #: fact about the item, and a round one has nothing to turn.
    CAN_ROTATE: bool = False

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
        self._name = ''
        self._description = ''
        self._label = None

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(ITEM_Z)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    # ------------------------------------------------------------------
    # What is written beside it
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """str: What the net calls the item, and the first thing its label says."""

        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._relabel('_name', str(name))

    @property
    def description(self) -> str:
        """str: What it is for, in a person's words, written after the name."""

        return self._description

    @description.setter
    def description(self, description: str) -> None:
        self._relabel('_description', str(description))

    def _relabel(self, field: str, value: str) -> None:
        """Set one half of the label, and draw the label again.

        The box is as big as what is in it, so this is a change of geometry and
        not merely of paint: the view is told before the box changes size, or it
        repaints the new box and leaves the old one on the sheet.

        Parameters
        ----------
        field : str
            Which half — the name or the description.
        value : str
            What it becomes.
        """

        if value == getattr(self, field):
            return
        self.prepareGeometryChange()
        setattr(self, field, value)
        self._label = None
        self.update()

    def label_text(self) -> str:
        """Give what is written in the item's box, on one line before it wraps.

        Returns
        -------
        str
            ``Name: Description``, the name alone for an item nobody has
            described, and nothing at all for one with no name — which is an
            item made outside the editor, since the editor invents a name for
            every item it puts on the sheet.
        """

        if not self._name:
            return ''
        if not self._description:
            return self._name
        return f'{self._name}{LABEL_SEPARATOR}{self._description}'

    def label(self):
        """Give the item's box: the glyphs, centred on nought, and its size.

        Worked out once and kept until the text changes, since a box is the same
        box wherever the item is dragged and however the sheet is zoomed.

        Returns
        -------
        tuple
            The path and the :class:`~PyQt6.QtCore.QSizeF` it was laid out in.
        """

        if self._label is None:
            self._label = text_block(self.label_text(), LABEL_WIDTH)
        return self._label

    def label_centre(self, size: QSizeF) -> QPointF:
        """Say where a box of this size goes, in the item's own coordinates.

        **Under the item, centred**, which is where the name of a place goes on
        a drawn net.  A transition says otherwise; see
        :meth:`~masafi_simtwin.documents.transition.Transition.label_centre`.

        Parameters
        ----------
        size : PyQt6.QtCore.QSizeF
            How big the box is, in millimetres.

        Returns
        -------
        PyQt6.QtCore.QPointF
            Where its centre goes.
        """

        room = self.item_rect()
        return QPointF(
            room.center().x(), room.bottom() + LABEL_GAP + size.height() / 2.0
        )

    def label_rect(self) -> QRectF:
        """Give where the box is, in the item's own coordinates.

        Returns
        -------
        PyQt6.QtCore.QRectF
            The box, and an empty rectangle for an item with nothing written
            beside it.
        """

        _glyphs, size = self.label()
        if size.isEmpty():
            return QRectF()
        centre = self.label_centre(size)
        return QRectF(
            centre.x() - size.width() / 2.0,
            centre.y() - size.height() / 2.0,
            size.width(),
            size.height(),
        )

    def paint_label(self, painter, option) -> None:
        """Write the item's name and description beside it.

        In the item's own ink — the accent while it is selected — as the tokens
        of a place are, so that what belongs to one item reads as one thing.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the view.
        option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
            What the view knows about drawing this item, its palette included.
        """

        glyphs, size = self.label()
        if glyphs.isEmpty():
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ink_colour(self.isSelected(), option))
        painter.drawPath(glyphs.translated(self.label_centre(size)))

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

    def reshaped(self) -> None:
        """Take in that the item is drawn differently than it was.

        Moving is the scene's own business and goes through :meth:`itemChange`,
        but an item that changes **shape** where it stands moves nothing, so
        nothing is told: the view holds the rectangle the item used to have, the
        arcs are still aimed at where its connecting points used to be, and it
        may now reach off the paper.  This is the three of those put right, and
        it is called by whatever changed the shape — after the change, since it
        is the new shape that has to fit.

        :meth:`~PyQt6.QtWidgets.QGraphicsItem.prepareGeometryChange` is **not**
        called here: it says the geometry is *about to* change, so that the view
        repaints where the item was last drawn, and by now it already has.
        """

        self._label = None
        if self._bounds is not None:
            x, y = self._inside(self.pos().x(), self.pos().y(), self._bounds())
            self.setPos(QPointF(x, y))
        for arc in self._arcs:
            arc.route()
        self.update()

    def _inside(self, x: float, y: float, area: QRectF) -> tuple[float, float]:
        """Hold a centre far enough inside an area for the whole item to fit.

        The centre is what is moved, but it is the shape that has to stay on the
        sheet, so the room the item takes is taken off each edge first.  An area
        too small to hold it at all is left alone rather than pinning the item to
        a corner of a sheet it does not fit on.

        It is :meth:`item_rect` that is measured and not :meth:`boundingRect`:
        what has to stay on the paper is the **shape**.  Holding the label on as
        well would make how far a node can be dragged depend on how long its
        description is, and typing one would then be a thing that moves nodes.

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

        room = self.item_rect()
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
        """Draw the item, what is written beside it, and its connecting points.

        The label and the points are drawn here rather than by each subclass, so
        that a name is written the same way on every item of a net and the
        points are the same rings in the same colour however it is shaped, and
        so that both are always on top of what they belong to.

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
        self.paint_label(painter, option)
        if not self._ports_visible:
            return

        painter.setPen(QPen(option.palette.color(QPalette.ColorRole.Link), 0.0))
        painter.setBrush(paper_colour(option))
        for point in self.ports():
            painter.drawEllipse(point, PORT_RADIUS, PORT_RADIUS)

    def shape(self) -> QPainterPath:
        """Give what can be taken hold of.

        The label is **not** in it, deliberately: what is written beside an item
        says what the item is, and clicking or dragging a caption is not
        clicking or dragging the thing it captions.  A scene hit-tests and
        rubber-bands against the shape, so the box is out of both.

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

    def item_rect(self) -> QRectF:
        """Give what the shape itself is drawn inside, its connecting points and
        its thickest outline included.

        This is the item's **room**: what is held on the paper as it is dragged,
        and what a label is measured from.

        Returns
        -------
        PyQt6.QtCore.QRectF
            The rectangle, in the item's own coordinates.

        Raises
        ------
        NotImplementedError
            Always.  A subclass says how big it is.
        """

        raise NotImplementedError

    def boundingRect(self) -> QRectF:  # noqa: N802  (Qt naming)
        """Give everything the item paints inside.

        The shape's own room and the box its name is written in, which is a
        rectangle around both and so is not centred on the item.

        Returns
        -------
        PyQt6.QtCore.QRectF
            The rectangle, in the item's own coordinates.
        """

        return self.item_rect().united(self.label_rect())
