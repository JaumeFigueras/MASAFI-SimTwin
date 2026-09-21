"""Tests for the box of text that says what something on the sheet is.

What a *node* does with its caption is in :mod:`test_net_item`; what is here is
the box itself: how big it is, what can be taken hold of, how it is drawn in
either scheme, and the one rule that makes it safe to have on the sheet at all —
a caption is selected by clicking it and by nothing else.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QLineF, QPointF, Qt
from PyQt6.QtGui import QColor, QMouseEvent, QPainterPath
from PyQt6.QtWidgets import QApplication

from masafi_simtwin.documents.ink import HANDLE_GRAB, line_height
from masafi_simtwin.documents.label import LABEL_PADDING, MIN_LABEL_WIDTH, Label
from masafi_simtwin.theme import DARK_COLORS, LIGHT_COLORS
from simtwin_core.petri_net import TextStyle

#: The two schemes every pixel test is run against.
SCHEMES = [LIGHT_COLORS, DARK_COLORS]

#: What each is called, so a failure names the scheme it happened in.
SCHEME_NAMES = ['light', 'dark']


def on_the_grid(label: Label, step: float = 1.0) -> list[QPointF]:
    """Give the points of a box that sit on a crossing of the sheet's grid.

    Parameters
    ----------
    label : masafi_simtwin.documents.label.Label
        The box, on a sheet.
    step : float, optional
        The grid step, in millimetres.

    Returns
    -------
    list of PyQt6.QtCore.QPointF
        The anchors, in the label's own coordinates, whose place on the sheet
        is a whole number of steps along and down.
    """

    def whole(value: float) -> bool:
        return abs(value / step - round(value / step)) < 1e-6

    return [
        anchor
        for anchor in label.snap_anchors()
        if whole(label.mapToScene(anchor).x()) and whole(label.mapToScene(anchor).y())
    ]


def by_its_corner(label: Label, corner: QPointF) -> QPointF:
    """Give where to drag a box so its frame's top left corner is a hair off a crossing.

    Parameters
    ----------
    label : masafi_simtwin.documents.label.Label
        The box, on a sheet.
    corner : PyQt6.QtCore.QPointF
        The crossing, in scene millimetres.

    Returns
    -------
    PyQt6.QtCore.QPointF
        Where to put the box's centre, in its owner's coordinates, so that its
        top left corner is a hundredth off ``corner`` each way.  Another point
        of the box is nearer a crossing only if a side happens to be within two
        hundredths of a whole millimetre long; a side is as long as the font
        makes it, and five hundredths was not enough — the 2.9352 mm box of
        ``P1`` put its top right corner nearer.
    """

    top_left = label.frame().topLeft()
    return label.parentItem().mapFromScene(corner + QPointF(0.01, 0.01) - top_left)


def lands_by_its_top_left_corner(label: Label, corner: QPointF) -> bool:
    """Say whether a frame's top left corner is on a crossing and its centre is not.

    Parameters
    ----------
    label : masafi_simtwin.documents.label.Label
        The box, on a sheet.
    corner : PyQt6.QtCore.QPointF
        The crossing it was aimed at, in scene millimetres.

    Returns
    -------
    bool
        Whether it was snapped by that corner rather than by its centre.
    """

    landed = label.mapToScene(label.frame().topLeft())
    return (
        landed.x() == pytest.approx(corner.x(), abs=1e-9)
        and landed.y() == pytest.approx(corner.y(), abs=1e-9)
        and QPointF(0.0, 0.0) not in on_the_grid(label)
    )


def press(view, label: Label) -> None:
    """Press the label through the view, the way a person clicking it does.

    A scene hit-tests a mouse event through its **global** position, so the
    press has to be built the way :mod:`test_arc` builds one that must reach an
    item.  A rubber band selects through the scene and sends no press at all,
    which is the whole of what tells the two apart.

    Parameters
    ----------
    view : masafi_simtwin.documents.canvas.CanvasView
        The view the label is shown in.
    label : masafi_simtwin.documents.label.Label
        The label to press.
    """

    spot = QPointF(view.mapFromScene(label.scenePos()))
    view.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            spot,
            QPointF(view.viewport().mapToGlobal(spot.toPoint())),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )


def repainted(scene, act) -> QPainterPath:
    """Give the part of the sheet the scene asked to have painted again.

    The same question :func:`test_arc.repainted` asks, for the same reason: a
    fresh painting of the sheet is right either way, and a caption left in the
    wrong ink is a fault in the *region* the view is told to repaint.  The
    connection is taken off again before this returns, since the scene outlives
    the test.

    Parameters
    ----------
    scene : PyQt6.QtWidgets.QGraphicsScene
        The scene.
    act : collections.abc.Callable
        What to do to it.

    Returns
    -------
    list of PyQt6.QtCore.QRectF
        Every rectangle reported, in scene millimetres.
    """

    seen = []
    watch = scene.changed.connect(seen.extend)
    try:
        QApplication.processEvents()
        seen.clear()
        act()
        QApplication.processEvents()
    finally:
        scene.changed.disconnect(watch)
    return list(seen)


def covers(rects, area) -> bool:
    """Say whether one of the rectangles repainted holds the whole of an area.

    Rectangles rather than a path united out of them: a path does not count a
    rectangle that shares its edges as inside it, and the scene reports a
    caption repainted by exactly the caption's own rectangle.

    Parameters
    ----------
    rects : list of PyQt6.QtCore.QRectF
        What :func:`repainted` gave.
    area : PyQt6.QtCore.QRectF
        What has to have been repainted.

    Returns
    -------
    bool
        Whether it was.
    """

    return any(rect.contains(area) for rect in rects)


def band(view, label: Label) -> None:
    """Sweep a rubber band over the whole sheet, the way a drag over it does.

    Both halves of the gesture: the press on the bare sheet that starts a band,
    which is what puts the last selection down, and the ``setSelectionArea``
    that is what a band selection comes to.

    Parameters
    ----------
    view : masafi_simtwin.documents.canvas.CanvasView
        The view the band is drawn in.
    label : masafi_simtwin.documents.label.Label
        A label on the scene to be swept.
    """

    scene = label.scene()
    spot = QPointF(view.mapFromScene(scene.sceneRect().bottomRight()))
    view.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            spot,
            QPointF(view.viewport().mapToGlobal(spot.toPoint())),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    area = QPainterPath()
    area.addRect(scene.sceneRect())
    scene.setSelectionArea(area)


# ----------------------------------------------------------------------
# The box
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# Repainting what an owner's selection changes
# ----------------------------------------------------------------------


def test_selecting_a_node_repaints_its_caption(editor, place):
    """The caption turns the accent with its node, and lies outside the node's
    rectangle — which is all Qt repaints of its own accord."""

    area = place.label.sceneBoundingRect()

    region = repainted(editor.scene(), lambda: place.setSelected(True))

    assert covers(region, area)


def test_deselecting_a_node_repaints_its_caption(editor, place):
    """What was reported: a caption left in the accent reads as still selected."""

    place.setSelected(True)
    area = place.label.sceneBoundingRect()

    region = repainted(editor.scene(), lambda: place.setSelected(False))

    assert covers(region, area)


@pytest.mark.parametrize('selected', [True, False], ids=['selected', 'deselected'])
def test_an_arcs_weight_is_repainted_with_its_arc(editor, place, transition, selected):
    """The number is a caption of the arc, drawn in the accent with it.

    For an arc it is ``prepareGeometryChange()`` on ``ItemSelectedChange`` that
    does it — Qt invalidates an item's children with it — and the explicit
    ``label.update()`` beside it is a second word for the same thing; the test
    fails only when both are gone, which is what was checked.
    """

    arc = editor.add_arc(place, transition)
    arc.weight = 3
    arc.setSelected(not selected)
    area = arc.label.sceneBoundingRect()

    region = repainted(editor.scene(), lambda: arc.setSelected(selected))

    assert covers(region, area)


def test_deselecting_a_caption_repaints_where_its_frame_and_handles_were(editor, place):
    """A selected caption is bigger than an unselected one — its handles are in
    its rectangle only while it is selected — so letting go of it repaints what it
    was, not what it becomes."""

    place.label.select()
    area = place.label.sceneBoundingRect()

    region = repainted(editor.scene(), lambda: place.label.setSelected(False))

    assert covers(region, area)


def test_where_the_owner_puts_a_label_is_taken_exactly(place):
    """Neither snapped nor held on the paper: a box laid out under a place is
    already where it belongs."""

    place.label.place(QPointF(0.35, -2.7))

    assert place.label.pos() == QPointF(0.35, -2.7)


def test_a_box_snaps_by_its_centre_its_sides_and_its_corners(place):
    """Nine points of the frame a person sees, the centre first since a tie goes
    to the first."""

    box = place.label.frame()

    assert place.label.snap_anchors() == (
        QPointF(0.0, 0.0),
        QPointF(0.0, box.top()),
        QPointF(box.right(), 0.0),
        QPointF(0.0, box.bottom()),
        QPointF(box.left(), 0.0),
        box.topLeft(),
        box.topRight(),
        box.bottomRight(),
        box.bottomLeft(),
    )


def test_the_frame_is_the_box_with_air_round_it(place):
    """What is drawn while selected, and what a caption is lined up by."""

    box = place.label.box()

    assert place.label.frame() == box.adjusted(
        -LABEL_PADDING, -LABEL_PADDING, LABEL_PADDING, LABEL_PADDING
    )


def test_a_label_with_nothing_to_say_snaps_by_its_centre_alone(place):
    """It has no box to have corners."""

    place.name = ''

    assert place.label.snap_anchors() == (QPointF(0.0, 0.0),)


def test_a_label_dragged_lands_a_point_of_its_box_on_the_grid(place):
    """A drag is any move that is not :meth:`Label.place` — which is how Qt moves
    one under the hand.  A caption's box is as tall as its font makes it, never a
    round number, so snapping its centre would leave every edge off the grid."""

    place.label.setPos(by_its_corner(place.label, QPointF(110.0, 90.0)))

    assert lands_by_its_top_left_corner(place.label, QPointF(110.0, 90.0))


def test_a_label_lands_on_the_sheet_s_grid_not_a_step_from_its_node(editor, place):
    """Its node may be off the grid — read from a file, or snapped by an edge —
    and the box is lined up with the sheet, not with the node."""

    place.place(QPointF(100.4, 80.3))
    place.label.setPos(QPointF(3.4, 8.6))

    assert on_the_grid(place.label)
    assert place.label.pos() != QPointF(3.0, 9.0), 'what rounding the offset gave'


def test_a_label_is_moved_by_the_least_any_point_of_its_box_asks_for(editor, place):
    """At a step of 3 mm, where the nine points ask for nine different moves."""

    editor.view.set_grid_step(3.0)
    wanted = QPointF(3.4, 8.6)
    origin = place.scenePos()

    place.label.setPos(wanted)
    moved = QLineF(wanted, place.label.pos()).length()

    assert on_the_grid(place.label, 3.0)
    assert moved > 0.0
    for anchor in place.label.snap_anchors():
        alone = editor.view.snap_point(wanted, [anchor], origin)
        assert moved <= QLineF(wanted, alone).length() + 1e-9


def test_an_offset_is_kept_as_the_snap_gave_it(editor, place):
    """Worked out in the node's frame, not mapped to the sheet and back.

    With the node at 100.4 a round trip through the sheet adds and takes away
    100.4, which is not exact in binary, and the offset written to the file
    would carry the error in its last digits.
    """

    place.place(QPointF(100.4, 80.3))
    place.label.setPos(QPointF(3.4, 8.6))
    x, y = place.label.pos().x(), place.label.pos().y()

    assert (x, y) == (round(x, 9), round(y, 9))


def test_an_arc_s_weight_snaps_by_its_box_as_a_caption_does(editor, place, transition):
    """The weight is the same box, hung on an arc at the sheet's origin."""

    arc = editor.add_arc(place, transition)
    editor.set_weight([arc.uuid], 3)

    arc.label.setPos(by_its_corner(arc.label, QPointF(120.0, 60.0)))

    assert lands_by_its_top_left_corner(arc.label, QPointF(120.0, 60.0))


