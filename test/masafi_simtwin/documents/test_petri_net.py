"""Tests for the Petri net document."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QLineF, QPointF, Qt
from PyQt6.QtGui import QContextMenuEvent, QMouseEvent
from PyQt6.QtWidgets import QDialog, QMenu

from masafi_simtwin.documents.arc import (
    DEFAULT_CONTROLS,
    DEFAULT_S_POINTS,
    ArcKind,
    ArcShape,
)
from masafi_simtwin.documents.canvas import Canvas
from masafi_simtwin.documents.place import Place
from masafi_simtwin.documents.petri_net import PetriNetEditor
from masafi_simtwin.documents.ruler import MILLIMETRES
from simtwin_core.operations import (
    OPERATIONS,
    AddArc,
    AddGuide,
    AddNode,
    Change,
    MoveArcEnd,
    MoveGuide,
    MoveNode,
    Operation,
    RemoveArc,
    RemoveGuide,
    RemoveNode,
    SetArcBends,
    SetArcKind,
    SetArcShape,
    SetArcWeight,
    SetDescription,
    SetNodeName,
    SetTokens,
    SetVertical,
)
from simtwin_core.petri_net import (
    ArcData,
    GuideData,
    NetDocument,
    PlaceData,
    TransitionData,
)

#: The manifest entry the editor is opened over.
MODEL = {
    'uuid': '7f3f9c6a',
    'name': 'Filling Station',
    'kind': 'petri-net',
    'file': 'models/Filling_Station.pnml',
    'units': {'time': 's'},
}


@pytest.fixture
def editor(qtbot):
    """Build a Petri net document over a model.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    masafi_simtwin.documents.petri_net.PetriNetEditor
        The document.
    """

    widget = PetriNetEditor(MODEL)
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    return widget


def test_the_editor_knows_which_model_it_shows(editor):
    """Its UUID is also the key of its tab, so the two cannot drift apart."""

    assert editor.model_id == MODEL['uuid']
    assert editor.model_name == 'Filling Station'


def test_a_net_is_drawn_on_a_ruled_sheet(editor):
    """The same sheet the flow and 2D documents will be drawn on."""

    assert isinstance(editor, Canvas)
    assert all(ruler.unit is MILLIMETRES for ruler in editor.rulers)


def test_an_empty_net_says_it_is_empty(editor):
    """Honestly: there is nothing to put on it yet."""

    assert editor.view.empty_note


# ----------------------------------------------------------------------
# The names the editor invents
# ----------------------------------------------------------------------


def put(editor, element: str, across: float):
    """Put a place or a transition on the sheet.

    Parameters
    ----------
    editor : masafi_simtwin.documents.petri_net.PetriNetEditor
        The document.
    element : str
        ``place`` or ``transition``.
    across : float
        Where, in millimetres from the left; they all stand on one line.

    Returns
    -------
    masafi_simtwin.documents.net_item.NetItem
        The item.
    """

    return editor.add_element('pt-petri-net', element, QPointF(across, 40.0))


def test_places_and_transitions_are_named_as_they_are_put_down(editor):
    """``P1``, ``P2`` and ``T1``: each counts on its own."""

    first = put(editor, 'place', 20.0)
    transition = put(editor, 'transition', 50.0)
    second = put(editor, 'place', 80.0)

    assert (first.name, second.name, transition.name) == ('P1', 'P2', 'T1')


def test_a_new_name_follows_the_highest_in_use(editor):
    """A name deleted from the middle of a net is not handed out again."""

    places = [put(editor, 'place', 20.0 + 25.0 * index) for index in range(3)]
    editor.view.remove(places[1])

    assert put(editor, 'place', 120.0).name == 'P4'


def test_every_name_in_a_net_is_its_own(editor):
    """MASAFI-sim-petri knows a node by its name."""

    for index in range(4):
        put(editor, 'place' if index % 2 else 'transition', 20.0 + 25.0 * index)

    assert len(set(editor.names)) == len(editor.names) == 4


def test_an_invented_name_is_a_python_identifier_with_no_digit_first(editor):
    """The rule names will be held to when they can be typed."""

    names = [put(editor, 'place', 20.0).name, put(editor, 'transition', 50.0).name]

    assert all(name.isidentifier() and not name[0].isdigit() for name in names)


def test_a_name_that_was_not_invented_is_passed_over(editor):
    """Only the names of the pattern count towards the next number."""

    put(editor, 'place', 20.0).name = 'Buffer'

    assert editor.next_name(Place.NAME_PREFIX) == 'P1'


def test_an_item_made_outside_the_editor_has_no_name_yet():
    """The name is the net's to give, not the item's."""

    assert Place().name == ''


# ----------------------------------------------------------------------
# The net as a document
# ----------------------------------------------------------------------


def fresh_editor(qtbot):
    """Build a second editor over the same model, to load a document into.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    masafi_simtwin.documents.petri_net.PetriNetEditor
        The document, shown.
    """

    widget = PetriNetEditor(MODEL)
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    return widget


def draw_a_net(editor) -> dict:
    """Draw a net with something of everything a net can hold.

    Two places, two transitions, an arc of every shape — shaped by hand where a
    shape can be — a weight, an inhibitor arc and a guide each way.

    Parameters
    ----------
    editor : masafi_simtwin.documents.petri_net.PetriNetEditor
        Where to draw it.

    Returns
    -------
    dict
        What was drawn, by what it is.
    """

    add = editor.add_element
    place = add('pt-petri-net', 'place', QPointF(20.0, 20.0))
    other = add('pt-petri-net', 'place', QPointF(20.0, 80.0))
    transition = add('pt-petri-net', 'transition', QPointF(70.0, 20.0))
    second = add('pt-petri-net', 'transition', QPointF(70.0, 80.0))

    straight = editor.add_arc(place, transition, source_port=0, target_port=10)
    straight.weight = 3
    curved = editor.add_arc(transition, place, shape_kind=ArcShape.CURVED)
    curved.move_handle('source_control', curved.chord_point(0.3, 0.4))
    ess = editor.add_arc(other, second, shape_kind=ArcShape.S_CURVED)
    ess.insert_point(ess.path().pointAtPercent(0.5))
    ell = editor.add_arc(second, place, shape_kind=ArcShape.L_SHAPED)
    inhibitor = editor.add_arc(other, transition, kind=ArcKind.INHIBITOR)

    editor.add_guide(Qt.Orientation.Horizontal, 50.0)
    editor.add_guide(Qt.Orientation.Vertical, 45.0)
    return {
        'place': place,
        'other': other,
        'transition': transition,
        'second': second,
        'straight': straight,
        'curved': curved,
        'ess': ess,
        'ell': ell,
        'inhibitor': inhibitor,
    }


def test_an_empty_sheet_is_an_empty_net(editor):
    """Of the model the sheet shows."""

    assert editor.to_document() == NetDocument(model_uuid=MODEL['uuid'])


def test_every_node_is_described_by_its_identity_name_and_centre(editor):
    """Which is all a node is, until it carries tokens."""

    drawn = draw_a_net(editor)
    document = editor.to_document()

    assert document.places[0] == PlaceData(drawn['place'].uuid, 'P1', (20.0, 20.0))
    assert document.transitions[1] == TransitionData(drawn['second'].uuid, 'T2', (70.0, 80.0))


def test_an_arc_is_described_as_it_is_drawn(editor):
    """Its ends, its connecting points, its weight, its kind, its shape and its
    bends as the arc keeps them — never as *untouched*."""

    drawn = draw_a_net(editor)
    straight, ess = drawn['straight'], drawn['ess']
    described = {arc.uuid: arc for arc in editor.to_document().arcs}

    assert described[straight.uuid] == ArcData(
        straight.uuid,
        drawn['place'].uuid,
        drawn['transition'].uuid,
        0,
        10,
        3,
        'normal',
        'straight',
        straight.control_frames,
        (),
    )
    assert described[ess.uuid].shape == 's-curved'
    assert described[ess.uuid].points == ess.point_frames
    assert len(described[ess.uuid].points) == 3
    assert described[drawn['inhibitor'].uuid].kind == 'inhibitor'


def test_every_arc_has_an_identity_of_its_own(editor):
    """An arc has no name, so its UUID is what a document tells it apart by."""

    draw_a_net(editor)

    assert len({arc.uuid for arc in editor.arcs}) == len(editor.arcs) == 5


def test_the_guides_are_part_of_the_drawing(editor):
    """Not of the net, but of what is saved with it."""

    draw_a_net(editor)

    assert editor.to_document().guides == (
        GuideData('horizontal', 50.0),
        GuideData('vertical', 45.0),
    )


def test_a_document_holds_its_nodes_in_reading_order(editor):
    """``P2`` before ``P10``, whatever order the scene holds them in, so the same
    net is always the same file."""

    for index in range(10):
        put(editor, 'place', 20.0 + 12.0 * index)
    editor.places[3].setSelected(True)

    names = [place.name for place in editor.to_document().places]

    assert names == [f'P{number}' for number in range(1, 11)]


def test_a_net_comes_back_as_it_was_drawn(editor, qtbot):
    """The whole point: a net read back is the net that was written."""

    draw_a_net(editor)
    document = editor.to_document()

    again = fresh_editor(qtbot)
    again.load_document(document)

    assert again.to_document() == document


def test_a_net_read_back_is_drawn_exactly_as_it_was(editor, qtbot):
    """Not merely described alike: every arc runs through the same places."""

    draw_a_net(editor)
    again = fresh_editor(qtbot)
    again.load_document(editor.to_document())
    before = {arc.uuid: arc.path() for arc in editor.arcs}
    after = {arc.uuid: arc.path() for arc in again.arcs}

    assert before.keys() == after.keys()
    for uuid, path in before.items():
        for step in range(11):
            gap = QLineF(
                path.pointAtPercent(step / 10.0), after[uuid].pointAtPercent(step / 10.0)
            ).length()
            assert gap < 1e-9, uuid


def test_loading_replaces_what_was_on_the_sheet(editor):
    """A sheet shows one net."""

    put(editor, 'place', 20.0)
    editor.add_guide(Qt.Orientation.Vertical, 10.0)
    document = NetDocument(
        model_uuid=MODEL['uuid'],
        transitions=(TransitionData('t', 'T1', (40.0, 40.0)),),
    )

    editor.load_document(document)

    assert editor.places == []
    assert editor.guides == []
    assert [transition.name for transition in editor.transitions] == ['T1']


def test_names_are_invented_after_the_highest_loaded(editor):
    """A loaded ``P7`` is a name in use like any other."""

    editor.load_document(NetDocument(places=(PlaceData('p', 'P7', (20.0, 20.0)),)))

    assert put(editor, 'place', 60.0).name == 'P8'


def test_an_untouched_arc_is_given_its_shapes_defaults(editor):
    """What a file from another tool, which knows nothing of bends, gives."""

    editor.load_document(
        NetDocument(
            places=(PlaceData('p', 'P1', (20.0, 20.0)),),
            transitions=(TransitionData('t', 'T1', (60.0, 20.0)),),
            arcs=(ArcData('a', 'p', 't', 0, 10, shape='s-curved'),),
        )
    )
    arc = editor.arcs[0]

    assert arc.control_frames == DEFAULT_CONTROLS
    assert arc.point_frames == DEFAULT_S_POINTS


def test_an_s_without_points_is_not_given_them_back(editor):
    """Every point taken out is a straight line, and it is read back as one."""

    editor.load_document(
        NetDocument(
            places=(PlaceData('p', 'P1', (20.0, 20.0)),),
            transitions=(TransitionData('t', 'T1', (60.0, 20.0)),),
            arcs=(ArcData('a', 'p', 't', 0, 10, shape='s-curved', points=()),),
        )
    )

    assert editor.arcs[0].curve_points() == []


def test_a_position_read_back_is_snapped_like_any_other(editor):
    """A net written by another tool lands on the millimetre."""

    editor.load_document(NetDocument(places=(PlaceData('p', 'P1', (20.4, 19.7)),)))

    assert editor.to_document().places[0].position == (20.0, 20.0)


def test_a_connecting_point_a_node_lacks_is_held_to_its_last(editor):
    """So the arc drawn is the arc written back."""

    editor.load_document(
        NetDocument(
            places=(PlaceData('p', 'P1', (20.0, 20.0)),),
            transitions=(TransitionData('t', 'T1', (60.0, 20.0)),),
            arcs=(ArcData('a', 'p', 't', 500, 10),),
        )
    )
    arc = editor.arcs[0]

    assert arc.source_port == len(arc.source.ports()) - 1
    assert editor.to_document().arcs[0].source_port == arc.source_port


def test_loading_leaves_the_bar_showing_the_next_arc(editor, qtbot):
    """Nothing is selected in a net just read."""

    draw_a_net(editor)['curved'].setSelected(True)
    again = fresh_editor(qtbot)
    again.load_document(editor.to_document())

    assert again.scene().selectedItems() == []
    assert again.arc_tool_bar.target_text == 'New Arc'


def test_the_route_of_an_arc_is_where_its_points_are_on_the_sheet(editor):
    """For readers that know nothing of the chord frame; nothing for an arc led
    through nothing."""

    drawn = draw_a_net(editor)
    described = {arc.uuid: arc for arc in editor.to_document().arcs}

    for name in ('ell', 'ess'):
        arc = drawn[name]
        assert described[arc.uuid].route == tuple(
            (point.x(), point.y()) for point in arc.curve_points()
        )
        assert described[arc.uuid].route
    assert described[drawn['straight'].uuid].route == ()
    assert described[drawn['curved'].uuid].route == ()


def test_an_arc_left_without_connecting_points_takes_the_ones_facing(editor):
    """Which is what a file from another tool gives."""

    editor.load_document(
        NetDocument(
            places=(PlaceData('p', 'P1', (20.0, 20.0)),),
            transitions=(TransitionData('t', 'T1', (60.0, 20.0)),),
            arcs=(ArcData('a', 'p', 't', None, None),),
        )
    )
    arc = editor.arcs[0]

    assert arc.source_port == arc.source.port_index_towards(arc.target.scenePos())
    assert arc.line.p2().x() < arc.target.scenePos().x()


# ----------------------------------------------------------------------
# Changing the net
# ----------------------------------------------------------------------


def little_net(editor):
    """Draw the smallest net every operation can be tried against.

    Two places — one of them joined to nothing, so that it can be removed and
    moved about — a transition, an arc, and a guide.

    Parameters
    ----------
    editor : masafi_simtwin.documents.petri_net.PetriNetEditor
        Where to draw it.

    Returns
    -------
    tuple
        The place, the free place, the transition and the arc.
    """

    place = editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))
    free = editor.add_element('pt-petri-net', 'place', QPointF(20.0, 80.0))
    transition = editor.add_element('pt-petri-net', 'transition', QPointF(60.0, 20.0))
    arc = editor.add_arc(place, transition, source_port=0, target_port=10)
    editor.add_guide(Qt.Orientation.Horizontal, 50.0)
    return place, free, transition, arc


def operations_for(editor) -> dict:
    """Give one of every operation there is, against the net just drawn.

    Parameters
    ----------
    editor : masafi_simtwin.documents.petri_net.PetriNetEditor
        An empty document, on which the net is drawn.

    Returns
    -------
    dict
        The operations, by the name they are written under, so that an
        operation added to the core and forgotten here is a test that fails
        rather than a gap nobody sees.
    """

    place, free, transition, arc = little_net(editor)
    guide = GuideData('horizontal', 50.0)
    where = (free.pos().x(), free.pos().y())
    made = [
        AddNode(PlaceData('new-place', 'P9', (100.0, 40.0))),
        RemoveNode(PlaceData(free.uuid, free.name, where)),
        MoveNode(free.uuid, where, (90.0, 90.0)),
        SetNodeName(free.uuid, free.name, 'Buffer'),
        SetTokens(place.uuid, 0, 3),
        SetDescription(transition.uuid, '', 'Fill a bottle'),
        SetVertical(transition.uuid, False, True),
        AddArc(
            ArcData(
                'new-arc',
                transition.uuid,
                place.uuid,
                3,
                4,
                controls=DEFAULT_CONTROLS,
                points=(),
            )
        ),
        RemoveArc(editor.to_document().arcs[0]),
        MoveArcEnd(arc.uuid, 'source', place.uuid, arc.source_port, free.uuid, 2),
        SetArcShape(arc.uuid, 'straight', 'l-shaped'),
        SetArcKind(arc.uuid, 'normal', 'inhibitor'),
        SetArcWeight(arc.uuid, 1, 5),
        SetArcBends(
            arc.uuid,
            arc.control_frames,
            arc.point_frames,
            ((0.3, 0.4), (0.6, 0.2)),
            ((0.5, 0.5),),
        ),
        AddGuide(GuideData('vertical', 45.0)),
        RemoveGuide(guide),
        MoveGuide(guide, GuideData('horizontal', 70.0)),
    ]
    return {operation.NAME: operation for operation in made}


@pytest.mark.parametrize('name', sorted(OPERATIONS), ids=sorted(OPERATIONS))
def test_the_sheet_and_the_description_agree_about_every_operation(editor, name):
    """The whole of why the operations are in the core: an operation applied to
    the sheet and the same operation applied to the sheet's description give one
    answer.  Two ways of meaning one edit that cannot drift apart."""

    operation = operations_for(editor)[name]
    before = editor.to_document()

    editor.apply(Change('gesture', (operation,)))

    assert editor.to_document() == operation.apply(before)


@pytest.mark.parametrize('name', sorted(OPERATIONS), ids=sorted(OPERATIONS))
def test_every_operation_undone_leaves_the_sheet_as_it_was(editor, name):
    """Which is what the undo stack will be made of."""

    operation = operations_for(editor)[name]
    before = editor.to_document()
    change = Change('gesture', (operation,))

    editor.apply(change)
    editor.apply(change.inverse())

    assert editor.to_document() == before


def test_a_change_of_several_operations_is_undone_whole(editor):
    """Deleting a place takes its arcs with it, and undoing brings back both."""

    place, _free, _transition, arc = little_net(editor)
    document = editor.to_document()
    change = Change(
        'delete',
        (
            RemoveArc(document.arcs[0]),
            RemoveNode(PlaceData(place.uuid, place.name, (place.pos().x(), place.pos().y()))),
        ),
    )

    editor.apply(change)
    assert (len(editor.places), len(editor.arcs)) == (1, 0)

    editor.apply(change.inverse())

    assert editor.to_document() == document


def test_an_undone_item_comes_back_as_itself(editor):
    """The same UUID and the same name, not a new place that looks like it."""

    place, _free, _transition, _arc = little_net(editor)
    was = (place.uuid, place.name)
    change = Change(
        'delete',
        (
            RemoveArc(editor.to_document().arcs[0]),
            RemoveNode(PlaceData(place.uuid, place.name, (place.pos().x(), place.pos().y()))),
        ),
    )

    editor.apply(change)
    editor.apply(change.inverse())

    restored = editor.node(was[0])
    assert (restored.uuid, restored.name) == was


def test_an_undone_arc_comes_back_drawn_as_it_was(editor):
    """Not a straight line between the same two items."""

    _place, _free, _transition, arc = little_net(editor)
    arc.shape_kind = ArcShape.S_CURVED
    arc.insert_point(arc.path().pointAtPercent(0.5))
    before = arc.path()
    change = Change('delete', (RemoveArc(editor.to_document().arcs[0]),))

    editor.apply(change)
    editor.apply(change.inverse())

    after = editor.arcs[0].path()
    for step in range(11):
        gap = QLineF(
            before.pointAtPercent(step / 10.0), after.pointAtPercent(step / 10.0)
        ).length()
        assert gap < 1e-9


def test_an_operation_about_something_that_is_not_on_the_sheet_is_refused(editor):
    """A change made against another net, or a journal that has been damaged."""

    little_net(editor)

    with pytest.raises(ValueError, match='no node'):
        editor.apply(Change('move', (MoveNode('nobody', (0.0, 0.0), (1.0, 1.0)),)))
    with pytest.raises(ValueError, match='no arc'):
        editor.apply(Change('weight', (SetArcWeight('nothing', 1, 2),)))
    with pytest.raises(ValueError, match='guide'):
        editor.apply(Change('guide', (RemoveGuide(GuideData('vertical', 12.0)),)))


def test_an_operation_the_editor_cannot_make_is_refused(editor):
    """One added to the core and forgotten here."""

    class Invented(Operation):
        NAME = 'invented'

    with pytest.raises(TypeError, match='invented|Invented'):
        editor.apply(Change('gesture', (Invented(),)))


def test_an_operation_says_what_a_thing_is_rather_than_what_it_is_untouched(editor):
    """An operation the editor records carries the bends an arc **has**, not
    ``None``.  ``None`` is what a description read from another tool says, and
    it still draws: the arc is given the shape's own defaults, which is what
    the editor has always done with a shape it was given nothing else about."""

    _place, _free, transition, arc = little_net(editor)
    described = editor.to_document().arcs[0]

    assert described.controls == arc.control_frames
    assert described.points == ()

    editor.apply(
        Change(
            'draw',
            (AddArc(ArcData('bare', transition.uuid, _place.uuid, 3, 4, shape='s-curved')),),
        )
    )

    assert editor.arc('bare').point_frames == DEFAULT_S_POINTS


# ----------------------------------------------------------------------
# What can be undone
# ----------------------------------------------------------------------


def test_every_gesture_is_one_entry_on_the_stack(editor):
    """Three elements dropped and an arc drawn are four things to undo, in the
    order they were done."""

    little_net(editor)

    assert editor.undo_stack.count() == 4
    assert editor.undo_stack.command(3).text() == 'Draw Arc'
    assert editor.undo_stack.command(0).text() == 'Add Element'


def test_dropping_an_element_is_undone_and_done_again(editor):
    """And the element comes back as itself, name and all."""

    before = editor.to_document()
    place = editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))
    drawn = editor.to_document()

    editor.undo_stack.undo()
    assert editor.to_document() == before

    editor.undo_stack.redo()
    assert editor.to_document() == drawn
    assert editor.node(place.uuid).name == place.name


def test_drawing_an_arc_is_undone_without_taking_its_items(editor):
    """Undoing a gesture undoes that gesture and nothing more."""

    little_net(editor)

    editor.undo_stack.undo()

    assert editor.arcs == []
    assert len(editor.places) == 2


def test_a_gesture_that_changed_nothing_is_not_on_the_stack(editor):
    """There is nothing to offer to put back."""

    little_net(editor)
    count = editor.undo_stack.count()

    editor.choose_arc_kind(ArcKind.NORMAL)

    assert editor.undo_stack.count() == count


def test_a_shape_chosen_from_the_menu_is_undone_whole(editor):
    """The shape and the points it was given are one gesture, so undoing gives
    back the straight line that was there."""

    _place, _free, _transition, arc = little_net(editor)
    before = editor.to_document()

    editor.view.set_arc_shape(arc, ArcShape.L_SHAPED)

    assert editor.undo_stack.command(editor.undo_stack.count() - 1).text() == 'Change Arc Shape'
    assert len(arc.point_frames) == 1

    editor.undo_stack.undo()

    assert editor.to_document() == before


@pytest.mark.parametrize('gesture', ['add', 'remove'], ids=['add-point', 'remove-point'])
def test_a_point_put_in_or_taken_out_is_undone(editor, gesture):
    """Both are how an arc bends, and both are one entry."""

    _place, _free, _transition, arc = little_net(editor)
    editor.view.set_arc_shape(arc, ArcShape.S_CURVED)
    before = editor.to_document()

    if gesture == 'add':
        editor.view.add_arc_point(arc, arc.path().pointAtPercent(0.5))
        expected = 'Add Point'
    else:
        editor.view.remove_arc_point(arc, 0)
        expected = 'Delete Point'

    assert editor.undo_stack.command(editor.undo_stack.count() - 1).text() == expected
    assert editor.to_document() != before

    editor.undo_stack.undo()

    assert editor.to_document() == before


def test_a_kind_chosen_on_the_bar_is_undone(editor):
    """Whatever the bar does to a selection is one entry."""

    _place, _free, _transition, arc = little_net(editor)
    arc.setSelected(True)
    before = editor.to_document()

    editor.choose_arc_kind(ArcKind.INHIBITOR)

    assert arc.kind is ArcKind.INHIBITOR
    editor.undo_stack.undo()

    assert editor.to_document() == before


def test_a_weight_set_on_arcs_is_one_change_that_undoes(editor):
    """What the Properties pane asks for, named for *Undo*."""

    _place, _free, _transition, arc = little_net(editor)

    assert editor.set_weight((arc.uuid,), 5)

    assert arc.weight == 5
    assert editor.undo_stack.command(editor.undo_stack.count() - 1).text() == 'Change Weight'

    editor.undo_stack.undo()

    assert arc.weight == 1


def test_a_weight_below_one_or_already_carried_is_not_a_change(editor):
    """Nothing to undo."""

    _place, _free, _transition, arc = little_net(editor)
    count = editor.undo_stack.count()

    assert not editor.set_weight((arc.uuid,), 1)
    assert not editor.set_weight((arc.uuid,), 0)
    assert editor.undo_stack.count() == count
    assert arc.weight == 1


def test_a_net_read_from_a_file_has_nothing_to_undo(editor, qtbot):
    """What was drawn before it was saved is not this session's to put back."""

    little_net(editor)
    document = editor.to_document()

    again = fresh_editor(qtbot)
    again.load_document(document)

    assert again.undo_stack.count() == 0
    assert again.undo_stack.isClean()


