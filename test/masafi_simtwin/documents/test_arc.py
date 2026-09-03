"""Tests for the arcs of a Petri net, and for the gesture that draws one."""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import QEvent, QLineF, QPointF, Qt
from PyQt6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainterPath
from PyQt6.QtWidgets import QApplication, QDialog

from masafi_simtwin.documents import petri_net
from masafi_simtwin.documents.arc import (
    ARROW_LENGTH,
    ARROW_WIDTH,
    CURVE_BOW,
    DEFAULT_WEIGHT,
    END_HANDLES,
    HANDLE_SIZE,
    SHAPE_HANDLES,
    Arc,
    ArcShape,
    point_handle,
)
from masafi_simtwin.documents.net_item import ARC_Z, ITEM_Z, NetItem
from masafi_simtwin.documents.place import Place
from masafi_simtwin.documents.transition import Transition
from masafi_simtwin.theme import DARK_COLORS, LIGHT_COLORS

#: The two schemes the pixel tests are run against.
SCHEMES = [LIGHT_COLORS, DARK_COLORS]

#: What each is called, so a failure names the scheme it happened in.
SCHEME_NAMES = ['light', 'dark']


@pytest.fixture
def net(editor):
    """Put a place and a transition on the sheet, a little apart.

    Parameters
    ----------
    editor : masafi_simtwin.documents.petri_net.PetriNetEditor
        The document.

    Returns
    -------
    tuple
        The place and the transition.
    """

    place = editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))
    transition = editor.add_element('pt-petri-net', 'transition', QPointF(60.0, 20.0))
    return place, transition


def mouse(kind: QEvent.Type, position: QPointF) -> QMouseEvent:
    """Build a left-button mouse event.

    Parameters
    ----------
    kind : PyQt6.QtCore.QEvent.Type
        Press, move, release or double click.
    position : PyQt6.QtCore.QPointF
        Where it happened, in the viewport's coordinates.

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


def viewport_point(view, scene: QPointF) -> QPointF:
    """Put a place in the scene where the mouse events want it.

    Parameters
    ----------
    view : masafi_simtwin.documents.canvas.CanvasView
        The view.
    scene : PyQt6.QtCore.QPointF
        Where it is, in scene millimetres.

    Returns
    -------
    PyQt6.QtCore.QPointF
        The same place, in the viewport's coordinates.
    """

    return QPointF(view.mapFromScene(scene))


def drag_arc(view, source, target) -> None:
    """Draw an arc by pressing on a port and dragging onto another item.

    Parameters
    ----------
    view : masafi_simtwin.documents.canvas.CanvasView
        The view.
    source : masafi_simtwin.documents.net_item.NetItem
        What to draw from.  The press lands on its first connecting point.
    target : masafi_simtwin.documents.net_item.NetItem
        What to draw to.  The release lands on its middle.
    """

    start = viewport_point(view, source.scene_ports()[0])
    end = viewport_point(view, target.scenePos())
    view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    view.mouseMoveEvent(mouse(QEvent.Type.MouseMove, end))
    view.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, end))


# ----------------------------------------------------------------------
# What an arc is
# ----------------------------------------------------------------------


def test_an_arc_joins_two_items_and_both_know_it(editor, net):
    """An item has to be able to tell its arcs that it has moved."""

    place, transition = net
    arc = editor.add_arc(place, transition)

    assert arc.source is place
    assert arc.target is transition
    assert place.arcs == [arc]
    assert transition.arcs == [arc]


def test_an_arc_runs_between_the_two_points_it_was_drawn_to(editor, net):
    """It keeps the index of a connecting point at each end, not a position."""

    place, transition = net
    arc = editor.add_arc(place, transition)

    assert arc.line.p1() == place.scene_port(arc.source_port)
    assert arc.line.p2() == transition.scene_port(arc.target_port)


def test_an_arc_leaves_by_the_point_it_was_given(editor, net):
    """Which, when a person draws one, is the point the press landed on."""

    place, transition = net
    arc = editor.add_arc(place, transition, source_port=7)

    assert arc.source_port == 7
    assert arc.line.p1() == place.scene_port(7)


def test_an_arc_has_no_position_of_its_own(editor, net):
    """It is a relation, so it is never dragged and never moves itself."""

    place, transition = net
    arc = editor.add_arc(place, transition)

    assert arc.pos() == QPointF(0.0, 0.0)
    assert not arc.flags() & Arc.GraphicsItemFlag.ItemIsMovable
    assert arc.flags() & Arc.GraphicsItemFlag.ItemIsSelectable


def test_moving_either_end_moves_the_arc(editor, net):
    """Which is the whole reason an arc holds items rather than positions."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    before = arc.line

    transition.setPos(QPointF(60.0, 70.0))
    assert arc.line != before

    moved = arc.line
    place.setPos(QPointF(30.0, 70.0))
    assert arc.line != moved


def test_an_arc_keeps_its_points_as_the_net_is_dragged_about(editor, net):
    """An arc drawn once is drawn the same way for ever.

    Dragging a place moves the arc's end along with it; it does not pass the arc
    round to whichever point happens to face the other item now.  A net laid out
    by hand stays laid out.
    """

    place, transition = net
    arc = editor.add_arc(place, transition)
    ports = (arc.source_port, arc.target_port)
    leaving = arc.line.p1() - place.scenePos()

    for corner in (QPointF(20.0, 90.0), QPointF(120.0, 20.0), QPointF(120.0, 90.0)):
        transition.setPos(corner)
        assert (arc.source_port, arc.target_port) == ports
        assert arc.line.p1() - place.scenePos() == leaving

    place.setPos(QPointF(80.0, 60.0))
    assert (arc.source_port, arc.target_port) == ports
    assert arc.line.p1() - place.scenePos() == leaving


def test_the_arcs_go_under_the_items_they_join(editor, net):
    """So a line runs behind a place rather than across it."""

    place, transition = net
    arc = editor.add_arc(place, transition)

    assert arc.zValue() == ARC_Z
    assert ARC_Z < ITEM_Z


def test_an_arc_points_at_the_item_it_enters(editor, net):
    """The arrowhead is at the target, and it is on the boundary."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    head = arc.arrow()

    assert not head.isEmpty()
    assert head.contains(arc.line.p2()) or head.boundingRect().contains(arc.line.p2())
    assert head.boundingRect().width() <= ARROW_LENGTH + 1e-9


def test_an_arc_can_be_taken_hold_of(editor, net):
    """A line a third of a millimetre wide is a line nobody can click on."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    middle = arc.line.center()

    assert arc.shape().contains(middle)
    assert arc.shape().contains(QPointF(middle.x(), middle.y() + 1.0))
    assert not arc.shape().contains(QPointF(middle.x(), middle.y() + 5.0))


# ----------------------------------------------------------------------
# Two arcs between one pair
# ----------------------------------------------------------------------


def test_two_arcs_between_one_pair_take_different_points(editor, net):
    """A place and a transition joined both ways is an ordinary thing in a net.

    Both would otherwise take the point facing the other and draw the same line
    twice over, so an end **nobody chose** passes over the points that already
    carry an arc.  A point that was aimed at is taken whether it is free or not;
    this is about the ends that are worked out rather than chosen.
    """

    place, transition = net
    first = editor.add_arc(place, transition)
    second = editor.add_arc(transition, place)

    assert first.line.p1() != second.line.p2()
    assert first.line.p2() != second.line.p1()
    assert place.used_ports() == {first.source_port, second.target_port}
    assert len(place.used_ports()) == 2


def test_an_end_that_was_asked_for_is_taken_even_if_it_is_busy(editor, net):
    """Passing over the taken points is for the end nobody chose.  A press on a
    point that already has an arc on it is still a press on that point."""

    place, transition = net
    first = editor.add_arc(place, transition)
    second = editor.add_arc(place, transition, source_port=first.source_port)

    assert second.source_port == first.source_port
    assert second.target_port != first.target_port


def test_removing_one_arc_leaves_the_other_where_it_was(editor, net):
    """Fixed means fixed: nothing an arc does moves another one."""

    place, transition = net
    first = editor.add_arc(place, transition)
    second = editor.add_arc(transition, place)
    ports = (second.source_port, second.target_port)
    line = second.line

    editor.view.remove(first)

    assert (second.source_port, second.target_port) == ports
    assert second.line == line


def test_an_arc_knows_which_pair_it_joins(editor, net):
    """Either way round: the direction tells two arcs of a pair apart rather
    than making them a different pair."""

    place, transition = net
    arc = editor.add_arc(place, transition)

    assert arc.joins(place, transition)
    assert arc.joins(transition, place)


# ----------------------------------------------------------------------
# The weight
# ----------------------------------------------------------------------


def test_an_arc_carries_one_token_unless_it_is_told_otherwise(editor, net):
    """And a weight of one is not drawn, which is the convention of every net."""

    place, transition = net
    arc = editor.add_arc(place, transition)

    assert arc.weight == DEFAULT_WEIGHT == 1
    assert arc.weight_path() is None


def test_a_weight_that_is_not_one_is_drawn_beside_the_line(editor, net):
    """Writing the one in would put a number on nearly every arc of every net."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.weight = 4
    drawn = arc.weight_path()

    assert drawn is not None
    assert arc.boundingRect().contains(drawn.boundingRect())


def test_a_weight_below_one_is_not_a_weight(editor, net):
    """An arc that carries no tokens is an arc that is not there."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.weight = 0

    assert arc.weight == 1


# ----------------------------------------------------------------------
# Which items may be joined
# ----------------------------------------------------------------------


def test_a_place_joins_a_transition_and_nothing_else(editor):
    """A Petri net is bipartite, itself included."""

    first = editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))
    second = editor.add_element('pt-petri-net', 'place', QPointF(60.0, 20.0))
    transition = editor.add_element('pt-petri-net', 'transition', QPointF(20.0, 60.0))

    assert first.may_connect_to(transition)
    assert transition.may_connect_to(first)
    assert not first.may_connect_to(second)
    assert not first.may_connect_to(first)
    assert not transition.may_connect_to(transition)


