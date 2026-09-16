"""Tests for the Properties pane."""

from __future__ import annotations

import pytest

from PyQt6.QtCore import Qt

from masafi_simtwin import preferences
from masafi_simtwin.documents.petri_net import Selection
from masafi_simtwin.panes import PropertiesPane
from masafi_simtwin.panes.properties import unit_symbol
from masafi_simtwin.project import ModelKind
from simtwin_core.petri_net import (
    AUTOMATIC,
    ArcData,
    LineStyle,
    NameProblem,
    PlaceData,
    TextStyle,
    TransitionData,
)


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


# ----------------------------------------------------------------------
# The arc page
# ----------------------------------------------------------------------

#: An arc of weight three from P1 to T1, and one of weight five back.
ARC = ArcData('a', 'p', 't', 0, 10, 3)
BACK = ArcData('b', 't', 'p', 1, 2, 5)

#: The nodes they run between, as the selection names them.
NODE_NAMES = (('p', 'P1'), ('t', 'T1'))


def test_one_arc_is_shown_with_its_ends_and_its_weight(pane):
    """Named by the nodes it runs between; shape and kind stay on the tool bar."""

    pane.show_arcs((ARC,), NODE_NAMES)

    assert pane.page is pane.arc_page
    assert pane.arc_heading.text() == 'Arc'
    assert (pane.arc_source_value.text(), pane.arc_target_value.text()) == ('P1', 'T1')
    assert pane.arc_form.isRowVisible(pane.arc_source_label)
    assert pane.arc_weight_spin.value() == 3
    assert 'tool bar' in pane.arc_note.text()


def test_several_arcs_show_no_ends_and_a_blank_weight_where_they_differ(pane):
    """Rather than the ends of one of them."""

    pane.show_arcs((ARC, BACK), NODE_NAMES)

    assert pane.arc_heading.text() == 'Arcs: 2'
    assert not pane.arc_form.isRowVisible(pane.arc_source_label)
    assert not pane.arc_form.isRowVisible(pane.arc_target_label)
    assert pane.arc_weight_spin.value() == pane.arc_weight_spin.minimum()
    assert pane.arc_weight_spin.text().strip() == ''


def test_several_arcs_of_one_weight_show_it(pane):
    """What they agree on is shown."""

    pane.show_arcs((ARC, ArcData('b', 't', 'p', 1, 2, 3)), NODE_NAMES)

    assert pane.arc_weight_spin.value() == 3
    assert pane.arc_weight_spin.minimum() == 1


def test_showing_arcs_asks_for_nothing(pane, qtbot):
    """Filling the weight in is not an edit of it."""

    with qtbot.assertNotEmitted(pane.weight_asked):
        pane.show_arcs((ARC,), NODE_NAMES)
        pane.show_arcs((ARC, BACK), NODE_NAMES)
        pane.show_arcs((BACK,), NODE_NAMES)


def test_a_weight_is_asked_for_every_arc_shown(pane, qtbot):
    """One number for all of them."""

    pane.show_arcs((ARC, BACK), NODE_NAMES)

    with qtbot.waitSignal(pane.weight_asked, timeout=1000) as blocker:
        pane.arc_weight_spin.setValue(4)

    assert blocker.args == [('a', 'b'), 4]


def test_a_page_of_another_kind_forgets_the_arcs(pane, qtbot):
    """So a weight chosen afterwards is not asked of arcs no longer shown."""

    pane.show_arcs((ARC,), NODE_NAMES)
    pane.show_nodes((PLACE,), NAMES)

    with qtbot.assertNotEmitted(pane.weight_asked):
        pane.arc_weight_spin.setValue(9)


# ----------------------------------------------------------------------
# The appearance of what is selected
# ----------------------------------------------------------------------

#: A place with an appearance of its own, and one that follows the defaults.
STYLED = PlaceData(
    'p',
    'P1',
    (0.0, 0.0),
    2,
    'Bottles waiting',
    None,
    None,
    TextStyle('DejaVu Sans', 4.0, bold=True, colour='#aa0000'),
    LineStyle('#0055aa', 1.5),
)


@pytest.fixture
def chosen_colour(monkeypatch):
    """Answer the colour dialog instead of opening one.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The patcher.

    Returns
    -------
    list
        One entry per colour asked for; append one to be given it next.
    """

    answers = ['#117744']
    monkeypatch.setattr(
        'masafi_simtwin.panes.properties.ask_for_colour',
        lambda parent, current: answers[-1],
    )
    return answers