# ----------------------------------------------------------------------
# What the sheet does, and the document records
# ----------------------------------------------------------------------


def test_dragging_items_is_one_change(editor):
    """Qt moves them as they are dragged, so the sheet says what happened once
    the button is up — and a whole selection moved is one thing to undo."""

    place, free, _transition, _arc = little_net(editor)
    before = editor.to_document()
    count = editor.undo_stack.count()

    editor.view._remember_before_a_drag()
    place.setPos(QPointF(40.0, 40.0))
    free.setPos(QPointF(40.0, 90.0))
    editor.view._report_a_drag()

    assert editor.undo_stack.count() == count + 1
    assert editor.undo_stack.command(count).text() == 'Move'

    editor.undo_stack.undo()

    assert editor.to_document() == before


def test_a_press_and_a_release_are_what_note_and_report_a_drag(editor):
    """The two halves are driven by the mouse, not called by hand: a press notes
    where everything is, and the release says what moved."""

    place, _free, _transition, _arc = little_net(editor)
    count = editor.undo_stack.count()
    spot = QPointF(editor.view.mapFromScene(place.scenePos()))
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        spot,
        spot,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        spot,
        spot,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    editor.view.mousePressEvent(press)
    assert editor.view._before_drag is not None
    place.setPos(QPointF(45.0, 45.0))
    editor.view.mouseReleaseEvent(release)

    assert editor.view._before_drag is None
    assert editor.undo_stack.count() == count + 1
    assert editor.undo_stack.command(count).text() == 'Move'


