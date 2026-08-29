"""Tests for the guides a sheet is aligned against."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QPainter, QPalette

from masafi_simtwin.documents.canvas import SNAP_STEP, Canvas
from masafi_simtwin.documents.guide import Guide


@pytest.fixture
def canvas(qtbot):
    """Build a canvas, shown, so that its rulers can be dragged from.

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


def mouse(kind: QEvent.Type, position: QPointF) -> QMouseEvent:
    """Build a left-button mouse event.

    Parameters
    ----------
    kind : PyQt6.QtCore.QEvent.Type
        Press, move or release.
    position : PyQt6.QtCore.QPointF
        Where it happened, in the widget's coordinates.

    Returns
    -------
    PyQt6.QtGui.QMouseEvent
        The event.
    """

    return QMouseEvent(
        kind,
        position,
        position,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def drag_from(ruler, start: QPointF, end: QPointF, release: bool = True) -> None:
    """Pull a guide out of a ruler.

    Parameters
    ----------
    ruler : masafi_simtwin.documents.ruler.Ruler
        The ruler to drag from.
    start : PyQt6.QtCore.QPointF
        Where the press lands, in the ruler's coordinates.
    end : PyQt6.QtCore.QPointF
        Where the pointer is taken, in the same coordinates — past the ruler's
        own thickness is over the sheet.
    release : bool, optional
        Whether to let go at the end.
    """

    ruler.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    ruler.mouseMoveEvent(mouse(QEvent.Type.MouseMove, end))
    if release:
        ruler.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, end))


# ----------------------------------------------------------------------
# Pulling one out of a ruler
# ----------------------------------------------------------------------


def test_the_top_ruler_gives_a_guide_across_the_sheet(canvas):
    """Which is the one that moves up and down, as every drawing program has it."""

    drag_from(canvas.horizontal_ruler, QPointF(300.0, 10.0), QPointF(300.0, 120.0))

    assert len(canvas.guides) == 1
    assert canvas.guides[0].orientation == Qt.Orientation.Horizontal


def test_the_left_ruler_gives_a_guide_up_the_sheet(canvas):
    """And the two can be on the sheet at once, in any number."""

    drag_from(canvas.horizontal_ruler, QPointF(300.0, 10.0), QPointF(300.0, 120.0))
    drag_from(canvas.vertical_ruler, QPointF(10.0, 200.0), QPointF(150.0, 200.0))
    drag_from(canvas.vertical_ruler, QPointF(10.0, 100.0), QPointF(320.0, 100.0))

    assert [guide.orientation for guide in canvas.guides] == [
        Qt.Orientation.Horizontal,
        Qt.Orientation.Vertical,
        Qt.Orientation.Vertical,
    ]


def test_a_guide_lands_where_the_pointer_left_it(canvas):
    """Snapped, but where the pointer was and not somewhere of its own."""

    end = QPointF(300.0, 150.0)
    drag_from(canvas.horizontal_ruler, QPointF(300.0, 10.0), end)

    on_screen = canvas.horizontal_ruler.mapToGlobal(end.toPoint())
    scene = canvas.view.mapToScene(canvas.view.viewport().mapFromGlobal(on_screen))

    assert canvas.guides[0].position == pytest.approx(canvas.view.snap(scene.y()))


def test_a_guide_follows_the_pointer_before_it_is_dropped(canvas):
    """What is dragged is the guide itself, not a preview of one."""

    ruler = canvas.horizontal_ruler
    drag_from(ruler, QPointF(300.0, 10.0), QPointF(300.0, 80.0), release=False)
    first = canvas.guides[0].position

    ruler.mouseMoveEvent(mouse(QEvent.Type.MouseMove, QPointF(300.0, 260.0)))

    assert len(canvas.guides) == 1
    assert canvas.guides[0].position > first


def test_a_click_on_a_ruler_leaves_nothing_behind(canvas):
    """Let go without leaving the ruler, it was a click on a ruler."""

    ruler = canvas.horizontal_ruler
    drag_from(ruler, QPointF(300.0, 10.0), QPointF(320.0, 12.0))

    assert canvas.guides == []


def test_dragging_from_a_ruler_marks_the_pointer_on_it(canvas):
    """The rulers say where the guide is going while it is being placed."""

    drag_from(canvas.horizontal_ruler, QPointF(300.0, 10.0), QPointF(300.0, 150.0))

    assert canvas.horizontal_ruler.pointer is not None
    assert canvas.vertical_ruler.pointer is not None


# ----------------------------------------------------------------------
# Snapping
# ----------------------------------------------------------------------


