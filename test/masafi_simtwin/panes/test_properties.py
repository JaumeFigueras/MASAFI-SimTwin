"""Tests for the Properties pane."""

from __future__ import annotations

import pytest

from masafi_simtwin.documents.petri_net import Selection
from masafi_simtwin.panes import PropertiesPane
from masafi_simtwin.panes.properties import unit_symbol
from masafi_simtwin.project import ModelKind
from simtwin_core.petri_net import ArcData, NameProblem, PlaceData, TransitionData


@pytest.fixture
def pane(qtbot):
    """Build the pane.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    masafi_simtwin.panes.PropertiesPane
        The pane, showing nothing.
    """

    widget = PropertiesPane()
    qtbot.addWidget(widget)
    return widget


def test_the_pane_starts_with_nothing_to_show(pane):
    """No model is open when the window is built."""

    assert pane.page is pane.nothing_page
    assert 'Open a model' in pane.nothing_label.text()
    assert pane.nothing_label.property('placeholder') is True


def test_a_model_is_shown_by_its_name_kind_and_units(pane):
    """Read-only: the model's properties are changed in its own dialog."""

    pane.show_model({'name': 'Filling Station', 'kind': 'petri-net', 'units': {'time': 'min'}})

    assert pane.page is pane.model_page
    assert pane.model_name_value.text() == 'Filling Station'
    assert pane.model_kind_value.text() == 'Petri Net'
    assert pane.model_time_value.text() == 'min'


def test_a_model_with_no_distance_unit_shows_no_distance_row(pane):
    """A Petri net is a graph: an empty row would suggest something is missing."""

    pane.show_model({'name': 'N', 'kind': 'petri-net', 'units': {'time': 's'}})
    assert not pane.model_form.isRowVisible(pane.model_distance_label)

    pane.show_model({'name': 'L', 'kind': 'process-2d', 'units': {'time': 's', 'distance': 'km'}})
    assert pane.model_form.isRowVisible(pane.model_distance_label)
    assert pane.model_distance_value.text() == 'km'


def test_a_unit_is_shown_by_its_symbol():
    """The microsecond is stored as ASCII and written as itself."""

    assert unit_symbol('us') == 'µs'
    assert unit_symbol('s') == 's'


@pytest.mark.parametrize('kind', list(ModelKind), ids=[kind.value for kind in ModelKind])
def test_every_kind_of_model_has_a_name(pane, kind):
    """Rather than its stored value."""

    assert pane.kind_name(kind.value) != kind.value


def test_a_kind_nobody_has_named_is_shown_as_it_is_stored(pane):
    """So nothing is hidden."""

    assert pane.kind_name('hologram') == 'hologram'


def test_a_selection_is_shown_by_what_it_holds(pane):
    """How many of each."""

    selection = Selection(
        places=(PlaceData('p', 'P1', (0.0, 0.0)), PlaceData('q', 'P2', (0.0, 30.0))),
        transitions=(),
        arcs=(ArcData('a', 'p', 't', 0, 10),),
    )

    pane.show_selection(selection)

    assert pane.page is pane.selection_page
    assert (pane.places_value.text(), pane.transitions_value.text(), pane.arcs_value.text()) == (
        '2',
        '0',
        '1',
    )


def test_an_empty_selection_is_nothing_selected():
    """Which is what decides between the model and the selection."""

    assert not Selection()
    assert Selection(transitions=(TransitionData('t', 'T1', (0.0, 0.0)),))


# ----------------------------------------------------------------------
# The place page
# ----------------------------------------------------------------------

#: A place, and another that agrees with it on nothing.
PLACE = PlaceData('p', 'P1', (0.0, 0.0), 2, 'Bottles waiting')
OTHER = PlaceData('q', 'P2', (0.0, 30.0), 5, '')

#: The names of the net they are in.
NAMES = ('P1', 'P2', 'T1')


def test_one_place_is_shown_to_be_edited(pane):
    """Its name, its tokens and its description, and no complaint about any."""

    pane.show_nodes((PLACE,), NAMES)

    assert pane.page is pane.node_page
    assert pane.node_heading.text() == 'Place'
    assert pane.node_name_edit.isEnabled()
    assert pane.node_name_edit.text() == 'P1'
    assert pane.node_tokens_spin.value() == 2
    assert pane.node_description_edit.text() == 'Bottles waiting'
    assert pane.node_name_problem.isHidden()