def test_a_click_that_moves_nothing_is_not_a_change(editor):
    """Selecting an item is not something to undo."""

    little_net(editor)
    count = editor.undo_stack.count()

    editor.view._remember_before_a_drag()
    editor.view._report_a_drag()

    assert editor.undo_stack.count() == count


def test_a_guide_pulled_off_a_ruler_is_recorded(editor):
    """The sheet makes it; the document remembers that it was made."""

    before = editor.to_document()

    editor._on_guide_dragged(editor.horizontal_ruler, QPointF(30.0, 50.0))
    editor._on_guide_dropped(True)

    assert len(editor.guides) == 1
    assert editor.undo_stack.command(editor.undo_stack.count() - 1).text() == 'Add Guide'

    editor.undo_stack.undo()

    assert editor.to_document() == before


def test_a_guide_taken_back_to_its_ruler_is_not_recorded(editor):
    """It was never on the sheet."""

    editor._on_guide_dragged(editor.horizontal_ruler, QPointF(30.0, 50.0))
    editor._on_guide_dropped(False)

    assert editor.guides == []
    assert editor.undo_stack.count() == 0


def test_dragging_a_guide_is_recorded(editor):
    """One entry, and undoing puts it back where it was."""

    guide = editor.add_guide(Qt.Orientation.Horizontal, 50.0)
    editor.view._remember_before_a_drag()
    guide.position = 70.0
    editor.view._report_a_drag()

    assert editor.undo_stack.command(editor.undo_stack.count() - 1).text() == 'Move Guide'

    editor.undo_stack.undo()

    assert [guide.position for guide in editor.guides] == [50.0]


