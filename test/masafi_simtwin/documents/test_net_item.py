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

from PyQt6.QtGui import QColor

from masafi_simtwin.documents.net_item import (
    LABEL_GAP,
    LABEL_LINE_HEIGHT,
    LABEL_WIDTH,
    PORT_GRAB,
    PORT_RADIUS,
    NetItem,
    text_block,
)
from masafi_simtwin.documents.place import Place
from masafi_simtwin.documents.transition import Transition
from masafi_simtwin.library_tree import element_mime_data
from masafi_simtwin.theme import DARK_COLORS, LIGHT_COLORS

#: The two schemes every pixel test is run against.
SCHEMES = [LIGHT_COLORS, DARK_COLORS]

#: What each is called, so a failure names the scheme it happened in.
SCHEME_NAMES = ['light', 'dark']

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
    near = QPointF(on.x(), on.y() + PORT_GRAB * 0.5)
    far = QPointF(on.x(), on.y() + PORT_GRAB * 2.0)

    assert item.port_at(near) is not None
    assert item.port_at(far) is None


def test_a_connecting_point_is_aimed_at_beyond_where_it_is_drawn(item):
    """What is drawn is a mark; what is aimed at is wider than the mark."""

    assert PORT_GRAB > PORT_RADIUS

    item.setPos(QPointF(50.0, 40.0))
    on = item.scene_ports()[0]
    outside_the_ring = QPointF(on.x(), on.y() + (PORT_RADIUS + PORT_GRAB) / 2.0)

    assert item.port_at(outside_the_ring) is not None


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
    """Which is what the connecting points are measured from.  It is the shape's
    own room that is centred on it; the bounding rectangle holds the label as
    well, which hangs to one side."""

    assert item.pos() == QPointF(100.0, 80.0)
    assert item.item_rect().center() == QPointF(0.0, 0.0)


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
    reach = item.item_rect()

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

    assert place.item_rect() != transition.item_rect()
    assert math.isclose(place.item_rect().width(), place.item_rect().height())
    assert transition.item_rect().width() > transition.item_rect().height()


# ----------------------------------------------------------------------
# What is written on the sheet
# ----------------------------------------------------------------------


def test_text_is_written_a_height_on_the_paper_centred_on_nought():
    """The weight of an arc and the tokens of a place are written the same way."""

    from masafi_simtwin.documents.net_item import glyph_path

    written = glyph_path('42', 3.0).boundingRect()

    assert written.height() == pytest.approx(3.0, abs=0.01)
    assert written.center().x() == pytest.approx(0.0, abs=0.01)
    assert written.center().y() == pytest.approx(0.0, abs=0.01)


def test_text_too_wide_for_its_room_is_narrowed_to_it():
    """Keeping its proportions, so it grows no taller than asked."""

    from masafi_simtwin.documents.net_item import glyph_path

    tall = glyph_path('1234567', 4.0).boundingRect()
    narrowed = glyph_path('1234567', 4.0, 7.0).boundingRect()

    assert narrowed.width() == pytest.approx(7.0, abs=0.01)
    assert narrowed.height() / narrowed.width() == pytest.approx(tall.height() / tall.width(), rel=0.01)


def test_text_that_draws_nothing_is_an_empty_path():
    """Nothing to scale."""

    from masafi_simtwin.documents.net_item import glyph_path

    assert glyph_path('', 3.0).isEmpty()


# ----------------------------------------------------------------------
# Laying out a block of text
# ----------------------------------------------------------------------


def test_a_block_of_one_line_is_one_line_high():
    """The font's own line height, scaled to millimetres, so a block is as many
    lines tall as it has lines."""

    _glyphs, box = text_block('P1', LABEL_WIDTH)

    assert box.height() == pytest.approx(LABEL_LINE_HEIGHT)
    assert 0.0 < box.width() <= LABEL_WIDTH


def test_a_block_goes_onto_another_line_rather_than_growing_wider():
    """Which is what makes a label a box rather than a line of text running off
    across the sheet."""

    _glyphs, box = text_block(
        'P1: bottles waiting to be filled, capped and taken away', LABEL_WIDTH
    )

    assert box.width() <= LABEL_WIDTH
    assert box.height() == pytest.approx(LABEL_LINE_HEIGHT * round(box.height() / LABEL_LINE_HEIGHT))
    assert box.height() > LABEL_LINE_HEIGHT * 2