def test_an_arc_between_two_places_is_refused(editor):
    """Silently: the arc simply is not there."""

    first = editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))
    second = editor.add_element('pt-petri-net', 'place', QPointF(60.0, 20.0))

    assert editor.add_arc(first, second) is None
    assert editor.arcs == []
    assert first.arcs == []


def test_the_groups_are_what_decides_and_not_the_class(editor):
    """A timed transition will be a transition for this however it is drawn."""

    assert Place.GROUP == 'place'
    assert Transition.GROUP == 'transition'
    assert Place.CONNECTS_TO == ('transition',)
    assert Transition.CONNECTS_TO == ('place',)


# ----------------------------------------------------------------------
# Drawing one with the mouse
# ----------------------------------------------------------------------


def test_dragging_from_a_connecting_point_draws_an_arc(editor, net):
    """Which is the gesture the connecting points were built for."""

    place, transition = net
    drag_arc(editor.view, place, transition)

    assert len(editor.arcs) == 1
    assert editor.arcs[0].source is place
    assert editor.arcs[0].target is transition


def test_the_arc_leaves_by_the_point_that_was_pressed(editor, net):
    """Which is why the pointer is aimed at a point to start one, and why the
    press has to find the *nearest* point rather than the first within reach."""

    place, transition = net
    chosen = 4
    start = viewport_point(editor.view, place.scene_ports()[chosen])
    end = viewport_point(editor.view, transition.scenePos())
    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    editor.view.mouseMoveEvent(mouse(QEvent.Type.MouseMove, end))
    editor.view.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, end))

    assert editor.arcs[0].source_port == chosen


def test_the_press_finds_the_nearest_point_and_not_the_first(editor, net):
    """On a transition the points along an edge are a fifth of a millimetre
    clear of one another, so first-within-reach would hand back a neighbour."""

    _, transition = net
    points = transition.scene_ports()
    wanted = len(points) - 2
    just_off = QPointF(points[wanted].x() + 0.2, points[wanted].y())

    assert transition.port_index_at(just_off) == wanted


def test_pressing_anywhere_else_on_an_item_does_not_draw_an_arc(editor, net):
    """A press on a connecting point starts an arc; a press on the shape moves
    it.  That is the whole of what tells the two apart."""

    place, transition = net
    middle = viewport_point(editor.view, place.scenePos())
    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, middle))

    assert editor.view.connecting is None


def test_a_drag_onto_something_that_may_not_be_joined_leaves_nothing(editor):
    """And gives up the arc rather than leaving it half drawn."""

    first = editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))
    second = editor.add_element('pt-petri-net', 'place', QPointF(60.0, 20.0))
    drag_arc(editor.view, first, second)

    assert editor.arcs == []
    assert editor.view.connecting is None


def test_a_drag_onto_the_bare_sheet_leaves_nothing(editor, net):
    """A drag that missed is a drag that missed."""

    place, _ = net
    start = viewport_point(editor.view, place.scene_ports()[0])
    end = viewport_point(editor.view, QPointF(200.0, 200.0))
    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    editor.view.mouseMoveEvent(mouse(QEvent.Type.MouseMove, end))
    editor.view.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, end))

    assert editor.arcs == []
    assert editor.view.connecting is None


def test_an_arc_can_be_drawn_by_clicking_once_at_each_end(editor, net):
    """Which is the only way to join two items further apart than the window.

    A press and a release in the same place is a click, and leaves the arc being
    drawn with the button up so the sheet can be scrolled between the two ends.
    """

    place, transition = net
    start = viewport_point(editor.view, place.scene_ports()[0])
    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    editor.view.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, start))

    assert editor.view.connecting is place
    assert editor.arcs == []

    end = viewport_point(editor.view, transition.scenePos())
    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, end))

    assert editor.view.connecting is None
    assert len(editor.arcs) == 1


def test_escape_gives_up_an_arc_being_drawn(editor, net):
    """And puts the connecting points it brought out back away."""

    place, _ = net
    start = viewport_point(editor.view, place.scene_ports()[0])
    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    editor.view.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, start))
    assert editor.view.connecting is place

    editor.view.keyPressEvent(
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    )

    assert editor.view.connecting is None
    assert not place.ports_visible


def test_the_points_come_out_while_an_arc_is_being_drawn(editor, net):
    """The item being drawn from shows where the arc is coming out of."""

    place, _ = net
    start = viewport_point(editor.view, place.scene_ports()[0])
    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))

    assert place.ports_visible


def test_the_receiving_points_come_out_when_the_arc_reaches_an_item(editor, net):
    """Both ends of the binding are visible while it is being made."""

    place, transition = net
    start = viewport_point(editor.view, place.scene_ports()[0])
    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    assert not transition.ports_visible

    over = viewport_point(editor.view, transition.scenePos())
    editor.view.mouseMoveEvent(mouse(QEvent.Type.MouseMove, over))

    assert editor.view.connection_target is transition
    assert transition.ports_visible
    assert place.ports_visible


def test_the_receiving_points_go_again_when_the_arc_is_taken_off(editor, net):
    """They belong to the aim, not to the item."""

    place, transition = net
    start = viewport_point(editor.view, place.scene_ports()[0])
    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    editor.view.mouseMoveEvent(
        mouse(QEvent.Type.MouseMove, viewport_point(editor.view, transition.scenePos()))
    )
    editor.view.mouseMoveEvent(
        mouse(QEvent.Type.MouseMove, viewport_point(editor.view, QPointF(150.0, 150.0)))
    )

    assert editor.view.connection_target is None
    assert not transition.ports_visible


def test_an_item_that_may_not_be_joined_lights_up_nothing(editor):
    """Which is the refusal made visible while there is still time to aim
    somewhere else."""

    first = editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))
    second = editor.add_element('pt-petri-net', 'place', QPointF(60.0, 20.0))
    start = viewport_point(editor.view, first.scene_ports()[0])
    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    editor.view.mouseMoveEvent(
        mouse(QEvent.Type.MouseMove, viewport_point(editor.view, second.scenePos()))
    )

    assert editor.view.connection_target is None
    assert not second.ports_visible


def drag_onto_port(view, source, source_port, target, target_port):
    """Draw an arc from one named point onto another, and give it back.

    The new arc is the last one attached to the source: an item appends each arc
    as it is joined, whereas ``editor.arcs`` is in the scene's stacking order,
    which puts the newest **first**.

    Parameters
    ----------
    view : masafi_simtwin.documents.canvas.CanvasView
        The view.
    source, target : masafi_simtwin.documents.net_item.NetItem
        The two ends.
    source_port, target_port : int
        Which connecting point of each to aim at.

    Returns
    -------
    masafi_simtwin.documents.arc.Arc, optional
        The arc, or ``None`` when none was drawn.
    """

    before = source.arcs
    start = viewport_point(view, source.scene_ports()[source_port])
    end = viewport_point(view, target.scene_ports()[target_port])
    view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    view.mouseMoveEvent(mouse(QEvent.Type.MouseMove, end))
    view.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, end))
    drawn = [arc for arc in source.arcs if arc not in before]
    return drawn[0] if drawn else None


def test_the_arc_lands_on_the_point_it_was_let_go_nearest(editor, net):
    """The point an arc arrives at is chosen the way the point it leaves by is:
    by aiming at it.  Letting go over one end of a transition and over the other
    binds to different points."""

    place, transition = net
    far = len(transition.ports()) // 2

    first = drag_onto_port(editor.view, place, 0, transition, 0)
    second = drag_onto_port(editor.view, place, 6, transition, far)

    assert first.target_port == 0
    assert second.target_port == far
    assert first.line.p2() != second.line.p2()


def test_a_connecting_point_is_aimed_at_by_its_ring(editor, net):
    """Half of every ring is drawn outside the shape it stands on, and an arc
    let go on that half would otherwise find nothing there — a miss at the very
    place a person is told to aim, and a silent one."""

    place, transition = net
    outside = transition.scene_ports()[len(transition.ports()) // 2]
    beyond = QPointF(outside.x(), outside.y() - 0.5)

    assert editor.view.item_at(editor.view.mapFromScene(beyond)) is transition


def test_moving_about_the_target_changes_where_the_arc_would_land(editor, net):
    """Which is what makes the point a thing that is chosen rather than given."""

    place, transition = net
    start = viewport_point(editor.view, place.scene_ports()[0])
    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))

    seen = []
    for point in (transition.scene_ports()[0], transition.scene_ports()[5]):
        editor.view.mouseMoveEvent(
            mouse(QEvent.Type.MouseMove, viewport_point(editor.view, point))
        )
        seen.append(editor.view.connection_endpoint())

    assert seen[0] != seen[1]
    assert seen == [transition.scene_ports()[0], transition.scene_ports()[5]]


def test_landing_on_a_point_that_is_busy_is_allowed(editor, net):
    """Choosing one is choosing it, exactly as a press on a busy point is.  The
    preview showed where it was going, so a person who does it meant to."""

    place, transition = net
    first = editor.add_arc(place, transition, source_port=0, target_port=3)
    second = drag_onto_port(editor.view, place, 6, transition, 3)

    assert second is not None
    assert second.target_port == first.target_port == 3


def test_the_line_being_dragged_ends_on_the_point_it_would_bind_to(editor, net):
    """So the preview is the arc that would be made rather than something near
    it, and the point it lands on can be seen before the button is let go."""

    place, transition = net
    start = viewport_point(editor.view, place.scene_ports()[0])
    over = viewport_point(editor.view, transition.scenePos())
    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    editor.view.mouseMoveEvent(mouse(QEvent.Type.MouseMove, over))
    aimed = editor.view.connection_endpoint()

    editor.view.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, over))

    assert aimed == editor.arcs[0].line.p2()