def test_shaping_an_arc_by_hand_is_recorded(editor):
    """Dragging a handle is a change like any other."""

    _place, _free, _transition, arc = little_net(editor)
    editor.view.set_arc_shape(arc, ArcShape.CURVED)
    before = editor.to_document()

    editor.view._remember_before_a_drag()
    arc.move_handle('middle', arc.chord_point(0.5, 0.4))
    editor.view._report_a_drag()

    assert editor.undo_stack.command(editor.undo_stack.count() - 1).text() == 'Shape Arc'

    editor.undo_stack.undo()

    assert editor.to_document() == before


def test_moving_an_arc_end_is_recorded_and_undone(editor):
    """The sheet asks and the document moves it, so it can be put back."""

    place, _free, _transition, arc = little_net(editor)
    before = editor.to_document()

    editor.view.arc_end_asked.emit(arc, 'source', place, 6)

    assert arc.source_port == 6
    assert editor.undo_stack.command(editor.undo_stack.count() - 1).text() == 'Move Arc End'

    editor.undo_stack.undo()

    assert editor.to_document() == before


def test_an_end_put_where_it_already_is_is_not_a_change(editor):
    """A click on a handle that goes nowhere."""

    place, _free, _transition, arc = little_net(editor)
    count = editor.undo_stack.count()

    editor.view.arc_end_asked.emit(arc, 'source', place, arc.source_port)

    assert editor.undo_stack.count() == count


