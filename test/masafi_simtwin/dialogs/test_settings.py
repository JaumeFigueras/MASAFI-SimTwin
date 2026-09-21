"""Tests for the Settings dialog."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QDialogButtonBox, QLabel

from masafi_simtwin import fonts, paper
from masafi_simtwin.dialogs.settings import (
    ALIGNMENT_VALUES,
    THEME_VALUES,
    SettingsDialog,
)
from masafi_simtwin.preferences import (
    APPEARANCE_KEYS,
    AUTOSAVE_INTERVALS,
    AUTOSAVE_KEY,
    DEFAULT_FONT_SIZE,
    DEFAULT_GRID_STEP,
    DEFAULT_LINE_WIDTH,
    DISTANCE_UNITS,
    GRID_STEP_KEY,
    MAX_GRID_STEP,
    MIN_GRID_STEP,
    SURFACE_UNITS,
    SYSTEM_FONT,
    SYSTEM_LANGUAGE,
    SYSTEM_THEME,
    TIME_UNITS,
    BY_KEY,
    Preferences,
    needs_restart,
)
from masafi_simtwin.theme import DARK_COLORS, LIGHT_COLORS
from masafi_simtwin.translations import LANGUAGE_NAMES, LANGUAGES
from simtwin_core.petri_net import (
    ALIGNMENTS,
    AUTOMATIC,
    MAX_FONT_SIZE,
    MAX_LINE_WIDTH,
    MIN_FONT_SIZE,
    MIN_LINE_WIDTH,
)

#: The tree the form declares, parents with their children.
CATEGORIES = {
    'Appearance': ['Language', 'Themes', 'Page'],
    'Petri Net': ['Text Appearance', 'Line Appearance'],
    'Default Units': ['Time', 'Space'],
    'Saving': [],
}

#: The categories that have children, and so a list of links on their page.
PARENTS = [name for name, children in CATEGORIES.items() if children]

#: The same tree walked depth first, which is the order of the pages.
DEPTH_FIRST = [
    name
    for parent, children in CATEGORIES.items()
    for name in (parent, *children)
]


@pytest.fixture
def preferences(tmp_path):
    """Give preferences of this test's own, with nothing chosen.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary directory pytest made.

    Returns
    -------
    masafi_simtwin.preferences.Preferences
        Preferences over an empty file.
    """

    path = tmp_path / 'preferences.ini'
    return Preferences(QSettings(str(path), QSettings.Format.IniFormat))


@pytest.fixture
def dialog(qtbot, preferences):
    """Build the Settings dialog.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.
    preferences : masafi_simtwin.preferences.Preferences
        The preferences its pages edit.

    Returns
    -------
    masafi_simtwin.dialogs.settings.SettingsDialog
        The dialog, on its first category.
    """

    widget = SettingsDialog(preferences=preferences)
    qtbot.addWidget(widget)
    return widget


def categories(dialog):
    """List the categories of a dialog by name.

    Parameters
    ----------
    dialog : masafi_simtwin.dialogs.settings.SettingsDialog
        The dialog.

    Returns
    -------
    list of str
        The names, depth first.
    """

    return [category.text(0) for category in dialog.categories()]


def category(dialog, name):
    """Find one category by name.

    Parameters
    ----------
    dialog : masafi_simtwin.dialogs.settings.SettingsDialog
        The dialog.
    name : str
        The name shown in the tree.

    Returns
    -------
    PyQt6.QtWidgets.QTreeWidgetItem
        The item.
    """

    return next(item for item in dialog.categories() if item.text(0) == name)


def test_the_tree_holds_the_categories_of_the_form(dialog):
    """The two groups are there, each with its two leaves, and all expanded."""

    assert categories(dialog) == DEPTH_FIRST
    for name in CATEGORIES:
        assert category(dialog, name).isExpanded()


def test_every_category_has_a_page_of_its_own(dialog):
    """The pairing is by order, so it only holds while the two lists agree."""

    assert dialog.page_stack.count() == len(DEPTH_FIRST)
    pages = [dialog.page_of(item).objectName() for item in dialog.categories()]
    assert len(set(pages)) == len(pages)
    assert pages == [dialog.page_stack.widget(i).objectName() for i in range(len(pages))]


def test_the_first_category_is_shown_when_the_dialog_opens(dialog):
    """A settings dialog never opens on an empty right hand side."""

    first = next(dialog.categories())
    assert dialog.category_tree.currentItem() is first
    assert dialog.page_stack.currentWidget() is dialog.page_of(first)


@pytest.mark.parametrize('name', DEPTH_FIRST)
def test_selecting_a_category_shows_its_page(dialog, name):
    """Every category, leaf or not, brings its own page to the front."""

    item = category(dialog, name)
    dialog.category_tree.setCurrentItem(item)
    assert dialog.page_stack.currentWidget() is dialog.page_of(item)


@pytest.mark.parametrize('name', DEPTH_FIRST)
def test_the_heading_of_a_page_is_the_name_of_its_category(dialog, name):
    """The heading is written from the tree, so the two cannot disagree."""

    page = dialog.page_of(category(dialog, name))
    stem = page.objectName().removesuffix('_page')
    assert page.findChild(QLabel, f'{stem}_heading').text() == name


@pytest.mark.parametrize('name', PARENTS)
def test_a_parent_lists_its_children_as_links(dialog, name):
    """Clicking a root shows a clickable list of what is under it."""

    page = dialog.page_of(category(dialog, name))
    stem = page.objectName().removesuffix('_page')
    links = [
        page.findChild(QLabel, f'{stem}_link_{position}')
        for position in range(len(CATEGORIES[name]))
    ]
    assert all(link is not None for link in links)
    for link, child in zip(links, CATEGORIES[name]):
        assert child in link.text()
        assert link.text().startswith('<a href=')
        assert link.cursor().shape() == Qt.CursorShape.PointingHandCursor


@pytest.mark.parametrize(
    ('parent', 'child'),
    [(parent, child) for parent, children in CATEGORIES.items() for child in children],
)
def test_a_link_selects_the_child_it_names(dialog, parent, child):
    """Following a link moves the tree too, so the two halves stay in step."""

    page = dialog.page_of(category(dialog, parent))
    stem = page.objectName().removesuffix('_page')
    position = CATEGORIES[parent].index(child)
    page.findChild(QLabel, f'{stem}_link_{position}').linkActivated.emit('#')

    expected = category(dialog, child)
    assert dialog.category_tree.currentItem() is expected
    assert dialog.page_stack.currentWidget() is dialog.page_of(expected)


@pytest.mark.parametrize('name', PARENTS)
def test_clicking_the_selected_parent_returns_to_its_list(dialog, name):
    """A click moves no selection when the item is already current.

    Following a link leaves the parent expanded and the child selected; clicking
    the parent again has to take the user back to the list rather than do
    nothing, which is why the click is connected as well as the selection.
    """

    parent = category(dialog, name)
    dialog.category_tree.setCurrentItem(parent)
    dialog._select(parent.child(0))
    assert dialog.page_stack.currentWidget() is not dialog.page_of(parent)

    dialog.category_tree.itemClicked.emit(parent, 0)
    assert dialog.page_stack.currentWidget() is dialog.page_of(parent)


def test_the_buttons_are_standard_ones(dialog):
    """Standard buttons are translated by Qt's own catalogue, not by ours."""

    buttons = QDialogButtonBox.StandardButton
    assert dialog.button_box.standardButtons() == buttons.Ok | buttons.Cancel


