"""The canvas every drawn document is built on.

A canvas is a sheet with rulers along its top and its left, a view of the scene
between them, and a corner box saying what the rulers count in.  The Petri net
editor is the first document over it; the process flow and the 2D animation are
the same thing with different items on the scene, which is why this is a canvas
rather than a part of the Petri net editor.

**One scene unit is one millimetre.**  A scene is otherwise in units of nothing
in particular, and a ruler cannot be drawn over units of nothing in particular.
Millimetres are also what a sheet is measured in everywhere else it might end up
— printed, exported, or laid beside another sheet — and they are a property of
the drawing rather than of the model on it: a Petri net has no distance unit of
its own, but the drawing of one has a size.

At a zoom of ``1.0`` a millimetre of the scene is :data:`PIXELS_PER_MM` pixels
across, so the sheet is life size.  The number is Qt's own reference resolution
rather than the screen's, deliberately: a zoom means the same thing on every
machine, and Qt's high-DPI scaling already puts the right number of physical
pixels behind a logical one.

The sheet is **ruled into pages**: it is a whole number of them —
:data:`PAGES_ACROSS` by :data:`PAGES_DOWN` — and the boundary of every one is
drawn, so that what falls on which sheet of paper can be seen without printing
anything.  Which page that is, and which way round, are the two preferences
:func:`masafi_simtwin.preferences.page` resolves — by default the size this
machine prints on, upright.  The lines are drawn like the grid and belong with it: the
paper the drawing is measured against rather than anything in the drawing.

The **origin is the sheet's top left corner**, not its middle.  Both rulers read
nought there and count right and down, the way a page is read, so nothing on the
sheet is at a negative coordinate and the first page is the one a new document
opens on.

Guides are pulled out of the rulers and dropped on the sheet, and they snap as
they go — to the **grid step**, the distance between the points a drawing lands
on, which is the preference :func:`masafi_simtwin.preferences.grid_step` resolves
and a millimetre by default.  It is the same at every zoom.  A snap that changed
with the zoom would mean the same drag put a guide in a different place depending
on how close the sheet happened to be, which is the one thing a guide is there
not to do.  Everything that snaps on the sheet goes through
:meth:`CanvasView.snap`, or through :meth:`CanvasView.snap_point` when a thing
has more than one point of its own that may land on the grid.

The grid that is **drawn** is not the grid things snap to, decided with Jaume:
the squares stay :data:`GRID_STEP` whatever the step is.  At the default step of
a millimetre a drawn grid would be under :data:`MIN_GRID_PIXELS` at life size and
dropped, leaving the sheet with no squares at all.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from PyQt6.QtCore import QLineF, QPointF, QRectF, QSizeF, Qt, pyqtSignal
from PyQt6.QtGui import QActionGroup, QColor, QCursor, QPainter, QPalette, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from masafi_simtwin import preferences
from masafi_simtwin.documents.arc import (
    END_HANDLES,
    HANDLE_SIZE,
    INHIBITOR_RADIUS,
    Arc,
    ArcKind,
    ArcShape,
    arc_between,
    arrowhead,
    chord_point,
    ring_centre,
    route_path,
    route_segments,
    shape_label,
    untouched_segments,
)
from masafi_simtwin.documents.guide import Guide
from masafi_simtwin.documents.net_item import PORT_GRAB, NetItem
from masafi_simtwin.documents.ruler import MILLIMETRES, Ruler, RulerCorner, RulerUnit
from masafi_simtwin.library_tree import element_from_mime

#: Millimetres to an inch, which is what makes a scene in millimetres a scene.
MM_PER_INCH = 25.4

#: Qt's reference resolution, in dots per inch.
REFERENCE_DPI = 96.0

#: Pixels to one millimetre at a zoom of ``1.0``.
PIXELS_PER_MM = REFERENCE_DPI / MM_PER_INCH

#: Side, in millimetres, of one square of the grid.
GRID_STEP = 5

#: How many squares there are between two heavier lines.
GRID_MAJOR = 10

#: Opacity, out of 255, of a minor grid line and of a major one.
GRID_MINOR_ALPHA = 22
GRID_MAJOR_ALPHA = 45

#: A grid whose squares come closer than this, in pixels, is not drawn: the
#: heavier lines are enough to say which way is which, and the rest is a haze.
MIN_GRID_PIXELS = 5.0

#: How much one notch of the wheel, or one press of the zoom, changes the scale.
ZOOM_STEP = 1.15

#: How far in and out the canvas can be taken, ``1.0`` being life size.
MIN_ZOOM = 0.1
MAX_ZOOM = 8.0

#: How many pages the sheet is, across and down.  The sheet is a whole number
#: of pages so that the tiling comes out even: a part-page along the right or
#: the bottom would be a page nothing could be printed on.
PAGES_ACROSS = 20
PAGES_DOWN = 10


def sheet_rect(page: QSizeF) -> QRectF:
    """Give the sheet a page of this size makes.

    The sheet's origin is its **top left corner**: both rulers read nought there
    and count right and down from it, which is the way a page is read and the
    way a printed sheet is laid out.  Nothing on the sheet is at a negative
    coordinate, so a position is a position on the paper.

    Parameters
    ----------
    page : PyQt6.QtCore.QSizeF
        The page, in millimetres, the way round it is used.

    Returns
    -------
    PyQt6.QtCore.QRectF
        :data:`PAGES_ACROSS` by :data:`PAGES_DOWN` of them — four metres by
        three, for an upright A4.
    """

    return QRectF(0.0, 0.0, page.width() * PAGES_ACROSS, page.height() * PAGES_DOWN)

#: How many decimals of a millimetre a snapped coordinate is kept to.  A step
#: that is not a whole number multiplies out inexactly — three steps of 0.1 are
#: 0.30000000000000004 — and a position is written to a file as it is held, so
#: it is rounded to what anybody could have meant: a nanometre, far below
#: anything a sheet can show and far above what a double loses at four metres.
SNAP_DIGITS = 9

#: How much longer one anchor's move may be than another's and still be the
#: same move, in millimetres.  The anchors of a place a whole number of steps
#: from its centre all ask for one move, which floating point makes differ in
#: the last bit; within this they tie, and the tie goes to the first anchor —
#: the centre — rather than to whichever the rounding happened to favour.
SNAP_TIE = 1e-9


def _multiples_of(spacing: float, first: float, last: float) -> list[float]:
    """List the multiples of a spacing that fall inside a stretch of the scene.

    The stretch is a *float* one — the rectangle a view hands to
    ``drawBackground`` is whatever part of the scene needs painting, and after a
    scroll that is a strip with fractional edges.  Rounding those edges inwards
    is what leaves the grid in dashes: each strip stops short of the next, and
    the sliver between them is painted by neither.

    Parameters
    ----------
    spacing : float
        The step, in scene millimetres.
    first : float
        Where the stretch begins.
    last : float
        Where it ends.

    Returns
    -------
    list of float
        Every multiple of ``spacing`` from the first at or after ``first`` to the
        last at or before ``last``.
    """

    start = math.ceil(first / spacing)
    end = math.floor(last / spacing)
    return [index * spacing for index in range(start, end + 1)]


class CanvasView(QGraphicsView):
    """The view of the sheet: the grid, the zoom, the panning and the selection.

    Parameters
    ----------
    page : PyQt6.QtCore.QSizeF, optional
        The page the sheet is ruled into, in millimetres and the way round it
        is used.  The one the preferences ask for is taken when it is omitted,
        which is what every document does; passing one is for the tests.
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.

    Attributes
    ----------
    empty_note : str
        What to say over an empty sheet.  Nothing is said when it is empty
        itself, and the note goes of its own accord once the scene holds
        something to look at.
    view_changed : PyQt6.QtCore.pyqtSignal
        Emitted whenever the scene moves under the viewport — scrolled, zoomed
        or resized — which is when a ruler has to be drawn again.
    pointer_moved : PyQt6.QtCore.pyqtSignal
        Emitted with the scene position of the pointer as it moves over the
        sheet, which is what puts the mark on the rulers.
    pointer_left : PyQt6.QtCore.pyqtSignal
        Emitted when the pointer leaves the sheet, which takes the mark off
        again.
    element_dropped : PyQt6.QtCore.pyqtSignal
        Emitted with the keys of the library and of the element dragged out of
        the Libraries pane, and the scene position it was let go over — not
        snapped, since which of its points lands on the grid is the element's to
        say, and the element does not exist until the document makes it.
        The view takes the drop and says so; what an element *becomes* is the
        document's to decide, a canvas being the sheet rather than the drawing
        on it.
    connection_drawn : PyQt6.QtCore.pyqtSignal
        Emitted with the two :class:`~masafi_simtwin.documents.net_item.NetItem`
        an arc has been drawn between — the one it was started from first — and
        the indices of the connecting point it leaves by and the one it enters
        by, which are where it is attached for good — and the points laid on the
        bare sheet on the way, in scene millimetres, which is a list and most
        often an empty one.  The view runs the gesture and checks that the two
        may be joined at all, and by an arc of :attr:`new_arc_kind`; making the
        arc is the document's, for the same reason a drop is.
    arc_end_asked : PyQt6.QtCore.pyqtSignal
        Emitted with an arc, which end of it was dragged, and the item and
        connecting point it was let go on.  The sheet does not move it: that is
        a change to the net, and a change belongs to the document.
    deletion_asked : PyQt6.QtCore.pyqtSignal
        Emitted with the things a person asked to have deleted — items, arcs and
        guides together, whatever was selected or aimed at.
    items_moved : PyQt6.QtCore.pyqtSignal
        Emitted after a drag with every item that ended up somewhere else, as
        ``(item, before, after)`` in scene millimetres.  Qt moves an item as it
        is dragged, so this says what happened rather than asking.
    guides_moved : PyQt6.QtCore.pyqtSignal
        The same for the guides, as ``(guide, before, after)``.
    labels_moved : PyQt6.QtCore.pyqtSignal
        The same for the captions a person dragged — a node's and an arc's
        weight alike — as ``(owner, before, after)``: what the caption belongs
        to, its ``label_offset`` before — ``None`` for a caption nobody had
        moved — and after, as the owner keeps one: relative to a node's centre,
        in an arc's chord frame.  Only a caption the label itself says was
        dragged is reported, so one carried along by its node, re-placed as its
        arc is re-routed, or shifted by a resize is not.
    labels_resized : PyQt6.QtCore.pyqtSignal
        The same for the captions a handle was dragged on, as ``(item, before,
        after)``: the item and its
        :attr:`~masafi_simtwin.documents.net_item.NetItem.label_width` before
        and after, ``None`` being the editor's own width.
    arcs_shaped : PyQt6.QtCore.pyqtSignal
        The same for the arcs a shaping handle was dragged on, as ``(arc,
        before controls, before points, after controls, after points)`` in each
        arc's own chord frame.
    arc_shape_asked : PyQt6.QtCore.pyqtSignal
        Emitted with an arc and the shape its context menu was used to choose.
        The sheet does not reshape it: **what a change to a net is belongs to
        the document**, which is what can record it so that it can be undone.
    arc_point_asked : PyQt6.QtCore.pyqtSignal
        Emitted with an arc and where, in scene millimetres, its context menu
        asked for a point to be put into it.
    arc_point_removal_asked : PyQt6.QtCore.pyqtSignal
        Emitted with an arc and which of its points its context menu asked to
        have taken out.
    rotation_asked : PyQt6.QtCore.pyqtSignal
        Emitted with the items its context menu asked to have turned the other
        way round.  The sheet does not turn them, for the reason it does not
        reshape an arc: a change to a net is the document's.
    text_reset_asked : PyQt6.QtCore.pyqtSignal
        Emitted with the things whose context menu asked for the lettering they
        were given to be taken back, so that they follow the application's
        defaults again.
    line_reset_asked : PyQt6.QtCore.pyqtSignal
        The same for the lines they are drawn with.
    """

    view_changed = pyqtSignal()
    pointer_moved = pyqtSignal(QPointF)
    pointer_left = pyqtSignal()
    element_dropped = pyqtSignal(str, str, QPointF)
    connection_drawn = pyqtSignal(object, object, int, int, object)
    item_activated = pyqtSignal(object)
    arc_shape_asked = pyqtSignal(object, object)
    text_reset_asked = pyqtSignal(object)
    line_reset_asked = pyqtSignal(object)
    arc_end_asked = pyqtSignal(object, str, object, int)
    deletion_asked = pyqtSignal(object)
    items_moved = pyqtSignal(object)
    guides_moved = pyqtSignal(object)
    labels_moved = pyqtSignal(object)
    labels_resized = pyqtSignal(object)
    arcs_shaped = pyqtSignal(object)
    arc_point_asked = pyqtSignal(object, QPointF)
    arc_point_removal_asked = pyqtSignal(object, int)
    rotation_asked = pyqtSignal(object)

    def __init__(self, page: QSizeF | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('CanvasView')
        self.empty_note = ''
        self._page = QSizeF(page) if page is not None else preferences.page()
        self._grid_step = preferences.grid_step()

        scene = QGraphicsScene(self)
        scene.setSceneRect(sheet_rect(self._page))
        self.setScene(scene)

        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.viewport().setMouseTracking(True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setAcceptDrops(True)

        self._panning_from: QPointF | None = None
        self._connecting_from: NetItem | None = None
        self._connecting_over: NetItem | None = None
        self._connecting_port = 0
        self._moving_end: tuple[Arc, str] | None = None
        self._connecting_at = QPointF()
        self._connecting_pressed_at: QPointF | None = None
        self._connecting_points: list[QPointF] = []
        self._before_drag: dict | None = None
        self._new_arc_shape = ArcShape.STRAIGHT
        self._new_arc_kind = ArcKind.NORMAL
        self.scale(PIXELS_PER_MM, PIXELS_PER_MM)
        self.scroll_to_origin()

    @property
    def page(self) -> QSizeF:
        """PyQt6.QtCore.QSizeF: The page the sheet is ruled into, in millimetres."""

        return QSizeF(self._page)

    def set_page(self, page: QSizeF) -> None:
        """Rule the sheet into a page of a different size.

        The sheet is a whole number of pages, so changing the page changes the
        sheet, and the guides drawn across it have to be told: a guide runs the
        length of the sheet and its geometry belongs to the scene.

        Parameters
        ----------
        page : PyQt6.QtCore.QSizeF
            The page, in millimetres, the way round it is used.
        """

        if page == self._page:
            return

        self._page = QSizeF(page)
        sheet = sheet_rect(self._page)
        self.scene().setSceneRect(sheet)
        for guide in self.guides:
            guide.set_sheet(sheet)
        self.viewport().update()
        self.view_changed.emit()

    def scroll_to_origin(self) -> None:
        """Show the top left corner of the sheet, where the first page is.

        A view of its own accord opens on the middle of its scene, which on a
        sheet four metres wide is a blank stretch a long way from anything.  The
        corner is where the rulers read nought and where the first page is, so
        it is where a sheet is opened.
        """

        self.horizontalScrollBar().setValue(self.horizontalScrollBar().minimum())
        self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    @property
    def zoom(self) -> float:
        """float: The scale the sheet is drawn at, ``1.0`` being life size."""

        return self.transform().m11() / PIXELS_PER_MM

    def zoom_by(self, factor: float) -> None:
        """Scale the sheet, without letting it out of its limits.

        Parameters
        ----------
        factor : float
            What to multiply the current zoom by.
        """

        target = min(max(self.zoom * factor, MIN_ZOOM), MAX_ZOOM)
        if target != self.zoom:
            self.scale(target / self.zoom, target / self.zoom)
            self.view_changed.emit()

    def zoom_in(self) -> None:
        """Take the sheet one step closer."""

        self.zoom_by(ZOOM_STEP)

    def zoom_out(self) -> None:
        """Take the sheet one step further away."""

        self.zoom_by(1.0 / ZOOM_STEP)

    def reset_zoom(self) -> None:
        """Put the sheet back to life size."""

        self.zoom_by(1.0 / self.zoom)

    def wheelEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Zoom on a wheel turn with *Control*, and scroll on one without it.

        Parameters
        ----------
        event : PyQt6.QtGui.QWheelEvent
            The wheel event.
        """

        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self.zoom_by(ZOOM_STEP if delta > 0 else 1.0 / ZOOM_STEP)
            event.accept()
            return
        super().wheelEvent(event)

    # ------------------------------------------------------------------
    # Snapping
    # ------------------------------------------------------------------

    @property
    def grid_step(self) -> float:
        """float: How far apart the points a drawing lands on are, in millimetres."""

        return self._grid_step

    def set_grid_step(self, step: float) -> None:
        """Snap to points a different distance apart from now on.

        Nothing already on the sheet moves.  Where a thing is was recorded when
        it was put there, and moving every item of every open net onto a new
        grid would be a change nobody made and nothing could undo.  The next
        drag lands on the new grid; what is not dragged stays where it was.

        Nothing is repainted either: the squares that are drawn are
        :data:`GRID_STEP` whatever the step is.

        Parameters
        ----------
        step : float
            The distance, in millimetres.

        Raises
        ------
        ValueError
            When it is not a positive number, which no grid can be made of.
        """

        if not (math.isfinite(step) and step > 0.0):
            raise ValueError(f'a grid step must be a positive distance, not {step!r}')
        self._grid_step = float(step)

    def snap(self, value: float) -> float:
        """Round a scene coordinate to the grid.

        The zoom has nothing to do with it.  A guide dropped at the same place
        lands on the same point whether the sheet was close to or far from the
        eye when it was dropped.  The grid is measured from the sheet's origin,
        where both rulers read nought.

        Parameters
        ----------
        value : float
            A coordinate in scene millimetres.

        Returns
        -------
        float
            The nearest multiple of :attr:`grid_step`, kept to
            :data:`SNAP_DIGITS` decimals.
        """

        step = self._grid_step
        return round(round(value / step) * step, SNAP_DIGITS)

    def snap_point(
        self,
        point: QPointF,
        anchors: Sequence[QPointF] = (),
        origin: QPointF | None = None,
    ) -> QPointF:
        """Move a point by the least that puts one of its anchors on the grid.

        An anchor is a point of a thing that may land on the grid, measured from
        the point the thing is placed by — a place's centre and the four
        points of its rim, a transition's centre and the ends of its bar.  Each
        asks for the move that would put *it* on the nearest crossing of the
        grid, and the shortest of those moves is the one made, so a thing
        dragged near a line by its edge snaps by its edge and by its centre
        when that is nearer.  Decided with Jaume: no mode to choose, and a
        thing whose anchors all ask the same is snapped by its centre, exactly
        as before there were anchors.

        The anchor is chosen as a **point**, both coordinates at once, rather
        than one per axis: a place lands with one of its five points on a
        crossing, not with its left edge on one line and its centre on another.

        The grid is the **sheet's** whatever frame the point is in.  A caption
        is placed in its owner's coordinates, so it says where that frame begins
        on the sheet as ``origin``, and its corner lands on a crossing of the
        sheet rather than on a whole step from its node.  The answer is worked
        out and rounded here, in the point's own frame, rather than mapped out
        to the sheet and back — a round trip that turns 2.85 into
        2.8499999999999996 on the way.

        Parameters
        ----------
        point : PyQt6.QtCore.QPointF
            Where the thing would be placed, in scene millimetres.
        anchors : sequence of PyQt6.QtCore.QPointF, optional
            Its anchors, from ``point``, the centre first: a tie goes to the
            first.  None given is the centre alone.
        origin : PyQt6.QtCore.QPointF, optional
            Where the frame ``point`` is measured in begins, in scene
            millimetres.  Left out, ``point`` is on the sheet already.  A frame
            is only ever moved, never turned or scaled: nothing on the sheet is.

        Returns
        -------
        PyQt6.QtCore.QPointF
            Where the thing is placed instead, in the frame ``point`` was in.
        """

        ox, oy = (origin.x(), origin.y()) if origin is not None else (0.0, 0.0)
        best: tuple[float, QPointF] | None = None
        for anchor in anchors or (QPointF(),):
            x = round(
                self.snap(ox + point.x() + anchor.x()) - anchor.x() - ox, SNAP_DIGITS
            )
            y = round(
                self.snap(oy + point.y() + anchor.y()) - anchor.y() - oy, SNAP_DIGITS
            )
            length = math.hypot(x - point.x(), y - point.y())
            if best is None or length < best[0] - SNAP_TIE:
                best = (length, QPointF(x, y))
        return best[1]

    def pointer_on_the_sheet(self) -> QPointF | None:
        """Give where the pointer is on the sheet, if it is over it at all.

        Asked when it is wanted rather than followed and kept: a position noted
        at the last move is a position that was true then, and what a paste
        wants to know is where the pointer is **now** — which may be over
        another window, or over the menu the paste was chosen from.

        Returns
        -------
        PyQt6.QtCore.QPointF, optional
            The pointer's place in scene millimetres, or ``None`` when it is not
            over the sheet.
        """

        if not self.viewport().underMouse():
            return None
        where = self.viewport().mapFromGlobal(QCursor.pos())
        if not self.viewport().rect().contains(where):
            return None
        return self.mapToScene(where)

    # ------------------------------------------------------------------
    # Guides
    # ------------------------------------------------------------------

    @property
    def guides(self) -> list[Guide]:
        """list: The guides on the sheet, across it first and then up it."""

        found = [item for item in self.scene().items() if isinstance(item, Guide)]
        return sorted(found, key=lambda guide: (guide.orientation.value, guide.position))

    def add_guide(
        self, orientation: Qt.Orientation, position: float, exact: bool = False
    ) -> Guide:
        """Put a guide on the sheet.

        Parameters
        ----------
        orientation : PyQt6.QtCore.Qt.Orientation
            ``Horizontal`` for one lying across the sheet, ``Vertical`` for one
            standing up it.
        position : float
            Where it goes, in scene millimetres.  It is snapped like any other
            move of a guide, unless it is ``exact``.
        exact : bool, optional
            Whether the position is a record of where a guide was — read from a
            file, put back by an undo — rather than where one is being dropped,
            and so goes exactly there.  See
            :meth:`~masafi_simtwin.documents.guide.Guide.place`.

        Returns
        -------
        masafi_simtwin.documents.guide.Guide
            The guide, already on the scene.
        """

        guide = Guide(orientation, position, self.sceneRect(), self.snap)
        if exact:
            guide.place(position)
        self.scene().addItem(guide)
        return guide

    def remove_guide(self, guide: Guide) -> None:
        """Take one guide off the sheet.

        Parameters
        ----------
        guide : masafi_simtwin.documents.guide.Guide
            The guide to remove.
        """

        self.scene().removeItem(guide)

    def clear_guides(self) -> None:
        """Take every guide off the sheet."""

        for guide in self.guides:
            self.remove_guide(guide)

    def remove(self, item) -> None:
        """Take one thing off the sheet, and whatever cannot outlive it.

        An arc is a relation between two items, so an item taken off the sheet
        takes its arcs with it: a line drawn to somewhere nothing is would be
        worse than no line.  An arc taken off on its own tells both of its ends,
        so that neither goes on reporting its movements to something that is no
        longer there.

        Parameters
        ----------
        item : PyQt6.QtWidgets.QGraphicsItem
            What to remove.
        """

        scene = self.scene()
        if isinstance(item, NetItem):
            for arc in item.arcs:
                self.remove(arc)
        if isinstance(item, Arc):
            item.detach()
        if item.scene() is scene:
            scene.removeItem(item)

    def delete_selection(self) -> int:
        """Ask for everything that is selected to be deleted, whatever it is.

        Guides, items and arcs alike: *Delete* acts on the selection, which is
        the only rule that can be explained in one sentence.  The sheet does not
        delete any of it — deleting is a change to the net, and a change belongs
        to the document, which is what can put it back — so this says what was
        asked for and the document does it.

        Returns
        -------
        int
            How many things were asked about, so that a caller can say whether
            anything was.
        """

        selected = self.scene().selectedItems()
        if selected:
            self.deletion_asked.emit(selected)
        return len(selected)

    def delete_selected_guides(self) -> int:
        """Remove the guides that are selected.

        Returns
        -------
        int
            How many there were.
        """

        selected = [guide for guide in self.guides if guide.isSelected()]
        for guide in selected:
            self.remove_guide(guide)
        return len(selected)

    def has_content(self) -> bool:
        """Say whether the sheet holds anything but its guides.

        Returns
        -------
        bool
            Whether there is anything drawn on it.  A guide is not something
            drawn on the sheet: it is something the drawing is lined up against,
            so a sheet with guides and nothing else is still an empty sheet.
        """

        return any(not isinstance(item, Guide) for item in self.scene().items())

    def keyPressEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Delete what is selected on *Delete* or *Backspace*, and abandon an
        arc being drawn on *Escape*.

        While an arc is being drawn with points laid for it, *Backspace* takes
        the last of them back instead, the way it does in every tool that draws
        a line click by click: a point laid in the wrong place should cost one
        key rather than the whole route.

        Parameters
        ----------
        event : PyQt6.QtGui.QKeyEvent
            The key event.
        """

        if event.key() == Qt.Key.Key_Backspace and self.take_back_point():
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.delete_selection():
                event.accept()
                return
        if event.key() == Qt.Key.Key_Escape and self.connecting:
            self.abandon_connection()
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Offer what can be done to whatever is under the pointer.

        An arc first, because an arc lies over the sheet a guide runs across and
        is the smallest target there is; then the item under the pointer, which
        an arc may end on; then the guides, which run the whole length of the
        sheet.  None of the three has an entry in the menu bar to be reached
        from, so this is where they are found, and when the *Edit* menu grows a
        *Delete* it should come here rather than repeat this.

        While an arc is being drawn a right click **gives it up** instead, and
        offers nothing.  A click of the left button on the bare sheet lays a
        point for the arc to be led through, so the right button is the mouse's
        way out, beside *Escape*.

        Parameters
        ----------
        event : PyQt6.QtGui.QContextMenuEvent
            The context menu event.
        """

        if self._connecting_from is not None:
            self.abandon_connection()
            event.accept()
            return

        menu = self.arc_menu(self.arc_at(event.pos()), self.mapToScene(event.pos()))
        if menu is None:
            menu = self.item_menu(self.item_at(event.pos()))
        if menu is None:
            menu = self.guide_menu(self.guide_at(event.pos()))
        if menu is None:
            super().contextMenuEvent(event)
            return
        menu.exec(event.globalPos())
        event.accept()

    def guide_at(self, position) -> Guide | None:
        """Find the guide under a point of the viewport.

        Parameters
        ----------
        position : PyQt6.QtCore.QPoint
            Where to look, in the viewport's coordinates.

        Returns
        -------
        masafi_simtwin.documents.guide.Guide, optional
            The guide, or ``None`` when there is none there.
        """

        for item in self.items(position):
            if isinstance(item, Guide):
                return item
        return None

    def arc_at(self, position) -> Arc | None:
        """Find the arc under a point of the viewport.

        Parameters
        ----------
        position : PyQt6.QtCore.QPoint
            Where to look, in the viewport's coordinates.

        Returns
        -------
        masafi_simtwin.documents.arc.Arc, optional
            The arc, or ``None`` when there is none there.
        """

        for item in self.items(position):
            if isinstance(item, Arc):
                return item
        return None

    def arc_menu(self, arc: Arc | None, at: QPointF | None = None) -> QMenu | None:
        """Build what is offered over an arc.

        Kept apart from showing it, the way :meth:`guide_menu` is, so that what
        is offered can be checked without a menu going up and blocking on its
        own event loop.

        The three shapes are one choice, so they are one exclusive group of
        checkable actions with the arc's own shape already checked: a menu that
        says what a thing *is* is worth more than one that only says what can be
        done to it.  It acts on the arc under the pointer and on no other, even
        when several are selected — a context menu is aimed at a thing.

        A shape that is **led through points** — the S and the L — offers its
        points as well, and which entry it offers is decided by where the menu
        was opened: *Delete Point* over a point, *Add Point* anywhere else along
        the line.  They are one question — *is there a point here?* — so they
        are one place in the menu rather than two entries of which one is always
        dead.  The other two shapes offer neither: choosing a shape that is led
        through points is the step before putting points into it.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc, optional
            The arc under the pointer, if there is one.
        at : PyQt6.QtCore.QPointF, optional
            Where the menu was opened, in scene millimetres, which is where a
            point would go and which point would go.  Half way along the arc
            when it is left out, so that a menu asked for without a position —
            which is what a test does — still offers everything it has.

        Returns
        -------
        PyQt6.QtWidgets.QMenu, optional
            The menu, or ``None`` when the pointer is not over an arc.
        """

        if arc is None:
            return None
        if at is None:
            at = arc.path().pointAtPercent(0.5)

        menu = QMenu(self)
        shapes = QActionGroup(menu)
        shapes.setExclusive(True)
        for shape in ArcShape:
            action = menu.addAction(shape_label(shape))
            action.setCheckable(True)
            action.setChecked(arc.shape_kind is shape)
            action.setData(shape)
            shapes.addAction(action)
            action.triggered.connect(
                lambda checked, chosen=shape, one=arc: self.set_arc_shape(one, chosen)
            )

        if arc.shape_kind.led_through_points:
            menu.addSeparator()
            point = arc.point_at(at)
            if point is None:
                add = menu.addAction(self.tr('Add Point'))
                add.triggered.connect(lambda: self.add_arc_point(arc, at))
            else:
                drop = menu.addAction(self.tr('Delete Point'))
                drop.triggered.connect(lambda: self.remove_arc_point(arc, point))

        self._add_reset_entries(menu, [arc])

        menu.addSeparator()
        delete = menu.addAction(self.tr('Delete Arc'))
        delete.triggered.connect(lambda: self.deletion_asked.emit([arc]))
        return menu

    def set_arc_shape(self, arc: Arc, shape: ArcShape) -> None:
        """Ask for one arc to be drawn straight or curved from now on.

        The sheet does not reshape it.  A change to a net is the document's —
        it is the document that knows how to record one so that it can be
        undone — so this says what was asked for and nothing more.

        Kept as a method rather than written into the menu so that the menu is
        the only thing a test of the menu has to drive.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc
            The arc.
        shape : masafi_simtwin.documents.arc.ArcShape
            Which shape.
        """

        self.arc_shape_asked.emit(arc, shape)

    def add_arc_point(self, arc: Arc, at: QPointF) -> None:
        """Ask for another point to be put into an arc, where the menu was
        opened.

        The document puts it in — see :meth:`set_arc_shape` — and leaves the arc
        in hand afterwards.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc
            The arc.
        at : PyQt6.QtCore.QPointF
            Where it was aimed at, in scene millimetres.
        """

        self.arc_point_asked.emit(arc, at)

    def remove_arc_point(self, arc: Arc, index: int) -> None:
        """Ask for one point of an arc to be taken out again.

        The document takes it out — see :meth:`set_arc_shape` — and leaves the
        arc in hand afterwards.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc
            The arc.
        index : int
            Which of its points, counting from the source.
        """

        self.arc_point_removal_asked.emit(arc, index)

    def work_on(self, arc: Arc) -> None:
        """Leave one arc selected, and nothing else.

        A point is put in to be dragged somewhere, and the handle to drag it by
        is there only while the arc is selected — so putting one in and leaving
        the arc unselected means aiming at the arc twice for one wish.  A right
        click does not select what it is aimed at, and the menu is opened by one,
        so this is where that is put right.

        The rest of the selection is **put down**, which is what a click on the
        arc would have done: what the menu was aimed at is the thing being
        worked on, and *Delete* afterwards should reach that and nothing else.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc
            The arc to leave selected.
        """

        self.scene().clearSelection()
        arc.setSelected(True)

    def item_menu(self, item: NetItem | None) -> QMenu | None:
        """Build what is offered over an item of a net.

        Kept apart from showing it, the way :meth:`arc_menu` and
        :meth:`guide_menu` are, so that what is offered can be checked without a
        menu going up and blocking on its own event loop.

        There is one entry so far and not every item has it: a bar has a way
        round and can be turned, a circle has not — which the item says of
        itself through
        :attr:`~masafi_simtwin.documents.net_item.NetItem.CAN_ROTATE` rather than
        being asked what class it is.  An item with nothing to offer gives no
        menu at all, so the pointer falls through to whatever is under it.

        It acts on the item under the pointer and on no other, even when several
        are selected: a context menu is aimed at a thing, as an arc's is.

        Parameters
        ----------
        item : masafi_simtwin.documents.net_item.NetItem, optional
            The item under the pointer, if there is one.

        Returns
        -------
        PyQt6.QtWidgets.QMenu, optional
            The menu, or ``None`` when there is nothing to offer over it.
        """

        if item is None:
            return None
        given = item.text_style is not None or item.line_style is not None
        if not (item.CAN_ROTATE or given):
            return None

        menu = QMenu(self)
        if item.CAN_ROTATE:
            rotate = menu.addAction(self.tr('Rotate'))
            rotate.triggered.connect(lambda: self.rotate([item]))
        self._add_reset_entries(menu, [item])
        return menu

    def rotate(self, items) -> None:
        """Ask for some items to be turned the other way round.

        The sheet does not turn them — see :meth:`set_arc_shape` for why a
        change to a net is the document's — so this says what was asked for and
        nothing more.

        Parameters
        ----------
        items : list of masafi_simtwin.documents.net_item.NetItem
            The items.
        """

        self.rotation_asked.emit(list(items))

    def reset_text_appearance(self, items) -> None:
        """Ask for the lettering given to some things to be taken back.

        The sheet does not take it back — see :meth:`set_arc_shape` for why a
        change to a net is the document's — so this says what was asked for and
        nothing more.

        Parameters
        ----------
        items : list
            The places, transitions or arcs.
        """

        self.text_reset_asked.emit(list(items))

    def reset_line_appearance(self, items) -> None:
        """Ask for the lines given to some things to be taken back.

        Parameters
        ----------
        items : list
            The places, transitions or arcs.
        """

        self.line_reset_asked.emit(list(items))

    def _add_reset_entries(self, menu: QMenu, items) -> bool:
        """Offer to take back the appearance given to some things.

        Only the half there is something to take back for is offered: an entry
        that would do nothing is worse than no entry, which is the rule this
        menu already keeps by giving no menu at all over an item with nothing
        to offer.  A separator goes in first only when the menu already holds
        something, so a place — which has no *Rotate* — does not open on one.

        Parameters
        ----------
        menu : PyQt6.QtWidgets.QMenu
            What to add them to.
        items : list
            The things the menu was aimed at.

        Returns
        -------
        bool
            Whether anything was added.
        """

        lettered = [item for item in items if item.text_style is not None]
        drawn = [item for item in items if item.line_style is not None]
        if not (lettered or drawn):
            return False

        if menu.actions():
            menu.addSeparator()
        if lettered:
            entry = menu.addAction(self.tr('Reset Text Appearance'))
            entry.triggered.connect(lambda: self.reset_text_appearance(lettered))
        if drawn:
            entry = menu.addAction(self.tr('Reset Line Appearance'))
            entry.triggered.connect(lambda: self.reset_line_appearance(drawn))
        return True

    def guide_menu(self, guide: Guide | None) -> QMenu | None:
        """Build what is offered over a guide, or over the bare sheet.

        Kept apart from showing it so that what is offered can be checked
        without a menu going up and blocking on its own event loop.

        Parameters
        ----------
        guide : masafi_simtwin.documents.guide.Guide, optional
            The guide under the pointer, if there is one.

        Returns
        -------
        PyQt6.QtWidgets.QMenu, optional
            The menu, or ``None`` when there is nothing to offer.
        """

        if guide is None and not self.guides:
            return None

        menu = QMenu(self)
        if guide is not None:
            delete = menu.addAction(self.tr('Delete Guide'))
            delete.triggered.connect(lambda: self.deletion_asked.emit([guide]))
        clear = menu.addAction(self.tr('Delete All Guides'))
        clear.triggered.connect(lambda: self.deletion_asked.emit(list(self.guides)))
        return menu

    # ------------------------------------------------------------------
    # What is dropped on the sheet
    # ------------------------------------------------------------------

    def _dragged_element(self, event) -> tuple[str, str] | None:
        """Read the element a drag carries, and take the drag if it is one.

        The three drag events answer the same question and have to answer it the
        same way, or a drag is welcomed on the way in and refused on the way
        down.

        Parameters
        ----------
        event : PyQt6.QtGui.QDropEvent
            The drag or drop event.

        Returns
        -------
        tuple of str, optional
            The keys of the library and of the element, or ``None`` when the
            drag is not one — in which case the event is left alone for whatever
            else might want it.
        """

        element = element_from_mime(event.mimeData())
        if element is None:
            event.ignore()
            return None
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        return element

    def dragEnterEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Take a drag of an element onto the sheet.

        Parameters
        ----------
        event : PyQt6.QtGui.QDragEnterEvent
            The event.
        """

        if self._dragged_element(event) is None:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Keep taking it while it is over the sheet.

        Parameters
        ----------
        event : PyQt6.QtGui.QDragMoveEvent
            The event.
        """

        if self._dragged_element(event) is None:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Say what was dropped and where, in scene millimetres.

        The position is where the pointer let go, **not snapped**.  What is
        dropped snaps as it lands, by whichever of its own anchors is nearest
        the grid — a place by its rim, a transition by the end of its bar — and
        the sheet cannot know those: it does not know what a place is.
        Rounding the position here first would put the element's centre on the
        grid and leave its anchors nothing to do.

        Parameters
        ----------
        event : PyQt6.QtGui.QDropEvent
            The event.
        """

        element = self._dragged_element(event)
        if element is None:
            super().dropEvent(event)
            return

        position = self.mapToScene(event.position().toPoint())
        self.element_dropped.emit(element[0], element[1], position)

    # ------------------------------------------------------------------
    # Drawing an arc between two items
    # ------------------------------------------------------------------

    @property
    def gesture_in_progress(self) -> bool:
        """bool: Whether a gesture has begun on the sheet and not yet ended.

        A press that may be dragging something, an arc being drawn, an arc's end
        being moved.  What the sheet shows in the middle of one is not a recorded
        change — a dragged item is somewhere the undo stack has not heard of —
        so it is no moment to write the sheet down.
        """

        return (
            self._before_drag is not None
            or self._connecting_from is not None
            or self._moving_end is not None
        )

    @property
    def connecting(self) -> NetItem | None:
        """NetItem, optional: The item an arc is being drawn from, if one is."""

        return self._connecting_from

    @property
    def connection_target(self) -> NetItem | None:
        """NetItem, optional: The item the arc being drawn is aimed at.

        Only an item it may actually be joined to.  Aiming at one it may not be
        joined to is aiming at nothing, which is what makes the refusal visible
        before the button is let go rather than only afterwards.
        """

        return self._connecting_over

    @property
    def new_arc_shape(self) -> ArcShape:
        """ArcShape: The shape the next arc drawn will be.

        Held on the view rather than on the document because the view draws the
        line previewed while an arc is being drawn, and a preview of another arc
        than the one that will be made is worse than none.  The document reads
        it back when the arc lands.
        """

        return self._new_arc_shape

    @new_arc_shape.setter
    def new_arc_shape(self, shape: ArcShape) -> None:
        """Draw the next arc in a shape.

        The preview is drawn again at once, so a shape can be chosen in the
        middle of drawing an arc click by click and seen before it lands.

        Parameters
        ----------
        shape : ArcShape
            The shape.
        """

        self._new_arc_shape = ArcShape(shape)
        self.viewport().update()

    @property
    def new_arc_kind(self) -> ArcKind:
        """ArcKind: The kind the next arc drawn will be.

        It decides what the arc may be aimed at as well as what it is: an
        inhibitor arc runs from a place to a transition, so one drawn out of a
        transition lights up nothing.
        """

        return self._new_arc_kind

    @new_arc_kind.setter
    def new_arc_kind(self, kind: ArcKind) -> None:
        """Make the next arc of a kind.

        An arc being drawn is aimed again, so an item it may no longer be joined
        to puts its connecting points away at once rather than at the next move.

        Parameters
        ----------
        kind : ArcKind
            The kind.
        """

        self._new_arc_kind = ArcKind(kind)
        if self._connecting_from is not None:
            self.aim_at(self.mapFromScene(self._connecting_at))
        self.viewport().update()

    def may_join(self, start: NetItem, end: NetItem) -> bool:
        """Say whether the gesture under way may join two items.

        Both questions have to be answered yes: the items' own — a Petri net is
        bipartite — and the arc's kind, which may run only one way.  Which kind
        that is depends on what the gesture is doing.  Drawing a new arc, it is
        :attr:`new_arc_kind`, from ``start`` to ``end``.  Putting an end of an
        arc somewhere else, it is **that arc's** kind, and the direction is the
        arc's: the gesture runs from the end that stays, so moving a source
        runs it backwards.

        And **no arc of that kind may run that way already** — one arc per
        source, target and kind, see
        :func:`~masafi_simtwin.documents.arc.arc_between`.  An arc being moved
        does not count against itself, so an end can still be put on another
        point of the item it is on.

        Parameters
        ----------
        start : masafi_simtwin.documents.net_item.NetItem
            What the gesture runs from.
        end : masafi_simtwin.documents.net_item.NetItem
            What it would land on.

        Returns
        -------
        bool
            Whether it may land there.
        """

        if start is None or not start.may_connect_to(end):
            return False
        if self._moving_end is not None:
            arc, moving = self._moving_end
            source, target = (end, start) if moving == 'source' else (start, end)
            return (
                arc.kind.permits(source, target)
                and arc_between(source, target, arc.kind, besides=arc) is None
            )
        return (
            self._new_arc_kind.permits(start, end)
            and arc_between(start, end, self._new_arc_kind) is None
        )

    @property
    def laid_points(self) -> list[QPointF]:
        """list: The points laid for the arc being drawn, in scene millimetres,
        in the order they were laid."""

        return [QPointF(point) for point in self._connecting_points]

    def lay_point(self, at: QPointF) -> None:
        """Lay a point for the arc being drawn to be led through.

        This is what a click on the bare sheet does while an arc is being drawn
        click by click: the route is laid out **while the net is in front of the
        person laying it**, round whatever is in the way, rather than drawn
        straight through it and shaped afterwards.  The point is snapped like
        every other position on the sheet.

        Parameters
        ----------
        at : PyQt6.QtCore.QPointF
            Where, in scene millimetres.
        """

        if self._connecting_from is None or self._moving_end is not None:
            return
        self._connecting_points.append(QPointF(self.snap(at.x()), self.snap(at.y())))
        self.viewport().update()

    def take_back_point(self) -> bool:
        """Take back the last point laid for the arc being drawn.

        Returns
        -------
        bool
            Whether there was one to take back.
        """

        if not self._connecting_points:
            return False
        self._connecting_points.pop()
        self.viewport().update()
        return True

    def landing_port(self, target: NetItem, at: QPointF) -> int:
        """Give which connecting point of an item an arc let go there binds to.

        **The one nearest the pointer**, so that the point an arc arrives at is
        chosen the way the point it leaves by is: by aiming at it.  Nearest
        rather than exactly-on, because the pointer is somewhere over the item
        rather than on a point of it, and because on a transition the points are
        a millimetre and a half apart and asking for more precision than that
        would be asking for a fight.

        A point that already has an arc on it is **not** passed over.  Choosing
        one is choosing it, exactly as a press on a busy point is still a press
        on that point; the preview shows where the arc would land, so a person
        who lands two arcs on one point meant to.

        Parameters
        ----------
        target : masafi_simtwin.documents.net_item.NetItem
            What the arc is arriving at.
        at : PyQt6.QtCore.QPointF
            Where the pointer is, in scene millimetres.

        Returns
        -------
        int
            The index of the point.
        """

        return target.port_index_towards(at)

    def connection_endpoint(self) -> QPointF:
        """Give where the arc being drawn currently ends.

        The **exact connecting point it would bind to** while it is aimed at an
        item, and the pointer itself while it is not — so what is drawn is what
        would be made, and the point it will land on can be seen, and changed by
        moving the pointer about the item, before the button is let go.

        Returns
        -------
        PyQt6.QtCore.QPointF
            The end of the line, in scene millimetres.
        """

        target = self._connecting_over
        if self._connecting_from is None or target is None:
            return QPointF(self._connecting_at)
        return target.scene_port(self.landing_port(target, self._connecting_at))

    def aim_at(self, position) -> NetItem | None:
        """Follow the arc being drawn onto whatever it is over.

        The item it is over shows its connecting points, the way the item it
        came from does, so that both ends of the binding can be seen while it is
        being made.  They go again as soon as the arc is taken off it.

        Only an item the arc **may** be joined to lights up: a Petri net is
        bipartite, so a place aimed at a place shows nothing, and an inhibitor
        arc runs from a place to a transition, so one aimed back at a place
        shows nothing either.  That is the refusal made visible while there is
        still time to aim somewhere else.  See :meth:`may_join`.

        Parameters
        ----------
        position : PyQt6.QtCore.QPoint
            Where the pointer is, in the viewport's coordinates.

        Returns
        -------
        masafi_simtwin.documents.net_item.NetItem, optional
            What it is now aimed at, if anything.
        """

        source = self._connecting_from
        found = self.item_at(position) if source is not None else None
        if found is not None and not self.may_join(source, found):
            found = None

        if found is self._connecting_over:
            return found

        if self._connecting_over is not None:
            self._connecting_over.ports_visible = False
        self._connecting_over = found
        if found is not None:
            found.ports_visible = True
        return found

    @property
    def moving_end(self) -> tuple | None:
        """tuple, optional: The arc and the end of it being put somewhere else."""

        return self._moving_end

    def arc_end_at(self, position) -> tuple[Arc, str] | None:
        """Find the end handle of a selected arc under a point of the viewport.

        An end handle sits **on** the connecting point its arc is attached to,
        which is also where a press starts a *new* arc, so this is asked first
        and the two gestures cannot both fire.  Only a selected arc has handles,
        so nothing is in the way until an arc has been chosen.

        Parameters
        ----------
        position : PyQt6.QtCore.QPoint
            Where to look, in the viewport's coordinates.

        Returns
        -------
        tuple, optional
            The arc and which of its ends, or ``None`` when there is no handle
            there.
        """

        where = self.mapToScene(position)
        for item in self.scene().selectedItems():
            if not isinstance(item, Arc):
                continue
            end = item.handle_at(where, END_HANDLES)
            if end is not None:
                return item, end
        return None

    def begin_moving_end(self, arc: Arc, end: str, at: QPointF, pressed_at=None) -> None:
        """Start putting one end of an arc somewhere else.

        It is the gesture that draws an arc, started from an end rather than
        from an item: the arc's **other** end is what the line comes out of and
        stays where it is, and the pointer carries the end being moved.  So the
        whole of the drawing gesture is reused — the aiming, the lighting up of
        what may be joined, the landing point, the giving up — and what is
        different is only what happens when it lands.

        Parameters
        ----------
        arc : masafi_simtwin.documents.arc.Arc
            The arc.
        end : str
            ``source`` or ``target``, whichever is being moved.
        at : PyQt6.QtCore.QPointF
            Where the pointer is, in the scene.
        pressed_at : PyQt6.QtCore.QPointF, optional
            Where the press landed, in the viewport.
        """

        staying = arc.target if end == 'source' else arc.source
        port = arc.target_port if end == 'source' else arc.source_port
        self.begin_connection(staying, port, at, pressed_at)
        self._moving_end = (arc, end)

    def item_at(self, position) -> NetItem | None:
        """Find the item of a net under a point of the viewport.

        **A connecting point counts as part of the item it belongs to**, even
        though half of every one of them is drawn outside its shape: the points
        stand *on* the boundary, so a ring is half in and half out, and an arc
        aimed at the visible half that happens to be outside would find nothing
        there.  That is a miss at the very place a person is told to aim, and it
        is silent — no arc is drawn and nothing says why.

        The reach is :data:`masafi_simtwin.documents.net_item.PORT_GRAB` rather
        than the radius the ring is drawn at, so a point that is drawn small is
        still a point that can be aimed at.

        The shape itself is not widened to include the rings, because what the
        item is *taken hold of* by is its drawn shape: a transition is grabbed by
        its bar.  Reaching for the points is what drawing an arc does, and only
        that.

        Parameters
        ----------
        position : PyQt6.QtCore.QPoint
            Where to look, in the viewport's coordinates.

        Returns
        -------
        masafi_simtwin.documents.net_item.NetItem, optional
            The item, or ``None`` when there is none there.
        """

        for item in self.items(position):
            if isinstance(item, NetItem):
                return item

        where = self.mapToScene(position)
        near = QRectF(
            where.x() - PORT_GRAB,
            where.y() - PORT_GRAB,
            PORT_GRAB * 2.0,
            PORT_GRAB * 2.0,
        )
        for item in self.scene().items(near):
            if isinstance(item, NetItem) and item.port_index_at(where) is not None:
                return item
        return None

    def port_pressed(self, position) -> tuple[NetItem, int] | None:
        """Find the item and the connecting point under a point of the viewport.

        A press on a connecting point starts an arc; a press anywhere else on
        the same item moves it.  That is the whole of what tells the two apart,
        and it is why the points are worth having.  *Which* point was pressed
        matters as well, because it is the one the arc will leave by for good.

        Parameters
        ----------
        position : PyQt6.QtCore.QPoint
            Where the press landed, in the viewport's coordinates.

        Returns
        -------
        tuple, optional
            The item and the index of its connecting point, or ``None`` when the
            press was not on one.
        """

        item = self.item_at(position)
        if item is None:
            return None
        index = item.port_index_at(self.mapToScene(position))
        return None if index is None else (item, index)

    def begin_connection(
        self, item: NetItem, port: int, at: QPointF, pressed_at=None
    ) -> None:
        """Start drawing an arc out of one connecting point of an item.

        Parameters
        ----------
        item : masafi_simtwin.documents.net_item.NetItem
            What the arc is being drawn from.
        port : int
            Which of its connecting points was pressed.  The arc will leave by
            that one and no other, so the line being dragged is drawn from it
            rather than from wherever happens to face the pointer.
        at : PyQt6.QtCore.QPointF
            Where the pointer is, in the scene.
        pressed_at : PyQt6.QtCore.QPointF, optional
            Where the press landed, in the viewport.  It is kept so that letting
            go can tell a drag from a click: a drag that lands on nothing is a
            drag that missed and is given up, while a click leaves the arc being
            drawn with the button up, which is what makes the second half of a
            click-click possible.
        """

        self._connecting_from = item
        self._connecting_port = int(port)
        self._connecting_at = QPointF(at)
        self._connecting_pressed_at = None if pressed_at is None else QPointF(pressed_at)
        item.ports_visible = True
        self.viewport().update()

    def abandon_connection(self) -> None:
        """Give up the arc being drawn, leaving nothing behind.

        Both ends put their connecting points away — the one the arc came from
        and the one it was aimed at — because neither is being pointed at any
        more, whether the arc landed or was given up.  The pointer's next move
        goes to the scene again, so an item it is still over lights up by
        hovering the way it would have anyway.
        """

        for item in (self._connecting_from, self._connecting_over):
            if item is not None:
                item.ports_visible = False
        self._connecting_from = None
        self._connecting_over = None
        self._connecting_pressed_at = None
        self._connecting_points = []
        self._moving_end = None
        self.viewport().update()

    def finish_connection(self, position) -> bool:
        """Land the arc being drawn, if it lands on something it may join.

        Parameters
        ----------
        position : PyQt6.QtCore.QPoint
            Where the pointer is, in the viewport's coordinates.

        Returns
        -------
        bool
            Whether an arc was drawn.  It was not if the pointer is over nothing,
            over the item the arc came from, or over one this one may not be
            joined to — a Petri net is bipartite, an inhibitor arc runs one way
            only, and a refusal is silent because the arc simply is not there.

        Notes
        -----
        The point it arrives at is :meth:`landing_port` of wherever the pointer
        is, which is the point the preview has been ending on, so an arc lands
        where it was seen to be going.

        An end being *moved* lands the same way and by the same rules, and
        :meth:`~masafi_simtwin.documents.arc.Arc.reattach` puts it there instead
        of a new arc being made.  Nothing is emitted for it: the document is not
        told, because no arc has come or gone.
        """

        source = self._connecting_from
        target = self.item_at(position)
        if source is None or target is None or not self.may_join(source, target):
            return False

        leaving = self._connecting_port
        arriving = self.landing_port(target, self.mapToScene(position))
        moving = self._moving_end
        points = self.laid_points
        self.abandon_connection()

        if moving is not None:
            arc, end = moving
            self.arc_end_asked.emit(arc, end, target, arriving)
            return True

        self.connection_drawn.emit(source, target, leaving, arriving, points)
        return True

    def preview_route(self) -> tuple | None:
        """Give the arc the gesture under way would make if it landed now.

        **The arc itself, not a line near it**: its shape, the points laid for
        it and the mark it ends in, so that what a person sees while aiming is
        what they will get — which is the whole point of choosing the shape
        before the arc is drawn rather than after.  Two cases:

        * **drawing a new arc**, it is an untouched arc of :attr:`new_arc_shape`
          led through the points laid so far — :attr:`ArcShape.routed`, once
          there are any, which is what the document makes of them;
        * **moving an end**, it is the arc being moved, with its own shape and
          its own points kept in its own chord's frame, along the chord it would
          have — the gesture runs from the end that stays, so moving a source
          turns the chord the arc's way round again.

        Returns
        -------
        tuple, optional
            The chord, the segments along it and the kind of arc, or ``None``
            while no arc is being drawn.
        """

        source = self._connecting_from
        if source is None:
            return None

        here = source.scene_port(self._connecting_port)
        there = self.connection_endpoint()
        if self._moving_end is not None:
            arc, end = self._moving_end
            line = QLineF(there, here) if end == 'source' else QLineF(here, there)
            controls = [chord_point(line, *frame) for frame in arc.control_frames]
            points = [chord_point(line, *frame) for frame in arc.point_frames]
            return line, route_segments(line, arc.shape_kind, controls, points), arc.kind

        line = QLineF(here, there)
        shape = self._new_arc_shape
        if self._connecting_points:
            shape = shape.routed
        return line, untouched_segments(line, shape, self._connecting_points), self._new_arc_kind

    def _draw_connection(self, painter) -> None:
        """Draw the arc being dragged, from its point to the pointer.

        It runs from the point that was pressed to the point it would bind to,
        and it is drawn in the shape it will have, ending in the mark it will
        end in — see :meth:`preview_route` — so the preview is the arc that
        would be made rather than something near it.  Where it is over nothing
        it follows the pointer instead, there being no point to end on yet.

        The line is **dashed** and the mark at its end is not: the line says
        *not made yet*, and a dashed arrowhead two millimetres long is a smudge.
        The points laid for it are drawn the way an arc's handles are, a square
        of the accent around the colour of the paper, because once the arc is
        made that is exactly what they will be.

        It is drawn in the view's foreground rather than as an item, because it
        is not one: nothing is on the sheet until the arc lands, and a preview
        that had to be added and removed is a preview that can be left behind.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the view.
        """

        route = self.preview_route()
        if route is None:
            return

        line, segments, kind = route
        path = route_path(line, segments)
        colour = self.palette().color(QPalette.ColorRole.Link)
        paper = self.palette().color(QPalette.ColorRole.Base)

        painter.save()
        pen = QPen(colour, 0)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.setPen(QPen(colour, 0))
        if kind is ArcKind.INHIBITOR:
            painter.setBrush(paper)
            painter.drawEllipse(
                ring_centre(line, path, bool(segments)), INHIBITOR_RADIUS, INHIBITOR_RADIUS
            )
        else:
            painter.setBrush(colour)
            painter.drawPath(arrowhead(line, path, bool(segments)))

        painter.setBrush(paper)
        half = HANDLE_SIZE / 2.0
        for point in self._connecting_points:
            painter.drawRect(QRectF(point.x() - half, point.y() - half, HANDLE_SIZE, HANDLE_SIZE))
        painter.restore()

    # ------------------------------------------------------------------
    # Panning, and where the pointer is
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Start panning on the middle button, draw an arc from a connecting
        point, and select with the rest.

        The middle button is the one free of meaning once the left one draws and
        selects, and panning with it is what every canvas of this kind does.

        A press on the end handle of a **selected arc** takes that end off and
        carries it, which is asked before anything else because such a handle
        sits on the connecting point a press would otherwise start a new arc
        from.  Otherwise a press on a connecting point starts an arc; a press
        anywhere else on the same item is left to the scene, which moves it.  A
        press while an arc is already being drawn is the second click of a
        **click-click**: an
        arc can be drawn by holding the button down and dragging, or by clicking
        once at each end — which is the one that works when the two items are
        far enough apart that the sheet has to be scrolled between them.  What
        such a press does is :meth:`_press_while_connecting`.

        A press of the right button while an arc is being drawn is kept from
        the scene, which would otherwise put the selection down under it: the
        context menu that follows it is what gives the arc up.

        Parameters
        ----------
        event : PyQt6.QtGui.QMouseEvent
            The mouse event.
        """

        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning_from = event.position()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.RightButton and self._connecting_from is not None:
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._remember_before_a_drag()
            spot = event.position().toPoint()
            if self._connecting_from is not None:
                self._press_while_connecting(spot, event.position())
                event.accept()
                return
            moving = self.arc_end_at(spot)
            if moving is not None:
                arc, end = moving
                self.begin_moving_end(
                    arc, end, self.mapToScene(spot), event.position()
                )
                event.accept()
                return

            pressed = self.port_pressed(spot)
            if pressed is not None:
                item, port = pressed
                self.begin_connection(item, port, self.mapToScene(spot), event.position())
                event.accept()
                return

        super().mousePressEvent(event)

    def _press_while_connecting(self, spot, position) -> None:
        """Land the arc being drawn, lay a point for it, or leave it be.

        Three answers, by what is under the press:

        * **an item it may join** — the arc lands there;
        * **the bare sheet** — a point is laid for the arc to be led through,
          and the arc goes on being drawn.  That is what lets a route be laid
          out round the net while it is being drawn, and it is why a click on
          nothing no longer gives an arc up: *Escape* and the right button do;
        * **an item it may not join** — nothing.  A route of a dozen points is
          not thrown away because the last click fell on the wrong place, and
          the item not lighting up has already said it would be refused.

        Moving an end has no route to lay — an arc keeps its own points — so
        there a press anywhere but on an item the end may go to gives the move
        up, as it always did.

        Parameters
        ----------
        spot : PyQt6.QtCore.QPoint
            Where the press landed, in the viewport's coordinates.
        position : PyQt6.QtCore.QPointF
            The same, as the event gave it, which is kept so the release can
            tell a click from a drag.
        """

        if self.finish_connection(spot):
            return
        if self._moving_end is not None:
            self.abandon_connection()
            return
        if self.item_at(spot) is None:
            self.lay_point(self.mapToScene(spot))
            self._connecting_pressed_at = QPointF(position)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Drag the sheet while the middle button is down, and say where the
        pointer is the rest of the time.

        Parameters
        ----------
        event : PyQt6.QtGui.QMouseEvent
            The mouse event.
        """

        if self._panning_from is not None:
            movement = event.position() - self._panning_from
            self._panning_from = event.position()
            horizontal = self.horizontalScrollBar()
            vertical = self.verticalScrollBar()
            horizontal.setValue(horizontal.value() - int(movement.x()))
            vertical.setValue(vertical.value() - int(movement.y()))
            event.accept()
            return

        where = self.mapToScene(event.position().toPoint())
        self.pointer_moved.emit(where)
        if self._connecting_from is not None:
            self._connecting_at = where
            self.aim_at(event.position().toPoint())
            self.viewport().update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Stop panning when the middle button comes back up, and land an arc
        that was dragged onto something.

        A click — a press and a release in one place — leaves the arc being
        drawn with the button up, which is what makes a click-click and what
        lets the sheet be scrolled between the two ends.  A **drag** let go on
        nothing it may land on gives the arc up, a drag that missed being a drag
        that missed — unless points have already been laid for it, when it goes
        on being drawn: a route is not thrown away by a slip of the hand.
        *Escape* and the right button are what give one up.

        Parameters
        ----------
        event : PyQt6.QtGui.QMouseEvent
            The mouse event.
        """

        if event.button() == Qt.MouseButton.MiddleButton and self._panning_from is not None:
            self._panning_from = None
            self.viewport().unsetCursor()
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self._connecting_from is not None:
            if not self._dragged_since_press(event.position()):
                self._connecting_pressed_at = None
            elif not self.finish_connection(event.position().toPoint()):
                if self._connecting_points:
                    self._connecting_pressed_at = None
                else:
                    self.abandon_connection()
            event.accept()
            return

        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self._report_a_drag()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Say what was double-clicked, so that the document can open it.

        Parameters
        ----------
        event : PyQt6.QtGui.QMouseEvent
            The mouse event.
        """

        if event.button() == Qt.MouseButton.LeftButton:
            found = self.items(event.position().toPoint())
            self.item_activated.emit(found[0] if found else None)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _remember_before_a_drag(self) -> None:
        """Note where everything is, before a press that may drag something.

        Qt moves an item, a guide or a shaping handle as the pointer moves, so
        what a drag *did* can only be told by having looked before it.  The
        whole sheet is noted rather than only what is selected: a press selects
        what it lands on, so what is about to move is not yet known.
        """

        self._before_drag = {
            'items': {
                item: (item.pos().x(), item.pos().y())
                for item in self.scene().items()
                if isinstance(item, NetItem)
            },
            'guides': {guide: guide.position for guide in self.guides},
            'labels': {
                owner: owner.label_offset
                for owner in self.scene().items()
                if isinstance(owner, (NetItem, Arc))
            },
            'widths': {
                item: item.label_width
                for item in self.scene().items()
                if isinstance(item, NetItem)
            },
            'arcs': {
                arc: (arc.control_frames, arc.point_frames)
                for arc in self.scene().items()
                if isinstance(arc, Arc)
            },
        }
        for owner in self._before_drag['labels']:
            owner.label.dragged = False

    def _report_a_drag(self) -> None:
        """Say what a drag moved or shaped, once the button is up.

        Nothing is said when nothing moved, so a plain click on an item — which
        selects it and moves it nowhere — is not a change to be undone.
        """

        before = self._before_drag
        self._before_drag = None
        if before is None:
            return

        moved = [
            (item, was, (item.pos().x(), item.pos().y()))
            for item, was in before['items'].items()
            if item.scene() is self.scene() and was != (item.pos().x(), item.pos().y())
        ]
        if moved:
            self.items_moved.emit(moved)

        guides = [
            (guide, was, guide.position)
            for guide, was in before['guides'].items()
            if guide.scene() is self.scene() and was != guide.position
        ]
        if guides:
            self.guides_moved.emit(guides)

        resized = [
            (item, width, item.label_width)
            for item, width in before['widths'].items()
            if item.scene() is self.scene() and width != item.label_width
        ]
        labels = []
        for owner, was in before['labels'].items():
            if owner.scene() is not self.scene() or not owner.label.dragged:
                continue
            owner.label.dragged = False
            now = owner.label_offset_at(owner.label.pos())
            if now != was:
                labels.append((owner, was, now))
        if labels:
            self.labels_moved.emit(labels)
        if resized:
            self.labels_resized.emit(resized)

        shaped = [
            (arc, was[0], was[1], arc.control_frames, arc.point_frames)
            for arc, was in before['arcs'].items()
            if arc.scene() is self.scene()
            and was != (arc.control_frames, arc.point_frames)
        ]
        if shaped:
            self.arcs_shaped.emit(shaped)

    def _dragged_since_press(self, position) -> bool:
        """Say whether the pointer has moved far enough to count as a drag.

        The two halves of the gesture part here.  A press, a drag and a release
        is one motion and ends the arc where it was let go, on something or on
        nothing.  A press and a release in the same place is a *click*, and
        leaves the arc being drawn with the button up so that the sheet can be
        scrolled before the second click — which is the only way to join two
        items further apart than the window is wide.

        Qt's own ``startDragDistance`` is what draws the line, because it is the
        distance the desktop has already decided separates a click from a drag.

        Parameters
        ----------
        position : PyQt6.QtCore.QPointF
            Where the pointer is now, in the viewport.

        Returns
        -------
        bool
            Whether it has moved that far since the press.
        """

        pressed = self._connecting_pressed_at
        if pressed is None:
            return True

        moved = position - pressed
        reach = QApplication.startDragDistance()
        return moved.x() ** 2 + moved.y() ** 2 > reach * reach

    def leaveEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Take the pointer's mark off the rulers when it leaves the sheet.

        Parameters
        ----------
        event : PyQt6.QtCore.QEvent
            The leave event.
        """

        self.pointer_left.emit()
        super().leaveEvent(event)

    # ------------------------------------------------------------------
    # What the rulers listen to
    # ------------------------------------------------------------------

    def scrollContentsBy(self, dx: int, dy: int) -> None:  # noqa: N802  (Qt naming)
        """Report every scroll of the viewport, whatever caused it.

        Parameters
        ----------
        dx : int
            How far the contents moved horizontally.
        dy : int
            How far they moved vertically.
        """

        super().scrollContentsBy(dx, dy)
        self.view_changed.emit()

    def resizeEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Report a resize, which moves the scene under the viewport.

        Parameters
        ----------
        event : PyQt6.QtGui.QResizeEvent
            The resize event.
        """

        super().resizeEvent(event)
        self.view_changed.emit()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def drawBackground(self, painter, rect) -> None:  # noqa: N802  (Qt naming)
        """Fill the ground and rule the grid over it.

        The grid is in millimetres like everything else on the sheet: a square
        of :data:`GRID_STEP` with a heavier line every :data:`GRID_MAJOR` of
        them.  The squares are dropped once they come closer than
        :data:`MIN_GRID_PIXELS`, leaving the heavier lines to say which way is
        which.

        Everything here is drawn across the whole of ``rect`` and in the
        coordinates it is given.  A view repaints only the part of the scene
        that has changed — after a scroll, a strip a couple of millimetres deep
        with fractional edges — so a grid drawn to rounded edges comes out in
        dashes as soon as anything moves.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the view.
        rect : PyQt6.QtCore.QRectF
            The part of the scene that needs painting.
        """

        painter.fillRect(rect, self.palette().color(QPalette.ColorRole.Base))

        text = self.palette().color(QPalette.ColorRole.Text)
        minor = QColor(text)
        minor.setAlpha(GRID_MINOR_ALPHA)
        major = QColor(text)
        major.setAlpha(GRID_MAJOR_ALPHA)
        heavy = GRID_MAJOR * GRID_STEP

        spacings = [(QPen(major, 0), heavy)]
        if GRID_STEP * self.zoom * PIXELS_PER_MM >= MIN_GRID_PIXELS:
            spacings.insert(0, (QPen(minor, 0), GRID_STEP))

        for pen, spacing in spacings:
            painter.setPen(pen)
            for x in _multiples_of(spacing, rect.left(), rect.right()):
                if spacing == GRID_STEP and x % heavy == 0:
                    continue
                painter.drawLine(QLineF(x, rect.top(), x, rect.bottom()))
            for y in _multiples_of(spacing, rect.top(), rect.bottom()):
                if spacing == GRID_STEP and y % heavy == 0:
                    continue
                painter.drawLine(QLineF(rect.left(), y, rect.right(), y))

        self._draw_pages(painter, rect, major)

    def _draw_pages(self, painter, rect, colour: QColor) -> None:
        """Rule the sheet into pages, so that every one of them can be seen.

        The lines fall every page from the origin, dashed, in the
        colour of the grid's own heavier lines: they are a thing to measure
        against rather than a thing on the sheet, so they belong to the paper
        and not to the drawing.  They are drawn at every zoom — the squares of
        the grid are dropped when they crowd, but where a page ends is worth
        knowing however far away the sheet is held.

        They are held to the sheet rather than to the exposed rectangle: the
        sheet is a whole number of pages, and a page line beyond its edge would
        be the edge of a page that does not exist.

        The pen is width nought, Qt's cosmetic hairline, so the dashes are the
        same length on the screen at any zoom rather than growing with it.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the view.
        rect : PyQt6.QtCore.QRectF
            The part of the scene that needs painting.
        colour : PyQt6.QtGui.QColor
            The colour of the grid's heavier lines.
        """

        area = rect.intersected(self.sceneRect())
        if area.isEmpty():
            return

        pen = QPen(colour, 0)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)

        for x in _multiples_of(self._page.width(), area.left(), area.right()):
            painter.drawLine(QLineF(x, area.top(), x, area.bottom()))
        for y in _multiples_of(self._page.height(), area.top(), area.bottom()):
            painter.drawLine(QLineF(area.left(), y, area.right(), y))

    def drawForeground(self, painter, rect) -> None:  # noqa: N802  (Qt naming)
        """Say what an empty sheet is for, while it is empty.

        The note is drawn in the viewport rather than in the scene, so that it
        stays where it is when the sheet is zoomed or scrolled, and it goes of
        its own accord as soon as there is a first item to look at.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the view.
        rect : PyQt6.QtCore.QRectF
            The part of the scene that needs painting.
        """

        super().drawForeground(painter, rect)
        self._draw_connection(painter)
        if not self.empty_note or self.scene() is None or self.has_content():
            return

        painter.save()
        painter.resetTransform()
        painter.setPen(self.palette().color(QPalette.ColorRole.PlaceholderText))
        painter.drawText(
            self.viewport().rect(),
            int(Qt.AlignmentFlag.AlignCenter),
            self.empty_note,
        )
        painter.restore()

    def changeEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Repaint the sheet when the theme changes under it.

        The grid and the ground are painted from the palette, and a painted
        widget is not restyled by a new stylesheet the way a styled one is.

        Parameters
        ----------
        event : PyQt6.QtCore.QEvent
            The event that changed the widget.
        """

        super().changeEvent(event)
        if event.type() == event.Type.PaletteChange:
            self.viewport().update()