def test_deleting_a_selection_is_one_change_and_is_undone_whole(editor):
    """An item takes its arcs with it, and both come back together."""

    place, _free, _transition, _arc = little_net(editor)
    before = editor.to_document()
    place.setSelected(True)

    assert editor.view.delete_selection() == 1
    assert editor.arcs == []
    assert len(editor.places) == 1
    assert editor.undo_stack.command(editor.undo_stack.count() - 1).text() == 'Delete'

    editor.undo_stack.undo()

    assert editor.to_document() == before


def test_deleting_an_arc_from_its_menu_is_undone(editor):
    """The menu asks the document, as everything that changes the net does."""

    _place, _free, _transition, arc = little_net(editor)
    before = editor.to_document()
    menu = editor.view.arc_menu(arc)

    [action for action in menu.actions() if action.text() == 'Delete Arc'][0].trigger()

    assert editor.arcs == []

    editor.undo_stack.undo()

    assert editor.to_document() == before


def test_deleting_guides_from_the_menu_is_undone(editor):
    """*Delete All Guides* is one change, however many there are."""

    editor.add_guide(Qt.Orientation.Horizontal, 50.0)
    editor.add_guide(Qt.Orientation.Vertical, 45.0)
    before = editor.to_document()
    menu = editor.view.guide_menu(None)

    [action for action in menu.actions() if action.text() == 'Delete All Guides'][0].trigger()

    assert editor.guides == []

    editor.undo_stack.undo()

    assert editor.to_document() == before