def test_the_dialog_opens_an_edit_that_starts_empty(dialog):
    """A dialog that was only opened changes nothing."""

    assert not dialog.edit.changed
    assert dialog.written == ()


def test_cancelling_drops_the_pending_changes(dialog, preferences, qtbot):
    """Cancel is what the pending copy exists for."""

    dialog.edit.set_value('appearance/language', 'ca')
    dialog.show()
    qtbot.waitExposed(dialog)
    dialog.button_box.button(QDialogButtonBox.StandardButton.Cancel).click()

    assert not dialog.isVisible()
    assert dialog.result() == int(SettingsDialog.DialogCode.Rejected)
    assert not dialog.edit.changed
    assert preferences.value('appearance/language') == SYSTEM_LANGUAGE


def test_accepting_writes_the_pending_changes(dialog, preferences, qtbot):
    """OK commits, and the dialog says which keys it wrote."""

    dialog.edit.set_value('appearance/language', 'ca')
    dialog.show()
    qtbot.waitExposed(dialog)
    dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).click()

    assert not dialog.isVisible()
    assert dialog.result() == int(SettingsDialog.DialogCode.Accepted)
    assert dialog.written == ('appearance/language',)
    assert preferences.value('appearance/language') == 'ca'


def test_closing_without_touching_anything_writes_nothing(dialog, preferences, qtbot):
    """Pressing OK on an untouched dialog is not a write."""

    dialog.show()
    qtbot.waitExposed(dialog)
    dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).click()
    assert dialog.written == ()


# ----------------------------------------------------------------------
# The theme, the first parameter there is
# ----------------------------------------------------------------------


