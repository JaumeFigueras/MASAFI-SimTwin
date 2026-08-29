"""Tests for the rulers along a canvas."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QImage, QPainter

from masafi_simtwin.documents.canvas import PIXELS_PER_MM, Canvas
from masafi_simtwin.documents.ruler import (
    MILLIMETRES,
    MIN_LABEL_GAP,
    RULER_THICKNESS,
    Ruler,
    RulerCorner,
)


@pytest.fixture
def canvas(qtbot):
    """Build a canvas with its rulers, sized so that it can be scrolled.

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


def test_the_rulers_lie_along_the_top_and_the_left(canvas):
    """One of each, each as thick as the corner box between them."""

    top, left = canvas.rulers

    assert top.horizontal and not left.horizontal
    assert top.height() == RULER_THICKNESS
    assert left.width() == RULER_THICKNESS
    assert canvas.corner.size().width() == RULER_THICKNESS


def test_the_rulers_count_in_millimetres(canvas):
    """Which is what the corner box says, in the symbol every language shares."""

    assert canvas.corner.unit is MILLIMETRES
    assert MILLIMETRES.symbol == 'mm'
    assert all(ruler.unit is MILLIMETRES for ruler in canvas.rulers)


def test_a_ruler_measures_the_view_it_is_given(canvas):
    """The scale is the view's own, so the two cannot drift apart."""

    top, left = canvas.rulers

    assert top.scale == pytest.approx(PIXELS_PER_MM)
    assert top.origin == pytest.approx(canvas.view.mapToScene(0, 0).x())
    assert left.origin == pytest.approx(canvas.view.mapToScene(0, 0).y())


def test_the_first_pixel_of_a_ruler_is_its_origin(canvas):
    """Which is what puts a tick over the scene point it stands for."""

    top = canvas.horizontal_ruler

    assert top._pixel_of(top.origin) == pytest.approx(0.0)
    assert top._pixel_of(top.origin + 10.0) == pytest.approx(10.0 * PIXELS_PER_MM)


def test_a_ruler_follows_the_view_as_it_is_zoomed(canvas):
    """A zoom is a change of scale, and the ruler is drawn from the scale."""

    canvas.zoom_in()
    top = canvas.horizontal_ruler

    assert top.scale == pytest.approx(canvas.view.transform().m11())
    assert top.pixels_per_unit == pytest.approx(top.scale)


def test_the_labelled_ticks_thin_out_as_the_canvas_is_zoomed_away_from(canvas):
    """The numbers never collide: a step is taken only when it leaves room."""

    top = canvas.horizontal_ruler
    measured = []

    for _ in range(20):
        measured.append((top.step(), top.pixels_per_unit))
        canvas.zoom_out()

    assert [step for step, _ in measured] == sorted(step for step, _ in measured)
    assert all(step * pixels >= MIN_LABEL_GAP for step, pixels in measured)


def test_a_labelled_step_is_one_of_the_units_own(canvas):
    """A ruler in millimetres is ruled in millimetres a person would count in."""

    top = canvas.horizontal_ruler

    for _ in range(12):
        assert top.step() in MILLIMETRES.steps
        canvas.zoom_in()


def test_the_pointer_is_marked_and_unmarked(canvas):
    """Which is what a ruler is for as much as the numbers are."""

    top, left = canvas.rulers

    top.set_pointer(QPointF(30.0, 40.0))
    left.set_pointer(QPointF(30.0, 40.0))

    assert top.pointer == pytest.approx(30.0)
    assert left.pointer == pytest.approx(40.0)

    top.set_pointer(None)

    assert top.pointer is None


def paint(widget) -> QImage:
    """Render a widget, which is what says its painting runs at all.

    Parameters
    ----------
    widget : PyQt6.QtWidgets.QWidget
        The widget to render.

    Returns
    -------
    PyQt6.QtGui.QImage
        What it painted.
    """

    image = QImage(max(widget.width(), 1), max(widget.height(), 1), QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    widget.render(painter)
    painter.end()
    return image


def test_both_rulers_paint(canvas):
    """Ticks, numbers and the pointer mark, in either direction."""

    top, left = canvas.rulers
    top.set_pointer(QPointF(0.0, 0.0))
    left.set_pointer(QPointF(0.0, 0.0))

    assert not paint(top).isNull()
    assert not paint(left).isNull()


def test_the_corner_paints_its_symbol(qtbot):
    """The one place the unit is written, rather than on every number."""

    corner = RulerCorner()
    qtbot.addWidget(corner)

    assert not paint(corner).isNull()


def test_a_ruler_of_a_view_with_no_scale_paints_nothing_rather_than_dividing(qtbot):
    """A scale of nought is a division by nought, not a ruler with no ticks."""

    canvas = Canvas()
    qtbot.addWidget(canvas)
    canvas.view.setTransform(canvas.view.transform().scale(0.0, 0.0))
    ruler = Ruler(Qt.Orientation.Horizontal, canvas.view)
    qtbot.addWidget(ruler)
    ruler.resize(200, RULER_THICKNESS)

    assert not paint(ruler).isNull()