# ----------------------------------------------------------------------
# Whether the sheet differs from its file
# ----------------------------------------------------------------------


def test_a_new_sheet_has_nothing_unsaved(editor):
    """Nothing has been done to it."""

    assert not editor.is_modified


def test_a_change_says_the_sheet_is_modified(editor, qtbot):
    """With the model's UUID, so a window knows which tab to mark."""

    with qtbot.waitSignal(editor.modified_changed, timeout=1000) as blocker:
        editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))

    assert blocker.args == [MODEL['uuid'], True]
    assert editor.is_modified


def test_undoing_back_to_the_saved_state_says_so(editor, qtbot):
    """The sheet is what was written again, so nothing is unsaved."""

    editor.undo_stack.setClean()
    editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))

    with qtbot.waitSignal(editor.modified_changed, timeout=1000) as blocker:
        editor.undo_stack.undo()

    assert blocker.args == [MODEL['uuid'], False]
    assert not editor.is_modified


def test_further_changes_say_nothing_more(editor, qtbot):
    """The answer changed once; a second stroke does not change it again."""

    editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))

    with qtbot.assertNotEmitted(editor.modified_changed):
        editor.add_element('pt-petri-net', 'place', QPointF(40.0, 20.0))


def test_a_net_read_from_a_file_is_not_modified(editor, qtbot):
    """What is drawn is the file."""

    little_net(editor)
    document = editor.to_document()
    assert editor.is_modified

    editor.load_document(document)

    assert not editor.is_modified



# ----------------------------------------------------------------------
# Names, tokens and descriptions on the sheet
# ----------------------------------------------------------------------


def test_a_new_place_holds_no_tokens_and_nothing_has_a_description(editor):
    """Until it is given some."""

    place, _free, transition, _arc = little_net(editor)

    assert place.tokens == 0
    assert (place.description, transition.description) == ('', '')


def test_the_tokens_and_descriptions_survive_a_document(editor, qtbot):
    """What is on the sheet is what is described, and what is loaded is drawn."""

    place, _free, transition, _arc = little_net(editor)
    editor.apply(
        Change(
            'gesture',
            (
                SetTokens(place.uuid, 0, 4),
                SetDescription(place.uuid, '', 'Bottles waiting'),
                SetDescription(transition.uuid, '', 'Fill a bottle'),
            ),
        )
    )
    document = editor.to_document()

    again = fresh_editor(qtbot)
    again.load_document(document)

    assert again.to_document() == document
    assert again.node(place.uuid).tokens == 4
    assert again.node(transition.uuid).description == 'Fill a bottle'