def test_the_line_follows_the_pointer_while_it_is_over_nothing(editor, net):
    """There is no point to end on until it is aimed at something."""

    place, _ = net
    start = viewport_point(editor.view, place.scene_ports()[0])
    nowhere = QPointF(150.0, 150.0)
    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    editor.view.mouseMoveEvent(mouse(QEvent.Type.MouseMove, nowhere))

    assert editor.view.connection_endpoint() == editor.view.mapToScene(nowhere.toPoint())


def test_both_ends_put_their_points_away_when_the_arc_lands(editor, net):
    """Neither is being pointed at any more, so the net is left to be looked at
    rather than covered in dots."""

    place, transition = net
    drag_arc(editor.view, place, transition)

    assert not place.ports_visible
    assert not transition.ports_visible


# ----------------------------------------------------------------------
# Taking one off again
# ----------------------------------------------------------------------


def test_deleting_an_arc_takes_it_off_both_of_its_ends(editor, net):
    """Or an item would go on telling something that is not there that it moved."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.setSelected(True)

    assert editor.view.delete_selection() == 1
    assert editor.arcs == []
    assert place.arcs == []
    assert transition.arcs == []


def test_deleting_an_item_takes_its_arcs_with_it(editor, net):
    """A line drawn to somewhere nothing is would be worse than no line."""

    place, transition = net
    editor.add_arc(place, transition)
    editor.add_arc(transition, place)
    place.setSelected(True)

    editor.view.delete_selection()

    assert editor.places == []
    assert editor.arcs == []
    assert transition.arcs == []


def test_delete_acts_on_the_whole_selection(editor, net):
    """Guides, items and arcs alike, which is the only rule that fits in a
    sentence."""

    place, transition = net
    editor.add_arc(place, transition)
    guide = editor.add_guide(Qt.Orientation.Horizontal, 40.0)
    guide.setSelected(True)
    transition.setSelected(True)

    editor.view.keyPressEvent(
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
    )

    assert editor.guides == []
    assert editor.transitions == []
    assert editor.arcs == []
    assert editor.places == [place]


class StubDialog:
    """Stands in for the Arc dialog, which would otherwise block on ``exec()``.

    A modal dialog runs an event loop of its own, so a test that opened the real
    one would sit there waiting for a person.  This answers the two questions
    the editor asks of a dialog and nothing else; the real one is tested where
    it lives, in ``test/masafi_simtwin/dialogs``.

    Parameters
    ----------
    weight : int
        The weight the editor opened it on.
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget, ignored.
    """

    #: What the next one built will answer, and whether it will be accepted.
    answer = 1
    accepted = True

    #: The weights the editor opened dialogs on, in order, so that a test can
    #: say the dialog was shown what the arc actually carries.
    opened: list[int] = []

    def __init__(self, weight: int = 1, parent=None) -> None:
        self.weight = StubDialog.answer
        StubDialog.opened.append(weight)

    def exec(self):
        """Answer as a dialog that has been accepted or cancelled.

        Returns
        -------
        PyQt6.QtWidgets.QDialog.DialogCode
            What the class attribute says.
        """

        return (
            QDialog.DialogCode.Accepted
            if StubDialog.accepted
            else QDialog.DialogCode.Rejected
        )


@pytest.fixture
def stub_dialog(monkeypatch):
    """Put the stub in front of the real Arc dialog.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The patcher.

    Returns
    -------
    type
        The stub, reset, so that a test can say what it will answer.
    """

    StubDialog.answer = 1
    StubDialog.accepted = True
    StubDialog.opened = []
    monkeypatch.setattr(petri_net, 'ArcDialog', StubDialog)
    return StubDialog


def test_a_double_click_on_an_arc_asks_what_it_carries(editor, net, stub_dialog):
    """Until the right-hand properties pane exists, a double click is where the
    weight is set."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    stub_dialog.answer = 5

    editor.view.mouseDoubleClickEvent(
        mouse(QEvent.Type.MouseButtonDblClick, viewport_point(editor.view, arc.line.center()))
    )

    assert stub_dialog.opened == [1]
    assert arc.weight == 5


def test_cancelling_the_dialog_leaves_the_arc_as_it_was(editor, net, stub_dialog):
    """Cancel means cancel."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.weight = 2
    stub_dialog.answer = 9
    stub_dialog.accepted = False

    assert not editor.edit_arc(arc)
    assert arc.weight == 2


def test_a_double_click_on_the_bare_sheet_opens_nothing(editor, net, stub_dialog):
    """There is nothing there to be asked about."""

    editor.view.mouseDoubleClickEvent(
        mouse(QEvent.Type.MouseButtonDblClick, QPointF(4.0, 4.0))
    )

    assert stub_dialog.opened == []


# ----------------------------------------------------------------------
# How an arc is drawn, in both schemes
# ----------------------------------------------------------------------


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_an_arc_is_drawn_in_the_ink_of_the_sheet(editor, ink, colors):
    """The same rule the items follow, so a net reads as one drawing."""

    place = editor.add_element('pt-petri-net', 'place', QPointF(0.0, 0.0))
    transition = editor.add_element('pt-petri-net', 'transition', QPointF(30.0, 0.0))
    arc = editor.add_arc(place, transition)

    middle = arc.line.center()
    close = ink.close_up(middle.x(), middle.y(), 20.0)

    assert ink.holds(
        close.window(close.painted(arc, colors), 0.0, 0.0, 0.5), QColor(colors.text)
    )


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_selected_arc_is_drawn_in_the_accent(editor, ink, colors):
    """``Link``, where the accent is kept, exactly as a guide and an item do."""

    place = editor.add_element('pt-petri-net', 'place', QPointF(0.0, 0.0))
    transition = editor.add_element('pt-petri-net', 'transition', QPointF(30.0, 0.0))
    arc = editor.add_arc(place, transition)
    arc.setSelected(True)

    middle = arc.line.center()
    close = ink.close_up(middle.x(), middle.y(), 20.0)

    assert ink.holds(
        close.window(close.painted(arc, colors), 0.0, 0.0, 0.5), QColor(colors.accent)
    )


def test_an_arc_is_something_drawn_on_the_sheet(editor, net):
    """The note over an empty sheet is long gone by the time there is one."""

    place, transition = net
    editor.add_arc(place, transition)

    assert editor.view.has_content()
    assert isinstance(place, NetItem)


# ----------------------------------------------------------------------
# Straight or curved
# ----------------------------------------------------------------------


def elements(path: QPainterPath) -> set:
    """Give what a path is made of, apart from where it begins.

    ``QPainterPath`` keeps a quadratic curve as a cubic one, so counting the
    elements says less than asking what kind they are.

    Parameters
    ----------
    path : PyQt6.QtGui.QPainterPath
        The path.

    Returns
    -------
    set
        The element types in it, without the ``MoveToElement`` every path opens
        with.
    """

    kinds = {path.elementAt(index).type for index in range(path.elementCount())}
    return kinds - {QPainterPath.ElementType.MoveToElement}


def test_an_arc_is_straight_until_it_is_told_otherwise(editor, net):
    """Which is what a Petri net arc is in most drawings."""

    place, transition = net
    arc = editor.add_arc(place, transition)

    assert arc.shape_kind is ArcShape.STRAIGHT
    assert not arc.curved
    assert elements(arc.path()) == {QPainterPath.ElementType.LineToElement}


def test_a_curved_arc_bows_off_its_chord(editor, net):
    """A cubic Bézier with a control point at each end, and no S until one is
    asked for: both controls start the same distance across the chord, which is
    the cubic that draws exactly a single bow of :data:`CURVE_BOW`."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.shape_kind = ArcShape.CURVED

    assert arc.curved
    assert QPainterPath.ElementType.CurveToElement in elements(arc.path())
    assert QPainterPath.ElementType.LineToElement not in elements(arc.path())

    chord = arc.line
    across = [arc.chord_frame(control)[1] for control in arc.control_points()]

    assert across[0] == pytest.approx(across[1])
    assert across[0] == pytest.approx(CURVE_BOW * 2.0 / 3.0)

    bow = arc.path().pointAtPercent(0.5) - chord.center()

    assert (bow.x() ** 2 + bow.y() ** 2) ** 0.5 == pytest.approx(
        chord.length() * CURVE_BOW / 2.0, rel=1e-3
    )


def test_a_curved_arc_keeps_the_two_points_it_is_attached_to(editor, net):
    """Bowing is how it is drawn between them, not where it is attached."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    ends = (arc.line.p1(), arc.line.p2())

    arc.shape_kind = ArcShape.CURVED

    assert (arc.line.p1(), arc.line.p2()) == ends
    assert arc.path().pointAtPercent(0.0) == ends[0]
    assert arc.path().pointAtPercent(1.0) == ends[1]


def test_two_arcs_drawn_both_ways_bow_apart(editor, net):
    """Which way it bows follows the arc's own direction, so a pair between one
    place and one transition separates without either knowing the other is
    there."""

    place, transition = net
    there = editor.add_arc(place, transition, source_port=0, target_port=10)
    back = editor.add_arc(transition, place, source_port=10, target_port=0)
    for arc in (there, back):
        arc.shape_kind = ArcShape.CURVED

    away = there.path().pointAtPercent(0.5) - there.line.center()
    back_away = back.path().pointAtPercent(0.5) - back.line.center()

    assert away.x() == pytest.approx(-back_away.x(), abs=1e-6)
    assert away.y() == pytest.approx(-back_away.y(), abs=1e-6)


def test_a_curved_arc_arrives_along_its_own_curve(editor, net):
    """So it meets its target the way the curve does rather than the way the
    chord does."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    straight_on = arc.arrow().boundingRect()

    arc.shape_kind = ArcShape.CURVED

    assert arc.arrow().boundingRect() != straight_on
    assert arc.arrow().contains(arc.line.p2()) or arc.arrow().boundingRect().contains(
        arc.line.p2()
    )


