"""Tests for the box of text that says what something on the sheet is.

What a *node* does with its caption is in :mod:`test_net_item`; what is here is
the box itself: how big it is, what can be taken hold of, how it is drawn in
either scheme, and the one rule that makes it safe to have on the sheet at all —
a caption is selected by clicking it and by nothing else.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QColor, QMouseEvent, QPainterPath

from masafi_simtwin.documents.ink import HANDLE_GRAB, LABEL_LINE_HEIGHT
from masafi_simtwin.documents.label import LABEL_PADDING, MIN_LABEL_WIDTH, Label
from masafi_simtwin.theme import DARK_COLORS, LIGHT_COLORS

#: The two schemes every pixel test is run against.
SCHEMES = [LIGHT_COLORS, DARK_COLORS]

#: What each is called, so a failure names the scheme it happened in.
SCHEME_NAMES = ['light', 'dark']


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


def test_where_the_owner_puts_a_label_is_taken_exactly(place):
    """Neither snapped nor held on the paper: a box laid out under a place is
    already where it belongs."""

    place.label.place(QPointF(0.35, -2.7))

    assert place.label.pos() == QPointF(0.35, -2.7)


def test_a_label_dragged_is_snapped_to_the_millimetre(place):
    """A drag is any move that is not :meth:`Label.place` — which is how Qt moves
    one under the hand."""

    place.label.setPos(QPointF(3.4, 8.6))

    assert place.label.pos() == QPointF(3.0, 9.0)


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
    assert place.label.size.height() == LABEL_LINE_HEIGHT

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
    belongs to is in hand*, both being drawn in the accent."""

    press(editor.view, place.label)
    box = place.label.box()
    image = ink.painted(place.label, colors)

    written = ink.window(image, 0.0, 0.0, 1.0)
    above = ink.window(image, 0.0, box.top() - LABEL_PADDING, 1.0)

    assert ink.holds(written, QColor(colors.accent))
    assert ink.holds(above, QColor(colors.accent))


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
