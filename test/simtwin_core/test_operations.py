"""Tests for the operations one edit of a drawn net is made of."""

from __future__ import annotations

import json

import pytest

from simtwin_core import operations
from simtwin_core.operations import (
    AddArc,
    AddGuide,
    AddNode,
    Change,
    MoveArcEnd,
    MoveGuide,
    MoveNode,
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
    InvalidNet,
    NetDocument,
    PlaceData,
    TransitionData,
)

#: A place, a transition and the arc between them: the smallest net worth
#: changing.
PLACE = PlaceData('p', 'P1', (20.0, 20.0))
OTHER = PlaceData('q', 'P2', (20.0, 80.0))
TRANSITION = TransitionData('t', 'T1', (60.0, 20.0))
ARC = ArcData('a', 'p', 't', 0, 10)
GUIDE = GuideData('horizontal', 50.0)


def net(**rest) -> NetDocument:
    """Give the little net, or one of the same shape.

    Parameters
    ----------
    **rest
        What to hold instead of the usual.

    Returns
    -------
    simtwin_core.petri_net.NetDocument
        The net.
    """

    return NetDocument(
        model_uuid=rest.pop('model_uuid', 'model'),
        places=rest.pop('places', (PLACE,)),
        transitions=rest.pop('transitions', (TRANSITION,)),
        arcs=rest.pop('arcs', (ARC,)),
        guides=rest.pop('guides', ()),
        **rest,
    )


#: One of every operation, on the net above, with what it is expected to do.
EVERY_OPERATION = [
    AddNode(OTHER),
    RemoveNode(PLACE),
    MoveNode('t', TRANSITION.position, (90.0, 45.0)),
    SetNodeName('p', 'P1', 'Buffer'),
    SetTokens('p', 0, 3),
    SetDescription('t', '', 'Fill a bottle'),
    SetVertical('t', False, True),
    AddArc(ArcData('b', 't', 'p', 3, 4)),
    RemoveArc(ARC),
    MoveArcEnd('a', 'source', 'p', 0, 'p', 6),
    SetArcShape('a', 'straight', 'l-shaped'),
    SetArcKind('a', 'normal', 'inhibitor'),
    SetArcWeight('a', 1, 4),
    SetArcBends('a', None, None, ((0.3, 0.4), (0.6, 0.2)), ((0.5, 0.5),)),
    AddGuide(GUIDE),
    RemoveGuide(GUIDE),
    MoveGuide(GUIDE, GuideData('horizontal', 70.0)),
]

#: What each of them needs on the sheet before it can be applied.
BEFORE = {
    RemoveNode: net(arcs=()),
    RemoveGuide: net(guides=(GUIDE,)),
    MoveGuide: net(guides=(GUIDE,)),
}


def sheet(operation) -> NetDocument:
    """Give the net an operation is applied to.

    Parameters
    ----------
    operation : simtwin_core.operations.Operation
        The operation.

    Returns
    -------
    simtwin_core.petri_net.NetDocument
        The net it wants: the little one, unless it needs something else there
        first — a guide to move, or a place with no arcs on it to remove.
    """

    return BEFORE.get(type(operation), net())


def names(operations_) -> list[str]:
    """Give what some operations are called.

    Parameters
    ----------
    operations_ : collections.abc.Iterable
        The operations.

    Returns
    -------
    list of str
        Their names.
    """

    return [operation.NAME for operation in operations_]


# ----------------------------------------------------------------------
# What an operation does
# ----------------------------------------------------------------------


def test_a_node_is_added_and_taken_away():
    """Whole, so that undoing gives back the same node and not a new one."""

    with_other = AddNode(OTHER).apply(net())

    assert with_other.places == (PLACE, OTHER)
    assert RemoveNode(OTHER).apply(with_other) == net()


def test_a_node_is_moved():
    """And only the one asked for."""

    moved = MoveNode('t', TRANSITION.position, (90.0, 45.0)).apply(net())

    assert moved.transitions[0].position == (90.0, 45.0)
    assert moved.places == (PLACE,)


def test_an_arc_is_added_and_taken_away():
    """With everything about how it is drawn."""

    drawn = ArcData('b', 't', 'p', 3, 4, 2, 'normal', 's-curved', None, ((0.4, 0.2),))
    with_arc = AddArc(drawn).apply(net())

    assert with_arc.arcs == (ARC, drawn)
    assert RemoveArc(drawn).apply(with_arc) == net()


def test_an_arc_end_is_moved():
    """To another connecting point, of the same node or another."""

    moved = MoveArcEnd('a', 'source', 'p', 0, 'q', 6).apply(net(places=(PLACE, OTHER)))

    assert (moved.arcs[0].source, moved.arcs[0].source_port) == ('q', 6)
    assert (moved.arcs[0].target, moved.arcs[0].target_port) == ('t', 10)