def hooked(editor, net):
    """Give an S that turns hard just before it lands.

    The shape the arrowhead was wrong on: the last leg comes up into the
    transition's bottom edge from a point almost directly below it, so the curve
    is still swinging round where the head is drawn.

    Parameters
    ----------
    editor : masafi_simtwin.documents.petri_net.PetriNetEditor
        The document.
    net : tuple
        The place and the transition.

    Returns
    -------
    masafi_simtwin.documents.arc.Arc
        The arc.
    """

    place, transition = net
    arc = editor.add_arc(place, transition, source_port=10, target_port=13)
    arc.shape_kind = ArcShape.S_CURVED
    arc.setSelected(True)
    arc.move_handle(point_handle(0), QPointF(place.x() + 6.0, place.y() + 14.0))
    arc.move_handle(point_handle(1), QPointF(transition.x() - 3.0, place.y() + 14.0))
    return arc


def base_of(head: QPainterPath) -> QPointF:
    """Give the middle of an arrowhead's base.

    Parameters
    ----------
    head : PyQt6.QtGui.QPainterPath
        The arrowhead, whose first element is its tip and whose next two are the
        corners of its base.

    Returns
    -------
    PyQt6.QtCore.QPointF
        Half way between the two corners.
    """

    corners = [QPointF(head.elementAt(index).x, head.elementAt(index).y) for index in (1, 2)]
    return QPointF(
        (corners[0].x() + corners[1].x()) / 2.0, (corners[0].y() + corners[1].y()) / 2.0
    )


def off_the_line(path: QPainterPath, point: QPointF) -> float:
    """Give how far a place is from a line, in millimetres.

    Parameters
    ----------
    path : PyQt6.QtGui.QPainterPath
        The line.
    point : PyQt6.QtCore.QPointF
        The place.

    Returns
    -------
    float
        The distance to the nearest place on it, sampled finely enough that the
        sampling is not what is being measured.
    """

    return min(
        math.hypot(
            path.pointAtPercent(step / 2000.0).x() - point.x(),
            path.pointAtPercent(step / 2000.0).y() - point.y(),
        )
        for step in range(2001)
    )


def test_the_line_runs_up_the_middle_of_its_own_arrowhead(editor, net):
    """An arrowhead is a straight triangle two and a half millimetres long, so
    laying it along the *tangent* where the arc lands puts a straight thing
    across a bend: on a curve that turns hard just before it lands the line then
    met the base at its corner — 0.9 mm off centre, the whole half-width — and
    the head read as a flag stuck on the end.  The base is taken off the line
    itself, so the line passes through it."""

    arc = hooked(editor, net)
    middle = base_of(arc.arrow())

    assert off_the_line(arc.path(), middle) < 0.01


def test_every_arrowhead_is_the_same_size(editor, net):
    """An arrowhead says what an arc *is*, not how it was drawn, so a curved
    one is neither stubbier nor longer than a straight one.  Measuring its
    length *along* the line is what made it stubby: the chord of a bend is
    shorter than the bend."""

    place, transition = net
    heads = {}
    arc = editor.add_arc(place, transition)
    heads['straight'] = arc.arrow()
    arc.shape_kind = ArcShape.CURVED
    heads['curved'] = arc.arrow()
    heads['s-curved'] = hooked(editor, net).arrow()

    for name, head in heads.items():
        tip = QPointF(head.elementAt(0).x, head.elementAt(0).y)
        corners = [
            QPointF(head.elementAt(index).x, head.elementAt(index).y) for index in (1, 2)
        ]
        middle = base_of(head)

        assert math.hypot(
            tip.x() - middle.x(), tip.y() - middle.y()
        ) == pytest.approx(ARROW_LENGTH, abs=1e-3), f'{name} is the wrong length'
        assert math.hypot(
            corners[0].x() - corners[1].x(), corners[0].y() - corners[1].y()
        ) == pytest.approx(ARROW_WIDTH, abs=1e-3), f'{name} is the wrong width'


def test_the_last_stretch_of_the_line_is_inside_the_arrowhead(editor, net):
    """Which is what makes the head read as the end of the line rather than as
    something stuck on it."""

    arc = hooked(editor, net)
    path = arc.path()
    head = arc.arrow()
    length = path.length()

    for back in (0.3, 0.9, 1.5, 2.1):
        where = path.pointAtPercent((length - back) / length)
        assert head.contains(where), f'the line leaves its own head {back} mm back'


def test_the_arrowhead_still_ends_on_the_connecting_point(editor, net):
    """Wherever it is aimed, its tip is where the arc lands."""

    arc = hooked(editor, net)
    tip = arc.arrow().elementAt(0)

    assert (tip.x, tip.y) == pytest.approx((arc.line.p2().x(), arc.line.p2().y()))


def test_the_arrowhead_of_a_straight_arc_is_the_straight_line(editor, net):
    """The two rules are one where the line and its chord are one, so nothing
    changes for the ordinary arc."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    head = arc.arrow()
    tip = arc.line.p2()
    along = arc.line.unitVector()
    base = QPointF(
        tip.x() - along.dx() * ARROW_LENGTH, tip.y() - along.dy() * ARROW_LENGTH
    )
    middle = base_of(head)

    assert middle.x() == pytest.approx(base.x(), abs=1e-6)
    assert middle.y() == pytest.approx(base.y(), abs=1e-6)


def test_the_weight_rides_the_curve(editor, net):
    """A number beside a curved arc sits beside the curve, not beside the chord."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.weight = 5
    on_the_chord = arc.weight_path().boundingRect().center()

    arc.shape_kind = ArcShape.CURVED

    assert arc.weight_path().boundingRect().center() != on_the_chord


def test_a_curved_arc_covers_and_is_grabbed_along_its_curve(editor, net):
    """Its bounding rectangle and the band it is taken hold of in both come
    from the path, so neither has to know which shape it is."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    straight_bounds = arc.boundingRect()

    arc.shape_kind = ArcShape.CURVED
    bowed = arc.path().pointAtPercent(0.5)

    assert arc.boundingRect() != straight_bounds
    assert arc.boundingRect().contains(bowed)
    assert arc.shape().contains(bowed)
    assert not arc.shape().contains(arc.line.center())


# ----------------------------------------------------------------------
# Choosing the shape
# ----------------------------------------------------------------------


def test_an_arc_offers_its_four_shapes_and_a_way_out(editor, net):
    """An arc has no entry in the menu bar, so this is where all of them are
    found."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    menu = editor.view.arc_menu(arc)

    assert [action.text() for action in menu.actions() if not action.isSeparator()] == [
        'Straight',
        'Curved',
        'S-Curved',
        'L-Shaped',
        'Delete Arc',
    ]


def test_the_menu_says_which_shape_the_arc_already_is(editor, net):
    """A menu that says what a thing is is worth more than one that only says
    what can be done to it."""

    place, transition = net
    arc = editor.add_arc(place, transition)

    checked = [
        action.data()
        for action in editor.view.arc_menu(arc).actions()
        if action.isCheckable() and action.isChecked()
    ]
    assert checked == [ArcShape.STRAIGHT]

    arc.shape_kind = ArcShape.CURVED
    checked = [
        action.data()
        for action in editor.view.arc_menu(arc).actions()
        if action.isCheckable() and action.isChecked()
    ]
    assert checked == [ArcShape.CURVED]


def test_the_two_shapes_are_one_choice(editor, net):
    """They are exclusive of their own accord, being one group."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    menu = editor.view.arc_menu(arc)
    groups = {
        action.actionGroup()
        for action in menu.actions()
        if action.isCheckable()
    }

    assert len(groups) == 1
    assert next(iter(groups)).isExclusive()


def test_choosing_curved_curves_the_arc(editor, net):
    """Which is the whole of what the menu is for."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    menu = editor.view.arc_menu(arc)
    curved = [action for action in menu.actions() if action.data() is ArcShape.CURVED]

    curved[0].trigger()

    assert arc.curved


def test_choosing_straight_straightens_it_again(editor, net):
    """And the choice can be made twice over."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.shape_kind = ArcShape.CURVED
    menu = editor.view.arc_menu(arc)
    straight = [
        action for action in menu.actions() if action.data() is ArcShape.STRAIGHT
    ]

    straight[0].trigger()

    assert not arc.curved


def test_the_menu_deletes_the_arc_it_was_aimed_at(editor, net):
    """And takes it off both of its ends, as any other removal does."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    other = editor.add_arc(transition, place)
    menu = editor.view.arc_menu(arc)

    [action for action in menu.actions() if action.text() == 'Delete Arc'][0].trigger()

    assert editor.arcs == [other]
    assert place.arcs == [other]


def test_the_menu_acts_on_the_arc_under_the_pointer_and_no_other(editor, net):
    """A context menu is aimed at a thing, selection or no selection."""

    place, transition = net
    aimed = editor.add_arc(place, transition)
    selected = editor.add_arc(transition, place)
    selected.setSelected(True)

    curved = [
        action
        for action in editor.view.arc_menu(aimed).actions()
        if action.data() is ArcShape.CURVED
    ]
    curved[0].trigger()

    assert aimed.curved
    assert not selected.curved


def test_the_bare_sheet_offers_no_arc_menu(editor, net):
    """There is no arc there to be shaped."""

    assert editor.view.arc_menu(None) is None


def test_an_arc_is_found_under_the_pointer(editor, net):
    """Which is what the context menu is built from."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    middle = editor.view.mapFromScene(arc.line.center())

    assert editor.view.arc_at(middle) is arc


# ----------------------------------------------------------------------
# Shaping a curve by hand
# ----------------------------------------------------------------------


@pytest.fixture
def curve(editor, net):
    """Give a curved arc, selected, so that its handles are out.

    Parameters
    ----------
    editor : masafi_simtwin.documents.petri_net.PetriNetEditor
        The document.
    net : tuple
        The place and the transition.

    Returns
    -------
    masafi_simtwin.documents.arc.Arc
        The arc.
    """

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.shape_kind = ArcShape.CURVED
    arc.setSelected(True)
    return arc


def test_a_straight_arc_has_nothing_to_shape(editor, net):
    """It carries its two end handles like any selected arc, and no others:
    there is no curve on it to take hold of."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.setSelected(True)

    assert sorted(arc.handles()) == sorted(END_HANDLES)


