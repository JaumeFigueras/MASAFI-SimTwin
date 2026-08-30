"""Tests for what every item of a net does the same way.

A place is a circle and a transition is a bar, and apart from that they are one
thing: dropped out of the Libraries pane, snapped to the millimetre, held on the
paper, and carrying connecting points that are not drawn until the pointer is
over them.  Every test here is run against both, so a rule that holds for one and
not the other is a failure rather than an oversight.

*Where* the connecting points are is not shared and is not tested here — a
circle spreads them by angle and a bar spreads them along its edges — but that
each shape has them, that they are on its boundary, and that they can be found
and shown, is.
"""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import QMimeData, QPointF, QSizeF, Qt
from PyQt6.QtGui import QDragMoveEvent, QDropEvent

from masafi_simtwin.documents.net_item import PORT_RADIUS, NetItem
from masafi_simtwin.documents.place import Place
from masafi_simtwin.documents.transition import Transition
from masafi_simtwin.library_tree import element_mime_data

#: The elements of the P/T library this editor can draw, and what each becomes.
ELEMENTS = [('place', Place), ('transition', Transition)]


@pytest.fixture(params=ELEMENTS, ids=[key for key, _ in ELEMENTS])
def item(request, editor):
    """Put one item of each kind on the sheet, one test run each.

    Parameters
    ----------
    request : pytest.FixtureRequest
        The parameter, which is the element's key and the class it becomes.
    editor : masafi_simtwin.documents.petri_net.PetriNetEditor
        The document.

    Returns
    -------
    masafi_simtwin.documents.net_item.NetItem
        The item, already on the scene.
    """

    key, kind = request.param
    built = editor.add_element('pt-petri-net', key, QPointF(100.0, 80.0))
    assert isinstance(built, kind)
    return built


@pytest.fixture(params=[key for key, _ in ELEMENTS])
def element(request) -> str:
    """Give the key of each element the editor can draw, one test run each.

    Parameters
    ----------
    request : pytest.FixtureRequest
        The parameter.

    Returns
    -------
    str
        The key.
    """

    return request.param