def test_a_label_dragged_off_the_sheet_is_held_on_it_whole(editor, place):
    """The box, not only its centre, as a node is held."""

    sheet = editor.view.sceneRect()

    place.label.setPos(place.mapFromScene(QPointF(-500.0, -500.0)))

    box = place.label.mapRectToScene(place.label.box())
    assert box.left() >= sheet.left() - 1e-9
    assert box.top() >= sheet.top() - 1e-9
    assert box.left() - sheet.left() < 1.0


def test_a_box_given_a_width_is_that_wide_and_wraps_to_it(place):
    """A box nobody resized fits its text; a resized one is the box drawn, and
    a narrower one is taller, the height following the lines."""

    place.description = 'Bottles waiting to be filled'
    fitted = place.label.size

    place.label_width = 50.0
    assert place.label.size.width() == 50.0
    assert place.label.size.height() == pytest.approx(line_height(place.appearance()))

    place.label_width = 12.0
    assert place.label.size.width() == 12.0
    assert place.label.size.height() > fitted.height()


def test_a_label_carries_handles_only_while_it_is_selected(editor, place):
    """And they are part of what can be taken hold of."""

    assert place.label.handles() == {}

    place.label.select()

    handles = place.label.handles()
    assert sorted(handles) == [-1, 1]
    assert handles[1].x() == pytest.approx(place.label.size.width() / 2.0 + LABEL_PADDING)
    assert place.label.shape().contains(handles[1] + QPointF(HANDLE_GRAB * 0.9, 0.0))
    assert place.label.handle_at(handles[-1] + QPointF(0.2, 0.3)) == -1