def test_a_curve_shows_its_handles_only_while_it_is_selected(editor, net):
    """A sheet showing a handle for every arc on it is a sheet nobody can read."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.shape_kind = ArcShape.CURVED

    assert arc.handles() == {}

    arc.setSelected(True)
    assert sorted(arc.handles()) == sorted(SHAPE_HANDLES + END_HANDLES)


def test_the_middle_handle_sits_on_the_curve(curve):
    """On it rather than off it, which is what makes it a thing to take hold of
    rather than a thing to interpret."""

    assert curve.handles()['middle'] == curve.curve_middle()
    assert curve.curve_middle() == curve.path().pointAtPercent(0.5)


def test_the_other_two_handles_are_the_control_points(curve):
    """One for each end, which is what says where the curve sets off."""

    first, second = curve.control_points()

    assert curve.handles()['source_control'] == first
    assert curve.handles()['target_control'] == second


def test_a_handle_is_found_by_being_near_enough(curve):
    """A handle that has to be hit exactly is a handle nobody can use."""

    middle = curve.handles()['middle']

    assert curve.handle_at(middle) == 'middle'
    assert curve.handle_at(QPointF(middle.x() + 0.5, middle.y())) == 'middle'
    assert curve.handle_at(QPointF(middle.x() + 20.0, middle.y())) is None


def test_a_handle_can_be_pressed_at_all(curve):
    """A handle outside the shape is a handle no press ever reaches, the scene
    sending a press to the item whose shape it fell in."""

    for where in curve.handles().values():
        assert curve.shape().contains(where)


def test_dragging_the_middle_handle_moves_the_curve_under_the_pointer(editor, curve):
    """It lands where it was put rather than short of it: a cubic's half-way
    point moves three quarters as far as its controls do, so the controls are
    moved four thirds of the way.  Where it was put is the nearest millimetre,
    every handle snapping like everything else on the sheet."""

    was = curve.curve_middle()
    wants = QPointF(was.x(), was.y() + 8.0)
    snapped = QPointF(editor.view.snap(wants.x()), editor.view.snap(wants.y()))

    curve.move_handle('middle', wants)

    assert curve.curve_middle().x() == pytest.approx(snapped.x(), abs=1e-6)
    assert curve.curve_middle().y() == pytest.approx(snapped.y(), abs=1e-6)


def test_dragging_the_middle_handle_keeps_the_curve_one_bow(curve):
    """Both control points shift by the same amount, so the plain gesture
    cannot make an S of it by accident."""

    before = [curve.chord_frame(control) for control in curve.control_points()]
    middle = curve.curve_middle()

    curve.move_handle('middle', QPointF(middle.x() + 5.0, middle.y() + 5.0))

    after = [curve.chord_frame(control) for control in curve.control_points()]
    shifts = [
        (now[0] - then[0], now[1] - then[1]) for then, now in zip(before, after)
    ]

    assert shifts[0][0] == pytest.approx(shifts[1][0])
    assert shifts[0][1] == pytest.approx(shifts[1][1])


def test_dragging_a_control_handle_moves_only_that_end(curve):
    """Which is what says where the curve sets off from that end."""

    before = curve.control_points()
    wants = QPointF(before[0].x() + 6.0, before[0].y() - 4.0)

    curve.move_handle('source_control', wants)
    after = curve.control_points()

    assert after[0] != before[0]
    assert after[1] == before[1]


def test_the_two_control_handles_can_be_pulled_into_an_s(curve):
    """Which is what the handles are for; the middle one is the gesture that
    cannot do it."""

    first, second = curve.control_points()
    chord = curve.line
    curve.move_handle('source_control', curve.chord_point(1.0 / 3.0, 0.4))
    curve.move_handle('target_control', curve.chord_point(2.0 / 3.0, -0.4))

    across = [curve.chord_frame(control)[1] for control in curve.control_points()]

    assert across[0] > 0.0
    assert across[1] < 0.0


def test_a_shaped_curve_keeps_its_shape_when_the_net_is_dragged_about(curve, net):
    """A control point is kept in the chord's own frame, so the whole picture
    turns and scales with the arc instead of coming apart."""

    place, transition = net
    curve.move_handle('source_control', curve.chord_point(0.2, 0.5))
    shaped = [curve.chord_frame(control) for control in curve.control_points()]

    transition.setPos(QPointF(30.0, 90.0))
    place.setPos(QPointF(90.0, 30.0))
    after = [curve.chord_frame(control) for control in curve.control_points()]

    for then, now in zip(shaped, after):
        assert now[0] == pytest.approx(then[0], abs=1e-6)
        assert now[1] == pytest.approx(then[1], abs=1e-6)


def test_a_handle_snaps_to_the_millimetre(curve):
    """The same grid everything else on the sheet lands on."""

    middle = curve.curve_middle()
    curve.move_handle('middle', QPointF(middle.x() + 4.4, middle.y() + 3.6))
    landed = curve.curve_middle()

    assert landed.x() == pytest.approx(round(landed.x()), abs=1e-6)
    assert landed.y() == pytest.approx(round(landed.y()), abs=1e-6)


def test_a_straight_arc_ignores_its_handles_being_moved(editor, net):
    """There is no curve to shape, so nothing happens."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.setSelected(True)
    before = arc.path().pointAtPercent(0.5)

    arc.move_handle('middle', QPointF(0.0, 0.0))

    assert arc.path().pointAtPercent(0.5) == before