class Canvas(QWidget):
    """A sheet with its rulers: the view, the two rulers and the corner box.

    Parameters
    ----------
    unit : masafi_simtwin.documents.ruler.RulerUnit, optional
        What the rulers count in, millimetres by default.
    page : PyQt6.QtCore.QSizeF, optional
        The page the sheet is ruled into.  The preferences answer when it is
        omitted.
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.

    Attributes
    ----------
    view : CanvasView
        The view of the sheet.
    horizontal_ruler : masafi_simtwin.documents.ruler.Ruler
        The ruler along the top.
    vertical_ruler : masafi_simtwin.documents.ruler.Ruler
        The ruler down the left.
    corner : masafi_simtwin.documents.ruler.RulerCorner
        The box where the two meet, which says what they count in.

    Notes
    -----
    A guide dragged off a ruler and kept is reported to
    :meth:`Canvas.guide_drawn`, which a document overrides to record it — the
    sheet makes the guide, and what a change to the drawing *is* belongs to the
    document.

    A guide is made by pressing on a ruler and dragging onto the sheet.  The
    canvas makes it on the press and moves it with the pointer, so that what is
    being dragged is the guide itself rather than a preview of one; letting go
    without leaving the ruler is a click on a ruler and leaves nothing behind.

    A document may put **tool bars** along the top, above the rulers, with
    :meth:`add_tool_bar`.  The sheet is shared by every drawn document and what
    each draws *with* is not, so the canvas has a place for a bar and the
    document says what goes in it.
    """

    def __init__(
        self,
        unit: RulerUnit = MILLIMETRES,
        page: QSizeF | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName('Canvas')

        self.view = CanvasView(page, self)
        self.horizontal_ruler = Ruler(Qt.Orientation.Horizontal, self.view, unit, self)
        self.vertical_ruler = Ruler(Qt.Orientation.Vertical, self.view, unit, self)
        self.corner = RulerCorner(unit, self)

        self._stack = QVBoxLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._stack.setSpacing(0)

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.corner, 0, 0)
        layout.addWidget(self.horizontal_ruler, 0, 1)
        layout.addWidget(self.vertical_ruler, 1, 0)
        layout.addWidget(self.view, 1, 1)
        self._stack.addLayout(layout)

        self._new_guide: Guide | None = None

        self.view.view_changed.connect(self._redraw_rulers)
        self.view.pointer_moved.connect(self._on_pointer_moved)
        self.view.pointer_left.connect(lambda: self._on_pointer_moved(None))
        for ruler in self.rulers:
            ruler.guide_dragged.connect(
                lambda position, source=ruler: self._on_guide_dragged(source, position)
            )
            ruler.guide_dropped.connect(self._on_guide_dropped)

    # ------------------------------------------------------------------
    # What the sheet holds, and how it is looked at
    # ------------------------------------------------------------------

    def scene(self) -> QGraphicsScene:
        """Give the scene the sheet's items live on.

        Returns
        -------
        PyQt6.QtWidgets.QGraphicsScene
            The scene.
        """

        return self.view.scene()

    @property
    def page(self) -> QSizeF:
        """PyQt6.QtCore.QSizeF: The page the sheet is ruled into, in millimetres."""

        return self.view.page

    def set_page(self, page: QSizeF) -> None:
        """Rule the sheet into a page of a different size.

        Parameters
        ----------
        page : PyQt6.QtCore.QSizeF
            The page, in millimetres, the way round it is used.
        """

        self.view.set_page(page)

    @property
    def grid_step(self) -> float:
        """float: How far apart the points a drawing lands on are, in millimetres."""

        return self.view.grid_step

    def set_grid_step(self, step: float) -> None:
        """Snap to points a different distance apart from now on.

        Parameters
        ----------
        step : float
            The distance, in millimetres.
        """

        self.view.set_grid_step(step)

    @property
    def zoom(self) -> float:
        """float: The scale the sheet is drawn at, ``1.0`` being life size."""

        return self.view.zoom

    def zoom_in(self) -> None:
        """Take the sheet one step closer."""

        self.view.zoom_in()

    def zoom_out(self) -> None:
        """Take the sheet one step further away."""

        self.view.zoom_out()

    def reset_zoom(self) -> None:
        """Put the sheet back to life size."""

        self.view.reset_zoom()

    def add_tool_bar(self, bar: QWidget) -> None:
        """Put a tool bar along the top of the sheet, above the rulers.

        Parameters
        ----------
        bar : PyQt6.QtWidgets.QWidget
            The bar.  Bars are stacked in the order they are added, the first
            at the top.
        """

        self._stack.insertWidget(self._stack.count() - 1, bar)

    @property
    def rulers(self) -> tuple[Ruler, Ruler]:
        """tuple: The two rulers, the top one first."""

        return self.horizontal_ruler, self.vertical_ruler

    def restyle(self) -> None:
        """Letter the sheet again, in whatever the defaults are now.

        A caption is **laid out** rather than merely painted: it is wrapped to a
        width, and the box is as tall as the lines that makes.  So a repaint
        alone would leave every box the size the old defaults gave it, with the
        text drawn at the new size inside the old box.  Everything on the sheet
        that letters itself is asked to do it again, and then the sheet is
        painted.

        The sheet knows nothing of places or arcs here on purpose: it asks for
        what it wants — *say what you are called again* — of whatever can answer,
        the way it asks a guide nothing and a node everything.
        """

        scene = self.scene()
        if scene is None:  # pragma: no cover - a canvas always has a scene
            return
        for item in scene.items():
            drawn = getattr(item, 'restyle', None)
            if callable(drawn):
                drawn()
        scene.update()

    # ------------------------------------------------------------------
    # Guides
    # ------------------------------------------------------------------

    @property
    def guides(self) -> list[Guide]:
        """list: The guides on the sheet, across it first and then up it."""

        return self.view.guides

    def add_guide(
        self, orientation: Qt.Orientation, position: float, exact: bool = False
    ) -> Guide:
        """Put a guide on the sheet.

        Parameters
        ----------
        orientation : PyQt6.QtCore.Qt.Orientation
            ``Horizontal`` for one lying across the sheet, ``Vertical`` for one
            standing up it.
        position : float
            Where it goes, in scene millimetres.
        exact : bool, optional
            Whether it goes exactly there rather than snapped, being a record of
            where a guide was.

        Returns
        -------
        masafi_simtwin.documents.guide.Guide
            The guide.
        """

        return self.view.add_guide(orientation, position, exact)

    def clear_guides(self) -> None:
        """Take every guide off the sheet."""

        self.view.clear_guides()

    @property
    def gesture_in_progress(self) -> bool:
        """bool: Whether a gesture has begun and not yet ended — one on the sheet,
        or a guide being pulled off a ruler, which the view never sees."""

        return self.view.gesture_in_progress or self._new_guide is not None

    def _on_guide_dragged(self, ruler: Ruler, position: QPointF) -> None:
        """Make or move the guide being pulled out of a ruler.

        Pressing on a ruler puts down whatever was selected before, the way
        pressing on the bare sheet does.  The scene does that itself for a press
        it sees, but it never sees this one: the ruler holds the mouse for the
        whole of the drag, so a guide selected earlier would otherwise still be
        drawn dashed beside the one being dragged out.

        Parameters
        ----------
        ruler : masafi_simtwin.documents.ruler.Ruler
            The ruler it is coming out of, which is what decides which way the
            guide lies: one out of the top ruler lies across the sheet.
        position : PyQt6.QtCore.QPointF
            Where the pointer is, in the scene.
        """

        along = position.y() if ruler.horizontal else position.x()
        if self._new_guide is None:
            self.scene().clearSelection()
            self._new_guide = self.add_guide(ruler.orientation, along)
        else:
            self._new_guide.position = along
        self._on_pointer_moved(position)

    def _on_guide_dropped(self, over_sheet: bool) -> None:
        """Keep the guide that was being dragged, or take it back.

        Parameters
        ----------
        over_sheet : bool
            Whether the pointer was let go over the sheet rather than back on
            the ruler the guide came from.
        """

        if self._new_guide is not None and not over_sheet:
            self.view.remove_guide(self._new_guide)
        elif self._new_guide is not None:
            self.guide_drawn(self._new_guide)
        self._new_guide = None

    def guide_drawn(self, guide: Guide) -> None:
        """Say that a guide has just been pulled off a ruler and kept.

        Nothing here: a bare sheet has nowhere to record it.  A document
        overrides this to put the guide on its undo stack.

        Parameters
        ----------
        guide : masafi_simtwin.documents.guide.Guide
            The guide, already on the sheet.
        """

    # ------------------------------------------------------------------
    # Keeping the rulers on the sheet
    # ------------------------------------------------------------------

    def _redraw_rulers(self) -> None:
        """Draw both rulers again, the sheet having moved under them."""

        for ruler in self.rulers:
            ruler.update()

    def _on_pointer_moved(self, position: QPointF | None) -> None:
        """Move the pointer's mark on both rulers.

        Parameters
        ----------
        position : PyQt6.QtCore.QPointF, optional
            Where the pointer is in the scene, or ``None`` once it has left.
        """

        for ruler in self.rulers:
            ruler.set_pointer(position)