@pytest.fixture
def silent_warning(monkeypatch):
    """Count the restart notices instead of putting them on the screen.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The patcher.

    Returns
    -------
    list
        One entry per notice raised, so a test can count them.
    """

    raised = []
    monkeypatch.setattr(
        'masafi_simtwin.dialogs.settings.warn_restart_needed',
        lambda parent=None: raised.append(parent),
    )
    return raised


def test_the_theme_entries_carry_the_values_they_stand_for(dialog):
    """The entries of the form are paired with the stored values by order."""

    values = [dialog.theme_combo.itemData(i) for i in range(dialog.theme_combo.count())]
    assert values == list(THEME_VALUES)
    assert values[0] == SYSTEM_THEME


def test_the_combo_opens_on_the_stored_theme(qtbot, preferences):
    """A dialog opened after a choice shows that choice, not the default."""

    preferences.set_value('appearance/theme', 'dark')
    dialog = SettingsDialog(preferences=preferences)
    qtbot.addWidget(dialog)
    assert dialog.theme_combo.currentData() == 'dark'


def test_choosing_a_theme_is_pending_until_the_dialog_is_accepted(
    dialog, preferences, silent_warning
):
    """The combo writes to the edit, which is not the store."""

    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData('dark'))
    assert dialog.edit.value('appearance/theme') == 'dark'
    assert preferences.value('appearance/theme') == SYSTEM_THEME

    dialog.accept()
    assert preferences.value('appearance/theme') == 'dark'
    assert dialog.written == ('appearance/theme',)


def test_cancelling_leaves_the_theme_alone(dialog, preferences, silent_warning):
    """The combo moved, the preference did not."""

    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData('light'))
    dialog.reject()
    assert preferences.value('appearance/theme') == SYSTEM_THEME


def test_the_theme_needs_a_restart(dialog, silent_warning):
    """Which is why the notice goes up at all."""

    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData('dark'))
    assert dialog.edit.needs_restart


def test_the_restart_notice_is_raised_once_however_often_the_theme_moves(
    dialog, silent_warning
):
    """The notice belongs to the change, not to every move of the control."""

    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData('dark'))
    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData('light'))
    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData(SYSTEM_THEME))
    assert silent_warning == [dialog]


def test_opening_the_dialog_raises_no_notice(dialog, silent_warning):
    """Filling the combo from the store is not the user changing anything."""

    assert silent_warning == []


# ----------------------------------------------------------------------
# The language
# ----------------------------------------------------------------------


def test_the_language_entries_come_from_the_language_list(dialog):
    """The combo is filled from LANGUAGES, so the two cannot fall out of step."""

    combo = dialog.language_combo
    values = [combo.itemData(i) for i in range(combo.count())]
    assert values == [SYSTEM_LANGUAGE, *LANGUAGES]


def test_a_language_is_shown_under_its_own_name(dialog):
    """An endonym is the same word in every language, so it is not translated."""

    combo = dialog.language_combo
    for language in LANGUAGES:
        assert combo.itemText(combo.findData(language)) == LANGUAGE_NAMES[language]


def test_the_first_entry_is_the_system_default(dialog):
    """Nothing chosen leaves the application following the desktop's locale."""

    assert dialog.language_combo.itemData(0) == SYSTEM_LANGUAGE
    assert dialog.language_combo.itemText(0) == 'System default'


def test_the_combo_opens_on_the_stored_language(qtbot, preferences):
    """A dialog opened after a choice shows that choice, not the default."""

    preferences.set_value('appearance/language', 'ca')
    dialog = SettingsDialog(preferences=preferences)
    qtbot.addWidget(dialog)
    assert dialog.language_combo.currentData() == 'ca'


def test_choosing_a_language_is_pending_until_the_dialog_is_accepted(
    dialog, preferences, silent_warning
):
    """The combo writes to the edit, which is not the store."""

    combo = dialog.language_combo
    combo.setCurrentIndex(combo.findData('ca'))
    assert dialog.edit.value('appearance/language') == 'ca'
    assert preferences.value('appearance/language') == SYSTEM_LANGUAGE

    dialog.accept()
    assert preferences.value('appearance/language') == 'ca'
    assert dialog.written == ('appearance/language',)


def test_cancelling_leaves_the_language_alone(dialog, preferences, silent_warning):
    """The combo moved, the preference did not."""

    combo = dialog.language_combo
    combo.setCurrentIndex(combo.findData('ca'))
    dialog.reject()
    assert preferences.value('appearance/language') == SYSTEM_LANGUAGE


def test_the_language_needs_a_restart(dialog, silent_warning):
    """Widgets do not retranslate themselves; the language is settled at start-up."""

    combo = dialog.language_combo
    combo.setCurrentIndex(combo.findData('ca'))
    assert dialog.edit.needs_restart