def test_tokens_asked_of_a_transition_are_refused(editor):
    """The sheet holds no place of that UUID to put them in."""

    _place, _free, transition, _arc = little_net(editor)

    with pytest.raises(ValueError, match='no place'):
        editor.apply(Change('tokens', (SetTokens(transition.uuid, 0, 2),)))


@pytest.mark.parametrize(
    ('name', 'label'),
    [
        ('rename-node', 'Rename'),
        ('set-tokens', 'Change Tokens'),
        ('set-description', 'Change Description'),
        ('rotate', 'Rotate'),
    ],
)
def test_the_new_changes_are_named_for_undo(editor, name, label):
    """What *Undo* offers to put back."""

    assert editor.change_label(name) == label



def test_an_invented_name_counts_numbers_whatever_the_case_of_their_prefix(editor):
    """Names are unique ignoring case, so beside a ``p7`` the next place is
    ``P8`` rather than a ``P7`` that would clash with it."""

    place, _free, _transition, _arc = little_net(editor)
    editor.apply(Change('rename', (SetNodeName(place.uuid, place.name, 'p7'),)))

    assert editor.next_name('P') == 'P8'


# ----------------------------------------------------------------------
# What is selected
# ----------------------------------------------------------------------


def test_nothing_is_selected_on_a_new_sheet(editor):
    """And an empty selection is false."""

    little_net(editor)

    assert not editor.selection()


def test_the_selection_is_described_rather_than_handed_over(editor):
    """Descriptions, so that whoever shows it never touches the scene; guides,
    having no properties, are left out."""

    place, _free, transition, arc = little_net(editor)
    for item in (place, transition, arc, *editor.guides):
        item.setSelected(True)

    selection = editor.selection()

    assert [data.uuid for data in selection.places] == [place.uuid]
    assert [data.uuid for data in selection.transitions] == [transition.uuid]
    assert [data.uuid for data in selection.arcs] == [arc.uuid]
    assert selection.places[0] == editor.to_document().node(place.uuid)


def test_the_selection_is_held_in_the_order_of_names(editor):
    """Whatever order the scene holds the items in."""

    place, free, _transition, _arc = little_net(editor)
    free.setSelected(True)
    place.setSelected(True)

    assert [data.name for data in editor.selection().places] == sorted(
        [place.name, free.name], key=lambda name: int(name[1:])
    )


def test_a_change_of_selection_is_said_with_the_model(editor, qtbot):
    """So a window knows which document spoke without a lambda to tell it."""

    place, _free, _transition, _arc = little_net(editor)

    with qtbot.waitSignal(editor.selection_changed, timeout=1000) as blocker:
        place.setSelected(True)

    assert blocker.args == [MODEL['uuid']]


# ----------------------------------------------------------------------
# What the Properties pane asks of the sheet
# ----------------------------------------------------------------------


def test_a_node_is_renamed_as_one_change_that_undoes(editor):
    """Named for *Undo*, and put back whole."""

    place, _free, _transition, _arc = little_net(editor)
    count = editor.undo_stack.count()

    assert editor.rename_node(place.uuid, 'Buffer')

    assert place.name == 'Buffer'
    assert editor.undo_stack.count() == count + 1
    assert editor.undo_stack.command(count).text() == 'Rename'
    editor.undo_stack.undo()
    assert place.name == 'P1'


@pytest.mark.parametrize('name', ['t1', 'class', 'Buffer 1', ''])
def test_a_name_the_rule_refuses_is_not_given(editor, name):
    """Held where the change is made, as well as in the pane."""

    place, _free, _transition, _arc = little_net(editor)
    count = editor.undo_stack.count()

    assert not editor.rename_node(place.uuid, name)

    assert place.name == 'P1'
    assert editor.undo_stack.count() == count


def test_renaming_to_the_same_name_is_not_a_change(editor):
    """Nothing to undo."""

    place, _free, _transition, _arc = little_net(editor)
    count = editor.undo_stack.count()

    assert not editor.rename_node(place.uuid, place.name)
    assert editor.undo_stack.count() == count


def test_tokens_are_set_on_every_place_as_one_change(editor):
    """A transition among them holds none and is passed over."""

    place, free, transition, _arc = little_net(editor)
    count = editor.undo_stack.count()

    assert editor.set_tokens((place.uuid, free.uuid, transition.uuid), 4)

    assert (place.tokens, free.tokens) == (4, 4)
    assert editor.undo_stack.count() == count + 1
    assert editor.undo_stack.command(count).text() == 'Change Tokens'
    editor.undo_stack.undo()
    assert (place.tokens, free.tokens) == (0, 0)


def test_tokens_already_held_or_below_nought_are_not_a_change(editor):
    """Nothing to undo."""

    place, _free, _transition, _arc = little_net(editor)
    count = editor.undo_stack.count()

    assert not editor.set_tokens((place.uuid,), 0)
    assert not editor.set_tokens((place.uuid,), -1)
    assert editor.undo_stack.count() == count


def test_a_description_is_set_on_every_node_as_one_change(editor):
    """Places and transitions alike."""

    place, _free, transition, _arc = little_net(editor)

    assert editor.describe((place.uuid, transition.uuid), 'Fill')

    assert (place.description, transition.description) == ('Fill', 'Fill')
    assert editor.undo_stack.command(editor.undo_stack.count() - 1).text() == 'Change Description'
    editor.undo_stack.undo()
    assert (place.description, transition.description) == ('', '')


def test_a_description_of_more_than_one_line_is_not_given(editor):
    """As the document refuses it."""

    place, _free, _transition, _arc = little_net(editor)

    assert not editor.describe((place.uuid,), 'two\nlines')
    assert place.description == ''


