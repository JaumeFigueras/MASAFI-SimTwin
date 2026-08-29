"""Tests for the ruled sheet every drawn document is built on."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PyQt6.QtGui import QImage, QMouseEvent, QPainter, QWheelEvent
from PyQt6.QtWidgets import QGraphicsView

from masafi_simtwin.documents.canvas import (
    MAX_ZOOM,
    MIN_ZOOM,
    PIXELS_PER_MM,
    SCENE_RECT,
    ZOOM_STEP,
    Canvas,
    _multiples_of,
)


@pytest.fixture
def canvas(qtbot):
    """Build a canvas, sized so that it can be scrolled.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    masafi_simtwin.documents.canvas.Canvas
        The canvas.
    """

    widget = Canvas()
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    return widget


# ----------------------------------------------------------------------
# The sheet
# ----------------------------------------------------------------------


def test_the_sheet_is_measured_in_millimetres(canvas):
    """One scene unit is one millimetre, which is what makes a ruler possible."""

    assert canvas.scene().sceneRect() == SCENE_RECT
    assert SCENE_RECT.width() == 4000.0


def test_life_size_is_the_zoom_of_one(canvas):
    """At a zoom of one a millimetre of the sheet is a millimetre on the screen."""

    assert canvas.zoom == pytest.approx(1.0)
    assert canvas.view.transform().m11() == pytest.approx(PIXELS_PER_MM)
    assert PIXELS_PER_MM == pytest.approx(96.0 / 25.4)


def test_the_sheet_selects_with_a_rubber_band(canvas):
    """The left button selects; drawing will take it later, panning never does."""

    assert canvas.view.dragMode() == QGraphicsView.DragMode.RubberBandDrag


# ----------------------------------------------------------------------
# Zoom
# ----------------------------------------------------------------------


def test_zooming_in_and_out_returns_to_where_it_started(canvas):
    """One step in and one step out is the same scale, not a drifting one."""

    canvas.zoom_in()
    assert canvas.zoom == pytest.approx(ZOOM_STEP)

    canvas.zoom_out()
    assert canvas.zoom == pytest.approx(1.0)


def test_the_zoom_is_held_between_its_limits(canvas):
    """A sheet cannot be scrolled to nothing, nor to a single square."""

    for _ in range(60):
        canvas.zoom_out()
    assert canvas.zoom == pytest.approx(MIN_ZOOM)

    for _ in range(60):
        canvas.zoom_in()
    assert canvas.zoom == pytest.approx(MAX_ZOOM)


def test_resetting_the_zoom_is_life_size(canvas):
    """Whatever it was before."""

    canvas.zoom_in()
    canvas.zoom_in()
    canvas.reset_zoom()

    assert canvas.zoom == pytest.approx(1.0)


def wheel(view, notches: int, modifiers: Qt.KeyboardModifier) -> QWheelEvent:
    """Build a wheel event over the middle of a view.

    Parameters
    ----------
    view : masafi_simtwin.documents.canvas.CanvasView
        The view the wheel is turned over.
    notches : int
        How far, in Qt's eighths of a degree.
    modifiers : PyQt6.QtCore.Qt.KeyboardModifier
        What is held down while it turns.

    Returns
    -------
    PyQt6.QtGui.QWheelEvent
        The event.
    """

    position = QPointF(view.viewport().rect().center())
    return QWheelEvent(
        position,
        view.viewport().mapToGlobal(position),
        QPoint(0, 0),
        QPoint(0, notches),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def test_the_wheel_zooms_with_control(canvas):
    """Which is what every canvas of this kind does."""

    canvas.view.wheelEvent(wheel(canvas.view, 120, Qt.KeyboardModifier.ControlModifier))

    assert canvas.zoom == pytest.approx(ZOOM_STEP)


def test_the_wheel_scrolls_without_control(canvas):
    """A plain turn belongs to the scroll bars, not to the scale."""

    canvas.view.wheelEvent(wheel(canvas.view, 120, Qt.KeyboardModifier.NoModifier))

    assert canvas.zoom == pytest.approx(1.0)


# ----------------------------------------------------------------------
# Panning and the pointer
# ----------------------------------------------------------------------


def mouse(kind: QEvent.Type, position: QPointF, button: Qt.MouseButton) -> QMouseEvent:
    """Build a mouse event on a view.

    Parameters
    ----------
    kind : PyQt6.QtCore.QEvent.Type
        Press, move or release.
    position : PyQt6.QtCore.QPointF
        Where it happened, in the widget's coordinates.
    button : PyQt6.QtCore.Qt.MouseButton
        Which button it was.

    Returns
    -------
    PyQt6.QtGui.QMouseEvent
        The event.
    """

    return QMouseEvent(kind, position, position, button, button, Qt.KeyboardModifier.NoModifier)


def test_the_middle_button_pans_the_sheet(canvas):
    """The one button left free once the left one draws and selects."""

    view = canvas.view
    start = view.horizontalScrollBar().value()

    view.mousePressEvent(
        mouse(QEvent.Type.MouseButtonPress, QPointF(300.0, 200.0), Qt.MouseButton.MiddleButton)
    )
    view.mouseMoveEvent(
        mouse(QEvent.Type.MouseMove, QPointF(240.0, 200.0), Qt.MouseButton.MiddleButton)
    )

    assert view.horizontalScrollBar().value() == start + 60

    view.mouseReleaseEvent(
        mouse(
            QEvent.Type.MouseButtonRelease,
            QPointF(240.0, 200.0),
            Qt.MouseButton.MiddleButton,
        )
    )
    view.mouseMoveEvent(
        mouse(QEvent.Type.MouseMove, QPointF(140.0, 200.0), Qt.MouseButton.NoButton)
    )

    assert view.horizontalScrollBar().value() == start + 60


def test_the_pointer_is_marked_on_both_rulers(canvas):
    """A ruler says where the pointer is as much as it says where anything is."""

    position = QPointF(120.0, 90.0)
    canvas.view.mouseMoveEvent(
        mouse(QEvent.Type.MouseMove, position, Qt.MouseButton.NoButton)
    )
    scene_position = canvas.view.mapToScene(position.toPoint())
    top, left = canvas.rulers

    assert top.pointer == pytest.approx(scene_position.x())
    assert left.pointer == pytest.approx(scene_position.y())


def test_the_mark_goes_when_the_pointer_leaves(canvas):
    """Otherwise a ruler would keep pointing at where the pointer last was."""

    canvas.view.mouseMoveEvent(
        mouse(QEvent.Type.MouseMove, QPointF(120.0, 90.0), Qt.MouseButton.NoButton)
    )
    canvas.view.leaveEvent(QEvent(QEvent.Type.Leave))

    assert all(ruler.pointer is None for ruler in canvas.rulers)


def test_panning_does_not_move_the_pointer_mark(canvas):
    """While the sheet is dragged the pointer stays on the same scene point."""

    canvas.view.mousePressEvent(
        mouse(QEvent.Type.MouseButtonPress, QPointF(300.0, 200.0), Qt.MouseButton.MiddleButton)
    )
    canvas.view.mouseMoveEvent(
        mouse(QEvent.Type.MouseMove, QPointF(240.0, 200.0), Qt.MouseButton.MiddleButton)
    )

    assert canvas.horizontal_ruler.pointer is None


# ----------------------------------------------------------------------
# What the rulers are told
# ----------------------------------------------------------------------


def test_a_zoom_tells_the_rulers(canvas, qtbot):
    """They are drawn from the view's geometry, so they redraw when it changes."""

    with qtbot.waitSignal(canvas.view.view_changed, timeout=1000):
        canvas.zoom_in()


