"""The box of text that says what something on the sheet is.

A **label** is what is written beside a place, a transition or an arc: one box,
holding the node's name and description as ``Name: Description``, or an arc's
weight.  It is a thing of its own rather than something its owner paints,
because a person is to be able to take hold of it — to select it, to move it and
to give it another width — and selecting, dragging and picking a thing out from
under the pointer are the scene's own work.  That is the argument
:class:`~masafi_simtwin.documents.guide.Guide` is a scene item for, met a second
time.

**A label is a child of what it belongs to.**  So it follows a node dragged
about the sheet, and an arc re-routed between two of them, with nothing to keep
in step: a child is drawn in its parent's coordinates, and Qt moves a parent
without touching what a child's own position says.  Qt also declines to move a
selected child of a selected parent twice, which is what makes a caption caught
in the same selection as its node harmless.

**It is dumb, and its owner is not.**  A label holds a piece of text and draws
it; *where it belongs* is its owner's to say — under a place, across a
transition, beside the middle of an arc — and so is what the text says.  The
owner sets both, and the label reports what a person did to it.

**A label is selected by clicking it, or by something asking outright — and by
nothing else.**  A rubber band
drawn over a net is aimed at the net, and a caption is not part of the drawing
in the way a place is: it says what the place is called.  So a band never picks
one up — :meth:`Label.itemChange` refuses a selection nobody asked for —
and a caption is never among what *Delete* or *Cut* act on.  A caption cannot be
deleted: it goes when the thing it describes goes.

**A label is moved by dragging it**, landing one of nine points of its box —
the centre, the middles of its sides, its corners — on the sheet's grid, and
held on the paper, as its owner is.  Those two rules are for a *person's* drag only: where
the owner puts the box — :meth:`Label.place` — is taken exactly as it is given,
since a box laid out under a place, or an offset read back from a file, is
already where it is meant to be.

**A resizable label is made wider or narrower by a handle on each side**, shown
while it is selected and drawn the way an arc's handles are.  Only the width
changes; the text wraps to it and the box is as tall as the lines that makes.
The side dragged follows the pointer and **where the box then goes is still its
owner's to say**: the owner is asked where a box of any width would be centred
(``label_centre``), so a box centred under a place grows both ways, and a box
beside an upright transition grows away from the bar with its near side held
still — which is why that side carries no handle at all.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PyQt6.QtCore import QLineF, QPointF, QRectF, QSizeF, Qt
from PyQt6.QtGui import QFont, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsItem

from masafi_simtwin.documents.ink import (
    HANDLE_GRAB,
    HANDLE_SIZE,
    LABEL_WIDTH,
    Block,
    block_path,
    ink_colour,
    paper_colour,
    text_layout,
    write_block,
)

#: How far a label stands off the item it belongs to, in millimetres.
LABEL_GAP = 1.0

#: What goes between a node's name and its description.
LABEL_SEPARATOR = ': '

#: How much air there is between the text and the frame drawn round it while it
#: is selected, in millimetres.  A frame tight on the ink reads as a box that is
#: too small for what is in it.
LABEL_PADDING = 0.5

#: How narrow a caption may be made, in millimetres.  Narrower than any word
#: worth writing, so a person can squeeze a box a long way; not so narrow that
#: every letter goes onto a line of its own.
MIN_LABEL_WIDTH = 5.0

#: Which way each side of a box lies from its centre: the left side and the
#: right side, which are the two a resizable label carries handles on.
LABEL_EDGES = (-1, 1)


class Label(QGraphicsItem):
    """What is written beside something on the sheet, as a thing of its own.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QGraphicsItem
        What the label belongs to.  A label is always a child: it is drawn in
        its owner's coordinates and goes when its owner goes.
    snap : collections.abc.Callable, optional
        What to round a width to as a person resizes the label, which is the
        grid step its owner is snapped to.
    bounds : collections.abc.Callable, optional
        Where the label may be dragged, as something returning a rectangle in
        scene coordinates — the sheet, asked for at every move.
    resizable : bool, optional
        Whether it carries handles to be made wider or narrower by.  Its owner
        then keeps the width, as ``label_width``, and says where a box of any
        size is centred, as ``label_centre(size)``.
    snap_point : collections.abc.Callable, optional
        What to move the box's centre to as a person drags it, given the centre,
        the box's :meth:`snap_anchors` and where its owner's frame begins on the
        sheet.  The canvas passes
        :meth:`~masafi_simtwin.documents.canvas.CanvasView.snap_point`, so one
        of the box's nine points lands on a crossing of the **sheet's** grid;
        without one a box goes where it is dragged.

    Attributes
    ----------
    text : str
        What is written in it.  Nothing at all for a thing with nothing to say,
        which draws no box and cannot be selected.
    width : float, optional
        How wide it has been made, or ``None`` for :data:`LABEL_WIDTH` with the
        box fitted to the text.
    """

    def __init__(
        self,
        parent: QGraphicsItem,
        snap: Callable[[float], float] | None = None,
        bounds: Callable[[], QRectF] | None = None,
        resizable: bool = False,
        *,
        snap_point: Callable[..., QPointF] | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = ''
        self._width: float | None = None
        self._style = None
        self._block = Block((), QSizeF(0.0, 0.0), 0.0, QFont())
        self._glyphs = QPainterPath()
        self._size = QSizeF(0.0, 0.0)
        self._asked = False
        self._snap = snap
        self._snap_point = snap_point
        self._bounds = bounds
        self._placing = False
        self._resizable = resizable
        self._resizing: int | None = None
        #: Whether a person has dragged the label since this was last put down.
        #: What the view reads after a drag, rather than comparing positions:
        #: a caption that shifted because its arc was re-routed, or because it
        #: was resized, has moved without anybody moving it.
        self.dragged = False

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    # ------------------------------------------------------------------
    # What it says
    # ------------------------------------------------------------------

    @property
    def text(self) -> str:
        """str: What is written in the box.

        Setting it lays the box out again, which is a change of geometry and not
        merely of paint: the box is as big as what is in it, so the view has to
        be told before it changes size or it repaints the new box and leaves the
        old one on the sheet.
        """

        return self._text

    @text.setter
    def text(self, text: str) -> None:
        text = str(text)
        if text == self._text:
            return
        self._text = text
        self._lay_out()
        if not self._text:
            self.setSelected(False)

    @property
    def style(self):
        """simtwin_core.petri_net.TextStyle, optional: What it is lettered in.

        Set by its owner, which is what resolves the application's defaults
        against the style the item was given of its own — a label is dumb, and
        what it is written in is told to it exactly as what it says is.  A label
        nobody has told letters nothing at all.
        """

        return self._style

    @style.setter
    def style(self, style) -> None:
        if style == self._style:
            return
        self._style = style
        self._lay_out()

    @property
    def width(self) -> float | None:
        """float, optional: How wide the box has been made.

        ``None`` wraps the text to :data:`LABEL_WIDTH` and fits the box to it;
        a width wraps it there and draws the box that wide.
        """

        return self._width

    @width.setter
    def width(self, width: float | None) -> None:
        width = None if width is None else float(width)
        if width == self._width:
            return
        self._width = width
        self._lay_out()

    def _lay_out(self) -> None:
        """Lay the text out again, at the width the box has.

        A change of geometry and not merely of paint: the box is as big as what
        is in it, so the view is told before it changes size or it repaints the
        new box and leaves the old one on the sheet.

        **Both the layout and the path are kept.**  The path is what the sheet
        is written with and is built once here rather than at every repaint; the
        layout is what the same caption is written from on paper, where it is
        text rather than a path — see
        :func:`~masafi_simtwin.documents.ink.write_block`.
        """

        self.prepareGeometryChange()
        if self._style is None:
            self._block = Block((), QSizeF(0.0, 0.0), 0.0, QFont())
        elif self._width is None:
            self._block = text_layout(self._text, LABEL_WIDTH, self._style)
        else:
            self._block = text_layout(
                self._text, self._width, self._style, fit=False
            )
        self._glyphs = block_path(self._block)
        self._size = self._block.box
        self.update()

    @property
    def size(self) -> QSizeF:
        """PyQt6.QtCore.QSizeF: How big the box is, in millimetres.

        Empty for a label with nothing to say.  It is what an owner works out
        where the box belongs from, so it is asked for rather than guessed at.
        """

        return QSizeF(self._size)

    def is_empty(self) -> bool:
        """Say whether there is nothing to draw.

        Returns
        -------
        bool
            Whether the box is empty, which is what a thing with no name comes
            to — an item made outside the editor.
        """

        return self._glyphs.isEmpty()

    def box(self) -> QRectF:
        """Give the box, centred on the label's own position.

        Returns
        -------
        PyQt6.QtCore.QRectF
            The rectangle the text was laid out in, and an empty one for a label
            with nothing to say.
        """

        if self.is_empty():
            return QRectF()
        return QRectF(
            -self._size.width() / 2.0,
            -self._size.height() / 2.0,
            self._size.width(),
            self._size.height(),
        )

    def frame(self) -> QRectF:
        """Give the frame drawn round the box while it is selected.

        :data:`LABEL_PADDING` outside the box on every side.  It is what a person
        sees of a caption while dragging it — a drag selects what it takes hold
        of — so it is also what the caption is lined up on the grid by.

        Returns
        -------
        PyQt6.QtCore.QRectF
            The rectangle, centred on the label's own position, and an empty one
            for a label with nothing to say.
        """

        box = self.box()
        if box.isEmpty():
            return QRectF()
        return box.adjusted(-LABEL_PADDING, -LABEL_PADDING, LABEL_PADDING, LABEL_PADDING)

    # ------------------------------------------------------------------
    # Being a thing on the sheet
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:  # noqa: N802  (Qt naming)
        """Give what the label paints inside: the box and its frame.

        Returns
        -------
        PyQt6.QtCore.QRectF
            The rectangle.
        """

        box = self.box()
        if box.isEmpty():
            return box
        reach = LABEL_PADDING * 2.0
        if self.handles():
            reach = LABEL_PADDING + max(LABEL_PADDING, HANDLE_GRAB)
        return box.adjusted(-reach, -reach, reach, reach)

    def shape(self) -> QPainterPath:
        """Give what can be taken hold of, which is the box and its air.

        Returns
        -------
        PyQt6.QtGui.QPainterPath
            The padded box and, while it carries handles, a reach of
            :data:`~masafi_simtwin.documents.ink.HANDLE_GRAB` round each — a
            press is sent to the item whose shape it falls in, so a handle
            outside the shape could never be taken hold of.  Nothing at all for
            a label with nothing in it: a thing with no name is a thing with
            nothing to click on.
        """

        path = QPainterPath()
        frame = self.frame()
        if not frame.isEmpty():
            path.addRect(frame)
            for where in self.handles().values():
                path.addEllipse(where, HANDLE_GRAB, HANDLE_GRAB)
        return path.simplified()

    def paint(self, painter, option, widget=None) -> None:
        """Write the text, and frame it while it is selected.

        The ink is the **owner's**: a caption is drawn in the accent while the
        thing it describes is selected, so that the two read as one thing, and
        in the accent while the caption itself is selected, so that taking hold
        of one can be seen.  The frame is what tells the two apart — a hairline
        of the accent, dashed, the way a selected guide is dashed.

        **How the text is marked is not this label's to decide**:
        :func:`~masafi_simtwin.documents.ink.write_block` writes it as a path on
        the sheet and as text on paper.  The frame and the handles are the
        session's rather than the drawing's, and a print never reaches them —
        nothing is selected while one is taken.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the view.
        option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
            What the view knows about drawing this label, its palette included.
        widget : PyQt6.QtWidgets.QWidget, optional
            The widget being painted on.
        """

        if self.is_empty():
            return

        owner = self.parentItem()
        chosen = self.isSelected() or (owner is not None and owner.isSelected())
        ink = ink_colour(chosen, option, self._style.colour)

        write_block(painter, self._block, self._glyphs, ink)

        if not self.isSelected():
            return
        painter.setPen(QPen(ink, 0.0, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.frame())

        painter.setPen(QPen(ink, 0.0))
        painter.setBrush(paper_colour(option))
        half = HANDLE_SIZE / 2.0
        for where in self.handles().values():
            painter.drawRect(QRectF(where.x() - half, where.y() - half, HANDLE_SIZE, HANDLE_SIZE))

    # ------------------------------------------------------------------
    # Making it wider or narrower
    # ------------------------------------------------------------------

    def _edge_rule(self, edge: int) -> tuple[float, float] | None:
        """Say where one side of the box is for a box of any width.

        The owner decides where a box is centred, and for both owners there are
        that is a straight line in the width — fixed for a box centred under a
        place or moved by hand, half the width out for a box put beside an
        upright transition — so it is asked at two widths and the line drawn
        through them.

        Parameters
        ----------
        edge : int
            ``-1`` for the left side, ``1`` for the right, as :data:`LABEL_EDGES`.

        Returns
        -------
        tuple of float, optional
            ``(start, rate)`` such that the side is at ``start + rate * width``
            in the owner's coordinates, or ``None`` for a side that does not move
            whatever the width — the one that is held still.
        """

        height = self._size.height()
        centre_for = getattr(self.parentItem(), 'label_centre', None)
        if centre_for is None:
            start, turn = self.pos().x(), 0.0
        else:
            narrow = centre_for(QSizeF(MIN_LABEL_WIDTH, height)).x()
            wide = centre_for(QSizeF(MIN_LABEL_WIDTH + 10.0, height)).x()
            turn = (wide - narrow) / 10.0
            start = narrow - turn * MIN_LABEL_WIDTH
        rate = turn + edge / 2.0
        if abs(rate) < 1e-9:
            return None
        return start, rate

    def handles(self) -> dict[int, QPointF]:
        """Give the handles the box is resized by, while it carries any.

        Returns
        -------
        dict
            Where the handle of each side is, in the label's own coordinates, by
            the side: the middle of that side of the frame.  Empty for a label
            that is not resizable, not selected or has nothing in it, and
            without the side that is held still.
        """

        if not (self._resizable and self.isSelected()) or self.is_empty():
            return {}
        half = self._size.width() / 2.0 + LABEL_PADDING
        return {
            edge: QPointF(edge * half, 0.0)
            for edge in LABEL_EDGES
            if self._edge_rule(edge) is not None
        }

    def handle_at(self, point: QPointF) -> int | None:
        """Find the handle a position falls on.

        Parameters
        ----------
        point : PyQt6.QtCore.QPointF
            Where to look, in the label's own coordinates.

        Returns
        -------
        int, optional
            The side whose handle is nearest within
            :data:`~masafi_simtwin.documents.ink.HANDLE_GRAB`, or ``None``.
        """

        near = [
            (QLineF(point, where).length(), edge)
            for edge, where in self.handles().items()
            if QLineF(point, where).length() <= HANDLE_GRAB
        ]
        return min(near)[1] if near else None

    def resize_to(self, edge: int, x: float) -> None:
        """Make the box as wide as puts one side under a place.

        Parameters
        ----------
        edge : int
            Which side is being dragged.
        x : float
            Where the pointer is across the sheet, in the owner's coordinates.
            The handle is on the frame, a padding outside the box.
        """

        rule = self._edge_rule(edge)
        if rule is None:
            return
        start, rate = rule
        width = (x - edge * LABEL_PADDING - start) / rate
        if self._snap is not None:
            width = self._snap(width)
        width = max(width, MIN_LABEL_WIDTH)
        owner = self.parentItem()
        if self._resizable and owner is not None and hasattr(owner, 'label_width'):
            owner.label_width = width
        else:
            self.width = width

    # ------------------------------------------------------------------
    # Taking hold of one
    # ------------------------------------------------------------------

    def select(self) -> None:
        """Take hold of the label, as a press on it does.

        The other door into a selection, for whatever asks for one outright.  A
        rubber band asks for nothing: it sets an area, and what falls inside it
        is selected without anybody having aimed at it, which is exactly what a
        caption is to be safe from.
        """

        self._asked = True
        try:
            self.setSelected(True)
        finally:
            self._asked = False

    def mousePressEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Take hold of a handle, or let the press through and let it select the
        label.

        Qt's own handler is what selects an item that is pressed, so the flag
        that :meth:`itemChange` looks for is raised around it and lowered again
        afterwards.  A press on a handle never reaches it: the label is already
        selected, and what is wanted is a resize rather than a move.

        Parameters
        ----------
        event : PyQt6.QtWidgets.QGraphicsSceneMouseEvent
            The press.
        """

        if event.button() == Qt.MouseButton.LeftButton:
            self._resizing = self.handle_at(event.pos())
            if self._resizing is not None:
                event.accept()
                return
        self._asked = True
        try:
            super().mousePressEvent(event)
        finally:
            self._asked = False

    def mouseMoveEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Drag the handle that was taken hold of, or move the label.

        Parameters
        ----------
        event : PyQt6.QtWidgets.QGraphicsSceneMouseEvent
            The mouse event.
        """

        if self._resizing is not None:
            self.resize_to(self._resizing, self.mapToParent(event.pos()).x())
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

        if self._resizing is not None:
            self._resizing = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def place(self, position: QPointF) -> None:
        """Put the label where its owner says, exactly.

        Parameters
        ----------
        position : PyQt6.QtCore.QPointF
            Where its centre goes, in its owner's coordinates.  Neither snapped
            nor held on the paper: those are rules for a drag, and what an owner
            gives is where the box belongs.
        """

        self._placing = True
        try:
            self.setPos(position)
        finally:
            self._placing = False

    def snap_anchors(self) -> tuple[QPointF, ...]:
        """Give the points of the box that may land on the grid.

        Nine, as agreed with Jaume: the centre, the middle of each side and the
        four corners — so a caption can be lined up by whichever edge or corner
        is nearest where it is let go, and a column of captions lined up by
        their left sides.  They are the points of the :meth:`frame`, the line a
        person sees while dragging, not of the text inside it: snapped by the
        text, a caption's visible corner sat half a millimetre off every
        crossing, which a render showed.

        Returns
        -------
        tuple of PyQt6.QtCore.QPointF
            The centre first, since a tie goes to the first; then the middles of
            the top, right, bottom and left sides; then the top left, top right,
            bottom right and bottom left corners.  In the label's own
            coordinates, which are measured from its centre.  A label with
            nothing to say has no box, and the centre alone.
        """

        frame = self.frame()
        if frame.isEmpty():
            return (QPointF(0.0, 0.0),)
        return (
            QPointF(0.0, 0.0),
            QPointF(0.0, frame.top()),
            QPointF(frame.right(), 0.0),
            QPointF(0.0, frame.bottom()),
            QPointF(frame.left(), 0.0),
            frame.topLeft(),
            frame.topRight(),
            frame.bottomRight(),
            frame.bottomLeft(),
        )

    def _dragged_to(self, position: QPointF) -> QPointF:
        """Snap a place a person is dragging the label to, and hold it on the paper.

        One of the box's :meth:`snap_anchors` is put on a crossing of the
        sheet's grid — not a whole step from its owner, whose own centre may
        be off the grid, having been snapped by an edge.  The whole **box** is
        then held inside the sheet, not merely its centre, the way a node is.

        Both are worked out in the owner's frame rather than by mapping out to
        the sheet and back, so a box that did not have to be held keeps exactly
        the offset the snap gave it.

        Parameters
        ----------
        position : PyQt6.QtCore.QPointF
            Where the drag would put its centre, in its owner's coordinates.

        Returns
        -------
        PyQt6.QtCore.QPointF
            Where it goes instead.
        """

        owner = self.parentItem()
        origin = owner.scenePos() if owner is not None else QPointF()
        if self._snap_point is not None:
            position = self._snap_point(position, self.snap_anchors(), origin)
        x, y = position.x(), position.y()
        box = self.box()
        if self._bounds is None or box.isEmpty():
            return QPointF(x, y)

        area = self._bounds()
        left = area.left() - box.left() - origin.x()
        right = area.right() - box.right() - origin.x()
        top = area.top() - box.top() - origin.y()
        bottom = area.bottom() - box.bottom() - origin.y()
        if left <= right:
            x = min(max(x, left), right)
        if top <= bottom:
            y = min(max(y, top), bottom)
        return QPointF(x, y)

    def itemChange(self, change, value):  # noqa: N802  (Qt naming)
        """Refuse a selection nobody asked for, and keep a drag on the paper.

        A rubber band is drawn over the net to pick up what is drawn; a caption
        is not that, and a band that swept up half the captions on a sheet would
        make *Delete* look dangerous when it is not.  A press and :meth:`select`
        are the two things that do ask.  Putting a selection **down** is never
        refused, whoever asks.

        A move that is not :meth:`place` is a person dragging the label, and is
        snapped and held on the paper.

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

        if (
            change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange
            and value
            and not self._asked
        ):
            return False
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            # The handles are in the rectangle only while it is selected, so the
            # area last painted is repainted — the reason Arc.itemChange gives.
            self.prepareGeometryChange()
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
            and not self._placing
        ):
            self.dragged = True
            return self._dragged_to(value)
        return super().itemChange(change, value)
