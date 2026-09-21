"""What every item of a net has in common.

A place is a circle and a transition is a bar, and apart from those two facts
they are the same thing: something of a fixed size in millimetres, dropped on
the sheet, moved about it a grid step at a time, held inside the paper, and
carrying **connecting points** for the arcs that will join them.  Which of its
points land on the grid as it moves is the one thing about snapping a subclass
may say, through :meth:`NetItem.anchors_for`.  That is
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

from collections.abc import Callable, Sequence
from uuid import uuid4

from PyQt6.QtCore import QPointF, QRectF, QSizeF, Qt
from PyQt6.QtGui import QColor, QPainterPath, QPalette, QPen
from PyQt6.QtWidgets import QGraphicsItem

from masafi_simtwin import preferences
from masafi_simtwin.documents.ink import ink_colour, paper_colour
from masafi_simtwin.documents.label import LABEL_GAP, LABEL_SEPARATOR, Label

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

#: How much thicker, in millimetres, a thing is drawn while it is selected.
#: Decided with Jaume: a fixed amount **more** rather than a width of its own,
#: so that a hairline and a heavy line both say the same thing by thickening.
#: How thick a line is to begin with is the item's own style — a real stroke
#: rather than Qt's cosmetic hairline, since these are things drawn on paper, so
#: an outline grows with the zoom the way the shape it draws does.
SELECTED_EXTRA = 0.3

#: The net sits on the sheet, under the guides the sheet is lined up against.
ITEM_Z = 10.0

#: The arcs go under the items they join, so that a line runs behind a place
#: rather than across it and an arrowhead meets a boundary cleanly.
ARC_Z = 5.0



class NetItem(QGraphicsItem):
    """One item of a net, drawn on the sheet.

    The item's ``pos`` is the **centre** of the shape, not a corner of it: the
    centre is what the connecting points are measured from, it is what a drop
    puts under the pointer, and it is the one point of a circle that means
    anything.

    A person dragging it lands one of its :meth:`snap_anchors` on the grid —
    whichever asks for the least move.  A position that is a **record** of where
    it was — read from a file, put back by an undo, replayed from a journal — is
    put down exactly by :meth:`place` instead, on whatever grid it was drawn on: snapping
    it again would move an item nobody moved, and the sheet would stop agreeing
    with the document.

    Parameters
    ----------
    snap : collections.abc.Callable, optional
        What to round one coordinate to.  The canvas passes
        :meth:`~masafi_simtwin.documents.canvas.CanvasView.snap`; the item hands
        it on to its caption, which snaps a width with it.
    bounds : collections.abc.Callable, optional
        Where the item may be, as something returning a
        :class:`~PyQt6.QtCore.QRectF` in scene coordinates.  The canvas passes
        the scene rectangle, so an item cannot be dragged off the sheet — the
        whole of it is held inside, not merely its centre.  The rectangle is
        asked for at every move rather than kept, because the sheet is ruled
        again whenever the page changes under it.
    parent : PyQt6.QtWidgets.QGraphicsItem, optional
        Parent item.
    snap_point : collections.abc.Callable, optional
        What to move a point to, given the point and its anchors, as the item is
        dragged.  The canvas passes
        :meth:`~masafi_simtwin.documents.canvas.CanvasView.snap_point`, the grid
        step at every zoom; without one an item goes where it is put.

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

    #: Which kind of text this item's caption is, which is what decides the
    #: typeface it is written in.  Declared here rather than asked of the class,
    #: the way :attr:`GROUP` and :attr:`CONNECTS_TO` are.
    ROLE: str = preferences.PLACE

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
        *,
        snap_point: Callable[[QPointF, Sequence[QPointF]], QPointF] | None = None,
    ) -> None:
        super().__init__(parent)
        self._snap_point = snap_point
        self._bounds = bounds
        self._placing = False
        self._ports_visible = False
        self._arcs: list = []
        self.uuid = str(uuid4())
        self._name = ''
        self._description = ''
        self._label_offset: tuple[float, float] | None = None
        self._label_width: float | None = None
        self._text_style = None
        self._line_style = None
        self._label = Label(self, snap, bounds, resizable=True)

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
        """Set one half of what the label says, and say it.

        Parameters
        ----------
        field : str
            Which half — the name or the description.
        value : str
            What it becomes.
        """

        if value == getattr(self, field):
            return
        setattr(self, field, value)
        self.show_label()

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

    @property
    def label(self) -> Label:
        """masafi_simtwin.documents.label.Label: The box written beside the item.

        A child of the item, so it follows it about the sheet of its own accord
        and goes when it goes.  What it says and where it belongs are set from
        here; everything a person does to it is the label's own.
        """

        return self._label

    @property
    def label_offset(self) -> tuple[float, float] | None:
        """tuple of float, optional: Where the box has been moved to.

        The centre of the box relative to the centre of the item, in
        millimetres, or ``None`` for a box nobody has moved — which goes where
        :meth:`label_anchor` says and follows the text as it grows.  A box that
        has been moved stays where it was put: its centre does not move when
        what is written in it changes, nor when a transition is turned.
        """

        return self._label_offset

    @label_offset.setter
    def label_offset(self, offset) -> None:
        offset = None if offset is None else (float(offset[0]), float(offset[1]))
        if offset == self._label_offset:
            return
        self._label_offset = offset
        self.show_label()

    def show_label(self) -> None:
        """Put what the item is called in its box, and the box where it belongs.

        Called whenever either could have changed: the name, the description,
        where the box has been moved to, and the shape the box is measured from
        — a transition stood up is captioned somewhere else than one lying
        across.
        """

        self._label.style = self.appearance()
        self._label.width = self._label_width
        self._label.text = self.label_text()
        self._label.place(self.label_centre(self._label.size))

    @property
    def text_style(self):
        """simtwin_core.petri_net.TextStyle, optional: What the item was given to
        be written in, or ``None`` to follow the application's defaults.

        **Setting it draws the item again.**  An operation assigns this
        attribute — and so do an undo, a journal replayed and a piece pasted —
        so the attribute is what has to tell the sheet; assigning it and leaving
        the drawing as it was is exactly the bug Jaume reported, where a
        caption went on being lettered the way it had been.
        """

        return self._text_style

    @text_style.setter
    def text_style(self, style) -> None:
        if style == self._text_style:
            return
        self._text_style = style
        self.restyle()

    @property
    def line_style(self):
        """simtwin_core.petri_net.LineStyle, optional: What the item was given to
        be drawn with, or ``None`` to follow the application's defaults.

        Setting it draws the item again, for the reason :attr:`text_style`
        gives — and a width is geometry, so what it calls is
        :meth:`restyle`.
        """

        return self._line_style

    @line_style.setter
    def line_style(self, style) -> None:
        if style == self._line_style:
            return
        self._line_style = style
        self.restyle()

    def appearance(self):
        """Give the style the item's caption is actually written in.

        The item's own style where it has one, and the application's defaults
        for its kind of text where it has not — which is the one resolver,
        :func:`masafi_simtwin.preferences.text_appearance`, asked here rather
        than anywhere a caption is drawn.

        Returns
        -------
        simtwin_core.petri_net.TextStyle
            A complete style, its family one this machine can letter in.
        """

        return preferences.text_appearance(self.text_style, self.ROLE)

    @property
    def label_width(self) -> float | None:
        """float, optional: How wide the box has been made, in millimetres.

        ``None`` for a box nobody has resized, which wraps to
        :data:`~masafi_simtwin.documents.ink.LABEL_WIDTH` and fits its text.
        Taken exactly as it is given: snapping is for a drag of a handle.
        """

        return self._label_width

    @label_width.setter
    def label_width(self, width) -> None:
        width = None if width is None else float(width)
        if width == self._label_width:
            return
        self._label_width = width
        self.show_label()

    def label_offset_at(self, position: QPointF) -> tuple[float, float]:
        """Say what offset a caption at a position has, as the item keeps one.

        Parameters
        ----------
        position : PyQt6.QtCore.QPointF
            Where the centre of the box is, in the item's own coordinates.

        Returns
        -------
        tuple of float
            The same place as a pair: an item keeps its caption relative to its
            own centre, so there is nothing to turn.  An arc keeps its weight in
            its chord frame and answers otherwise.
        """

        return (position.x(), position.y())

    def label_centre(self, size: QSizeF) -> QPointF:
        """Say where the centre of a box of this size goes.

        Parameters
        ----------
        size : PyQt6.QtCore.QSizeF
            How big the box is, in millimetres.

        Returns
        -------
        PyQt6.QtCore.QPointF
            Where it was moved to, when it has been, and otherwise where
            :meth:`label_anchor` puts it — in the item's own coordinates.
        """

        if self._label_offset is not None:
            return QPointF(*self._label_offset)
        return self.label_anchor(size)

    def label_anchor(self, size: QSizeF) -> QPointF:
        """Say where a box of this size belongs, in the item's own coordinates.

        **Under the item, centred**, which is where the name of a place goes on
        a drawn net.  A transition says otherwise; see
        :meth:`~masafi_simtwin.documents.transition.Transition.label_anchor`.

        Parameters
        ----------
        size : PyQt6.QtCore.QSizeF
            How big the box is, in millimetres.

        Returns
        -------
        PyQt6.QtCore.QPointF
            Where its centre goes.
        """

        room = self.boundingRect()
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

        return self._label.box().translated(self._label.pos())

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

    @classmethod
    def anchors_for(cls, vertical: bool = False) -> tuple[QPointF, ...]:
        """Give the points of this kind of item that may land on the grid.

        Asked of the kind rather than of an item, because a paste has to know
        where a node will land before there is an item to ask.  The shape is all
        it depends on, and the only way two items of one kind differ in shape is
        which way round a transition is.

        Parameters
        ----------
        vertical : bool, optional
            Whether the item stands up the sheet.  Only a kind that can be
            turned takes any notice.

        Returns
        -------
        tuple of PyQt6.QtCore.QPointF
            The anchors, in millimetres from the centre, **the centre first**:
            a tie goes to the first.  An item of no particular shape has the
            centre alone.
        """

        return (QPointF(0.0, 0.0),)

    def snap_anchors(self) -> tuple[QPointF, ...]:
        """Give the points of this item that may land on the grid.

        Returns
        -------
        tuple of PyQt6.QtCore.QPointF
            :meth:`anchors_for` its kind, the way round it is.
        """

        return self.anchors_for()

    def place(self, position: QPointF) -> None:
        """Put the item exactly where a record says it was.

        Not snapped: a position read from a file, or put back by an undo or a
        journal, was on the grid it was drawn on, which need not be today's.
        Still held on the paper, which is a rule of the sheet rather than of the
        grid.

        Parameters
        ----------
        position : PyQt6.QtCore.QPointF
            Where its centre goes, in scene millimetres.
        """

        self._placing = True
        try:
            self.setPos(position)
        finally:
            self._placing = False

    def itemChange(self, change, value):  # noqa: N802  (Qt naming)
        """Snap a moving item to the grid and hold it to the sheet.

        This is the one place a position is decided, so an item dropped from the
        library and one dragged by the hand land under the same rule: the one of
        its :meth:`snap_anchors` that asks for the least move is put on the
        grid.  An item put down by :meth:`place` is held on the paper and nothing
        more.

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
            if self._snap_point is not None and not self._placing:
                value = self._snap_point(value, self.snap_anchors())
            x, y = value.x(), value.y()
            if self._bounds is not None:
                x, y = self._inside(x, y, self._bounds())
            return QPointF(x, y)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for arc in self._arcs:
                arc.route()
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            # The caption is drawn in the accent while the item is selected, and
            # it lies outside the item's rectangle, which is all Qt repaints.
            self._label.update()
        return super().itemChange(change, value)

    def reshaped(self) -> None:
        """Take in that the item is drawn differently than it was.

        Moving is the scene's own business and goes through :meth:`itemChange`,
        but an item that changes **shape** where it stands moves nothing, so
        nothing is told: the view holds the rectangle the item used to have, its
        caption is where the old shape put it, the arcs are still aimed at where
        its connecting points used to be, and it may now reach off the paper.
        This is the four of those put right, and it is called by whatever
        changed the shape — after the change, since it is the new shape that has
        to fit.

        :meth:`~PyQt6.QtWidgets.QGraphicsItem.prepareGeometryChange` is **not**
        called here: it says the geometry is *about to* change, so that the view
        repaints where the item was last drawn, and by now it already has.
        """

        self.show_label()
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

        What is measured is the item's **own** rectangle.  Its caption is a child
        with a rectangle of its own and is not held on the paper with it: how far
        a node can be dragged cannot depend on how long its description is, or
        typing one would be a thing that moves nodes.

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

        return ink_colour(
            self.isSelected(), option, self.line_appearance().colour
        )

    def line_appearance(self):
        """Give the style the item's lines are actually drawn with.

        The item's own style where it has one, and the application's defaults
        otherwise — the line half of :meth:`appearance`, through the one
        resolver, :func:`masafi_simtwin.preferences.line_appearance`.

        Returns
        -------
        simtwin_core.petri_net.LineStyle
            A complete style.
        """

        return preferences.line_appearance(self.line_style)

    def outline_width(self) -> float:
        """Give how thick the outline is drawn, selection included.

        Returns
        -------
        float
            Millimetres: the item's own width, and :data:`SELECTED_EXTRA` more
            while it is selected.
        """

        width = self.line_appearance().width
        return width + SELECTED_EXTRA if self.isSelected() else width

    def drawn_width(self) -> float:
        """Give the thickest the item is ever drawn, whatever it is doing now.

        This is what a rectangle is measured from rather than
        :meth:`outline_width`, so that selecting an item is a repaint and never
        a change of geometry — which Qt would have to be told about separately,
        and which would make every selection cost a re-measure.

        Returns
        -------
        float
            Millimetres.
        """

        return self.line_appearance().width + SELECTED_EXTRA

    def restyle(self) -> None:
        """Take in that the item is drawn in a different style than it was.

        A width is **geometry**: a line three millimetres thick reaches a
        millimetre and a half beyond the shape, so the view is told before the
        rectangle changes rather than after, or it repaints the new rectangle
        and leaves what was drawn outside the old one on the sheet.  The caption
        is lettered again here too, since a size is geometry for the same
        reason — see :meth:`~masafi_simtwin.documents.canvas.Canvas.restyle`.
        """

        self.prepareGeometryChange()
        self.show_label()
        self.update()

    def pen(self, option) -> QPen:
        """Build the pen an item is outlined with.

        The join is **mitered**, which is what takes a corner to a point.  Qt's
        default is a bevel, and a bevel chamfers every corner by the width of
        the pen — on a bar two millimetres high drawn with a stroke of
        an ordinary width that is a visible cut across each corner, and a
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
        shaped, and so that they are always on top of what they belong to.  What
        is written beside the item is a child item and paints itself.

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

        The caption beside the item is not part of it and never was: it is a
        child item with a shape of its own, so clicking a caption is clicking
        the caption rather than the thing it captions.

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

    def boundingRect(self) -> QRectF:  # noqa: N802  (Qt naming)
        """Give what the item is drawn inside, its connecting points included.

        This is the item's own room, and the caption beside it is **not** in it:
        a label is a child with a rectangle of its own.  So this is what is held
        on the paper as the item is dragged, and what its caption is measured
        from.

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
