"""Tests for the description of a Petri net as it is drawn."""

from __future__ import annotations

import dataclasses

import pytest

from simtwin_core.petri_net import (
    ArcData,
    GuideData,
    InvalidNet,
    NetDocument,
    PlaceData,
    TransitionData,
)


def place(uuid: str = 'p', name: str = 'P1', position=(20.0, 20.0)) -> PlaceData:
    """Make a place.

    Parameters
    ----------
    uuid : str, optional
        Its UUID.
    name : str, optional
        Its name.
    position : tuple, optional
        Its centre.

    Returns
    -------
    PlaceData
        The place.
    """

    return PlaceData(uuid, name, position)


def transition(uuid: str = 't', name: str = 'T1', position=(60.0, 20.0)) -> TransitionData:
    """Make a transition.

    Parameters
    ----------
    uuid : str, optional
        Its UUID.
    name : str, optional
        Its name.
    position : tuple, optional
        Its centre.

    Returns
    -------
    TransitionData
        The transition.
    """

    return TransitionData(uuid, name, position)


def arc(uuid: str = 'a', source: str = 'p', target: str = 't', **rest) -> ArcData:
    """Make an arc between the usual place and transition.

    Parameters
    ----------
    uuid : str, optional
        Its UUID.
    source, target : str, optional
        The UUIDs of its ends.
    **rest
        Anything else an arc is given.

    Returns
    -------
    ArcData
        The arc.
    """

    return ArcData(uuid, source, target, rest.pop('source_port', 0), rest.pop('target_port', 10), **rest)


def net(*arcs: ArcData, **rest) -> NetDocument:
    """Make a document of one place, one transition and some arcs.

    Parameters
    ----------
    *arcs : ArcData
        The arcs.
    **rest
        Anything else a document is given, in place of the usual.

    Returns
    -------
    NetDocument
        The document.
    """

    return NetDocument(
        model_uuid=rest.pop('model_uuid', 'model'),
        places=rest.pop('places', (place(),)),
        transitions=rest.pop('transitions', (transition(),)),
        arcs=arcs,
        **rest,
    )


# ----------------------------------------------------------------------
# What a document holds
# ----------------------------------------------------------------------


def test_a_document_holds_what_is_drawn():
    """The nodes, the arcs, the guides and which model they are."""

    document = net(arc(), guides=(GuideData('horizontal', 50),))

    assert document.model_uuid == 'model'
    assert document.places[0].name == 'P1'
    assert document.transitions[0].position == (60.0, 20.0)
    assert document.arcs[0].weight == 1
    assert document.guides[0].position == 50.0


def test_an_empty_net_is_a_net():
    """A model nobody has drawn on yet."""

    assert NetDocument() == NetDocument(model_uuid='', places=(), arcs=())


def test_an_arc_is_normal_straight_and_untouched_unless_told_otherwise():
    """Untouched is ``None``: the shape's own default, which the editor knows."""

    made = arc()

    assert (made.kind, made.shape, made.weight) == ('normal', 'straight', 1)
    assert made.controls is None
    assert made.points is None


def test_an_s_with_every_point_taken_out_is_not_an_untouched_s():
    """``()`` is a straight line through nothing; ``None`` is the default S."""

    assert arc(shape='s-curved', points=()).points == ()
    assert arc(shape='s-curved').points is None


def test_two_documents_of_one_drawing_are_equal():
    """A document is a value, which is what a round trip is tested by."""

    assert net(arc(shape='l-shaped', points=[(0.5, 0.5)])) == net(
        arc(shape='l-shaped', points=((0.5, 0.5),))
    )


def test_lists_are_made_tuples_and_numbers_floats():
    """So the same drawing is the same document however it was put together."""

    made = arc(controls=[[0, 1], [1, 0]], points=[[0.25, 0.1]])
    document = NetDocument(places=[place(position=[20, 30])])

    assert made.controls == ((0.0, 1.0), (1.0, 0.0))
    assert made.points == ((0.25, 0.1),)
    assert isinstance(document.places, tuple)
    assert document.places[0].position == (20.0, 30.0)


def test_a_document_cannot_be_changed_once_made():
    """Nothing holding one can change what another sees."""

    document = net()

    with pytest.raises(dataclasses.FrozenInstanceError):
        document.model_uuid = 'other'
    with pytest.raises(dataclasses.FrozenInstanceError):
        document.places[0].name = 'P2'