def test_several_places_show_what_they_agree_on_and_no_name(pane):
    """A name belongs to one node, so it cannot be edited for several."""

    twin = PlaceData('q', 'P2', (0.0, 30.0), 2, 'Bottles waiting')

    pane.show_nodes((PLACE, twin), NAMES)

    assert pane.node_heading.text() == 'Places: 2'
    assert not pane.node_name_edit.isEnabled()
    assert pane.node_name_edit.text() == ''
    assert pane.node_name_edit.placeholderText() == 'Several places'
    assert pane.node_tokens_spin.value() == 2
    assert pane.node_description_edit.text() == 'Bottles waiting'


def test_where_several_places_differ_the_field_is_left_blank(pane):
    """Rather than showing one of them as though it were all of them."""

    pane.show_nodes((PLACE, OTHER), NAMES)

    assert pane.node_tokens_spin.value() == pane.node_tokens_spin.minimum()
    assert pane.node_tokens_spin.text().strip() == ''
    assert pane.node_description_edit.text() == ''
    assert pane.node_description_edit.placeholderText() == 'Several descriptions'


def test_showing_places_asks_for_nothing(pane, qtbot):
    """Filling a field in is not an edit of it."""

    with qtbot.assertNotEmitted(pane.name_asked), qtbot.assertNotEmitted(
        pane.tokens_asked
    ), qtbot.assertNotEmitted(pane.description_asked):
        pane.show_nodes((PLACE,), NAMES)
        pane.show_nodes((OTHER,), NAMES)
        pane.show_nodes((PLACE, OTHER), NAMES)
        pane.show_nodes((PLACE,), NAMES)


def test_a_name_that_breaks_the_rule_says_why_as_it_is_typed(pane, qtbot):
    """Under the field, in words."""

    pane.show_nodes((PLACE,), NAMES)
    edit = pane.node_name_edit

    edit.selectAll()
    qtbot.keyClicks(edit, '1st')
    assert not pane.node_name_problem.isHidden()
    assert pane.node_name_problem.text() == pane.name_problem_text(NameProblem.DIGIT_FIRST)

    edit.selectAll()
    qtbot.keyClicks(edit, 'p2')
    assert pane.node_name_problem.text() == pane.name_problem_text(NameProblem.TAKEN)

    edit.selectAll()
    qtbot.keyClicks(edit, 'Buffer')
    assert pane.node_name_problem.isHidden()


def test_the_place_may_keep_its_name_in_another_case(pane, qtbot):
    """Its own name is not another node's."""

    pane.show_nodes((PLACE,), NAMES)
    pane.node_name_edit.selectAll()
    qtbot.keyClicks(pane.node_name_edit, 'p1')

    assert pane.node_name_problem.isHidden()


def test_a_name_the_rule_allows_is_asked_for_when_editing_ends(pane, qtbot):
    """With the place's UUID; the document makes the change."""

    pane.show_nodes((PLACE,), NAMES)
    pane.node_name_edit.setText('Buffer')

    with qtbot.waitSignal(pane.name_asked, timeout=1000) as blocker:
        pane.node_name_edit.editingFinished.emit()

    assert blocker.args == ['p', 'Buffer']


def test_a_name_still_refused_when_editing_ends_is_put_back(pane, qtbot):
    """Nothing is asked for, and the field says what the place is called."""

    pane.show_nodes((PLACE,), NAMES)
    pane.node_name_edit.setText('T1')
    pane._show_name_problem(NameProblem.TAKEN)

    with qtbot.assertNotEmitted(pane.name_asked):
        pane.node_name_edit.editingFinished.emit()

    assert pane.node_name_edit.text() == 'P1'
    assert pane.node_name_problem.isHidden()


def test_the_name_the_place_has_asks_for_nothing(pane, qtbot):
    """Leaving the field without changing it is not a rename."""

    pane.show_nodes((PLACE,), NAMES)

    with qtbot.assertNotEmitted(pane.name_asked):
        pane.node_name_edit.editingFinished.emit()