def scene_mouse(view, kind: QEvent.Type, position: QPointF) -> QMouseEvent:
    """Build a mouse event the *scene* will act on, not only the view.

    A scene hit-tests a mouse event through its **global** position — it maps it
    back into the view that sent it — so an event whose global position is not
    where the widget actually is reaches the view's own handlers and stops
    there.  Every other test here drives ``CanvasView``'s overrides, which read
    the local position and never ask the scene; this one has to get all the way
    to an item.

    Parameters
    ----------
    view : masafi_simtwin.documents.canvas.CanvasView
        The view the event is for.
    kind : PyQt6.QtCore.QEvent.Type
        Press, move or release.
    position : PyQt6.QtCore.QPointF
        Where it happened, in the viewport's coordinates.

    Returns
    -------
    PyQt6.QtGui.QMouseEvent
        The event.
    """

    return QMouseEvent(
        kind,
        QPointF(position),
        QPointF(view.viewport().mapToGlobal(position.toPoint())),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def test_the_handles_are_dragged_with_the_mouse(editor, net, curve):
    """The whole chain: a press on a handle reaches the arc through the scene,
    the drag reshapes it, and letting go lets go."""

    view = editor.view
    was = curve.curve_middle()
    start = viewport_point(view, was)
    end = viewport_point(view, QPointF(was.x(), was.y() + 10.0))

    view.mousePressEvent(scene_mouse(view, QEvent.Type.MouseButtonPress, start))
    view.mouseMoveEvent(scene_mouse(view, QEvent.Type.MouseMove, end))
    moved = curve.curve_middle()
    view.mouseReleaseEvent(scene_mouse(view, QEvent.Type.MouseButtonRelease, end))

    assert moved.y() > was.y() + 5.0

    view.mouseMoveEvent(
        scene_mouse(
            view, QEvent.Type.MouseMove, viewport_point(view, QPointF(10.0, 90.0))
        )
    )
    assert curve.curve_middle() == moved


def repainted(scene, act) -> list:
    """Give the parts of the sheet the scene asked to have painted again.

    Which is the only way to catch something left behind: what is *drawn* is
    right either way — a fresh painting of the whole sheet shows nothing wrong —
    and the bug is in the region the view is told to repaint.  The scene reports
    it through ``changed``, which it emits once the dirty items have been
    processed, so the loop has to be let run.

    Parameters
    ----------
    scene : PyQt6.QtWidgets.QGraphicsScene
        The scene.
    act : collections.abc.Callable
        What to do to it.

    The connection is **taken off again** before this returns.  A connection
    made with a lambda belongs to the sender alone, and the scene outlives the
    test: left in place it is called again while the document is being torn
    down, which kills the interpreter outright.  That is the same rule the
    application follows for its own signals.

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


def test_letting_go_of_an_arc_repaints_where_its_handles_were(editor, curve):
    """A handle may lie a long way off the line, and it is inside the arc's
    rectangle only while the arc is selected — so deselecting shrinks the
    rectangle before Qt repaints, and the handles stay on the sheet with nothing
    left that knows they are there.  This was seen: two squares left hanging
    over a net."""

    curve.move_handle('source_control', QPointF(30.0, 4.0))
    QApplication.processEvents()
    where = curve.handles()['source_control']

    seen = repainted(editor.view.scene(), lambda: curve.setSelected(False))

    assert any(rect.contains(where) for rect in seen), (
        f'nothing repainted where the handle was, at {where}'
    )


def test_taking_hold_of_an_arc_paints_the_handles_it_grows(editor, net):
    """The other way round, which has always worked and must go on working."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.shape_kind = ArcShape.CURVED
    QApplication.processEvents()

    seen = repainted(editor.view.scene(), lambda: arc.setSelected(True))

    assert any(rect.contains(arc.handles()['middle']) for rect in seen)


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_handle_is_drawn_the_way_a_connecting_point_is(ink, curve, colors):
    """A hairline of the accent around the colour of the paper.

    The middle handle is read, which is the hard case: it sits **on** the curve,
    and the curve under a selected arc is drawn in the accent too — so the paper
    in the middle of the square is the fill covering the line, exactly as a
    connecting point is a hole in a transition.  What tells a handle from a
    connecting point is its shape, not its colour.
    """

    where = curve.handles()['middle']
    close = ink.close_up(where.x(), where.y(), 40.0)
    image = close.painted(curve, colors)

    assert close.at(image) == QColor(colors.editor)
    assert ink.holds(
        close.window(image, 0.0, 0.0, HANDLE_SIZE / 2.0), QColor(colors.accent)
    )


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_handle_is_not_a_solid_block_of_accent(ink, curve, colors):
    """Which is what it was before, and what made three of them a heavy thing to
    put on a drawing."""

    where = curve.handles()['source_control']
    close = ink.close_up(where.x(), where.y(), 40.0)
    inside = close.window(close.painted(curve, colors), 0.0, 0.0, HANDLE_SIZE / 4.0)

    assert all(pixel == QColor(colors.editor) for pixel in inside)


# ----------------------------------------------------------------------
# The S, and the points it is led through
# ----------------------------------------------------------------------


@pytest.fixture
def ess(editor, net):
    """Give an S-curved arc, selected, so that its points are out.

    Parameters
    ----------
    editor : masafi_simtwin.documents.petri_net.PetriNetEditor
        The document.
    net : tuple
        The place and the transition.

    Returns
    -------
    masafi_simtwin.documents.arc.Arc
        The arc.
    """

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.shape_kind = ArcShape.S_CURVED
    arc.setSelected(True)
    return arc


def knots(path: QPainterPath) -> list:
    """Give the places a path is drawn through.

    Parameters
    ----------
    path : PyQt6.QtGui.QPainterPath
        The path.

    Returns
    -------
    list of tuple
        The coordinates of every element of it, which for a run of cubics
        includes each point the curve passes through as well as the controls.
    """

    return [
        (path.elementAt(index).x, path.elementAt(index).y)
        for index in range(path.elementCount())
    ]


def test_an_s_is_an_s_as_soon_as_it_is_chosen(ess):
    """A shape named after what it looks like should look like it before
    anybody has touched it: two points, one bowed each way."""

    across = [ess.chord_frame(point)[1] for point in ess.curve_points()]

    assert len(across) == 2
    assert across[0] > 0.0
    assert across[1] < 0.0


def test_an_s_is_drawn_through_its_points(ess):
    """Which is what makes a point a place the line goes rather than a place it
    leans towards, and it is the whole reason for the spline."""

    drawn = knots(ess.path())

    for point in ess.curve_points():
        assert any(
            abs(x - point.x()) < 1e-6 and abs(y - point.y()) < 1e-6 for x, y in drawn
        )


def test_an_s_is_one_cubic_between_each_pair_of_knots(ess):
    """Its two ends and the points between them, so a point adds a segment."""

    assert len(ess.segments()) == len(ess.curve_points()) + 1

    ess.insert_point(ess.path().pointAtPercent(0.25))
    assert len(ess.segments()) == len(ess.curve_points()) + 1


def test_an_s_led_through_no_points_is_a_straight_line(ess):
    """Taking the last point out is allowed, and what is left is honest: a
    curve through nothing is a line, and the points can be put back."""

    while ess.remove_point(0):
        pass

    half = ess.path().pointAtPercent(0.5)
    chord = ess.line.center()

    assert ess.curve_points() == []
    assert half.x() == pytest.approx(chord.x(), abs=1e-6)
    assert half.y() == pytest.approx(chord.y(), abs=1e-6)


def test_an_s_carries_a_handle_on_every_point(ess):
    """They are the handles: a point is on the line, so it is at once where the
    line goes and the thing that moves it."""

    names = sorted(ess.handles())
    wanted = sorted([point_handle(0), point_handle(1), *END_HANDLES])

    assert names == wanted


def test_an_s_shows_its_points_only_while_it_is_selected(editor, net):
    """A sheet showing a handle for every arc on it is a sheet nobody can
    read."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.shape_kind = ArcShape.S_CURVED

    assert arc.handles() == {}

    arc.setSelected(True)
    assert point_handle(0) in arc.handles()


def test_a_point_of_an_s_is_dragged_where_it_is_put(editor, ess):
    """It is on the line, so there is nothing to work backwards: the point goes
    under the pointer, at the nearest millimetre like everything else."""

    was = ess.curve_points()[0]
    wants = QPointF(was.x() + 4.4, was.y() - 6.6)
    snapped = QPointF(editor.view.snap(wants.x()), editor.view.snap(wants.y()))

    ess.move_handle(point_handle(0), wants)
    landed = ess.curve_points()[0]

    assert landed.x() == pytest.approx(snapped.x(), abs=1e-6)
    assert landed.y() == pytest.approx(snapped.y(), abs=1e-6)


def test_dragging_one_point_leaves_the_others_where_they_are(ess):
    """A point is a point, not a bow: only the one taken hold of moves."""

    before = ess.curve_points()[1]
    first = ess.curve_points()[0]

    ess.move_handle(point_handle(0), QPointF(first.x(), first.y() + 10.0))

    assert ess.curve_points()[1] == before


def test_an_s_keeps_its_shape_when_the_net_is_dragged_about(ess, net):
    """The points are kept in the chord's own frame, as the control points are,
    so the whole picture turns and scales with the arc."""

    place, transition = net
    first = ess.curve_points()[0]
    ess.move_handle(point_handle(0), QPointF(first.x() + 3.0, first.y() - 9.0))
    shaped = [ess.chord_frame(point) for point in ess.curve_points()]

    transition.setPos(QPointF(30.0, 90.0))
    place.setPos(QPointF(90.0, 30.0))
    after = [ess.chord_frame(point) for point in ess.curve_points()]

    for then, now in zip(shaped, after):
        assert now[0] == pytest.approx(then[0], abs=1e-6)
        assert now[1] == pytest.approx(then[1], abs=1e-6)


def test_an_s_arrives_along_its_own_tangent(ess):
    """The arrowhead follows the last segment in, so a curve meets its target
    head on rather than at the angle of the chord."""

    first = ess.curve_points()[0]
    ess.move_handle(point_handle(0), QPointF(first.x(), first.y() - 20.0))

    head = ess.arrow().boundingRect().center()
    tip = ess.line.p2()
    tangent = ess.path().angleAtPercent(1.0)
    along = QPointF(math.cos(math.radians(tangent)), -math.sin(math.radians(tangent)))

    assert (tip.x() - head.x()) * along.x() + (tip.y() - head.y()) * along.y() > 0.0


def test_a_point_is_added_on_the_line(ess):
    """A curve that jumped as the point went in would have to be put back before
    it could be shaped, so the point goes on the nearest place on the curve."""

    on = ess.path().pointAtPercent(0.25)
    aimed = QPointF(on.x() + 3.0, on.y() + 3.0)

    index = ess.insert_point(aimed)
    put = ess.curve_points()[index]

    assert math.hypot(put.x() - on.x(), put.y() - on.y()) < 2.0


def test_a_point_goes_in_where_it_was_aimed(ess):
    """Between the two knots the pointer was between, not at the end of the run:
    an S can fold back on itself, so how far along the chord it is says nothing
    about where it belongs."""

    near_the_source = ess.path().pointAtPercent(0.05)
    near_the_target = ess.path().pointAtPercent(0.95)

    assert ess.insert_point(near_the_source) == 0
    assert ess.insert_point(near_the_target) == 3


def test_a_point_is_taken_out_again(ess):
    """The one it was aimed at and no other."""

    second = ess.curve_points()[1]

    assert ess.remove_point(0)

    assert ess.curve_points() == [second]


def test_a_point_that_is_not_there_cannot_be_taken_out(ess):
    """It says so rather than raising: the menu is built from what is under the
    pointer, and what is under the pointer can go."""

    assert not ess.remove_point(7)
    assert not ess.remove_point(-1)


def test_only_an_s_is_led_through_points(editor, net):
    """A single bow has its control points and a straight arc has nothing, so
    neither takes one."""

    place, transition = net
    arc = editor.add_arc(place, transition)

    assert arc.insert_point(QPointF(40.0, 20.0)) is None

    arc.shape_kind = ArcShape.CURVED
    assert arc.insert_point(QPointF(40.0, 20.0)) is None


def test_a_point_is_found_under_the_pointer(ess):
    """Which is what the menu asks to know whether it offers to add one or to
    take one out."""

    first = ess.curve_points()[0]

    assert ess.point_at(first) == 0
    assert ess.point_at(QPointF(first.x() + 0.5, first.y())) == 0
    assert ess.point_at(QPointF(first.x() + 20.0, first.y())) is None


def test_the_points_of_another_shape_are_not_there_to_be_found(editor, net):
    """An arc keeps its points for when it is made an S again, but until it is
    they are not on it."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.shape_kind = ArcShape.S_CURVED
    where = arc.curve_points()[0]

    arc.shape_kind = ArcShape.CURVED

    assert arc.point_at(where) is None


def test_an_s_keeps_what_it_was_shaped_into_when_it_is_put_back(editor, net):
    """Changing the shape is not throwing the shaping away, which is what the
    control points already do."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.shape_kind = ArcShape.S_CURVED
    arc.setSelected(True)
    first = arc.curve_points()[0]
    arc.move_handle(point_handle(0), QPointF(first.x(), first.y() - 12.0))
    shaped = [arc.chord_frame(point) for point in arc.curve_points()]

    arc.shape_kind = ArcShape.STRAIGHT
    arc.shape_kind = ArcShape.S_CURVED

    assert [arc.chord_frame(point) for point in arc.curve_points()] == shaped


def test_the_points_of_an_s_are_dragged_with_the_mouse(editor, ess):
    """The whole chain: a press on a point reaches the arc through the scene,
    the drag moves it, and letting go lets go."""

    view = editor.view
    was = ess.curve_points()[0]
    start = viewport_point(view, was)
    end = viewport_point(view, QPointF(was.x(), was.y() - 10.0))

    view.mousePressEvent(scene_mouse(view, QEvent.Type.MouseButtonPress, start))
    view.mouseMoveEvent(scene_mouse(view, QEvent.Type.MouseMove, end))
    moved = ess.curve_points()[0]
    view.mouseReleaseEvent(scene_mouse(view, QEvent.Type.MouseButtonRelease, end))

    assert moved.y() < was.y() - 5.0

    view.mouseMoveEvent(
        scene_mouse(
            view, QEvent.Type.MouseMove, viewport_point(view, QPointF(10.0, 90.0))
        )
    )
    assert ess.curve_points()[0] == moved


def test_a_point_of_an_s_can_be_pressed_at_all(ess):
    """A handle outside the shape is a handle no press ever reaches."""

    for where in ess.handles().values():
        assert ess.shape().contains(where)


def test_an_s_covers_and_is_grabbed_along_its_curve(ess):
    """Not merely along its chord: a curve led away from the straight line is a
    curve nobody could click on if the band stayed behind."""

    first = ess.curve_points()[0]
    ess.move_handle(point_handle(0), QPointF(first.x(), first.y() - 20.0))
    on = ess.path().pointAtPercent(0.3)

    assert ess.shape().contains(on)
    assert ess.boundingRect().contains(on)


# ----------------------------------------------------------------------
# Adding and taking out a point from the menu
# ----------------------------------------------------------------------


def entries(menu) -> list:
    """Give what a menu offers, leaving its separators out.

    Parameters
    ----------
    menu : PyQt6.QtWidgets.QMenu
        The menu.

    Returns
    -------
    list of str
        The text of every action of it.
    """

    return [action.text() for action in menu.actions() if not action.isSeparator()]


def test_an_s_offers_a_point_to_be_added(editor, ess):
    """Which is where the gesture lives: an arc has no entry in the menu bar."""

    on = ess.path().pointAtPercent(0.4)

    assert entries(editor.view.arc_menu(ess, on)) == [
        'Straight',
        'Curved',
        'S-Curved',
        'L-Shaped',
        'Add Point',
        'Delete Arc',
    ]


def test_a_point_of_an_s_offers_to_be_taken_out(editor, ess):
    """The same place in the menu: they are one question — is there a point
    here? — rather than two entries of which one is always dead."""

    on = ess.curve_points()[1]

    assert entries(editor.view.arc_menu(ess, on)) == [
        'Straight',
        'Curved',
        'S-Curved',
        'L-Shaped',
        'Delete Point',
        'Delete Arc',
    ]


def test_the_other_shapes_offer_no_points(editor, net):
    """A point is a thing an S is led through, and choosing the shape is the
    step before putting points into it."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    straight = entries(editor.view.arc_menu(arc, arc.line.center()))

    arc.shape_kind = ArcShape.CURVED
    curved = entries(editor.view.arc_menu(arc, arc.path().pointAtPercent(0.5)))

    assert 'Add Point' not in straight
    assert 'Delete Point' not in straight
    assert 'Add Point' not in curved
    assert 'Delete Point' not in curved


def test_the_menu_adds_the_point_where_it_was_opened(editor, ess):
    """And puts it in the run where it was aimed rather than at the end."""

    was = len(ess.curve_points())
    on = ess.path().pointAtPercent(0.05)
    menu = editor.view.arc_menu(ess, on)

    [action for action in menu.actions() if action.text() == 'Add Point'][0].trigger()

    assert len(ess.curve_points()) == was + 1
    put = ess.curve_points()[0]
    assert math.hypot(put.x() - on.x(), put.y() - on.y()) < 2.0


def test_adding_a_point_leaves_the_arc_in_hand(editor, ess):
    """A point is put in to be dragged somewhere, and the handle to drag it by
    is there only while the arc is selected.  A right click does not select what
    it is aimed at, so without this a person aims at the arc twice for one
    wish."""

    ess.setSelected(False)
    on = ess.path().pointAtPercent(0.4)
    menu = editor.view.arc_menu(ess, on)

    [action for action in menu.actions() if action.text() == 'Add Point'][0].trigger()

    assert ess.isSelected()
    assert point_handle(0) in ess.handles()


def test_taking_a_point_out_leaves_the_arc_in_hand_as_well(editor, ess):
    """The same wish: a route being worked on goes on being worked on."""

    ess.setSelected(False)
    corner = ess.curve_points()[0]
    menu = editor.view.arc_menu(ess, corner)

    [action for action in menu.actions() if action.text() == 'Delete Point'][0].trigger()

    assert ess.isSelected()


def test_working_on_an_arc_puts_the_rest_of_the_selection_down(editor, net, ess):
    """Which is what a click on the arc would have done: what the menu was aimed
    at is the thing being worked on, and *Delete* afterwards should reach that
    and nothing else."""

    place, transition = net
    place.setSelected(True)
    ess.setSelected(False)
    on = ess.path().pointAtPercent(0.4)
    menu = editor.view.arc_menu(ess, on)

    [action for action in menu.actions() if action.text() == 'Add Point'][0].trigger()

    assert ess.isSelected()
    assert not place.isSelected()


def test_the_menu_takes_out_the_point_it_was_aimed_at(editor, ess):
    """And no other, a context menu being aimed at a thing."""

    second = ess.curve_points()[1]
    menu = editor.view.arc_menu(ess, ess.curve_points()[0])

    [action for action in menu.actions() if action.text() == 'Delete Point'][
        0
    ].trigger()

    assert ess.curve_points() == [second]


def test_choosing_the_s_gives_the_arc_an_s(editor, net):
    """Which is the whole of what the menu is for."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    menu = editor.view.arc_menu(arc)
    chosen = [action for action in menu.actions() if action.data() is ArcShape.S_CURVED]

    chosen[0].trigger()

    assert arc.shape_kind is ArcShape.S_CURVED
    assert arc.curved


def test_the_menu_says_when_the_arc_is_an_s(editor, net):
    """A menu that says what a thing is is worth more than one that only says
    what can be done to it."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.shape_kind = ArcShape.S_CURVED

    checked = [
        action.data()
        for action in editor.view.arc_menu(arc).actions()
        if action.isCheckable() and action.isChecked()
    ]

    assert checked == [ArcShape.S_CURVED]


# ----------------------------------------------------------------------
# The L, and the corners it turns
# ----------------------------------------------------------------------


@pytest.fixture
def ell(editor, net):
    """Give an L-shaped arc, selected, so that its corners are out.

    Parameters
    ----------
    editor : masafi_simtwin.documents.petri_net.PetriNetEditor
        The document.
    net : tuple
        The place and the transition.

    Returns
    -------
    masafi_simtwin.documents.arc.Arc
        The arc.
    """

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.shape_kind = ArcShape.L_SHAPED
    arc.setSelected(True)
    return arc


def corner_angle(arc) -> float:
    """Give the angle the arc turns through at its first corner, in degrees.

    Parameters
    ----------
    arc : masafi_simtwin.documents.arc.Arc
        The arc, which must have at least one point.

    Returns
    -------
    float
        The angle between the leg coming in and the leg going out.
    """

    knots = [arc.line.p1(), *arc.curve_points(), arc.line.p2()]
    one = (knots[1].x() - knots[0].x(), knots[1].y() - knots[0].y())
    two = (knots[2].x() - knots[1].x(), knots[2].y() - knots[1].y())
    dot = one[0] * two[0] + one[1] * two[1]
    return math.degrees(
        math.acos(dot / (math.hypot(*one) * math.hypot(*two)))
    )


def test_an_l_is_an_l_as_soon_as_it_is_chosen(ell):
    """One corner, and a **right** one: half way along the chord and half way
    across it is on the circle whose diameter is the chord, and every point of
    that circle sees the chord at a right angle."""

    assert len(ell.curve_points()) == 1
    assert corner_angle(ell) == pytest.approx(90.0, abs=1e-6)


def test_an_l_stays_square_when_the_net_is_dragged_about(ell, net):
    """The point is kept in the chord's own frame, so the frame turns and
    scales with the arc and the corner goes on being a right angle."""

    place, transition = net
    transition.setPos(QPointF(30.0, 90.0))
    place.setPos(QPointF(95.0, 25.0))

    assert corner_angle(ell) == pytest.approx(90.0, abs=1e-6)


def test_an_l_is_straight_between_its_points(ell):
    """Which is the whole of what makes it an L rather than an S: the line goes
    from corner to corner and bends nowhere in between."""

    ell.insert_point(ell.path().pointAtPercent(0.75))

    for leg in ell.segment_paths():
        start = leg.pointAtPercent(0.0)
        finish = leg.pointAtPercent(1.0)
        span = math.hypot(finish.x() - start.x(), finish.y() - start.y())
        for step in range(1, 20):
            where = leg.pointAtPercent(step / 20.0)
            across = abs(
                (finish.x() - start.x()) * (start.y() - where.y())
                - (start.x() - where.x()) * (finish.y() - start.y())
            ) / span
            assert across < 1e-6


def test_an_l_and_an_s_are_one_route_drawn_two_ways(editor, net):
    """They share the points, so changing an arc from one to the other keeps
    where it goes and changes only whether its corners are rounded off."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.shape_kind = ArcShape.S_CURVED
    arc.setSelected(True)
    first = arc.curve_points()[0]
    arc.move_handle(point_handle(0), QPointF(first.x(), first.y() + 9.0))
    route = [arc.chord_frame(point) for point in arc.curve_points()]

    arc.shape_kind = ArcShape.L_SHAPED

    assert [arc.chord_frame(point) for point in arc.curve_points()] == route


def test_a_shape_led_through_points_starts_as_what_it_is_named(editor, net):
    """An S comes out an S and an L comes out an L, and a straight arc carries
    no points at all until it is made one of them."""

    place, transition = net
    arc = editor.add_arc(place, transition)

    assert arc.curve_points() == []

    arc.shape_kind = ArcShape.L_SHAPED
    assert len(arc.curve_points()) == 1

    other = editor.add_arc(place, transition)
    other.shape_kind = ArcShape.S_CURVED
    assert len(other.curve_points()) == 2


def test_taking_every_point_out_and_choosing_the_shape_again_starts_over(ell):
    """Which is the way back from a route that has gone wrong, and it falls out
    of seeding only when there are none rather than needing a *reset*."""

    while ell.remove_point(0):
        pass
    assert ell.curve_points() == []

    ell.shape_kind = ArcShape.STRAIGHT
    ell.shape_kind = ArcShape.L_SHAPED

    assert len(ell.curve_points()) == 1
    assert corner_angle(ell) == pytest.approx(90.0, abs=1e-6)


def test_a_corner_can_be_put_into_an_l_and_taken_out_again(ell):
    """The same gesture the S has, on the same points."""

    index = ell.insert_point(ell.path().pointAtPercent(0.25))

    assert index == 0
    assert len(ell.curve_points()) == 2

    assert ell.remove_point(index)
    assert len(ell.curve_points()) == 1


def test_an_l_carries_a_handle_on_every_corner(ell):
    """They are the handles, as the S's points are."""

    ell.insert_point(ell.path().pointAtPercent(0.25))

    assert sorted(ell.handles()) == sorted(
        [point_handle(0), point_handle(1), *END_HANDLES]
    )


def test_a_corner_of_an_l_is_dragged_where_it_is_put(editor, ell):
    """On the line and under the pointer, snapped to the millimetre."""

    was = ell.curve_points()[0]
    wants = QPointF(was.x() + 3.4, was.y() - 5.6)
    snapped = QPointF(editor.view.snap(wants.x()), editor.view.snap(wants.y()))

    ell.move_handle(point_handle(0), wants)

    assert ell.curve_points()[0].x() == pytest.approx(snapped.x(), abs=1e-6)
    assert ell.curve_points()[0].y() == pytest.approx(snapped.y(), abs=1e-6)


def test_the_arrowhead_of_an_l_lies_along_its_last_leg(ell):
    """A leg is straight, so the head is simply on it — and it is the same head
    every other shape carries."""

    head = ell.arrow()
    tip = QPointF(head.elementAt(0).x, head.elementAt(0).y)
    middle = base_of(head)
    knots = [ell.line.p1(), *ell.curve_points(), ell.line.p2()]
    leg = QLineF(knots[-2], knots[-1])

    assert math.hypot(tip.x() - middle.x(), tip.y() - middle.y()) == pytest.approx(
        ARROW_LENGTH, abs=1e-3
    )
    assert off_the_line(ell.path(), middle) < 0.01
    assert QLineF(middle, tip).angle() == pytest.approx(leg.angle(), abs=0.5)


def test_an_l_offers_its_points_in_the_menu(editor, ell):
    """The same two entries the S has, in the same place, for the same reason."""

    on = ell.path().pointAtPercent(0.25)
    corner = ell.curve_points()[0]

    assert 'Add Point' in entries(editor.view.arc_menu(ell, on))
    assert 'Delete Point' in entries(editor.view.arc_menu(ell, corner))


# ----------------------------------------------------------------------
# Putting an end somewhere else
# ----------------------------------------------------------------------


def drag_end(view, arc, end: str, target, port: int) -> None:
    """Take one end of an arc off and put it on a connecting point.

    Parameters
    ----------
    view : masafi_simtwin.documents.canvas.CanvasView
        The view.
    arc : masafi_simtwin.documents.arc.Arc
        The arc, which must be selected for its handles to be there at all.
    end : str
        ``source`` or ``target``.
    target : masafi_simtwin.documents.net_item.NetItem
        What to put it on.
    port : int
        Which of that item's connecting points to let go nearest.
    """

    start = viewport_point(view, arc.handles()[end])
    finish = viewport_point(view, target.scene_ports()[port])
    view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    view.mouseMoveEvent(mouse(QEvent.Type.MouseMove, finish))
    view.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, finish))