def test_a_node_is_found_by_its_uuid():
    """Which is how an arc's ends are looked up."""

    document = net()

    assert document.node('p').name == 'P1'
    assert document.node('t').name == 'T1'
    assert document.node('nothing') is None


def test_the_names_are_the_places_then_the_transitions():
    """In the order the document holds them."""

    assert net().names == ('P1', 'T1')


# ----------------------------------------------------------------------
# What is refused
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    'given',
    [
        {'kind': 'reset'},
        {'shape': 'zigzag'},
        {'weight': 0},
        {'source_port': -1},
        {'controls': ((0.3, 0.1),)},
        {'points': ((0.3,),)},
    ],
    ids=['kind', 'shape', 'weight', 'port', 'controls', 'point'],
)
def test_an_arc_that_could_not_be_drawn_is_refused(given):
    """Refused where it is made, before it reaches a net."""

    with pytest.raises(InvalidNet):
        arc(**given)


def test_a_guide_lying_no_way_there_is_is_refused():
    """Across the sheet or up it."""

    with pytest.raises(InvalidNet):
        GuideData('diagonal', 10.0)


def test_a_position_that_is_not_a_pair_is_refused():
    """A node is somewhere."""

    with pytest.raises(InvalidNet):
        place(position=(1.0, 2.0, 3.0))


def test_an_error_about_a_net_is_a_value_error():
    """So a caller that only knows the standard exceptions still catches it."""

    assert issubclass(InvalidNet, ValueError)


def test_two_nodes_sharing_a_uuid_are_refused():
    """An arc names its ends by UUID."""

    with pytest.raises(InvalidNet, match='UUID'):
        net(places=(place(), place(uuid='t', name='P2')))


def test_two_nodes_sharing_a_name_are_refused():
    """A place and a transition included: a backend knows a node by its name."""

    with pytest.raises(InvalidNet, match='name'):
        net(transitions=(transition(name='P1'),))


def test_an_arc_sharing_a_uuid_with_a_node_is_refused():
    """A UUID is an identity, whatever it identifies."""

    with pytest.raises(InvalidNet, match='UUID'):
        net(arc(uuid='p'))


def test_an_arc_to_something_not_in_the_net_is_refused():
    """A line drawn to where nothing is."""

    with pytest.raises(InvalidNet, match='not in the net'):
        net(arc(target='gone'))


def test_an_arc_between_two_places_is_refused():
    """A Petri net is bipartite."""

    with pytest.raises(InvalidNet, match='joins a place to a place'):
        net(arc(target='q'), places=(place(), place(uuid='q', name='P2')))


def test_an_inhibitor_arc_from_a_transition_is_refused():
    """It runs from a place to a transition and no other way."""

    assert net(arc(kind='inhibitor')).arcs[0].kind == 'inhibitor'
    with pytest.raises(InvalidNet, match='inhibitor'):
        net(arc(source='t', target='p', kind='inhibitor'))


def test_a_second_arc_of_one_kind_the_same_way_round_is_refused():
    """Wanting more of an arc is what its weight is for."""

    with pytest.raises(InvalidNet, match='same way'):
        net(arc(), arc(uuid='b'))


def test_arcs_each_way_and_of_each_kind_may_share_a_pair():
    """One normal arc each way, and an inhibitor beside the normal one."""

    document = net(
        arc(),
        arc(uuid='back', source='t', target='p'),
        arc(uuid='inhibit', kind='inhibitor'),
    )

    assert len(document.arcs) == 3


def test_connecting_points_may_be_left_to_the_editor():
    """A file from another tool knows nothing of them."""

    made = arc(source_port=None, target_port=None)

    assert (made.source_port, made.target_port) == (None, None)


def test_a_route_is_where_the_points_are_on_the_sheet():
    """Empty unless given, and made a tuple of floats like every point."""

    assert arc().route == ()
    assert arc(route=[[30, 25], [45.5, 18]]).route == ((30.0, 25.0), (45.5, 18.0))


def test_a_route_that_is_not_points_is_refused():
    """A route runs through places."""

    with pytest.raises(InvalidNet):
        arc(route=[(1.0,)])