def test_a_word_wider_than_the_whole_box_is_broken():
    """Rather than left to hang off the side, where it would run across whatever
    is drawn beside it."""

    _glyphs, box = text_block('P1: ' + 'x' * 200, LABEL_WIDTH)

    assert box.width() <= LABEL_WIDTH
    assert box.height() > LABEL_LINE_HEIGHT


def test_a_block_is_centred_on_nought_by_its_box_and_not_by_its_ink():
    """So where a label sits does not depend on which letters happen to be in
    it: a line with a ``g`` in it hangs below the line, and that must not move
    the box."""

    plain, box = text_block('nn nn', LABEL_WIDTH)
    tails, other = text_block('gg gg', LABEL_WIDTH)

    assert box.height() == other.height()
    assert plain.boundingRect().center().y() < tails.boundingRect().center().y()
    assert abs(plain.boundingRect().center().y()) < LABEL_LINE_HEIGHT


def test_a_block_of_nothing_is_nothing():
    """An item made outside the editor has no name, and writes nothing."""

    glyphs, box = text_block('', LABEL_WIDTH)

    assert glyphs.isEmpty()
    assert box.isEmpty()


# ----------------------------------------------------------------------
# What is written beside an item
# ----------------------------------------------------------------------


def test_an_item_is_labelled_with_its_name_and_its_description(item):
    """One box, reading ``Name: Description``."""

    item.description = 'Fill a bottle'

    assert item.label_text() == f'{item.name}: Fill a bottle'


def test_an_item_nobody_described_is_labelled_with_its_name_alone(item):
    """No stray colon at the end of it."""

    assert item.label_text() == item.name
    assert item.name


def test_an_item_with_no_name_is_labelled_with_nothing(item):
    """Which is an item made outside the editor; the editor names every item it
    puts on the sheet."""

    item.name = ''

    assert item.label_text() == ''
    assert item.label_rect().isEmpty()
    assert item.boundingRect() == item.item_rect()


def test_the_label_is_drawn_inside_the_item_but_is_not_part_of_it(item):
    """The bounding rectangle holds the box, so it is painted and repainted;
    the shape does not, so clicking or dragging a caption is not clicking or
    dragging the thing it captions."""

    item.description = 'Bottles waiting to be filled'
    box = item.label_rect()

    assert not box.isEmpty()
    assert item.boundingRect() == item.item_rect().united(box)
    assert not item.shape().intersects(box)


def test_the_label_stands_off_the_item_rather_than_touching_it(item):
    """A caption against the rim of a place would read as part of it."""

    room = item.item_rect()
    box = item.label_rect()

    assert not room.intersects(box)
    assert min(
        abs(box.top() - room.bottom()), abs(box.left() - room.right())
    ) == pytest.approx(LABEL_GAP)


def test_changing_the_name_or_the_description_writes_the_label_again(item):
    """The box is as big as what is in it, so it is worked out anew rather than
    kept from the last time."""

    was = item.label_rect()

    item.description = 'Bottles waiting to be filled, capped and taken away'

    assert item.label_rect() != was
    assert item.label_rect().height() > was.height()

    item.description = ''

    assert item.label_rect() == was


def test_the_label_is_not_held_on_the_sheet_the_way_the_item_is(editor, item):
    """What must stay on the paper is the shape: how far a node can be dragged
    cannot depend on how long its description is, or typing one would be a thing
    that moves nodes."""

    item.description = 'Bottles waiting to be filled, capped and taken away'
    sheet = editor.scene().sceneRect()
    room = item.item_rect()

    item.setPos(QPointF(sheet.right() + 500.0, sheet.bottom() + 500.0))

    assert item.pos() == QPointF(sheet.right() - room.right(), sheet.bottom() - room.bottom())


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_the_label_is_written_in_the_items_own_ink(item, ink, colors):
    """The same ink the item is drawn in, and the accent while it is selected,
    so that what belongs to one item reads as one thing."""

    box = item.label_rect()
    reach = min(box.width(), box.height()) / 2.0

    plain = ink.window(
        ink.painted(item, colors), box.center().x(), box.center().y(), reach
    )
    item.setSelected(True)
    chosen = ink.window(
        ink.painted(item, colors), box.center().x(), box.center().y(), reach
    )

    assert ink.holds(plain, QColor(colors.text))
    assert not ink.holds(plain, QColor(colors.accent))
    assert ink.holds(chosen, QColor(colors.accent))