def drop(view, data: QMimeData, position: QPointF) -> QDropEvent:
    """Let go of a drag over the sheet.

    The payload is kept alive for the whole of the call on purpose: a
    ``QDropEvent`` holds the ``QMimeData`` it is given without owning it, and a
    temporary one is freed under the event.

    Parameters
    ----------
    view : masafi_simtwin.documents.canvas.CanvasView
        The view the drop lands on.
    data : PyQt6.QtCore.QMimeData
        What is being dragged.
    position : PyQt6.QtCore.QPointF
        Where it is let go, in the viewport's coordinates.

    Returns
    -------
    PyQt6.QtGui.QDropEvent
        The event, so that a test can ask whether it was taken.
    """

    event = QDropEvent(
        position,
        Qt.DropAction.CopyAction,
        data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.dropEvent(event)
    return event


def dragged_over(view, data: QMimeData, position: QPointF) -> QDragMoveEvent:
    """Hold a drag over the sheet without letting go of it.

    This is the event that decides whether a drop can happen at all: it is what
    the cursor is drawn from, and a drag refused here never becomes a drop.

    Parameters
    ----------
    view : masafi_simtwin.documents.canvas.CanvasView
        The view the drag is over.
    data : PyQt6.QtCore.QMimeData
        What is being dragged.  It is kept alive by the caller for the same
        reason :func:`drop` keeps its own.
    position : PyQt6.QtCore.QPointF
        Where the pointer is, in the viewport's coordinates.

    Returns
    -------
    PyQt6.QtGui.QDragMoveEvent
        The event, so that a test can ask whether it was taken.
    """

    event = QDragMoveEvent(
        position.toPoint(),
        Qt.DropAction.CopyAction,
        data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.dragMoveEvent(event)
    return event


# ----------------------------------------------------------------------
# The connecting points
# ----------------------------------------------------------------------


def test_every_item_carries_connecting_points(item):
    """An arc has to have somewhere to land on whatever it is aimed at."""

    ports = item.ports()

    assert len(ports) >= 4
    assert len({(point.x(), point.y()) for point in ports}) == len(ports)


def test_the_connecting_points_stand_on_the_boundary(item):
    """An arc is attached to the edge of an item, not to the air beside it.

    The boundary is where a point stops being inside and starts being outside,
    so that is what is asked: a little way in along the same ray is in the
    shape, and a little way out is not.  Asking whether the point itself is
    contained would be asking a question about a hairline.
    """

    shape = item.shape()

    for point in item.ports():
        assert item.boundingRect().contains(point)
        assert shape.contains(point * 0.8)
        assert not shape.contains(point * 1.5)


def test_the_connecting_points_start_due_east_and_turn_upwards(item):
    """Both shapes are walked the same way round, so an arc tool reading the
    list of one has read the list of the other.

    The ``y`` axis of a scene points down, so turning upwards is ``y`` going
    negative — which is what a protractor does and what a person expects.
    """

    east, next_one = item.ports()[0], item.ports()[1]

    assert east.x() > 0.0
    assert east.y() == pytest.approx(0.0)
    assert next_one.y() < 0.0


def test_the_connecting_points_are_where_the_item_is(item):
    """They are asked for on the sheet as well, which is where an arc is drawn."""

    item.setPos(QPointF(50.0, 40.0))
    first = item.ports()[0]

    assert item.scene_ports()[0] == QPointF(50.0 + first.x(), 40.0 + first.y())
    assert item.port_at(item.scene_ports()[0]) is not None
    assert item.port_at(QPointF(50.0, 40.0)) is None


def test_a_connecting_point_is_found_by_being_near_enough(item):
    """A point one cannot miss by a hair is a point nobody can hit."""

    item.setPos(QPointF(50.0, 40.0))
    on = item.scene_ports()[0]
    near = QPointF(on.x(), on.y() + PORT_RADIUS * 0.5)
    far = QPointF(on.x(), on.y() + PORT_RADIUS * 2.0)

    assert item.port_at(near) is not None
    assert item.port_at(far) is None


def test_the_connecting_points_are_invisible_to_begin_with(item):
    """A net is read by its circles and its bars, not by the dots on them."""

    assert not item.ports_visible


def test_pointing_at_an_item_shows_its_connecting_points(item):
    """And taking the pointer away puts them back out of sight."""

    item.hoverEnterEvent(None)
    assert item.ports_visible

    item.hoverLeaveEvent(None)
    assert not item.ports_visible


def test_an_item_is_positioned_by_its_centre(item):
    """Which is what the connecting points are measured from."""

    assert item.pos() == QPointF(100.0, 80.0)
    assert item.boundingRect().center() == QPointF(0.0, 0.0)


# ----------------------------------------------------------------------
# Moving one about
# ----------------------------------------------------------------------


def test_an_item_can_be_moved_and_selected(item):
    """Which is what dragging one about on the sheet comes to."""

    assert item.flags() & NetItem.GraphicsItemFlag.ItemIsMovable
    assert item.flags() & NetItem.GraphicsItemFlag.ItemIsSelectable

    item.setSelected(True)
    assert item.isSelected()


def test_an_item_snaps_to_the_millimetre(item):
    """The same grid the guides snap to, so a net lines up against them."""

    item.setPos(QPointF(30.4, 20.6))

    assert item.pos() == QPointF(30.0, 21.0)


def test_the_snapping_does_not_follow_the_zoom(editor, item):
    """The sheet is in millimetres however close it happens to be held."""

    landed = []
    for _ in range(20):
        editor.zoom_out()
        item.setPos(QPointF(47.4, 62.6))
        landed.append((editor.zoom, item.pos()))
    for _ in range(40):
        editor.zoom_in()
        item.setPos(QPointF(47.4, 62.6))
        landed.append((editor.zoom, item.pos()))

    assert all(position == QPointF(47.0, 63.0) for _, position in landed)
    assert min(zoom for zoom, _ in landed) < 0.2
    assert max(zoom for zoom, _ in landed) > 4.0


def test_an_item_cannot_be_dragged_off_the_sheet(editor, item):
    """The whole of it stays on the paper, not merely its centre."""

    sheet = editor.scene().sceneRect()
    reach = item.boundingRect()

    item.setPos(QPointF(-500.0, -500.0))
    assert item.pos() == QPointF(-reach.left(), -reach.top())

    item.setPos(QPointF(sheet.right() + 500.0, sheet.bottom() + 500.0))
    assert item.pos() == QPointF(
        sheet.right() - reach.right(), sheet.bottom() - reach.bottom()
    )


def test_an_item_follows_the_sheet_when_the_page_changes(editor, item):
    """The sheet is a whole number of pages, so a smaller page is a smaller sheet."""

    editor.set_page(QSizeF(100.0, 100.0))
    sheet = editor.scene().sceneRect()
    item.setPos(QPointF(9000.0, 9000.0))

    assert item.pos().x() < sheet.right()
    assert item.pos().y() < sheet.bottom()


def test_an_item_is_something_drawn_on_the_sheet(editor, item):
    """Unlike a guide: the note over an empty sheet goes as soon as one lands."""

    assert editor.view.has_content()


# ----------------------------------------------------------------------
# Dragging one out of the Libraries pane
# ----------------------------------------------------------------------


def test_dropping_an_element_puts_one_on_the_sheet(editor, element):
    """Where it was let go, in the scene rather than in the viewport."""

    spot = QPointF(220.0, 140.0)
    event = drop(editor.view, element_mime_data('pt-petri-net', element), spot)
    scene = editor.view.mapToScene(spot.toPoint())
    dropped = editor.items_of(NetItem)

    assert event.isAccepted()
    assert len(dropped) == 1
    assert dropped[0].pos() == QPointF(
        editor.view.snap(scene.x()), editor.view.snap(scene.y())
    )


def test_a_dropped_item_can_be_moved_afterwards(editor, element):
    """An item put down by a drag is an item like any other."""

    drop(editor.view, element_mime_data('pt-petri-net', element), QPointF(220.0, 140.0))
    dropped = editor.items_of(NetItem)[0]
    dropped.setPos(QPointF(75.0, 55.0))

    assert dropped.pos() == QPointF(75.0, 55.0)


def test_several_items_can_be_dropped(editor, element):
    """A net is more than one of them, and each is its own item."""

    for x in (120.0, 220.0, 320.0):
        drop(
            editor.view,
            element_mime_data('pt-petri-net', element),
            QPointF(x, 140.0),
        )
    dropped = editor.items_of(NetItem)

    assert len(dropped) == 3
    assert len({one.pos().x() for one in dropped}) == 3


def test_the_two_kinds_land_on_the_same_sheet(editor):
    """A net is places and transitions together, told apart by their class."""

    drop(editor.view, element_mime_data('pt-petri-net', 'place'), QPointF(150.0, 140.0))
    drop(
        editor.view,
        element_mime_data('pt-petri-net', 'transition'),
        QPointF(300.0, 140.0),
    )

    assert len(editor.places) == 1
    assert len(editor.transitions) == 1
    assert len(editor.items_of(NetItem)) == 2


def test_dropping_an_element_that_is_not_built_leaves_nothing(editor):
    """Three of the four libraries are offered before they exist."""

    drop(
        editor.view,
        element_mime_data('timed-petri-net', 'timed-transition'),
        QPointF(220.0, 140.0),
    )

    assert editor.items_of(NetItem) == []
    assert not editor.view.has_content()


def test_a_drag_that_is_not_an_element_is_refused(editor):
    """A canvas takes the elements of a library and nothing else.

    It is the drag that is refused rather than the drop: a drag the sheet will
    not take is one the pointer says no to before the button is let go, which is
    what stops a stray drop of text from ever reaching it.
    """

    text = QMimeData()
    text.setText('a place, in words')

    assert not dragged_over(editor.view, text, QPointF(220.0, 140.0)).isAccepted()

    drop(editor.view, text, QPointF(220.0, 140.0))
    assert editor.items_of(NetItem) == []
    assert not editor.view.has_content()


def test_a_drag_of_an_element_is_taken(editor, element):
    """The pointer says as much before the button is let go."""

    data = element_mime_data('pt-petri-net', element)
    event = dragged_over(editor.view, data, QPointF(220.0, 140.0))

    assert event.isAccepted()
    assert event.dropAction() == Qt.DropAction.CopyAction


# ----------------------------------------------------------------------
# What a subclass has to say
# ----------------------------------------------------------------------


def test_the_base_item_draws_nothing_of_its_own():
    """Its shape, its size and its boundary are what a subclass is for."""

    bare = NetItem()

    for call in (
        bare.ports,
        bare.shape,
        lambda: bare.paint_item(None, None),
    ):
        with pytest.raises(NotImplementedError):
            call()


def test_each_shape_says_where_its_own_connecting_points_go(place, transition):
    """A circle is even the whole way round and a bar is not, so one rule for
    both would be good for neither."""

    assert place.ports() != transition.ports()
    assert len(place.ports()) != len(transition.ports())


def test_the_two_shapes_are_not_the_same_size(place, transition):
    """A place is round and a transition is long, so their reaches differ."""

    assert place.boundingRect() != transition.boundingRect()
    assert math.isclose(place.boundingRect().width(), place.boundingRect().height())
    assert transition.boundingRect().width() > transition.boundingRect().height()