def test_a_guide_snaps_to_the_millimetre(canvas):
    """The sheet is in millimetres, so a millimetre is where a guide goes."""

    guide = canvas.add_guide(Qt.Orientation.Horizontal, 12.4)

    assert SNAP_STEP == 1.0
    assert guide.position == pytest.approx(12.0)
    assert canvas.view.snap(12.6) == pytest.approx(13.0)
    assert canvas.view.snap(-7.4) == pytest.approx(-7.0)
    assert canvas.view.snap(-7.6) == pytest.approx(-8.0)


def test_the_snapping_does_not_follow_the_zoom(canvas):
    """The same drag puts a guide on the same millimetre, close to or far away.

    A snap that coarsened as the sheet was zoomed away from would mean the place
    a guide lands depends on how the sheet happened to be looked at when it was
    dropped, which is the one thing a guide is there not to do.
    """

    landed = []
    for _ in range(30):
        guide = canvas.add_guide(Qt.Orientation.Vertical, 47.4)
        landed.append((canvas.zoom, guide.position))
        canvas.clear_guides()
        canvas.zoom_out()

    for _ in range(60):
        guide = canvas.add_guide(Qt.Orientation.Vertical, 47.4)
        landed.append((canvas.zoom, guide.position))
        canvas.clear_guides()
        canvas.zoom_in()

    assert all(position == pytest.approx(47.0) for _, position in landed)
    assert min(zoom for zoom, _ in landed) < 0.2
    assert max(zoom for zoom, _ in landed) > 4.0


def test_a_guide_keeps_to_its_own_axis(canvas):
    """A guide across the sheet moves up and down and nowhere else."""

    guide = canvas.add_guide(Qt.Orientation.Horizontal, 10.0)
    guide.setPos(QPointF(80.0, 33.0))

    assert guide.pos().x() == pytest.approx(0.0)
    assert guide.position == pytest.approx(33.0)


# ----------------------------------------------------------------------
# Selecting and deleting
# ----------------------------------------------------------------------


def test_a_guide_can_be_selected(canvas):
    """Which is what makes deleting one a thing that can be aimed."""

    guide = canvas.add_guide(Qt.Orientation.Horizontal, 10.0)
    guide.setSelected(True)

    assert guide.isSelected()
    assert guide.flags() & Guide.GraphicsItemFlag.ItemIsSelectable


def test_delete_removes_the_selected_guides(canvas):
    """And leaves the ones that were not selected where they are."""

    first = canvas.add_guide(Qt.Orientation.Horizontal, 10.0)
    canvas.add_guide(Qt.Orientation.Vertical, 20.0)
    first.setSelected(True)

    canvas.view.keyPressEvent(
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
    )

    assert [guide.orientation for guide in canvas.guides] == [Qt.Orientation.Vertical]


def test_delete_with_nothing_selected_removes_nothing(canvas):
    """A key that deletes what is not selected is a key nobody can trust."""

    canvas.add_guide(Qt.Orientation.Horizontal, 10.0)

    canvas.view.keyPressEvent(
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Backspace, Qt.KeyboardModifier.NoModifier)
    )

    assert len(canvas.guides) == 1


def test_a_guide_offers_to_be_deleted(canvas):
    """A guide has no menu-bar entry, so this is where deleting one is found."""

    guide = canvas.add_guide(Qt.Orientation.Horizontal, 10.0)
    menu = canvas.view.guide_menu(guide)

    assert [action.text() for action in menu.actions()] == [
        'Delete Guide',
        'Delete All Guides',
    ]


def test_the_bare_sheet_offers_to_clear_the_guides_and_nothing_else(canvas):
    """There is no guide under the pointer to delete, but there are guides."""

    canvas.add_guide(Qt.Orientation.Horizontal, 10.0)
    menu = canvas.view.guide_menu(None)

    assert [action.text() for action in menu.actions()] == ['Delete All Guides']


def test_a_sheet_with_no_guides_offers_nothing(canvas):
    """A menu with nothing in it is worse than no menu."""

    assert canvas.view.guide_menu(None) is None


def test_the_guides_can_be_cleared(canvas):
    """Which is what the menu entry comes to."""

    canvas.add_guide(Qt.Orientation.Horizontal, 10.0)
    canvas.add_guide(Qt.Orientation.Vertical, 20.0)
    canvas.clear_guides()

    assert canvas.guides == []


def test_a_guide_is_found_under_the_pointer(canvas):
    """Which is what the context menu is built from, and a click takes hold of."""

    guide = canvas.add_guide(Qt.Orientation.Horizontal, 0.0)
    middle = canvas.view.mapFromScene(QPointF(0.0, 0.0))

    assert canvas.view.guide_at(middle) is guide


