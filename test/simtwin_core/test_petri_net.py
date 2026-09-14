"""Tests for the description of a Petri net as it is drawn."""

from __future__ import annotations

import dataclasses

import pytest

from simtwin_core.petri_net import (
    ArcData,
    GuideData,
    InvalidNet,
    NameProblem,
    NetDocument,
    PlaceData,
    TransitionData,
    name_problem,
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


def test_the_route_is_not_part_of_what_an_arc_is():
    """It says again, in another frame, what the points already say, and only
    the editor can work it out — so two drawings are equal without it."""

    assert arc(points=((0.5, 0.5),)) == arc(points=((0.5, 0.5),), route=((30.0, 25.0),))
    assert arc(points=((0.5, 0.5),), route=((1.0, 2.0),)) == arc(
        points=((0.5, 0.5),), route=((9.0, 9.0),)
    )


def test_a_route_that_is_not_points_is_refused():
    """A route runs through places."""

    with pytest.raises(InvalidNet):
        arc(route=[(1.0,)])


# ----------------------------------------------------------------------
# Tokens, descriptions and which way round a transition is
# ----------------------------------------------------------------------


def test_a_node_holds_no_tokens_and_no_description_unless_given_some():
    """A place dropped on the sheet."""

    assert (place().tokens, place().description) == (0, '')
    assert transition().description == ''


def test_a_place_holds_its_tokens_and_both_nodes_their_descriptions():
    """The initial marking, and a person's words."""

    held = PlaceData('p', 'P1', (20.0, 20.0), 4, 'Bottles waiting')
    described = TransitionData('t', 'T1', (60.0, 20.0), 'Fill a bottle')

    document = net(places=(held,), transitions=(described,))

    assert document.places[0].tokens == 4
    assert document.places[0].description == 'Bottles waiting'
    assert document.transitions[0].description == 'Fill a bottle'


@pytest.mark.parametrize('tokens', [-1, 2.0, True, '3'], ids=['negative', 'float', 'bool', 'text'])
def test_tokens_that_are_not_a_whole_number_of_nought_or_more_are_refused(tokens):
    """Nought is the fewest a place can hold."""

    with pytest.raises(InvalidNet, match='tokens'):
        PlaceData('p', 'P1', (20.0, 20.0), tokens)


def test_a_transition_lies_across_the_sheet_unless_it_is_stood_up():
    """Which is how it is drawn, and no part of the net a backend is given."""

    assert transition().vertical is False
    assert TransitionData('t', 'T1', (60.0, 20.0), '', True).vertical is True


def test_a_caption_nobody_has_moved_has_no_offset():
    """``None`` is where the editor puts it; a pair is where it was put."""

    assert PlaceData('p', 'P1', (20.0, 20.0)).label_offset is None
    assert TransitionData('t', 'T1', (60.0, 20.0), '', False, [1, 2]).label_offset == (1.0, 2.0)


@pytest.mark.parametrize('offset', [(1.0,), 'far', 3.0], ids=['one', 'text', 'number'])
def test_a_caption_moved_somewhere_that_is_not_a_place_is_refused(offset):
    """An offset is two numbers or nothing."""

    with pytest.raises(InvalidNet, match='caption'):
        PlaceData('p', 'P1', (20.0, 20.0), 0, '', offset)


@pytest.mark.parametrize('vertical', [1, 'true', None], ids=['number', 'text', 'nothing'])
def test_a_transition_drawn_neither_way_round_is_refused(vertical):
    """There is no angle between the two, so nothing but an answer will do."""

    with pytest.raises(InvalidNet, match='one way round'):
        TransitionData('t', 'T1', (60.0, 20.0), '', vertical)


@pytest.mark.parametrize('description', ['two\nlines', 'carriage\rreturn', 7], ids=['newline', 'return', 'not-text'])
@pytest.mark.parametrize('made', [
    lambda text: PlaceData('p', 'P1', (0.0, 0.0), 0, text),
    lambda text: TransitionData('t', 'T1', (0.0, 0.0), text),
], ids=['place', 'transition'])
def test_a_description_that_is_not_one_line_of_text_is_refused(made, description):
    """It is drawn on one line beside its node."""

    with pytest.raises(InvalidNet, match='description'):
        made(description)


# ----------------------------------------------------------------------
# The one order a document holds everything in
# ----------------------------------------------------------------------


def test_nodes_are_held_by_name_with_numbers_counted_as_numbers():
    """``P2`` before ``P10``, whatever order they were given in."""

    document = net(
        places=(place('p10', 'P10'), place('b', 'Buffer'), place('p2', 'P2')),
        transitions=(transition('t2', 'T2'), transition('t1', 'T1')),
    )

    assert [node.name for node in document.places] == ['Buffer', 'P2', 'P10']
    assert [node.name for node in document.transitions] == ['T1', 'T2']


def test_arcs_are_held_by_the_names_of_their_ends_then_their_kind():
    """So a file does not change with the order a scene happens to hold them in."""

    places = (place('p', 'P1'), place('q', 'P2'))
    back = arc('back', 't', 'p', source_port=1, target_port=2)
    inhibitor = arc('inhibitor', 'p', 't', kind='inhibitor')
    normal = arc('normal', 'p', 't')
    second = arc('second', 'q', 't')

    document = net(back, second, inhibitor, normal, places=places)

    assert [each.uuid for each in document.arcs] == ['inhibitor', 'normal', 'second', 'back']


def test_guides_are_held_across_the_sheet_first_then_by_where_they_are():
    """The order the sheet lists them in."""

    document = net(
        guides=(
            GuideData('vertical', 10.0),
            GuideData('horizontal', 90.0),
            GuideData('horizontal', 30.0),
        )
    )

    assert document.guides == (
        GuideData('horizontal', 30.0),
        GuideData('horizontal', 90.0),
        GuideData('vertical', 10.0),
    )


def test_one_drawing_put_together_in_two_orders_is_one_document():
    """What a journal replayed onto a file and an editor describing its sheet
    must agree on, or an untouched model would read as changed."""

    one = net(arc('a'), places=(place('p', 'P1'), place('q', 'P2')))
    other = net(arc('a'), places=(place('q', 'P2'), place('p', 'P1')))

    assert one == other
    assert dataclasses.replace(one, places=(place('p', 'Zeta'), place('q', 'P2'))).places[0].name == 'P2'


# ----------------------------------------------------------------------
# What a node may be called
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    'name',
    ['Buffer', 'Buffer_2', 'Station3', 'P1', '_hidden', 'CamelCase', 'match', 'type', 'random'],
)
def test_an_ascii_python_identifier_is_a_name(name):
    """Soft keywords and the names of standard modules are valid module names."""

    assert name_problem(name) is None