def test_the_appearance_is_shown_for_a_node_and_for_an_arc_and_for_nothing_else(pane):
    """It belongs to a thing on the sheet, and a model is not one."""

    pane.show_nodes((PLACE,), NAMES)
    assert not pane.appearance_box.isHidden()

    pane.show_arcs((ARC,), NODE_NAMES)
    assert not pane.appearance_box.isHidden()

    pane.show_model({'name': 'N', 'kind': 'petri-net', 'units': {'time': 's'}})
    assert pane.appearance_box.isHidden()

    pane.show_selection(Selection(places=(PLACE,), arcs=(ARC,)))
    assert pane.appearance_box.isHidden()

    pane.show_nothing()
    assert pane.appearance_box.isHidden()


def test_an_arc_is_offered_no_typeface_and_no_alignment(pane):
    """A weight is never bold, italic or aligned — the rule the core keeps."""

    pane.show_nodes((PLACE,), NAMES)
    assert pane.text_form.isRowVisible(pane.typeface_label)
    assert pane.text_form.isRowVisible(pane.alignment_label)

    pane.show_arcs((ARC,), NODE_NAMES)

    assert not pane.text_form.isRowVisible(pane.typeface_label)
    assert not pane.text_form.isRowVisible(pane.alignment_label)
    assert pane.text_form.isRowVisible(pane.font_label)
    assert pane.text_form.isRowVisible(pane.text_colour_label)


def test_an_item_that_follows_the_defaults_says_so_with_its_fields_dead(pane):
    """Which is what the box being ticked means."""

    pane.show_nodes((PLACE,), NAMES)

    assert pane.text_default_check.checkState() == Qt.CheckState.Checked
    assert pane.line_default_check.checkState() == Qt.CheckState.Checked
    assert not pane.font_combo.isEnabled()
    assert not pane.font_size_spin.isEnabled()
    assert not pane.line_width_spin.isEnabled()


def test_an_item_with_a_style_of_its_own_shows_it(pane):
    """Unticked, the fields alive and holding what the item was given."""

    pane.show_nodes((STYLED,), NAMES)

    assert pane.text_default_check.checkState() == Qt.CheckState.Unchecked
    assert pane.font_combo.currentText() == 'DejaVu Sans'
    assert pane.font_size_spin.value() == 4.0
    assert pane.bold_check.isChecked()
    assert not pane.italic_check.isChecked()
    assert pane.font_combo.isEnabled()

    assert pane.line_default_check.checkState() == Qt.CheckState.Unchecked
    assert pane.line_width_spin.value() == 1.5
    assert not pane.line_colour_automatic.isChecked()


@pytest.mark.parametrize(
    ('box', 'field'),
    [('text_default_check', 'font_size_spin'), ('line_default_check', 'line_width_spin')],
    ids=['text', 'line'],
)
def test_clicking_the_box_toggles_between_ticked_and_unticked(pane, box, field):
    """Reported by Jaume: unticking worked and ticking again did nothing.

    The box is tri-state so that a disagreement can be *shown*, and Qt lets a
    click cycle through that middle state — so the second click landed on
    *partly ticked*, where the tick never arrived and the fields stayed alive.
    A click is a person saying yes or no, and there is no third answer to give.
    """

    pane.show_nodes((PLACE,), NAMES)
    ticked, edited = getattr(pane, box), getattr(pane, field)
    assert ticked.checkState() == Qt.CheckState.Checked

    ticked.click()
    assert ticked.checkState() == Qt.CheckState.Unchecked
    assert edited.isEnabled()

    ticked.click()
    assert ticked.checkState() == Qt.CheckState.Checked
    assert not edited.isEnabled()


def test_a_disagreement_is_still_shown_as_a_partly_ticked_box(pane):
    """Shown, though a click can no longer land there."""

    pane.show_nodes((PLACE, STYLED), NAMES)

    assert pane.text_default_check.checkState() == Qt.CheckState.PartiallyChecked
    assert pane.line_default_check.checkState() == Qt.CheckState.PartiallyChecked


def test_items_that_disagree_leave_the_box_partly_ticked(pane):
    """Neither *they all follow the defaults* nor *they all have their own*."""

    pane.show_nodes((PLACE, STYLED), NAMES)

    assert pane.text_default_check.checkState() == Qt.CheckState.PartiallyChecked
    assert pane.line_default_check.checkState() == Qt.CheckState.PartiallyChecked


def test_showing_an_item_asks_for_nothing(pane, qtbot):
    """Filling the fields in is not choosing anything."""

    with qtbot.assertNotEmitted(pane.text_style_asked), qtbot.assertNotEmitted(
        pane.line_style_asked
    ):
        pane.show_nodes((PLACE,), NAMES)
        pane.show_nodes((STYLED,), NAMES)
        pane.show_nodes((PLACE, STYLED), NAMES)
        pane.show_arcs((ARC,), NODE_NAMES)