def test_a_selected_arc_carries_a_handle_at_each_end(editor, net):
    """On the connecting point that end is attached to, which is where it is
    taken hold of to be put somewhere else."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.setSelected(True)

    assert arc.handles()['source'] == arc.line.p1()
    assert arc.handles()['target'] == arc.line.p2()


def test_an_end_can_be_put_on_another_point_of_the_same_item(editor, net):
    """Which is the whole of *change the connection point*."""

    place, transition = net
    arc = editor.add_arc(place, transition, source_port=0, target_port=10)
    arc.setSelected(True)

    drag_end(editor.view, arc, 'source', place, 4)

    assert arc.source is place
    assert arc.source_port == 4
    assert arc.line.p1() == place.scene_ports()[4]
    assert place.arcs == [arc]


def test_the_far_end_stays_where_it_was(editor, net):
    """Only the end that was taken hold of moves."""

    place, transition = net
    arc = editor.add_arc(place, transition, source_port=0, target_port=10)
    arc.setSelected(True)
    was = arc.target_port

    drag_end(editor.view, arc, 'source', place, 4)

    assert arc.target is transition
    assert arc.target_port == was


def test_the_target_end_can_be_moved_too(editor, net):
    """Both ends carry a handle and both work the same way."""

    place, transition = net
    arc = editor.add_arc(place, transition, source_port=0, target_port=10)
    arc.setSelected(True)

    drag_end(editor.view, arc, 'target', transition, 5)

    assert arc.target_port == 5
    assert arc.source_port == 0


def test_an_end_can_be_put_on_another_item_altogether(editor, net):
    """The same gesture: it is one question — where does this end go?"""

    place, transition = net
    other = editor.add_element('pt-petri-net', 'place', QPointF(20.0, 70.0))
    arc = editor.add_arc(place, transition)
    arc.setSelected(True)

    drag_end(editor.view, arc, 'source', other, 0)

    assert arc.source is other
    assert other.arcs == [arc]
    assert place.arcs == []
    assert arc.line.p1() == other.scene_ports()[0]


def test_an_end_cannot_be_put_on_something_it_may_not_join(editor, net):
    """A Petri net stays bipartite however an arc is moved about."""

    place, transition = net
    other = editor.add_element('pt-petri-net', 'transition', QPointF(20.0, 70.0))
    arc = editor.add_arc(place, transition)
    arc.setSelected(True)

    drag_end(editor.view, arc, 'source', other, 0)

    assert arc.source is place
    assert other.arcs == []


def test_an_end_cannot_be_put_on_the_arc_own_other_end(editor, net):
    """An arc from a thing to itself is not an arc."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.setSelected(True)

    drag_end(editor.view, arc, 'source', transition, 3)

    assert arc.source is place
    assert arc.target is transition


