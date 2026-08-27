"""Tests for the Settings dialog."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QDialogButtonBox, QLabel

from masafi_simtwin.dialogs.settings import THEME_VALUES, SettingsDialog
from masafi_simtwin.preferences import (
    DISTANCE_UNITS,
    SURFACE_UNITS,
    SYSTEM_LANGUAGE,
    SYSTEM_THEME,
    TIME_UNITS,
    BY_KEY,
    Preferences,
)
from masafi_simtwin.translations import LANGUAGE_NAMES, LANGUAGES

#: The tree the form declares, parents with their children.
CATEGORIES = {
    'Appearance': ['Language', 'Themes'],
    'Default Units': ['Time', 'Space'],
}

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


@pytest.mark.parametrize('name', [name for name in CATEGORIES])
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


@pytest.mark.parametrize('name', [name for name in CATEGORIES])
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