# ----------------------------------------------------------------------
# What a guide is not
# ----------------------------------------------------------------------


def test_guides_are_not_something_drawn_on_the_sheet(canvas):
    """A sheet with guides and nothing else is still an empty sheet."""

    canvas.view.empty_note = 'Nothing here yet'
    canvas.add_guide(Qt.Orientation.Horizontal, 10.0)

    assert not canvas.view.has_content()


def test_the_guides_paint(canvas):
    """Selected and not, across and up, in one pass over the sheet."""

    canvas.add_guide(Qt.Orientation.Horizontal, 0.0)
    canvas.add_guide(Qt.Orientation.Vertical, 0.0).setSelected(True)

    image = QImage(600, 400, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    canvas.render(painter)
    painter.end()

    assert not image.isNull()


def distance(first, second) -> int:
    """Give how far apart two colours are, summed over the channels.

    Parameters
    ----------
    first : PyQt6.QtGui.QColor
        One colour.
    second : PyQt6.QtGui.QColor
        The other.

    Returns
    -------
    int
        The distance between them.
    """

    return (
        abs(first.red() - second.red())
        + abs(first.green() - second.green())
        + abs(first.blue() - second.blue())
    )


def test_a_guide_is_drawn_strongly_enough_to_be_seen(qapp, canvas):
    """The palette's ``Highlight`` is the pale wash behind selected text.

    A guide painted in it — which is what happened while the accent was being
    looked for in the wrong role — is very nearly the colour of the sheet it is
    on, so this checks the pixels rather than the role.

    The bar is the wash itself, and what is measured is the ink the line puts
    down over the rows it touches rather than the strongest of them: a hairline
    lands where it lands, and one spread evenly over two rows is as visible as
    one that fell on a single row.

    It is the *viewport* that is rendered.  ``QGraphicsView.render`` is not
    ``QWidget.render`` — it draws the whole scene into the painter, four metres
    of sheet in whatever room it is given, which is a grey mush and not a
    picture of anything anybody would see.

    The guide goes at 2 mm and is read at 2 mm across, which is between the
    grid's own lines in both directions: a sample taken on one of those would be
    measuring the grid as much as the guide.
    """

    guide = canvas.add_guide(Qt.Orientation.Horizontal, 2.0)
    viewport = canvas.view.viewport()
    spot = canvas.view.mapFromScene(QPointF(2.0, guide.position))

    image = QImage(viewport.width(), viewport.height(), QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    viewport.render(painter)
    painter.end()

    base = qapp.palette().color(QPalette.ColorRole.Base)
    wash = qapp.palette().color(QPalette.ColorRole.Highlight)
    ink = sum(
        distance(QColor(image.pixel(spot.x(), spot.y() + offset)), base)
        for offset in (-1, 0, 1)
    )

    assert ink > distance(wash, base)


def test_pulling_a_new_guide_out_puts_down_what_was_selected(canvas):
    """A press on a ruler is a press: it starts afresh, like one on the sheet.

    The scene clears the selection itself for a press it sees, and it never sees
    this one — the ruler holds the mouse for the whole of the drag — so a guide
    selected a moment ago would stay dashed beside the one being dragged out.
    """

    first = canvas.add_guide(Qt.Orientation.Horizontal, 10.0)
    first.setSelected(True)

    drag_from(canvas.horizontal_ruler, QPointF(300.0, 10.0), QPointF(300.0, 150.0))

    assert not first.isSelected()
    assert [guide.isSelected() for guide in canvas.guides] == [False, False]


def test_a_click_on_a_ruler_puts_it_down_too(canvas):
    """Even though the click leaves no guide behind, the press still happened."""

    first = canvas.add_guide(Qt.Orientation.Horizontal, 10.0)
    first.setSelected(True)

    drag_from(canvas.horizontal_ruler, QPointF(300.0, 10.0), QPointF(320.0, 12.0))

    assert canvas.guides == [first]
    assert not first.isSelected()


def test_a_guide_stays_selected_once_it_is_let_go(canvas):
    """Deliberately: *Delete* acts on what is selected, and a selection that
    lasted only as long as the button was held could never be deleted by it.

    What is selected is put down by the next press instead — on the bare sheet,
    on another guide, or on a ruler.
    """

    guide = canvas.add_guide(Qt.Orientation.Horizontal, 10.0)
    guide.setSelected(True)

    canvas.view.mouseReleaseEvent(
        mouse(QEvent.Type.MouseButtonRelease, QPointF(300.0, 200.0))
    )

    assert guide.isSelected()