def test_a_box_is_never_squeezed_below_its_narrowest(editor, place):
    """Dragging a side past the other one leaves a narrow box, not a negative one."""

    place.label.select()

    place.label.resize_to(1, place.label.pos().x() - 20.0)

    assert place.label_width == MIN_LABEL_WIDTH


def test_a_label_says_what_it_is_given(place):
    """And lays the box out again when it changes."""

    label = place.label
    was = label.size

    label.text = 'A rather longer caption than the one it had'

    assert label.text == 'A rather longer caption than the one it had'
    assert label.size.height() > was.height()


def test_a_box_is_centred_on_the_labels_own_position(place):
    """Its owner puts it somewhere by its middle, so that is where its middle
    is."""

    assert place.label.box().center() == QPointF(0.0, 0.0)
    assert place.label.box().size() == place.label.size


def test_a_label_with_nothing_to_say_is_nothing_at_all(place):
    """No box, nothing painted, and nothing to take hold of."""

    place.label.text = ''

    assert place.label.is_empty()
    assert place.label.box().isEmpty()
    assert place.label.boundingRect().isEmpty()
    assert place.label.shape().isEmpty()


def test_a_label_is_taken_hold_of_by_its_box_and_a_little_air(place):
    """A press within the padding counts, so a caption is not a target that has
    to be hit exactly."""

    box = place.label.box()

    assert place.label.shape().contains(box.center())
    assert place.label.shape().contains(
        QPointF(box.right() + LABEL_PADDING / 2.0, box.center().y())
    )
    assert not place.label.shape().contains(
        QPointF(box.right() + LABEL_PADDING * 2.0, box.center().y())
    )