@pytest.mark.parametrize(
    ('operation', 'field', 'expected'),
    [
        (SetArcShape('a', 'straight', 'l-shaped'), 'shape', 'l-shaped'),
        (SetArcKind('a', 'normal', 'inhibitor'), 'kind', 'inhibitor'),
        (SetArcWeight('a', 1, 4), 'weight', 4),
    ],
    ids=['shape', 'kind', 'weight'],
)
def test_what_an_arc_is_can_be_set(operation, field, expected):
    """One operation each, so that each says exactly what it did."""

    changed = operation.apply(net())

    assert getattr(changed.arcs[0], field) == expected


def test_the_bends_of_an_arc_are_set_together():
    """Dragging a handle, putting a point in and taking one out all say the same
    thing: this is how it bends now."""

    shaped = SetArcBends('a', None, None, ((0.3, 0.4), (0.6, 0.2)), ((0.5, 0.5),)).apply(net())

    assert shaped.arcs[0].controls == ((0.3, 0.4), (0.6, 0.2))
    assert shaped.arcs[0].points == ((0.5, 0.5),)


def test_a_guide_is_added_moved_and_taken_away():
    """A guide has no identity: the first one equal to it is the one meant."""

    with_guide = AddGuide(GUIDE).apply(net())
    moved = MoveGuide(GUIDE, GuideData('horizontal', 70.0)).apply(with_guide)

    assert with_guide.guides == (GUIDE,)
    assert moved.guides == (GuideData('horizontal', 70.0),)
    assert RemoveGuide(GUIDE).apply(with_guide) == net()


@pytest.mark.parametrize('operation', EVERY_OPERATION, ids=names(EVERY_OPERATION))
def test_every_operation_undone_puts_the_net_back(operation):
    """Which is the whole of undo, and it is checked for every operation there
    is rather than for a sample."""

    before = sheet(operation)

    after = operation.apply(before)

    assert after != before
    assert operation.inverse().apply(after) == before


@pytest.mark.parametrize('operation', EVERY_OPERATION, ids=names(EVERY_OPERATION))
def test_an_inverse_inverted_is_the_operation_again(operation):
    """So redo is undo of the undo, with nothing lost in between."""

    assert operation.inverse().inverse() == operation


def test_an_operation_that_would_break_the_net_is_refused():
    """A description is checked as it is made, so a damaged journal is refused
    rather than half replayed."""

    with pytest.raises(InvalidNet):
        MoveArcEnd('a', 'source', 'p', 0, 'gone', 0).apply(net())
    with pytest.raises(InvalidNet):
        AddArc(ArcData('b', 'p', 't', 0, 10)).apply(net())


# ----------------------------------------------------------------------
# What one gesture does
# ----------------------------------------------------------------------


def test_a_change_applies_its_operations_in_order():
    """A gesture is often more than one operation."""

    change = Change('delete', (RemoveArc(ARC), RemoveNode(PLACE)))

    after = change.apply(net())

    assert after.arcs == ()
    assert after.places == ()


def test_a_change_undone_is_undone_backwards():
    """A place is put back before the arcs that hang on it, or there would be an
    arc to nothing."""

    change = Change('delete', (RemoveArc(ARC), RemoveNode(PLACE)))
    inverse = change.inverse()

    assert names(inverse.operations) == ['add-node', 'add-arc']
    assert inverse.apply(change.apply(net())) == net()


def test_a_change_keeps_its_name():
    """Which is what the *Undo* entry offers to put back; the words belong to
    the application."""

    assert Change('move-nodes').inverse().name == 'move-nodes'


def test_a_change_of_nothing_changes_nothing():
    """Which is what a gesture that turned out to move nothing comes to."""

    assert Change('move-nodes').apply(net()) == net()


# ----------------------------------------------------------------------
# A change as a line of a journal
# ----------------------------------------------------------------------


@pytest.mark.parametrize('operation', EVERY_OPERATION, ids=names(EVERY_OPERATION))
def test_every_operation_survives_being_written_and_read(operation):
    """A journal is JSON, one change to a line, and what comes back must be what
    went in."""

    change = Change('gesture', (operation,))

    written = json.dumps(operations.encode(change))

    assert operations.decode(json.loads(written)) == change


def test_every_operation_can_be_written():
    """A new operation nobody registered would be found by this."""

    assert set(operations.OPERATIONS) == {
        operation.NAME for operation in EVERY_OPERATION
    }


def test_a_route_is_not_written_to_the_journal():
    """It is worked out from the points by whatever draws it."""

    change = Change('draw', (AddArc(ArcData('b', 't', 'p', 3, 4, route=((30.0, 25.0),))),))

    written = operations.encode(change)

    assert 'route' not in written['operations'][0]['arc']
    assert operations.decode(written).operations[0].arc.route == ()


def test_untouched_and_emptied_survive_the_journal():
    """The difference between an arc never shaped and one whose points were all
    taken out."""

    change = Change('shape', (SetArcBends('a', None, None, None, ()),))

    read = operations.decode(operations.encode(change))

    assert read.operations[0].after_points == ()
    assert read.operations[0].after_controls is None


