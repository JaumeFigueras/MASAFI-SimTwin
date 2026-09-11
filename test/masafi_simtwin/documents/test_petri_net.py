"""Tests for the Petri net document."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QLineF, QPointF, Qt

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