@pytest.mark.parametrize(
    ('name', 'problem'),
    [
        ('', NameProblem.EMPTY),
        ('Estació', NameProblem.NOT_ASCII),
        ('1st', NameProblem.DIGIT_FIRST),
        ('2', NameProblem.DIGIT_FIRST),
        ('Buffer 1', NameProblem.NOT_IDENTIFIER),
        ('filling-station', NameProblem.NOT_IDENTIFIER),
        (' Buffer', NameProblem.NOT_IDENTIFIER),
        ('class', NameProblem.KEYWORD),
        ('None', NameProblem.KEYWORD),
        ('lambda', NameProblem.KEYWORD),
    ],
)
def test_a_name_that_is_not_one_says_why(name, problem):
    """The first rule it breaks, as a code the application puts into words."""

    assert name_problem(name) is problem


def test_a_name_another_node_has_is_taken_whatever_its_case():
    """``Buffer`` and ``buffer`` are one file on Windows and macOS."""

    assert name_problem('buffer', ['P1', 'Buffer']) is NameProblem.TAKEN
    assert name_problem('BUFFER', ('buffer',)) is NameProblem.TAKEN
    assert name_problem('Buffer', ['P1', 'T1']) is None


def test_a_node_may_keep_its_name_or_change_its_case():
    """What is taken is the other nodes' names, not its own."""

    assert name_problem('p1', taken=['T1']) is None


def test_every_name_allowed_is_one_the_library_accepts():
    """The document must map onto MASAFI-sim-petri, which runs it: the library
    refuses only a blank name, and a name the rule allows is never blank."""

    from masafi_sim_petri import Place, Transition

    for name in ['Buffer', 'Buffer_2', '_hidden', 'match']:
        assert name_problem(name) is None
        assert Place(name).name == name
        assert Transition(name).name == name


@pytest.mark.parametrize('name', ['Buffer 1', '1st', 'class', 'Estació', ''])
def test_a_document_holding_a_name_that_is_not_one_is_refused(name):
    """A file that breaks the rule is refused when it is read."""

    with pytest.raises(InvalidNet, match='not a name a node may have'):
        net(places=(place('p', name),))


def test_two_nodes_whose_names_differ_only_in_case_are_refused():
    """A place and a transition included."""

    with pytest.raises(InvalidNet, match='share the name'):
        net(places=(place('p', 'Buffer'),), transitions=(transition('t', 'buffer'),))