def test_one_notice_covers_both_appearance_settings(dialog, silent_warning):
    """The notice belongs to the change, not to each control that made one."""

    dialog.language_combo.setCurrentIndex(dialog.language_combo.findData('ca'))
    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData('dark'))
    assert silent_warning == [dialog]


def test_both_appearance_settings_are_written_together(dialog, preferences, silent_warning):
    """One OK commits everything the pages changed."""

    dialog.language_combo.setCurrentIndex(dialog.language_combo.findData('ca'))
    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData('dark'))
    dialog.accept()

    assert set(dialog.written) == {'appearance/language', 'appearance/theme'}
    assert preferences.value('appearance/language') == 'ca'
    assert preferences.value('appearance/theme') == 'dark'


# ----------------------------------------------------------------------
# The units
# ----------------------------------------------------------------------

#: Each unit chooser: the combo box, the preference it edits, and its values.
UNIT_CHOOSERS = [
    ('time_combo', 'units/time', TIME_UNITS),
    ('distance_combo', 'units/distance', DISTANCE_UNITS),
    ('surface_combo', 'units/surface', SURFACE_UNITS),
]

#: The same, named for the test report.
UNIT_IDS = [key.rsplit('/', 1)[1] for _combo, key, _values in UNIT_CHOOSERS]


@pytest.mark.parametrize(('name', 'key', 'values'), UNIT_CHOOSERS, ids=UNIT_IDS)
def test_a_unit_chooser_carries_the_values_of_its_entries(dialog, name, key, values):
    """The entries of the form are paired with the stored values by order."""

    combo = getattr(dialog, name)
    assert [combo.itemData(i) for i in range(combo.count())] == list(values)


@pytest.mark.parametrize(('name', 'key', 'values'), UNIT_CHOOSERS, ids=UNIT_IDS)
def test_a_unit_chooser_opens_on_the_si_unit(dialog, name, key, values):
    """Nothing chosen means the SI base unit of that quantity."""

    assert getattr(dialog, name).currentData() == BY_KEY[key].default


@pytest.mark.parametrize(('name', 'key', 'values'), UNIT_CHOOSERS, ids=UNIT_IDS)
def test_a_unit_chooser_opens_on_the_stored_unit(qtbot, preferences, name, key, values):
    """A dialog opened after a choice shows that choice."""

    chosen = values[-1]
    preferences.set_value(key, chosen)
    dialog = SettingsDialog(preferences=preferences)
    qtbot.addWidget(dialog)
    assert getattr(dialog, name).currentData() == chosen


@pytest.mark.parametrize(('name', 'key', 'values'), UNIT_CHOOSERS, ids=UNIT_IDS)
def test_choosing_a_unit_is_pending_until_the_dialog_is_accepted(
    dialog, preferences, name, key, values
):
    """The combo writes to the edit, which is not the store."""

    combo = getattr(dialog, name)
    chosen = values[0]
    combo.setCurrentIndex(combo.findData(chosen))
    assert dialog.edit.value(key) == chosen
    assert preferences.value(key) == BY_KEY[key].default

    dialog.accept()
    assert preferences.value(key) == chosen


@pytest.mark.parametrize(('name', 'key', 'values'), UNIT_CHOOSERS, ids=UNIT_IDS)
def test_a_unit_asks_for_no_restart(dialog, silent_warning, name, key, values):
    """A unit is a way of showing a number, settled every time one is shown."""

    combo = getattr(dialog, name)
    combo.setCurrentIndex(combo.findData(values[0]))
    assert not dialog.edit.needs_restart
    assert silent_warning == []


def test_the_time_and_the_space_units_are_on_their_own_pages(dialog):
    """Space carries both a distance and a surface; time carries one chooser."""

    time_page = dialog.page_of(category(dialog, 'Time'))
    space_page = dialog.page_of(category(dialog, 'Space'))

    assert dialog.time_combo.parent() is time_page
    assert dialog.distance_combo.parent() is space_page
    assert dialog.surface_combo.parent() is space_page


def test_the_space_page_says_what_the_surface_unit_is_for(dialog):
    """Surface units are for statistics, never for defining a model."""

    note = dialog.space_note
    assert 'statistics' in note.text()
    assert note.property('placeholder') is True


# ----------------------------------------------------------------------
# The page
# ----------------------------------------------------------------------


def test_the_paper_combo_holds_what_this_machine_prints_on(dialog):
    """Built here rather than in the form: a different desk, a different list."""

    keys = [dialog.paper_combo.itemData(index) for index in range(dialog.paper_combo.count())]

    assert keys
    assert keys[: len(paper.installed_sizes())] == [
        size.key() for size in paper.installed_sizes()
    ]


