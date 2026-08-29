"""The rulers along the top and the left of a canvas.

A canvas is a sheet, and the sheet is measured in **millimetres**: one scene
unit is one millimetre, everywhere in the application.  That is a property of
the drawing rather than of the model on it — a Petri net has no distance unit of
its own, its blocks having no position that means anything, but the drawing of
one still has a size, and it is that size the rulers show.  It is also what
makes printing and exporting a sheet mean something later.

A ruler reads the geometry of the view it is given rather than being told about
it: the scale is the view's transform and the origin is the scene point at the
first pixel of the viewport, so a ruler cannot drift out of step with what it is
measuring.  The canvas only has to say *something moved*.

The spacing of the labelled ticks is chosen from :attr:`RulerUnit.steps` — the
smallest one that leaves :data:`MIN_LABEL_GAP` pixels between two labels — so the
numbers thin out as the canvas is zoomed away from and never collide.

A ruler is also where a guide comes from: pressing on one and dragging pulls a
line out onto the sheet.  The ruler only reports where the pointer is in the
scene and whether it was let go over the sheet; making, moving and dropping the
guide is the canvas's, which is what owns the items.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6.QtCore import QPointF, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPalette
from PyQt6.QtWidgets import QGraphicsView, QWidget

#: How thick a ruler is, in pixels, and therefore the side of the corner box.
RULER_THICKNESS = 20

#: How close two labels may come before the next spacing up is taken.
MIN_LABEL_GAP = 60

#: Length, in pixels, of a labelled tick and of a plain one.
MAJOR_TICK = 8
MINOR_TICK = 4

#: How many plain ticks divide one labelled step.
TICKS_PER_STEP = 5

#: A plain tick closer than this to the next is not drawn at all.
MIN_TICK_GAP = 4

#: Opacity, out of 255, of the ticks, of the numbers and of the hairline.
TICK_ALPHA = 110
LABEL_ALPHA = 170
BORDER_ALPHA = 60


@dataclass(frozen=True)
class RulerUnit:
    """What a ruler counts in.

    Attributes
    ----------
    symbol : str
        What the corner box says.  An SI symbol is the same in every language,
        so it is not translated.
    millimetres : float
        How many scene units one of them is, the scene being in millimetres.
    steps : tuple of float
        The spacings a labelled tick may take, in units and ascending.  Each is
        five times a plain tick, and they are chosen to fall on the canvas grid
        rather than beside it.
    """

    symbol: str
    millimetres: float
    steps: tuple[float, ...]


#: The unit a canvas is ruled in.  It is the only one there is for now; adding
#: another is an entry here and a way of choosing it, and nothing else.
MILLIMETRES = RulerUnit('mm', 1.0, (1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0))


class Ruler(QWidget):
    """One ruler, along the top or the left of a canvas.

    Parameters
    ----------
    orientation : PyQt6.QtCore.Qt.Orientation
        ``Horizontal`` for the ruler along the top, ``Vertical`` for the one
        down the left.
    view : PyQt6.QtWidgets.QGraphicsView
        The view whose geometry the ruler measures.  Its viewport is taken to
        begin at the same pixel as the ruler, which is what the canvas layout
        arranges.
    unit : RulerUnit, optional
        What to count in, millimetres by default.
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.

    Attributes
    ----------
    unit : RulerUnit
        What the ruler counts in.
    guide_dragged : PyQt6.QtCore.pyqtSignal
        Emitted with the scene position under the pointer while a guide is being
        pulled out of the ruler, from the press onwards.
    guide_dropped : PyQt6.QtCore.pyqtSignal
        Emitted when the pointer is let go, with whether it ended over the sheet
        rather than back on the ruler it came from.
    """

    guide_dragged = pyqtSignal(QPointF)
    guide_dropped = pyqtSignal(bool)

    def __init__(
        self,
        orientation: Qt.Orientation,
        view: QGraphicsView,
        unit: RulerUnit = MILLIMETRES,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName('Ruler')
        self.orientation = orientation
        self.unit = unit
        self._view = view
        self._pointer: float | None = None
        self._dragging = False

        if self.horizontal:
            self.setFixedHeight(RULER_THICKNESS)
        else:
            self.setFixedWidth(RULER_THICKNESS)

    @property
    def horizontal(self) -> bool:
        """bool: Whether this is the ruler along the top."""

        return self.orientation == Qt.Orientation.Horizontal

    # ------------------------------------------------------------------
    # What the ruler is measuring
    # ------------------------------------------------------------------

    @property
    def scale(self) -> float:
        """float: Pixels to one scene unit, which is the view's own scale."""

        return self._view.transform().m11()

    @property
    def origin(self) -> float:
        """float: The scene coordinate the ruler's first pixel stands on."""

        corner = self._view.mapToScene(0, 0)
        return corner.x() if self.horizontal else corner.y()

    @property
    def pixels_per_unit(self) -> float:
        """float: How many pixels one of :attr:`unit` takes at the current zoom."""

        return self.scale * self.unit.millimetres

    def step(self) -> float:
        """Choose the spacing of the labelled ticks, in units.

        Returns
        -------
        float
            The smallest spacing of :attr:`RulerUnit.steps` whose labels are at
            least :data:`MIN_LABEL_GAP` apart, and the largest there is when
            even that is not enough.
        """

        for step in self.unit.steps:
            if step * self.pixels_per_unit >= MIN_LABEL_GAP:
                return step
        return self.unit.steps[-1]

    @property
    def pointer(self) -> float | None:
        """float, optional: Where the pointer's mark is, along the ruler's axis."""

        return self._pointer

    def set_pointer(self, position: QPointF | None) -> None:
        """Mark where the pointer is, or take the mark away.

        Parameters
        ----------
        position : PyQt6.QtCore.QPointF, optional
            Where the pointer is in the scene, or ``None`` when it has left the
            canvas.
        """

        along = None
        if position is not None:
            along = position.x() if self.horizontal else position.y()
        if along != self._pointer:
            self._pointer = along
            self.update()

    # ------------------------------------------------------------------
    # Pulling a guide out of the ruler
    # ------------------------------------------------------------------

    def _scene_position(self, event) -> QPointF:
        """Give the scene point the pointer is over, wherever it has got to.

        The ruler holds the mouse for the whole of the drag, so the pointer is
        over the sheet while the events still arrive here.  Going through the
        screen is what makes the answer right on both sides of the border.

        Parameters
        ----------
        event : PyQt6.QtGui.QMouseEvent
            The mouse event, in the ruler's own coordinates.

        Returns
        -------
        PyQt6.QtCore.QPointF
            Where the pointer is, in the scene.
        """

        on_screen = self.mapToGlobal(event.position().toPoint())
        return self._view.mapToScene(self._view.viewport().mapFromGlobal(on_screen))

    def mousePressEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Begin pulling a guide out of the ruler.

        Parameters
        ----------
        event : PyQt6.QtGui.QMouseEvent
            The mouse event.
        """

        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.guide_dragged.emit(self._scene_position(event))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Report where the guide being dragged has got to.

        Parameters
        ----------
        event : PyQt6.QtGui.QMouseEvent
            The mouse event.
        """

        if self._dragging:
            self.guide_dragged.emit(self._scene_position(event))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Drop the guide, saying whether it was let go over the sheet.

        A press and a release without leaving the ruler is not a guide: it is a
        click on a ruler, and it leaves nothing behind.

        Parameters
        ----------
        event : PyQt6.QtGui.QMouseEvent
            The mouse event.
        """

        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.guide_dropped.emit(not self.rect().contains(event.position().toPoint()))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def _pixel_of(self, value: float) -> float:
        """Give the pixel a scene coordinate falls on.

        Parameters
        ----------
        value : float
            A coordinate along the ruler's axis, in scene units.

        Returns
        -------
        float
            Its distance, in pixels, from the start of the ruler.
        """

        return (value - self.origin) * self.scale

    def paintEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Draw the ground, the ticks, the numbers and the pointer mark.

        Parameters
        ----------
        event : PyQt6.QtGui.QPaintEvent
            The paint event.
        """

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        text = self.palette().color(QPalette.ColorRole.Text)
        painter.fillRect(self.rect(), self.palette().color(QPalette.ColorRole.Base))
        self._draw_border(painter, text)
        self._draw_ticks(painter, text)
        self._draw_pointer(painter)
        painter.end()

    def _draw_border(self, painter: QPainter, text: QColor) -> None:
        """Rule the hairline between the ruler and the canvas.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the widget.
        text : PyQt6.QtGui.QColor
            The foreground colour the ruler's own colours are made from.
        """

        colour = QColor(text)
        colour.setAlpha(BORDER_ALPHA)
        painter.setPen(colour)
        if self.horizontal:
            painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        else:
            painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

    def _draw_ticks(self, painter: QPainter, text: QColor) -> None:
        """Draw every tick of the ruler, and the number on the labelled ones.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the widget.
        text : PyQt6.QtGui.QColor
            The foreground colour the ruler's own colours are made from.
        """

        scale = self.scale
        if scale <= 0.0:
            return

        step = self.step()
        tick = step / TICKS_PER_STEP
        if tick * self.pixels_per_unit < MIN_TICK_GAP:
            tick = step

        ticks = QColor(text)
        ticks.setAlpha(TICK_ALPHA)
        labels = QColor(text)
        labels.setAlpha(LABEL_ALPHA)

        font = painter.font()
        font.setPointSizeF(max(6.0, font.pointSizeF() - 2.0))
        painter.setFont(font)

        divisions = max(1, round(step / tick))
        length = self.width() if self.horizontal else self.height()
        spacing = tick * self.unit.millimetres
        first = math.floor(self.origin / spacing)
        last = math.ceil((self.origin + length / scale) / spacing)

        for index in range(first, last + 1):
            labelled = index % divisions == 0
            pixel = round(self._pixel_of(index * spacing))
            painter.setPen(labels if labelled else ticks)
            self._draw_tick(painter, pixel, MAJOR_TICK if labelled else MINOR_TICK)
            if labelled:
                self._draw_label(painter, pixel, index * tick)

    def _draw_tick(self, painter: QPainter, pixel: int, length: int) -> None:
        """Draw one tick, growing from the canvas edge of the ruler.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the widget.
        pixel : int
            Where along the ruler the tick goes.
        length : int
            How long it is.
        """

        if self.horizontal:
            painter.drawLine(pixel, self.height() - length - 1, pixel, self.height() - 1)
        else:
            painter.drawLine(self.width() - length - 1, pixel, self.width() - 1, pixel)

    def _draw_label(self, painter: QPainter, pixel: int, value: float) -> None:
        """Write the number of a labelled tick beside it.

        The numbers of the left ruler are turned onto their side and read from
        the bottom up, which is what every drawing program does with them: a
        ruler twenty pixels wide has no room for them any other way.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the widget.
        pixel : int
            Where along the ruler the tick is.
        value : float
            What the tick stands for, in units.
        """

        label = f'{value:g}'
        if self.horizontal:
            painter.drawText(
                QRect(pixel + 3, 0, MIN_LABEL_GAP, self.height() - MAJOR_TICK - 1),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                label,
            )
            return

        painter.save()
        painter.translate(0, pixel)
        painter.rotate(-90.0)
        painter.drawText(
            QRect(3, 0, MIN_LABEL_GAP, self.width() - MAJOR_TICK - 1),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            label,
        )
        painter.restore()

    def _draw_pointer(self, painter: QPainter) -> None:
        """Mark where the pointer is on the canvas.

        In the palette's ``Link``, which is where the theme's accent is kept:
        ``Highlight`` is the pale wash behind selected text, and a mark drawn in
        it is a mark nobody can see.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the widget.
        """

        if self._pointer is None:
            return
        pixel = round(self._pixel_of(self._pointer))
        painter.setPen(self.palette().color(QPalette.ColorRole.Link))
        if self.horizontal:
            painter.drawLine(pixel, 0, pixel, self.height() - 1)
        else:
            painter.drawLine(0, pixel, self.width() - 1, pixel)


class RulerCorner(QWidget):
    """The square where the two rulers meet, which says what they count in.

    Parameters
    ----------
    unit : RulerUnit, optional
        What the rulers count in, millimetres by default.
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.

    Attributes
    ----------
    unit : RulerUnit
        What the corner says.
    """

    def __init__(self, unit: RulerUnit = MILLIMETRES, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('RulerCorner')
        self.unit = unit
        self.setFixedSize(RULER_THICKNESS, RULER_THICKNESS)

    def paintEvent(self, event) -> None:  # noqa: N802  (Qt naming)
        """Write the unit's symbol in the corner.

        Parameters
        ----------
        event : PyQt6.QtGui.QPaintEvent
            The paint event.
        """

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.fillRect(self.rect(), self.palette().color(QPalette.ColorRole.Base))

        colour = QColor(self.palette().color(QPalette.ColorRole.Text))
        colour.setAlpha(LABEL_ALPHA)
        font = painter.font()
        font.setPointSizeF(max(6.0, font.pointSizeF() - 2.0))
        painter.setFont(font)
        painter.setPen(colour)
        painter.drawText(
            self.rect(), int(Qt.AlignmentFlag.AlignCenter), self.unit.symbol
        )
        painter.end()