def test_moving_an_end_makes_no_new_arc(editor, net):
    """Nothing is emitted for it: no arc has come or gone."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.setSelected(True)
    drawn = []
    editor.view.connection_drawn.connect(lambda *args: drawn.append(args))

    drag_end(editor.view, arc, 'source', place, 4)

    assert drawn == []
    assert editor.arcs == [arc]


def test_an_end_handle_is_taken_before_a_new_arc_is_started(editor, net):
    """The handle sits on the connecting point a press would otherwise start a
    new arc from, so the two gestures cannot both fire."""

    place, transition = net
    arc = editor.add_arc(place, transition, source_port=0)
    arc.setSelected(True)
    spot = viewport_point(editor.view, arc.handles()['source'])

    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, spot))

    assert editor.view.moving_end == (arc, 'source')
    assert editor.view.connecting is transition


def test_a_press_on_a_point_of_an_unselected_arc_starts_a_new_arc(editor, net):
    """Only a selected arc has handles, so nothing is in the way until an arc
    has been chosen."""

    place, transition = net
    arc = editor.add_arc(place, transition, source_port=0)
    spot = viewport_point(editor.view, place.scene_ports()[0])

    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, spot))

    assert editor.view.moving_end is None
    assert editor.view.connecting is place
    assert arc.source_port == 0


def test_giving_up_leaves_the_end_where_it_was(editor, net):
    """Escape means escape here too."""

    place, transition = net
    arc = editor.add_arc(place, transition, source_port=0, target_port=10)
    arc.setSelected(True)
    start = viewport_point(editor.view, arc.handles()['source'])

    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    editor.view.keyPressEvent(
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    )

    assert editor.view.moving_end is None
    assert (arc.source, arc.source_port) == (place, 0)


def test_dropping_an_end_on_nothing_leaves_it_where_it_was(editor, net):
    """A drag that missed is a drag that missed, here as anywhere."""

    place, transition = net
    arc = editor.add_arc(place, transition, source_port=0)
    arc.setSelected(True)
    start = viewport_point(editor.view, arc.handles()['source'])
    nowhere = QPointF(40.0, 300.0)

    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    editor.view.mouseMoveEvent(mouse(QEvent.Type.MouseMove, nowhere))
    editor.view.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, nowhere))

    assert (arc.source, arc.source_port) == (place, 0)
    assert editor.view.moving_end is None


def test_putting_an_end_where_it_already_is_changes_nothing(editor, net):
    """Which is what a click on a handle comes to."""

    place, transition = net
    arc = editor.add_arc(place, transition, source_port=3)

    assert not arc.reattach('source', place, 3)
    assert arc.reattach('source', place, 4)


def test_a_shaping_handle_is_not_an_end_handle(editor, net):
    """The arc drags the ones that shape it; the canvas drags the ones at its
    ends.  Asking for one must never hand back the other."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.shape_kind = ArcShape.CURVED
    arc.setSelected(True)

    assert arc.handle_at(arc.handles()['middle'], SHAPE_HANDLES) == 'middle'
    assert arc.handle_at(arc.handles()['middle'], END_HANDLES) is None
    assert arc.handle_at(arc.handles()['source'], END_HANDLES) == 'source'
    assert arc.handle_at(arc.handles()['source'], SHAPE_HANDLES) is None