def test_a_label_paints_inside_its_frame(place):
    """The rectangle holds the dashed frame drawn round a selected box, or
    letting go of one would leave the frame on the sheet."""

    assert place.label.boundingRect().contains(place.label.shape().boundingRect())


# ----------------------------------------------------------------------
# Taking hold of one
# ----------------------------------------------------------------------


def test_a_label_is_selected_by_pressing_it(editor, place):
    """Which is the whole of how a person takes hold of a caption."""

    press(editor.view, place.label)

    assert place.label.isSelected()


def test_a_rubber_band_never_picks_a_label_up(editor, place):
    """A band is drawn over a net to pick up what is drawn; a caption says what
    a thing is called, and a band that swept up half the captions on a sheet
    would make *Delete* look dangerous when it is not."""

    band(editor.view, place.label)

    assert place.isSelected()
    assert not place.label.isSelected()


def test_a_band_puts_down_a_caption_that_was_in_hand(editor, place):
    """The press that starts a band lands on the bare sheet, and a press on the
    bare sheet puts the selection down — captions included.  Refusing to be
    picked up is not refusing to be let go of."""

    press(editor.view, place.label)
    assert place.label.isSelected()

    band(editor.view, place.label)

    assert not place.label.isSelected()


def test_a_label_is_put_down_when_the_scene_clears_the_selection(editor, place):
    """Refusing a selection is not refusing to let go of one."""

    press(editor.view, place.label)
    place.scene().clearSelection()

    assert not place.label.isSelected()


def test_a_label_with_nothing_to_say_is_put_down(editor, place):
    """A caption that has just lost its text is a caption nobody can see, and an
    invisible thing must not stay in hand."""

    press(editor.view, place.label)
    place.name = ''

    assert not place.label.isSelected()