def test_the_selection_carries_the_names_of_the_whole_net(editor):
    """What a new name is checked against, without the scene being asked."""

    place, free, transition, _arc = little_net(editor)
    place.setSelected(True)

    assert sorted(editor.selection().names) == sorted([place.name, free.name, transition.name])


# ----------------------------------------------------------------------
# Turning a transition
# ----------------------------------------------------------------------


def test_a_transition_is_turned_as_one_change_that_undoes(editor):
    """A gesture like any other: recorded, named for *Undo*, and put back."""

    _place, _free, transition, _arc = little_net(editor)
    count = editor.undo_stack.count()

    assert editor.rotate((transition.uuid,))

    assert transition.vertical is True
    assert editor.undo_stack.count() == count + 1
    assert editor.undo_stack.command(count).text() == 'Rotate'
    editor.undo_stack.undo()
    assert transition.vertical is False


def test_each_transition_is_turned_the_other_way_round_from_the_way_it_was(editor):
    """So a selection of both is not made to agree, and turning it twice gives
    back exactly the drawing it started as."""

    _place, _free, transition, _arc = little_net(editor)
    upright = editor.add_element('pt-petri-net', 'transition', QPointF(90.0, 60.0))
    upright.vertical = True

    editor.rotate((transition.uuid, upright.uuid))

    assert (transition.vertical, upright.vertical) == (True, False)
    editor.undo_stack.undo()
    assert (transition.vertical, upright.vertical) == (False, True)


def test_a_place_asked_to_turn_is_passed_over(editor):
    """A circle has no way round, so there is nothing to record."""

    place, _free, _transition, _arc = little_net(editor)
    count = editor.undo_stack.count()

    assert not editor.rotate((place.uuid,))
    assert editor.undo_stack.count() == count


def test_the_way_round_survives_a_document(editor, qtbot):
    """What is on the sheet is what is described, and what is loaded is drawn."""

    _place, _free, transition, _arc = little_net(editor)
    editor.rotate((transition.uuid,))
    document = editor.to_document()

    assert document.node(transition.uuid).vertical is True

    again = fresh_editor(qtbot)
    again.load_document(document)

    assert again.to_document() == document
    assert again.node(transition.uuid).vertical is True


def test_the_move_a_turn_forced_is_part_of_the_change(editor):
    """A bar at the very edge of the sheet is brought back onto the paper as it
    stands up, and undoing puts the drawing back rather than most of it."""

    edge = editor.add_element('pt-petri-net', 'transition', QPointF(100.0, 2.0))

    editor.rotate((edge.uuid,))
    moved = edge.pos()

    assert moved.y() > 2.0
    editor.undo_stack.undo()
    assert (edge.vertical, edge.pos().y()) == (False, 2.0)


def test_a_turn_asked_for_on_the_sheet_is_made_by_the_document(editor):
    """The context menu asks, and the document records — the sheet turns nothing
    of its own accord."""

    _place, _free, transition, _arc = little_net(editor)

    editor.view.rotate([transition])

    assert transition.vertical is True
    assert editor.undo_stack.command(editor.undo_stack.count() - 1).text() == 'Rotate'


def test_a_transition_stood_up_by_a_document_is_drawn_that_way(editor):
    """Which is what a journal replayed and a redo both do."""

    _place, _free, transition, _arc = little_net(editor)

    editor.apply(Change('rotate', (SetVertical(transition.uuid, False, True),)))

    assert transition.vertical is True
    assert transition.bar().height() == pytest.approx(16.0)


def test_a_place_the_document_asks_to_turn_is_refused(editor):
    """The sheet holds no transition of that UUID to turn."""

    place, _free, _transition, _arc = little_net(editor)

    with pytest.raises(ValueError, match='no transition'):
        editor.apply(Change('rotate', (SetVertical(place.uuid, False, True),)))


def test_a_transition_offers_to_be_turned_and_a_place_offers_nothing(editor):
    """A bar has a way round and a circle has not, which each item says of
    itself."""

    place, _free, transition, _arc = little_net(editor)

    assert [action.text() for action in editor.view.item_menu(transition).actions()] == ['Rotate']
    assert editor.view.item_menu(place) is None
    assert editor.view.item_menu(None) is None


def test_turning_a_transition_from_its_menu_is_undone(editor):
    """The menu asks the document, as everything that changes the net does."""

    _place, _free, transition, _arc = little_net(editor)
    before = editor.to_document()
    menu = editor.view.item_menu(transition)

    [action for action in menu.actions() if action.text() == 'Rotate'][0].trigger()

    assert transition.vertical is True

    editor.undo_stack.undo()

    assert editor.to_document() == before


def test_the_menu_turns_the_transition_it_was_aimed_at_and_no_other(editor):
    """A context menu is aimed at a thing, as an arc's is."""

    _place, _free, transition, _arc = little_net(editor)
    another = editor.add_element('pt-petri-net', 'transition', QPointF(90.0, 60.0))
    for item in (transition, another):
        item.setSelected(True)

    editor.view.item_menu(transition).actions()[0].trigger()

    assert (transition.vertical, another.vertical) == (True, False)


def test_the_menu_over_a_transition_is_the_item_menu(editor, monkeypatch):
    """The pointer falls through the arcs to the item and stops there, rather
    than reaching the guides that run under it."""

    shown = []
    monkeypatch.setattr(
        QMenu, 'exec', lambda self, *rest: shown.append([action.text() for action in self.actions()])
    )
    _place, _free, transition, _arc = little_net(editor)
    spot = editor.view.mapFromScene(transition.scenePos())

    editor.view.contextMenuEvent(
        QContextMenuEvent(QContextMenuEvent.Reason.Mouse, spot, editor.view.mapToGlobal(spot))
    )

    assert shown == [['Rotate']]