@pytest.mark.parametrize(
    'line',
    [
        {'change': 'gesture', 'operations': [{'op': 'fly-the-arc'}]},
        {'change': 'gesture', 'operations': [{'op': 'move-node', 'node': 'p'}]},
        {'change': 'gesture', 'operations': ['not an operation']},
        {'nothing': 'of the sort'},
    ],
    ids=['unknown', 'incomplete', 'not-an-operation', 'not-a-change'],
)
def test_a_journal_line_that_cannot_be_read_is_refused(line):
    """Half a change replayed is a net nobody drew."""

    with pytest.raises(ValueError):
        operations.decode(line)


# ----------------------------------------------------------------------
# Names, tokens and descriptions
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ('operation', 'field', 'expected'),
    [
        (SetNodeName('p', 'P1', 'Buffer'), 'name', 'Buffer'),
        (SetTokens('p', 0, 3), 'tokens', 3),
        (SetDescription('p', '', 'Bottles waiting'), 'description', 'Bottles waiting'),
    ],
    ids=['name', 'tokens', 'description'],
)
def test_what_a_place_is_can_be_set(operation, field, expected):
    """One operation each, and nothing else about the place changes."""

    changed = operation.apply(net())

    assert getattr(changed.places[0], field) == expected
    assert changed.places[0].position == PLACE.position
    assert changed.transitions == (TRANSITION,)


def test_a_transition_is_renamed_and_described():
    """A transition has a name and a description too."""

    renamed = SetNodeName('t', 'T1', 'Fill').apply(net())
    described = SetDescription('t', '', 'Fill a bottle').apply(renamed)

    assert (described.transitions[0].name, described.transitions[0].description) == (
        'Fill',
        'Fill a bottle',
    )


def test_tokens_set_on_a_transition_leave_it_as_it_is():
    """A transition holds no tokens."""

    assert SetTokens('t', 0, 3).apply(net()) == net()


def test_a_transition_is_stood_up_and_laid_back_across():
    """How it is drawn and nothing else: it is the same transition either way."""

    upright = SetVertical('t', False, True).apply(net())

    assert upright.transitions[0].vertical is True
    assert SetVertical('t', True, False).apply(upright) == net()


def test_a_place_stood_up_is_left_as_it_is():
    """A circle has no way round."""

    assert SetVertical('p', False, True).apply(net()) == net()


def test_a_way_round_that_is_neither_is_refused():
    """As a damaged journal would ask.  There is no angle between the two."""

    with pytest.raises(InvalidNet, match='one way round'):
        SetVertical('t', False, 90).apply(net())


def test_a_name_another_node_has_is_refused():
    """A backend knows a node by its name."""

    with pytest.raises(InvalidNet, match='share the name'):
        SetNodeName('t', 'T1', 'P1').apply(net())


@pytest.mark.parametrize('tokens', [-1, 1.5, True], ids=['negative', 'fraction', 'bool'])
def test_tokens_that_are_not_a_whole_number_of_nought_or_more_are_refused(tokens):
    """Where the operation is applied, as a damaged journal would ask."""

    with pytest.raises(InvalidNet, match='tokens'):
        SetTokens('p', 0, tokens).apply(net())


def test_a_description_of_more_than_one_line_is_refused():
    """A description is drawn on one line beside its node."""

    with pytest.raises(InvalidNet, match='one line'):
        SetDescription('p', '', 'two\nlines').apply(net())


def test_a_node_carries_its_tokens_and_description_through_the_journal():
    """Added and removed whole, so undoing gives back everything it had."""

    full = PlaceData('r', 'P3', (40.0, 40.0), 5, 'Bottles waiting')
    upright = TransitionData('u', 'T2', (1.0, 1.0), 'Cap', True)
    change = Change('gesture', (AddNode(full), RemoveNode(upright)))

    assert operations.decode(json.loads(json.dumps(operations.encode(change)))) == change


def test_a_node_written_before_tokens_existed_reads_as_holding_none():
    """A journal line from an earlier version still replays."""

    line = {
        'change': 'add-element',
        'operations': [
            {'op': 'add-node', 'node': {'kind': 'place', 'uuid': 'r', 'name': 'P3', 'position': [1, 2]}},
            {'op': 'add-node', 'node': {'kind': 'transition', 'uuid': 'u', 'name': 'T2', 'position': [3, 4]}},
        ],
    }

    place, transition = (operation.node for operation in operations.decode(line).operations)

    assert (place.tokens, place.description) == (0, '')
    assert (transition.description, transition.vertical) == ('', False)



def test_a_name_that_is_not_one_is_refused_where_it_is_applied():
    """As a damaged journal would ask; the pane asks the rule before it makes one."""

    with pytest.raises(InvalidNet, match='not a name'):
        SetNodeName('p', 'P1', 'Buffer 1').apply(net())
    with pytest.raises(InvalidNet, match='share the name'):
        SetNodeName('t', 'T1', 'p1').apply(net())


def test_a_node_may_be_renamed_to_its_own_name_in_another_case():
    """Its own name is not another node's."""

    assert SetNodeName('p', 'P1', 'p1').apply(net()).places[0].name == 'p1'
