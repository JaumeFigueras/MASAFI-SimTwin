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
they go — always to the millimetre, and to the millimetre at every zoom.  A snap
that changed with the zoom would mean the same drag put a guide in a different
place depending on how close the sheet happened to be, which is the one thing a
guide is there not to do.  Everything that snaps on the sheet goes through
:meth:`CanvasView.snap`.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QLineF, QPointF, QRectF, QSizeF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPalette, QPen
from PyQt6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QMenu,
    QWidget,
)

from masafi_simtwin import preferences
from masafi_simtwin.documents.guide import Guide
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

#: What a position is snapped to, in millimetres.  It does not follow the zoom:
#: the sheet is in millimetres, so a millimetre is where things go, whether or
#: not one can be told apart on the screen at the time.
SNAP_STEP = 1.0


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
        the Libraries pane, and the snapped scene position it was let go over.
        The view takes the drop and says so; what an element *becomes* is the
        document's to decide, a canvas being the sheet rather than the drawing
        on it.
    """

    view_changed = pyqtSignal()
    pointer_moved = pyqtSignal(QPointF)
    pointer_left = pyqtSignal()
    element_dropped = pyqtSignal(str, str, QPointF)

    def __init__(self, page: QSizeF | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('CanvasView')
        self.empty_note = ''
        self._page = QSizeF(page) if page is not None else preferences.page()

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

    def snap(self, value: float) -> float:
        """Round a scene coordinate to the millimetre.

        The zoom has nothing to do with it.  A guide dropped at the same place
        lands on the same millimetre whether the sheet was close to or far from
        the eye when it was dropped.

        Parameters
        ----------
        value : float
            A coordinate in scene millimetres.

        Returns
        -------
        float
            The nearest multiple of :data:`SNAP_STEP`.
        """

        return round(value / SNAP_STEP) * SNAP_STEP

    # ------------------------------------------------------------------
    # Guides
    # ------------------------------------------------------------------

    @property
    def guides(self) -> list[Guide]:
        """list: The guides on the sheet, across it first and then up it."""

        found = [item for item in self.scene().items() if isinstance(item, Guide)]
        return sorted(found, key=lambda guide: (guide.orientation.value, guide.position))

    def add_guide(self, orientation: Qt.Orientation, position: float) -> Guide:
        """Put a guide on the sheet.

        Parameters
        ----------
        orientation : PyQt6.QtCore.Qt.Orientation
            ``Horizontal`` for one lying across the sheet, ``Vertical`` for one
            standing up it.
        position : float
            Where it goes, in scene millimetres.  It is snapped like any other
            move of a guide.

        Returns
        -------
        masafi_simtwin.documents.guide.Guide
            The guide, already on the scene.
        """

        guide = Guide(orientation, position, self.sceneRect(), self.snap)
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

    def delete_selected_guides(self) -> int:
        """Remove the guides that are selected.

        Returns
        -------
        int
            How many there were, so that a caller can say whether anything
            happened.
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
        """Delete what is selected on *Delete* or *Backspace*.

        Parameters
        ----------
        event : PyQt6.QtGui.QKeyEvent
            The key event.
        """

        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.delete_selected_guides():
                event.accept()
                return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Offer to delete the guide under the pointer, or all of them.

        A guide has no entry in the menu bar to be deleted from, so this is
        where deleting one is found; when the *Edit* menu grows a *Delete* it
        should come here rather than repeat this.

        Parameters
        ----------
        event : PyQt6.QtGui.QContextMenuEvent
            The context menu event.
        """

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
            delete.triggered.connect(lambda: self.remove_guide(guide))
        clear = menu.addAction(self.tr('Delete All Guides'))
        clear.triggered.connect(self.clear_guides)
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

        The position is snapped like every other position on the sheet, so an
        element dropped by hand lands on the same millimetre grid the guides do
        and can be moved off it afterwards no more freely than it was put there.

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
        self.element_dropped.emit(
            element[0],
            element[1],
            QPointF(self.snap(position.x()), self.snap(position.y())),
        )

    # ------------------------------------------------------------------
    # Panning, and where the pointer is
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Start panning on the middle button, and select with the rest.

        The middle button is the one free of meaning once the left one draws and
        selects, and panning with it is what every canvas of this kind does.

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
        super().mousePressEvent(event)

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

        self.pointer_moved.emit(self.mapToScene(event.position().toPoint()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Stop panning when the middle button comes back up.

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
        super().mouseReleaseEvent(event)

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
    A guide is made by pressing on a ruler and dragging onto the sheet.  The
    canvas makes it on the press and moves it with the pointer, so that what is
    being dragged is the guide itself rather than a preview of one; letting go
    without leaving the ruler is a click on a ruler and leaves nothing behind.
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

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.corner, 0, 0)
        layout.addWidget(self.horizontal_ruler, 0, 1)
        layout.addWidget(self.vertical_ruler, 1, 0)
        layout.addWidget(self.view, 1, 1)

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

    @property
    def rulers(self) -> tuple[Ruler, Ruler]:
        """tuple: The two rulers, the top one first."""

        return self.horizontal_ruler, self.vertical_ruler

    # ------------------------------------------------------------------
    # Guides
    # ------------------------------------------------------------------

    @property
    def guides(self) -> list[Guide]:
        """list: The guides on the sheet, across it first and then up it."""

        return self.view.guides

    def add_guide(self, orientation: Qt.Orientation, position: float) -> Guide:
        """Put a guide on the sheet.

        Parameters
        ----------
        orientation : PyQt6.QtCore.Qt.Orientation
            ``Horizontal`` for one lying across the sheet, ``Vertical`` for one
            standing up it.
        position : float
            Where it goes, in scene millimetres.

        Returns
        -------
        masafi_simtwin.documents.guide.Guide
            The guide.
        """

        return self.view.add_guide(orientation, position)

    def clear_guides(self) -> None:
        """Take every guide off the sheet."""

        self.view.clear_guides()

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
        self._new_guide = None

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
