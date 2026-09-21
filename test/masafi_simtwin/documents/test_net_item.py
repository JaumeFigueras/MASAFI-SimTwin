"""Tests for what every item of a net does the same way.

A place is a circle and a transition is a bar, and apart from that they are one
thing: dropped out of the Libraries pane, snapped to the grid by whichever of
its anchors is nearest, held on the paper, and carrying connecting points that are not drawn until the pointer is
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
from PyQt6.QtWidgets import QStyleOptionGraphicsItem

from masafi_simtwin.documents.label import LABEL_GAP
from masafi_simtwin.documents.net_item import (
    PORT_GRAB,
    PORT_RADIUS,
    SELECTED_EXTRA,
    NetItem,
)
from masafi_simtwin.documents.place import Place
from masafi_simtwin.documents.transition import Transition
from masafi_simtwin.library_tree import element_mime_data
from masafi_simtwin.preferences import DEFAULT_LINE_WIDTH
from masafi_simtwin.theme import DARK_COLORS, LIGHT_COLORS, build_palette
from simtwin_core.petri_net import AUTOMATIC, LineStyle

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


def test_an_item_without_a_shape_snaps_by_its_centre_alone():
    """The rule before there were anchors, for anything that declares none."""

    assert NetItem.anchors_for() == (QPointF(0.0, 0.0),)
    assert NetItem.anchors_for(vertical=True) == (QPointF(0.0, 0.0),)


def test_an_item_s_anchors_are_its_centre_and_some_of_its_connecting_points(item):
    """So an item snapped by an edge puts an arc's end on the grid.

    The centre is first, since a tie goes to the first anchor, and every other
    anchor is a point an arc can be joined at.
    """

    anchors = item.snap_anchors()

    assert anchors[0] == QPointF(0.0, 0.0)
    assert len(anchors) > 1
    assert all(anchor in item.ports() for anchor in anchors[1:])


def test_an_item_is_snapped_by_the_anchor_nearest_the_grid(editor, item):
    """At a step its shape is not a whole number of steps across.

    A place's rim and a transition's ends are both five and eight millimetres
    out, neither a multiple of three, and for both the right-hand anchor asks
    for the least move: it lands on a crossing and the centre does not.  The
    item was put down at a millimetre, so the new step reaches what is already
    on the sheet the next time it is moved.
    """

    editor.view.set_grid_step(3.0)
    item.setPos(QPointF(10.4, 20.2))

    assert item.pos() == QPointF(10.0, 21.0)
    assert item.pos().x() % 3.0 != 0.0


def test_an_item_placed_is_put_exactly_where_it_is_told(editor, item):
    """A record of where it was is not a drag, and is not snapped."""

    editor.view.set_grid_step(3.0)
    item.place(QPointF(40.2, 40.7))

    assert item.pos() == QPointF(40.2, 40.7)


def test_an_item_placed_is_still_held_on_the_paper(editor, item):
    """The paper is the sheet's rule, not the grid's."""

    reach = item.boundingRect()
    item.place(QPointF(-500.0, -500.0))

    assert item.pos() == QPointF(-reach.left(), -reach.top())


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

# ----------------------------------------------------------------------
# What is written beside an item
# ----------------------------------------------------------------------


def test_an_item_is_labelled_with_its_name_and_its_description(item):
    """One box, reading ``Name: Description``."""

    item.description = 'Fill a bottle'

    assert item.label_text() == f'{item.name}: Fill a bottle'
    assert item.label.text == item.label_text()


def test_an_item_nobody_described_is_labelled_with_its_name_alone(item):
    """No stray colon at the end of it."""

    assert item.label_text() == item.name
    assert item.name


def test_an_item_with_no_name_is_labelled_with_nothing(item):
    """Which is an item made outside the editor; the editor names every item it
    puts on the sheet."""

    item.name = ''

    assert item.label_text() == ''
    assert item.label.is_empty()
    assert item.label_rect().isEmpty()


def test_the_caption_is_a_child_and_not_part_of_the_item(item):
    """It is drawn in the item's coordinates, so it follows the item about the
    sheet of its own accord; and it is outside the item's shape and rectangle,
    so clicking or dragging a caption is not clicking or dragging the thing it
    captions."""

    item.description = 'Bottles waiting to be filled'
    box = item.label_rect()

    assert item.label.parentItem() is item
    assert not box.isEmpty()
    assert not item.boundingRect().intersects(box)
    assert not item.shape().intersects(box)


def test_the_caption_goes_where_the_item_goes(item):
    """A child moves with its parent, and nothing has to be told."""

    was = item.label.scenePos()

    item.setPos(item.pos() + QPointF(30.0, 20.0))

    assert item.label.scenePos() == was + QPointF(30.0, 20.0)
    assert item.label.pos() == item.label_anchor(item.label.size)


def test_the_label_stands_off_the_item_rather_than_touching_it(item):
    """A caption against the rim of a place would read as part of it."""

    room = item.boundingRect()
    box = item.label_rect()

    assert not room.intersects(box)
    assert min(
        abs(box.top() - room.bottom()), abs(box.left() - room.right())
    ) == pytest.approx(LABEL_GAP)


def test_changing_the_name_or_the_description_writes_the_label_again(item):
    """The box is as big as what is in it, so it is laid out anew rather than
    kept from the last time — and it is put where the new box belongs."""

    was = item.label_rect()

    item.description = 'Bottles waiting to be filled, capped and taken away'

    assert item.label_rect() != was
    assert item.label_rect().height() > was.height()

    item.description = ''

    assert item.label_rect() == was


# ----------------------------------------------------------------------
# How thick a line is, and what colour
# ----------------------------------------------------------------------


def option_for(colors):
    """Give what a painter is told about a scheme.

    Parameters
    ----------
    colors : masafi_simtwin.theme.ThemeColors
        The scheme.

    Returns
    -------
    PyQt6.QtWidgets.QStyleOptionGraphicsItem
        The option, carrying that scheme's palette.
    """

    option = QStyleOptionGraphicsItem()
    option.palette = build_palette(colors)
    return option


def test_an_item_is_drawn_at_the_default_width_until_it_is_given_one(item):
    """Which is what every item on every sheet was drawn with before there were
    styles at all."""

    assert item.line_appearance().width == DEFAULT_LINE_WIDTH == 0.3
    assert item.outline_width() == DEFAULT_LINE_WIDTH


def test_a_selected_item_is_drawn_a_fixed_amount_thicker(item):
    """Decided with Jaume: the width and a fixed 0.3 mm more, whatever the width
    is — so a thin line and a thick one both say the same thing by thickening."""

    was = item.outline_width()
    item.setSelected(True)

    assert SELECTED_EXTRA == 0.3
    assert item.outline_width() == pytest.approx(was + SELECTED_EXTRA)


def test_a_width_of_the_items_own_is_what_it_is_drawn_with(item):
    """And the selected rule follows it rather than a constant."""

    item.line_style = LineStyle(AUTOMATIC, 1.5)

    assert item.outline_width() == 1.5

    item.setSelected(True)
    assert item.outline_width() == pytest.approx(1.5 + SELECTED_EXTRA)


@pytest.mark.parametrize('colors', [LIGHT_COLORS, DARK_COLORS], ids=['light', 'dark'])
def test_an_item_is_outlined_in_the_colour_it_was_given(item, colors):
    """*Automatic* is the sheet's own ink; a colour chosen is that colour in
    either scheme."""

    option = option_for(colors)

    assert item.outline_colour(option) == QColor(colors.text)

    item.line_style = LineStyle('#aa0000', DEFAULT_LINE_WIDTH)
    assert item.outline_colour(option) == QColor('#aa0000')


@pytest.mark.parametrize('colors', [LIGHT_COLORS, DARK_COLORS], ids=['light', 'dark'])
def test_a_selected_item_keeps_the_accent_whatever_colour_it_was_given(item, colors):
    """As agreed: a thing drawn in its own red while it is in hand would say
    nothing about being in hand."""

    item.line_style = LineStyle('#aa0000', DEFAULT_LINE_WIDTH)
    item.setSelected(True)

    assert item.outline_colour(option_for(colors)) == QColor(colors.accent)


def test_the_room_an_item_takes_follows_the_width_it_is_drawn_with(item):
    """A line three millimetres thick reaches a millimetre and a half beyond the
    shape, and the rectangle the view repaints has to know it."""

    was = item.boundingRect()

    item.line_style = LineStyle(AUTOMATIC, 3.0)
    item.restyle()

    assert item.boundingRect().width() > was.width()
    assert item.boundingRect().height() > was.height()
    assert item.boundingRect().contains(item.shape().boundingRect())


def test_the_room_does_not_change_when_an_item_is_selected(item):
    """It is measured from the *thickest* the item is ever drawn, so selecting
    one is a repaint and never a change of geometry — which Qt would have to be
    told about separately."""

    was = item.boundingRect()

    item.setSelected(True)

    assert item.boundingRect() == was


def test_the_label_is_not_held_on_the_sheet_the_way_the_item_is(editor, item):
    """What must stay on the paper is the shape: how far a node can be dragged
    cannot depend on how long its description is, or typing one would be a thing
    that moves nodes."""

    item.description = 'Bottles waiting to be filled, capped and taken away'
    sheet = editor.scene().sceneRect()
    room = item.boundingRect()

    item.setPos(QPointF(sheet.right() + 500.0, sheet.bottom() + 500.0))

    assert item.pos() == QPointF(sheet.right() - room.right(), sheet.bottom() - room.bottom())