# ----------------------------------------------------------------------
# How it is drawn, in both schemes
# ----------------------------------------------------------------------


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_label_is_written_in_the_sheets_ink(place, ink, colors):
    """The ordinary ink, with nothing selected."""

    written = ink.window(ink.painted(place.label, colors), 0.0, 0.0, 1.0)

    assert ink.holds(written, QColor(colors.text))
    assert not ink.holds(written, QColor(colors.accent))


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_caption_of_a_selected_item_is_the_accent(place, ink, colors):
    """So that a thing and what it is called read as one thing."""

    place.setSelected(True)
    written = ink.window(ink.painted(place.label, colors), 0.0, 0.0, 1.0)

    assert ink.holds(written, QColor(colors.accent))


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_selected_label_is_the_accent_and_is_framed(editor, place, ink, colors):
    """The frame is what tells *this caption is in hand* from *the thing it
    belongs to is in hand*, both being drawn in the accent.

    The frame is a **hairline**, so it is asked after with
    :meth:`Ink.leans` rather than :meth:`Ink.holds`: one device pixel of dashed
    line lands where the box's geometry puts it, and a box half a millimetre
    taller moves it onto a pixel boundary, where it is split over two rows and
    neither is within a fixed tolerance of the accent.  What is true either way
    is that it is the accent rather than the paper.
    """

    press(editor.view, place.label)
    box = place.label.box()
    image = ink.painted(place.label, colors)

    written = ink.window(image, 0.0, 0.0, 1.0)
    above = ink.window(image, 0.0, box.top() - LABEL_PADDING, 1.0)

    assert ink.holds(written, QColor(colors.accent))
    assert ink.leans(above, QColor(colors.accent), QColor(colors.editor))


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_an_unselected_label_carries_no_frame(place, ink, colors):
    """A frame on every caption would be a sheet of boxes."""

    box = place.label.box()
    above = ink.window(
        ink.painted(place.label, colors), 0.0, box.top() - LABEL_PADDING, 1.0
    )

    assert not ink.holds(above, QColor(colors.accent))
    assert not ink.holds(above, QColor(colors.text))


def test_a_label_can_be_taken_hold_of_outright(editor, place):
    """The other door in, for whatever asks for a selection rather than
    aiming at one."""

    place.label.select()

    assert place.label.isSelected()


# ----------------------------------------------------------------------
# Lettered in its owner's style
# ----------------------------------------------------------------------


def test_a_label_is_lettered_in_the_style_its_owner_resolves(place):
    """The label is dumb: what it is written in is set on it, as its text is."""

    assert place.label.style == place.appearance()
    assert place.label.size.height() == pytest.approx(line_height(place.appearance()))


def test_a_style_of_the_items_own_letters_its_caption(place):
    """Which is the whole of what giving a place an appearance of its own means."""

    was = place.label.size.height()

    place.text_style = TextStyle(place.appearance().font, 6.0)
    place.show_label()

    assert place.label.style.size == 6.0
    assert place.label.size.height() > was


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_caption_with_a_colour_of_its_own_is_written_in_it(place, ink, colors):
    """A colour chosen is that colour in either scheme, unlike *Automatic*."""

    place.text_style = TextStyle(place.appearance().font, 2.4, colour='#aa0000')
    place.show_label()

    written = ink.window(ink.painted(place.label, colors), 0.0, 0.0, 1.0)

    assert ink.holds(written, QColor('#aa0000'))


def test_new_defaults_reach_the_captions_already_drawn(editor, place):
    """A caption is **laid out** rather than merely painted, so a repaint alone
    would leave the old box on the sheet: the sheet is lettered again."""

    from masafi_simtwin.preferences import Preferences

    was = place.label.size.height()
    Preferences().set_value('petri_net/font_size', 6.0)

    editor.restyle()

    assert place.label.size.height() > was
    assert place.label.style.size == 6.0


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_selected_caption_of_its_own_colour_is_still_the_accent(place, ink, colors):
    """The selection keeps the accent, as agreed, whatever the caption's colour."""

    place.text_style = TextStyle(place.appearance().font, 2.4, colour='#aa0000')
    place.show_label()
    place.setSelected(True)

    written = ink.window(ink.painted(place.label, colors), 0.0, 0.0, 1.0)

    assert ink.holds(written, QColor(colors.accent))