def test_unticking_asks_for_a_complete_style_of_the_defaults(pane, qtbot):
    """Agreed with Jaume: unticking fills every field with the defaults of the
    moment, so nothing is ever half its own and half the application's."""

    pane.show_nodes((PLACE,), NAMES)

    with qtbot.waitSignal(pane.text_style_asked, timeout=1000) as blocker:
        pane.text_default_check.setCheckState(Qt.CheckState.Unchecked)

    uuids, style = blocker.args
    assert uuids == ('p',)
    assert style == preferences.text_appearance(None, preferences.PLACE)
    assert pane.font_size_spin.isEnabled()


def test_ticking_again_throws_the_items_own_style_away(pane, qtbot):
    """``None`` is *follow the defaults*, and Undo is what brings it back."""

    pane.show_nodes((STYLED,), NAMES)

    with qtbot.waitSignal(pane.text_style_asked, timeout=1000) as blocker:
        pane.text_default_check.setCheckState(Qt.CheckState.Checked)

    assert blocker.args == [('p',), None]


def test_a_field_changed_asks_for_the_whole_style(pane, qtbot):
    """A style is complete or absent, so every ask carries all of it."""

    pane.show_nodes((STYLED,), NAMES)

    with qtbot.waitSignal(pane.text_style_asked, timeout=1000) as blocker:
        pane.font_size_spin.setValue(6.0)

    _uuids, style = blocker.args
    assert style.size == 6.0
    assert style.font == 'DejaVu Sans'
    assert style.bold is True
    assert style.colour == '#aa0000'


def test_a_typeface_is_asked_for_every_item_shown(pane, qtbot):
    """One choice for all of them, as a description is."""

    twin = PlaceData('q', 'P2', (0.0, 30.0), 2, 'Bottles waiting', None, None,
                     STYLED.text_style, STYLED.line_style)

    pane.show_nodes((STYLED, twin), NAMES)

    with qtbot.waitSignal(pane.text_style_asked, timeout=1000) as blocker:
        pane.italic_check.setChecked(True)

    uuids, style = blocker.args
    assert uuids == ('p', 'q')
    assert style.italic is True


def test_a_width_changed_asks_for_the_whole_line_style(pane, qtbot):
    """The line half, which an arc has as well as a node."""

    pane.show_nodes((STYLED,), NAMES)

    with qtbot.waitSignal(pane.line_style_asked, timeout=1000) as blocker:
        pane.line_width_spin.setValue(2.0)

    _uuids, style = blocker.args
    assert style == LineStyle('#0055aa', 2.0)


def test_a_colour_is_chosen_on_a_button_and_automatic_follows_the_theme(
    pane, qtbot, chosen_colour
):
    """The control the settings dialog uses, met again on one item."""

    pane.show_nodes((STYLED,), NAMES)

    with qtbot.waitSignal(pane.text_style_asked, timeout=1000) as blocker:
        pane.text_colour_automatic.setChecked(True)
    assert blocker.args[1].colour == AUTOMATIC

    with qtbot.waitSignal(pane.text_style_asked, timeout=1000) as blocker:
        pane.text_colour_automatic.setChecked(False)
    assert blocker.args[1].colour == '#117744'


def test_a_colour_that_is_the_themes_own_ink_is_warned_about(pane, chosen_colour):
    """The same warning the settings dialog raises, for the same reason."""

    from masafi_simtwin.theme import LIGHT_COLORS

    pane.show_nodes((STYLED,), NAMES)
    assert pane.text_colour_note.isHidden()

    chosen_colour.append(LIGHT_COLORS.text)
    pane.text_colour_button.click()

    assert not pane.text_colour_note.isHidden()
    assert pane.text_colour_note.property('error') is True


def test_an_arc_is_asked_for_a_style_of_the_arcs_own_kind(pane, qtbot):
    """Its defaults are the arc's: never bold, italic or aligned."""

    pane.show_arcs((ARC,), NODE_NAMES)

    with qtbot.waitSignal(pane.text_style_asked, timeout=1000) as blocker:
        pane.text_default_check.setCheckState(Qt.CheckState.Unchecked)

    uuids, style = blocker.args
    assert uuids == ('a',)
    assert style == preferences.text_appearance(None, preferences.ARC)
    assert style.normal


def test_a_page_of_another_kind_forgets_the_appearance(pane, qtbot):
    """So a field moved afterwards is not asked of what is no longer shown."""

    pane.show_nodes((STYLED,), NAMES)
    pane.show_model({'name': 'N', 'kind': 'petri-net', 'units': {'time': 's'}})

    with qtbot.assertNotEmitted(pane.text_style_asked), qtbot.assertNotEmitted(
        pane.line_style_asked
    ):
        pane.font_size_spin.setValue(9.0)
        pane.line_width_spin.setValue(2.5)