def test_the_paper_combo_opens_on_what_the_machine_prints_on_by_default(dialog):
    """Which is what leaving ``appearance/page_size`` unset means."""

    assert dialog.paper_combo.currentData() == paper.default_key()


def test_a_stored_paper_size_this_machine_does_not_offer_is_still_shown(
    qtbot, preferences
):
    """A settings file carried from another desk says what is in force."""

    edit = preferences.edit()
    edit.set_value('appearance/page_size', 'JisB4')
    edit.commit()

    dialog = SettingsDialog(preferences=preferences)
    qtbot.addWidget(dialog)

    assert dialog.paper_combo.currentData() == 'JisB4'


def test_a_form_that_fills_the_paper_combo_is_refused(qtbot, preferences, monkeypatch):
    """The entries come from the machine, so the form has to leave it empty."""

    original = SettingsDialog._bind_paper

    def fill_it_first(self):
        self.paper_combo.addItem('A4', 'A4')
        original(self)

    monkeypatch.setattr(SettingsDialog, '_bind_paper', fill_it_first)

    with pytest.raises(RuntimeError, match='paper_combo'):
        SettingsDialog(preferences=preferences)


def test_choosing_a_paper_size_writes_it(qtbot, preferences):
    """On OK, and not before."""

    dialog = SettingsDialog(preferences=preferences)
    qtbot.addWidget(dialog)
    dialog.paper_combo.setCurrentIndex(dialog.paper_combo.findData('A3'))

    assert preferences.value('appearance/page_size') != 'A3'

    dialog.accept()

    assert preferences.value('appearance/page_size') == 'A3'
    assert 'appearance/page_size' in dialog.written


def test_the_orientation_is_a_pair_of_radio_buttons(dialog):
    """Portrait by default, and only one of them on."""

    assert dialog.portrait_radio.isChecked()
    assert not dialog.landscape_radio.isChecked()


def test_choosing_landscape_writes_it_and_turns_portrait_off(qtbot, preferences):
    """Two buttons are one choice, so the one turning on is the one that counts."""

    dialog = SettingsDialog(preferences=preferences)
    qtbot.addWidget(dialog)
    dialog.landscape_radio.setChecked(True)

    assert not dialog.portrait_radio.isChecked()

    dialog.accept()

    assert preferences.value('appearance/page_orientation') == paper.LANDSCAPE


def test_the_grid_step_is_on_the_page_of_the_paper(dialog):
    """The paper and the points drawn on it are one page: they are the sheet."""

    page = dialog.page_of(category(dialog, 'Page'))

    assert dialog.grid_step_spin.parent() is page
    assert dialog.grid_step_spin.suffix().strip() == 'mm'
    assert 'squares' in dialog.grid_step_note.text()


def test_the_grid_step_opens_on_the_millimetre_within_its_limits(dialog):
    """The limits are set in code, so Designer cannot drift away from them."""

    assert dialog.grid_step_spin.value() == DEFAULT_GRID_STEP
    assert dialog.grid_step_spin.minimum() == MIN_GRID_STEP
    assert dialog.grid_step_spin.maximum() == MAX_GRID_STEP


def test_the_grid_step_opens_on_what_was_chosen_before(qtbot, preferences):
    """A dialog opened after a choice shows that choice."""

    preferences.set_value(GRID_STEP_KEY, 2.5)
    dialog = SettingsDialog(preferences=preferences)
    qtbot.addWidget(dialog)

    assert dialog.grid_step_spin.value() == 2.5


def test_choosing_a_grid_step_is_pending_until_the_dialog_is_accepted(
    dialog, preferences
):
    """The spin box writes to the edit, which is not the store."""

    dialog.grid_step_spin.setValue(5.0)

    assert dialog.edit.value(GRID_STEP_KEY) == 5.0
    assert preferences.value(GRID_STEP_KEY) == DEFAULT_GRID_STEP

    dialog.accept()

    assert preferences.value(GRID_STEP_KEY) == 5.0
    assert GRID_STEP_KEY in dialog.written


def test_the_grid_step_has_no_size_in_points_beside_it(dialog):
    """A distance on the paper is not a typeface, so there is nothing to show."""

    assert dialog.findChild(QLabel, 'grid_step_points') is None


