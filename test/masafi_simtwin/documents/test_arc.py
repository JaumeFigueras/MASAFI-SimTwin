"""Tests for the arcs of a Petri net, and for the gesture that draws one."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QColor, QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QDialog

from masafi_simtwin.documents import petri_net
from masafi_simtwin.documents.arc import ARROW_LENGTH, DEFAULT_WEIGHT, Arc
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