def test_a_scroll_tells_the_rulers(canvas, qtbot):
    """However the scroll came about — the wheel, the bars, or a pan."""

    bar = canvas.view.horizontalScrollBar()

    with qtbot.waitSignal(canvas.view.view_changed, timeout=1000):
        bar.setValue(bar.value() + 20)


def test_a_zoom_that_changes_nothing_tells_them_nothing(canvas):
    """A zoom held at its limit is not a change of view."""

    for _ in range(60):
        canvas.zoom_out()
    told = []
    canvas.view.view_changed.connect(lambda: told.append(True))
    canvas.zoom_out()

    assert told == []


# ----------------------------------------------------------------------
# Painting
# ----------------------------------------------------------------------


def test_the_sheet_paints(canvas):
    """The grid is painted rather than styled, so this is where it is checked.

    A ``drawBackground`` that throws leaves a blank widget and no error
    anywhere else.
    """

    canvas.view.empty_note = 'Nothing here yet'
    image = QImage(600, 400, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    canvas.render(painter)
    painter.end()

    assert not image.isNull()


def test_the_sheet_paints_zoomed_out(canvas):
    """Far enough out the grid squares are dropped and the heavy lines are left."""

    for _ in range(60):
        canvas.zoom_out()

    image = QImage(600, 400, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    canvas.render(painter)
    painter.end()

    assert not image.isNull()


# ----------------------------------------------------------------------
# The grid, and the strips it is painted in
# ----------------------------------------------------------------------


class RecordingPainter:
    """A stand-in for the painter, which keeps what it was asked to draw.

    ``drawBackground`` is handed a painter and a rectangle and asks nothing of
    the painter but to fill, to take a pen and to draw lines, so the lines it
    would put down can be read off without a screen to put them on.

    Attributes
    ----------
    lines : list of PyQt6.QtCore.QLineF
        What was drawn, in scene coordinates.
    """

    def __init__(self) -> None:
        self.lines = []

    def fillRect(self, *arguments) -> None:  # noqa: N802  (Qt naming)
        """Ignore the fill.

        Parameters
        ----------
        *arguments
            Whatever the caller passes.
        """

    def setPen(self, *arguments) -> None:  # noqa: N802  (Qt naming)
        """Ignore the pen.

        Parameters
        ----------
        *arguments
            Whatever the caller passes.
        """

    def drawLine(self, line) -> None:  # noqa: N802  (Qt naming)
        """Keep a line.

        Parameters
        ----------
        line : PyQt6.QtCore.QLineF
            The line that would be drawn.
        """

        self.lines.append(line)


def grid_of(canvas, strip: QRectF) -> RecordingPainter:
    """Draw the grid of one exposed strip and give back what it came to.

    Parameters
    ----------
    canvas : masafi_simtwin.documents.canvas.Canvas
        The canvas whose grid it is.
    strip : PyQt6.QtCore.QRectF
        The part of the scene being repainted.

    Returns
    -------
    RecordingPainter
        The painter, holding the lines.
    """

    recorder = RecordingPainter()
    canvas.view.drawBackground(recorder, strip)
    return recorder


def test_the_grid_is_drawn_across_the_whole_of_the_exposed_rect(canvas):
    """A view repaints only what changed, which after a scroll is a thin strip
    with fractional edges.

    Rounding those edges inwards is what left the grid in dashes: each strip
    stopped short of the next, and the sliver between them was painted by
    neither.
    """

    strip = QRectF(-12.5, 52.1, 40.0, 1.8)
    lines = grid_of(canvas, strip).lines

    assert lines
    for line in lines:
        if line.x1() == line.x2():
            assert (line.y1(), line.y2()) == (strip.top(), strip.bottom())
        else:
            assert (line.x1(), line.x2()) == (strip.left(), strip.right())


def test_two_strips_meeting_leave_no_sliver_between_them(canvas):
    """What one strip stops drawing at is where the next starts."""

    above = QRectF(-12.5, 52.1, 40.0, 1.8)
    below = QRectF(-12.5, 53.9, 40.0, 1.8)

    ends = [line.y2() for line in grid_of(canvas, above).lines if line.x1() == line.x2()]
    starts = [line.y1() for line in grid_of(canvas, below).lines if line.x1() == line.x2()]

    assert ends and starts
    assert max(ends) == min(starts) == below.top()


def test_a_strip_holding_no_grid_line_draws_none_across_it(canvas):
    """The lines are the multiples of the step, not one per strip."""

    lines = grid_of(canvas, QRectF(11.1, 52.1, 1.2, 1.8)).lines

    assert lines == []


def test_the_multiples_of_a_step_are_those_inside_the_stretch(canvas):
    """Including over the origin, where rounding towards nought used to bite."""

    assert _multiples_of(5, 48.0, 62.0) == [50, 55, 60]
    assert _multiples_of(5, 52.1, 53.9) == []
    assert _multiples_of(5, -12.5, -2.0) == [-10, -5]
    assert _multiples_of(5, -7.0, 7.0) == [-5, 0, 5]
    assert _multiples_of(50, -60.0, 60.0) == [-50, 0, 50]