def test_the_page_asks_for_no_restart(qtbot, preferences, monkeypatch):
    """A sheet is ruled again where it stands, so nothing is said about restarting."""

    warned = []
    monkeypatch.setattr(
        'masafi_simtwin.dialogs.settings.warn_restart_needed',
        lambda parent: warned.append(parent),
    )
    dialog = SettingsDialog(preferences=preferences)
    qtbot.addWidget(dialog)
    dialog.paper_combo.setCurrentIndex(dialog.paper_combo.findData('A3'))
    dialog.landscape_radio.setChecked(True)
    dialog.grid_step_spin.setValue(2.0)
    dialog.accept()

    assert warned == []
    assert not needs_restart(dialog.written)


# ----------------------------------------------------------------------
# Saving
# ----------------------------------------------------------------------


def test_the_autosave_entries_carry_the_minutes_they_stand_for(dialog):
    """Paired by order with the declared intervals, nought first."""

    combo = dialog.autosave_combo
    assert [combo.itemData(i) for i in range(combo.count())] == list(AUTOSAVE_INTERVALS)
    assert combo.itemText(0) == '0 (Off)'
    assert [combo.itemText(i) for i in range(1, combo.count())] == [
        str(minutes) for minutes in AUTOSAVE_INTERVALS[1:]
    ]


def test_the_autosave_chooser_is_on_the_saving_page(dialog):
    """With the note saying what the journal does between saves."""

    page = dialog.page_of(category(dialog, 'Saving'))

    assert dialog.autosave_combo.parent() is page
    assert 'journal' in dialog.saving_note.text()


def test_the_autosave_opens_on_five_minutes(dialog):
    """Nothing chosen means the default."""

    assert dialog.autosave_combo.currentData() == 5


def test_the_autosave_opens_on_the_stored_interval(qtbot, preferences):
    """A dialog opened after a choice shows that choice."""

    preferences.set_value(AUTOSAVE_KEY, 0)
    dialog = SettingsDialog(preferences=preferences)
    qtbot.addWidget(dialog)

    assert dialog.autosave_combo.currentData() == 0


def test_choosing_an_interval_is_pending_until_the_dialog_is_accepted(
    dialog, preferences, silent_warning
):
    """And it asks for no restart: the timer starts again at once."""

    combo = dialog.autosave_combo
    combo.setCurrentIndex(combo.findData(15))

    assert preferences.value(AUTOSAVE_KEY) == 5
    assert not dialog.edit.needs_restart
    assert silent_warning == []

    dialog.accept()

    assert preferences.value(AUTOSAVE_KEY) == 15
    assert dialog.written == (AUTOSAVE_KEY,)


# ----------------------------------------------------------------------
# How a net is drawn: the lettering
# ----------------------------------------------------------------------


@pytest.fixture
def chosen_colour(monkeypatch):
    """Answer the colour dialog instead of opening one.

    A modal colour dialog in a test run is a test run that stops, so the asking
    is one function and this is what stands in for it.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The patcher.

    Returns
    -------
    list
        One entry per colour asked for; append a colour to it to be given that
        colour next, the default being a plain red.
    """

    answers = ['#aa0000']
    monkeypatch.setattr(
        'masafi_simtwin.dialogs.settings.ask_for_colour',
        lambda parent, current: answers[-1],
    )
    return answers


def test_the_font_combo_is_filled_from_this_machine(dialog):
    """Built here rather than in the form: a different desk, a different list."""

    combo = dialog.font_combo

    assert combo.count() > 1
    assert combo.itemData(0) == SYSTEM_FONT
    assert fonts.default_family() in combo.itemText(0)


def test_a_form_that_fills_the_font_combo_is_refused(qtbot, preferences, monkeypatch):
    """The entries come from the machine, so the form has to leave it empty."""

    original = SettingsDialog._bind_fonts

    def fill_it_first(self):
        self.font_combo.addItem('Nimbus Sans', 'Nimbus Sans')
        original(self)

    monkeypatch.setattr(SettingsDialog, '_bind_fonts', fill_it_first)

    with pytest.raises(RuntimeError, match='font_combo'):
        SettingsDialog(preferences=preferences)


def test_the_font_combo_opens_on_what_the_machine_offers(dialog):
    """Which is what leaving ``petri_net/font`` unset means."""

    assert dialog.font_combo.currentData() == SYSTEM_FONT


def test_a_stored_font_this_machine_lacks_is_still_shown(qtbot, preferences):
    """A settings file carried from another desk says what is in force."""

    preferences.set_value('petri_net/font', 'No Such Font At All')
    dialog = SettingsDialog(preferences=preferences)
    qtbot.addWidget(dialog)

    assert dialog.font_combo.currentData() == 'No Such Font At All'