def test_tokens_are_asked_for_every_place_shown(pane, qtbot):
    """One number for all of them."""

    pane.show_nodes((PLACE, OTHER), NAMES)

    with qtbot.waitSignal(pane.tokens_asked, timeout=1000) as blocker:
        pane.node_tokens_spin.setValue(7)

    assert blocker.args == [('p', 'q'), 7]


def test_a_description_is_asked_for_every_place_shown_when_editing_ends(pane, qtbot):
    """Once, when the field is left."""

    pane.show_nodes((PLACE, OTHER), NAMES)
    pane.node_description_edit.setText('Crates')

    with qtbot.waitSignal(pane.description_asked, timeout=1000) as blocker:
        pane.node_description_edit.editingFinished.emit()

    assert blocker.args == [('p', 'q'), 'Crates']


def test_descriptions_that_differ_left_blank_ask_for_nothing(pane, qtbot):
    """Leaving the blank field is not describing every place as nothing."""

    pane.show_nodes((PLACE, OTHER), NAMES)

    with qtbot.assertNotEmitted(pane.description_asked):
        pane.node_description_edit.editingFinished.emit()


def test_every_reason_a_name_is_refused_is_said_in_words_of_its_own(pane):
    """So a person is told which rule, not merely that one was broken."""

    texts = [pane.name_problem_text(problem) for problem in NameProblem]

    assert all(texts)
    assert len(set(texts)) == len(NameProblem)


# ----------------------------------------------------------------------
# Transitions on the node page
# ----------------------------------------------------------------------

#: A transition, and another that agrees with it on nothing.
TRANSITION = TransitionData('t', 'T1', (60.0, 0.0), 'Fill a bottle')
TWIN = TransitionData('u', 'T2', (60.0, 30.0), '')


def test_one_transition_is_shown_to_be_edited_without_tokens(pane):
    """A transition is a place without tokens: the row is not there."""

    pane.show_nodes((TRANSITION,), NAMES)

    assert pane.page is pane.node_page
    assert pane.node_heading.text() == 'Transition'
    assert pane.node_name_edit.text() == 'T1'
    assert pane.node_description_edit.text() == 'Fill a bottle'
    assert not pane.node_form.isRowVisible(pane.node_tokens_label)


def test_the_tokens_row_is_back_for_a_place(pane):
    """The same page, shown for the other kind."""

    pane.show_nodes((TRANSITION,), NAMES)
    pane.show_nodes((PLACE,), NAMES)

    assert pane.node_form.isRowVisible(pane.node_tokens_label)
    assert pane.node_tokens_spin.value() == 2


def test_several_transitions_are_counted_and_share_their_description(pane):
    """Named by their kind, the name disabled, a disagreement left blank."""

    pane.show_nodes((TRANSITION, TWIN), NAMES)

    assert pane.node_heading.text() == 'Transitions: 2'
    assert not pane.node_name_edit.isEnabled()
    assert pane.node_name_edit.placeholderText() == 'Several transitions'
    assert pane.node_description_edit.text() == ''
    assert pane.node_description_edit.placeholderText() == 'Several descriptions'


def test_a_transition_is_renamed_and_described_but_given_no_tokens(pane, qtbot):
    """The same requests as a place's, and never tokens."""

    pane.show_nodes((TRANSITION,), NAMES)
    pane.node_name_edit.setText('Fill')
    with qtbot.waitSignal(pane.name_asked, timeout=1000) as named:
        pane.node_name_edit.editingFinished.emit()
    assert named.args == ['t', 'Fill']

    pane.node_description_edit.setText('Cap a bottle')
    with qtbot.waitSignal(pane.description_asked, timeout=1000) as described:
        pane.node_description_edit.editingFinished.emit()
    assert described.args == [('t',), 'Cap a bottle']

    with qtbot.assertNotEmitted(pane.tokens_asked):
        pane.node_tokens_spin.setValue(4)


def test_a_transition_name_is_checked_against_the_places_too(pane, qtbot):
    """One set of names across both kinds."""

    pane.show_nodes((TRANSITION,), NAMES)
    pane.node_name_edit.selectAll()
    qtbot.keyClicks(pane.node_name_edit, 'p1')

    assert pane.node_name_problem.text() == pane.name_problem_text(NameProblem.TAKEN)