def test_the_size_is_in_millimetres_with_its_points_beside_it(dialog):
    """Millimetres are what the sheet is measured in; points are what a font is."""

    assert dialog.font_size_spin.value() == DEFAULT_FONT_SIZE
    assert dialog.font_size_spin.minimum() == MIN_FONT_SIZE
    assert dialog.font_size_spin.maximum() == MAX_FONT_SIZE
    assert 'pt' in dialog.font_size_points.text()
    assert '6.8' in dialog.font_size_points.text()


def test_the_points_follow_the_millimetres(dialog):
    """So the two never disagree about the same size."""

    dialog.font_size_spin.setValue(10.0)

    assert '28.3' in dialog.font_size_points.text()


def test_choosing_a_size_is_pending_until_the_dialog_is_accepted(dialog, preferences):
    """The spin box writes to the edit, which is not the store."""

    dialog.font_size_spin.setValue(4.0)

    assert dialog.edit.value('petri_net/font_size') == 4.0
    assert preferences.value('petri_net/font_size') == DEFAULT_FONT_SIZE

    dialog.accept()

    assert preferences.value('petri_net/font_size') == 4.0


def test_the_alignment_entries_carry_the_values_they_stand_for(dialog):
    """The entries of the form are paired with the core's names by order."""

    combo = dialog.alignment_combo
    values = [combo.itemData(i) for i in range(combo.count())]

    assert values == list(ALIGNMENT_VALUES) == list(ALIGNMENTS)
    assert combo.currentData() == 'left'


#: Each typeface: the kind of text, and the two check boxes that say how it is
#: written.  A guard and a time function do not exist yet and are stored anyway.
TYPEFACE_CHECKS = [
    ('place', 'place_bold_check', 'place_italic_check'),
    ('transition', 'transition_bold_check', 'transition_italic_check'),
    ('guard', 'guard_bold_check', 'guard_italic_check'),
    ('time_function', 'time_function_bold_check', 'time_function_italic_check'),
]


@pytest.mark.parametrize(
    ('role', 'bold', 'italic'), TYPEFACE_CHECKS, ids=[row[0] for row in TYPEFACE_CHECKS]
)
def test_every_kind_of_text_has_a_bold_and_an_italic(dialog, role, bold, italic):
    """Two check boxes are the typeface, as agreed."""

    assert getattr(dialog, bold).isChecked() is BY_KEY[f'petri_net/{role}_bold'].default
    assert getattr(dialog, italic).isChecked() is BY_KEY[f'petri_net/{role}_italic'].default


def test_a_guard_and_a_time_function_start_italic_and_nothing_else_does(dialog):
    """Which is what was decided, and is visible on the page."""

    assert dialog.guard_italic_check.isChecked()
    assert dialog.time_function_italic_check.isChecked()
    assert not dialog.place_italic_check.isChecked()
    assert not dialog.transition_italic_check.isChecked()


def test_ticking_a_typeface_is_pending_until_the_dialog_is_accepted(dialog, preferences):
    """The check box writes to the edit, which is not the store."""

    dialog.place_bold_check.setChecked(True)

    assert dialog.edit.value('petri_net/place_bold') is True
    assert preferences.value('petri_net/place_bold') is False

    dialog.accept()

    assert preferences.value('petri_net/place_bold') is True


# ----------------------------------------------------------------------
# The two colours
# ----------------------------------------------------------------------

#: Each colour: its preference, the *Automatic* box, the button and the note.
COLOUR_CONTROLS = [
    ('petri_net/text_colour', 'text_colour_automatic', 'text_colour_button', 'text_colour_note'),
    ('petri_net/line_colour', 'line_colour_automatic', 'line_colour_button', 'line_colour_note'),
]

#: The same, named for the test report.
COLOUR_IDS = [key.rsplit('/', 1)[1] for key, *_rest in COLOUR_CONTROLS]


@pytest.mark.parametrize(
    ('key', 'automatic', 'button', 'note'), COLOUR_CONTROLS, ids=COLOUR_IDS
)
def test_a_colour_starts_automatic_with_nothing_to_choose(dialog, key, automatic, button, note):
    """Only *Automatic* reads on both schemes, so it is where a colour starts."""

    assert getattr(dialog, automatic).isChecked()
    assert not getattr(dialog, button).isEnabled()
    assert getattr(dialog, note).isHidden()


@pytest.mark.parametrize(
    ('key', 'automatic', 'button', 'note'), COLOUR_CONTROLS, ids=COLOUR_IDS
)
def test_unticking_automatic_asks_for_a_colour(
    dialog, preferences, chosen_colour, key, automatic, button, note
):
    """The button is what a colour is chosen on, so it is what unticking opens."""

    getattr(dialog, automatic).setChecked(False)

    assert getattr(dialog, button).isEnabled()
    assert dialog.edit.value(key) == '#aa0000'

    dialog.accept()

    assert preferences.value(key) == '#aa0000'


@pytest.mark.parametrize(
    ('key', 'automatic', 'button', 'note'), COLOUR_CONTROLS, ids=COLOUR_IDS
)
def test_ticking_automatic_again_gives_the_colour_up(
    dialog, preferences, chosen_colour, key, automatic, button, note
):
    """Automatic is a value like any other, and it is the one that follows the theme."""

    getattr(dialog, automatic).setChecked(False)
    getattr(dialog, automatic).setChecked(True)

    assert dialog.edit.value(key) == AUTOMATIC
    assert not getattr(dialog, button).isEnabled()


@pytest.mark.parametrize(
    ('key', 'automatic', 'button', 'note'), COLOUR_CONTROLS, ids=COLOUR_IDS
)
def test_a_colour_that_is_the_theme_s_own_ink_is_warned_about(
    dialog, chosen_colour, key, automatic, button, note
):
    """It would not change with the theme, and *Automatic* is what would.

    The warning is asked after by :meth:`QWidget.isHidden` rather than by
    ``isVisibleTo``: every page but the one the dialog opened on is hidden by
    the stack it is in, so ``isVisibleTo`` answers *no* for everything on them
    whatever the label itself was told.
    """

    chosen_colour.append(LIGHT_COLORS.text)
    getattr(dialog, automatic).setChecked(False)

    assert not getattr(dialog, note).isHidden()
    assert getattr(dialog, note).property('error') is True

    chosen_colour.append(DARK_COLORS.text)
    getattr(dialog, button).click()

    assert not getattr(dialog, note).isHidden()

    chosen_colour.append('#aa0000')
    getattr(dialog, button).click()

    assert getattr(dialog, note).isHidden()


@pytest.mark.parametrize(
    ('key', 'automatic', 'button', 'note'), COLOUR_CONTROLS, ids=COLOUR_IDS
)
def test_giving_the_colour_dialog_up_changes_nothing(
    dialog, monkeypatch, key, automatic, button, note
):
    """Cancelling the colour dialog is not choosing a colour."""

    monkeypatch.setattr(
        'masafi_simtwin.dialogs.settings.ask_for_colour', lambda parent, current: None
    )
    getattr(dialog, automatic).setChecked(False)

    assert dialog.edit.value(key) == AUTOMATIC
    assert getattr(dialog, automatic).isChecked()


# ----------------------------------------------------------------------
# The lines, and what the whole family asks of the application
# ----------------------------------------------------------------------


def test_the_width_is_in_millimetres_within_the_limits_of_the_core(dialog):
    """0.1 to 3 mm, as agreed, and what every item is drawn with today."""

    assert dialog.line_width_spin.value() == DEFAULT_LINE_WIDTH
    assert dialog.line_width_spin.minimum() == MIN_LINE_WIDTH
    assert dialog.line_width_spin.maximum() == MAX_LINE_WIDTH
    assert 'pt' in dialog.line_width_points.text()


def test_choosing_a_width_is_pending_until_the_dialog_is_accepted(dialog, preferences):
    """The spin box writes to the edit, which is not the store."""

    dialog.line_width_spin.setValue(1.5)

    assert preferences.value('petri_net/line_width') == DEFAULT_LINE_WIDTH

    dialog.accept()

    assert preferences.value('petri_net/line_width') == 1.5


def test_the_two_pages_hold_their_own_controls(dialog):
    """The lettering on one page, the drawing on the other."""

    text_page = dialog.page_of(category(dialog, 'Text Appearance'))
    line_page = dialog.page_of(category(dialog, 'Line Appearance'))

    for name in ('font_combo', 'font_size_spin', 'alignment_combo', 'place_bold_check'):
        assert getattr(dialog, name).parent() is text_page
    for name in ('line_width_spin', 'line_colour_button'):
        assert getattr(dialog, name).parent() is line_page


def test_nothing_about_how_a_net_is_drawn_asks_for_a_restart(
    dialog, preferences, chosen_colour, silent_warning
):
    """A sheet is drawn again where it stands, as it is ruled again where it stands."""

    dialog.font_size_spin.setValue(5.0)
    dialog.place_bold_check.setChecked(True)
    dialog.alignment_combo.setCurrentIndex(dialog.alignment_combo.findData('center'))
    dialog.text_colour_automatic.setChecked(False)
    dialog.line_width_spin.setValue(1.0)

    assert not dialog.edit.needs_restart
    assert silent_warning == []

    dialog.accept()

    assert set(dialog.written) <= set(APPEARANCE_KEYS)
    assert not needs_restart(dialog.written)
