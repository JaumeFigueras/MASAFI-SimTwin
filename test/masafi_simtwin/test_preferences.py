"""Tests for the stored preferences."""

from __future__ import annotations

import dataclasses
import uuid

import pytest
from PyQt6.QtCore import QSettings, QSizeF

from masafi_simtwin import fonts, paper
from masafi_simtwin.preferences import (
    APPEARANCE_KEYS,
    AUTOSAVE_INTERVALS,
    AUTOSAVE_KEY,
    BY_KEY,
    DEFAULT_FONT_SIZE,
    DEFAULT_GRID_STEP,
    DEFAULT_LINE_WIDTH,
    GRID_KEYS,
    GRID_STEP_KEY,
    INSTALL_KEY,
    MAX_GRID_STEP,
    MIN_GRID_STEP,
    PAGE_KEYS,
    PREFERENCES,
    ROLES,
    grid_step,
    install_id,
    line_appearance,
    needs_restart,
    page,
    text_appearance,
    within,
    SYSTEM_FONT,
    SYSTEM_LANGUAGE,
    SYSTEM_PAGE_SIZE,
    SYSTEM_THEME,
    Preference,
    Preferences,
)
from simtwin_core.petri_net import AUTOMATIC, LineStyle, TextStyle

#: Every declared key, so a new preference is covered without touching a test.
KEYS = [declaration.key for declaration in PREFERENCES]


@pytest.fixture
def path(tmp_path):
    """Give a settings file of this test's own.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary directory pytest made.

    Returns
    -------
    pathlib.Path
        A file that does not exist yet.
    """

    return tmp_path / 'preferences.ini'


@pytest.fixture
def preferences(path):
    """Build preferences over an empty file.

    Parameters
    ----------
    path : pathlib.Path
        Where to store them.

    Returns
    -------
    masafi_simtwin.preferences.Preferences
        Preferences with nothing chosen yet.
    """

    return Preferences(QSettings(str(path), QSettings.Format.IniFormat))


def written(preferences, path):
    """Flush the store and read the file back.

    Parameters
    ----------
    preferences : masafi_simtwin.preferences.Preferences
        The preferences.
    path : pathlib.Path
        Where they are stored.

    Returns
    -------
    str
        What is on disk.
    """

    preferences.settings.sync()
    return path.read_text(encoding='utf-8') if path.exists() else ''


# ----------------------------------------------------------------------
# The declarations
# ----------------------------------------------------------------------


def test_the_keys_are_grouped_like_the_settings_tree():
    """A key is ``group/name``, so the file reads like the dialog."""

    assert KEYS == [
        'appearance/language',
        'appearance/theme',
        'appearance/page_size',
        'appearance/page_orientation',
        'appearance/grid_step',
        'petri_net/font',
        'petri_net/font_size',
        'petri_net/alignment',
        'petri_net/text_colour',
        'petri_net/place_bold',
        'petri_net/place_italic',
        'petri_net/transition_bold',
        'petri_net/transition_italic',
        'petri_net/guard_bold',
        'petri_net/guard_italic',
        'petri_net/time_function_bold',
        'petri_net/time_function_italic',
        'petri_net/line_colour',
        'petri_net/line_width',
        'units/time',
        'units/distance',
        'units/surface',
        'saving/autosave_interval',
    ]


def test_every_unit_defaults_to_the_si_one():
    """The second, the metre and the square metre, whatever the machine says."""

    assert BY_KEY['units/time'].default == 's'
    assert BY_KEY['units/distance'].default == 'm'
    assert BY_KEY['units/surface'].default == 'm2'


def test_a_unit_takes_effect_without_a_restart():
    """Nothing is settled at start-up by the units, unlike language and theme."""

    assert not needs_restart(['units/time', 'units/distance', 'units/surface'])
    assert needs_restart(['appearance/theme'])
    assert needs_restart(['appearance/language'])


def test_the_defaults_follow_the_desktop_where_there_is_one():
    """Nothing chosen means the machine decides, for language and for theme."""

    assert BY_KEY['appearance/language'].default == SYSTEM_LANGUAGE
    assert BY_KEY['appearance/theme'].default == SYSTEM_THEME


def test_every_default_is_one_of_the_choices():
    """A default outside its own choices would be restored and then rejected."""

    for declaration in PREFERENCES:
        assert declaration.holds(declaration.default)


# ----------------------------------------------------------------------
# Reading and writing
# ----------------------------------------------------------------------


@pytest.mark.parametrize('key', KEYS)
def test_an_unset_preference_reads_its_default(preferences, key):
    """A store with nothing in it answers with the declarations."""

    assert preferences.value(key) == BY_KEY[key].default


def test_a_written_preference_reads_back(preferences):
    """The ordinary round trip."""

    preferences.set_value('appearance/language', 'ca')
    assert preferences.value('appearance/language') == 'ca'


def test_writing_the_default_stores_nothing(preferences, path):
    """The file holds what the user chose, not what the application decided."""

    preferences.set_value('appearance/theme', 'dark')
    assert 'dark' in written(preferences, path)

    preferences.set_value('appearance/theme', SYSTEM_THEME)
    assert 'dark' not in written(preferences, path)
    assert preferences.value('appearance/theme') == SYSTEM_THEME


def test_resetting_forgets_what_was_chosen(preferences):
    """A reset preference is an unset one."""

    preferences.set_value('appearance/language', 'ca')
    preferences.reset('appearance/language')
    assert preferences.value('appearance/language') == SYSTEM_LANGUAGE


def test_a_value_outside_the_choices_is_refused(preferences):
    """The application does not write what it would not read back."""

    with pytest.raises(ValueError, match='appearance/language'):
        preferences.set_value('appearance/language', 'klingon')


def test_an_unknown_key_says_so(preferences):
    """A mistyped key is a mistake, not a preference with no value."""

    with pytest.raises(KeyError, match='not a preference'):
        preferences.value('appearance/colour')


# ----------------------------------------------------------------------
# What the file being hand-editable costs
# ----------------------------------------------------------------------


def test_a_hand_written_value_outside_the_choices_falls_back(preferences, path):
    """An INI a user edited can hold anything; the application still starts."""

    path.write_text('[appearance]\nlanguage=klingon\n', encoding='utf-8')
    reread = Preferences(QSettings(str(path), QSettings.Format.IniFormat))
    assert reread.value('appearance/language') == SYSTEM_LANGUAGE


def test_a_hand_written_value_is_converted_to_the_declared_type(path, monkeypatch):
    """Without the declared type a hand-edited ``false`` reads as a true string.

    Every preference is a string today, so this is checked against one declared
    for the test; it is the reason the declarations carry a type at all.
    """

    monkeypatch.setitem(BY_KEY, 'test/flag', Preference('test/flag', True, bool))
    path.write_text('[test]\nflag=false\n', encoding='utf-8')
    settings = QSettings(str(path), QSettings.Format.IniFormat)

    assert settings.value('test/flag') == 'false'
    assert bool(settings.value('test/flag')) is True
    assert Preferences(settings).value('test/flag') is False


# ----------------------------------------------------------------------
# The pending copy
# ----------------------------------------------------------------------


def test_an_edit_starts_with_nothing_pending(preferences):
    """Opening a dialog changes nothing by itself."""

    edit = preferences.edit()
    assert not edit.changed
    assert edit.changes == {}


def test_an_edit_reads_through_to_what_is_stored(preferences):
    """A page reads the edit and does not care which values are pending."""

    preferences.set_value('appearance/language', 'ca')
    edit = preferences.edit()
    assert edit.value('appearance/language') == 'ca'
    assert edit.value('appearance/theme') == SYSTEM_THEME


def test_a_pending_change_is_not_stored_until_it_is_committed(preferences):
    """This is what makes Cancel possible."""

    edit = preferences.edit()
    edit.set_value('appearance/language', 'ca')
    assert edit.value('appearance/language') == 'ca'
    assert preferences.value('appearance/language') == SYSTEM_LANGUAGE


def test_committing_writes_and_says_what_it_wrote(preferences):
    """The keys come back so a caller can react to what changed."""

    edit = preferences.edit()
    edit.set_value('appearance/language', 'ca')
    assert edit.commit() == ('appearance/language',)
    assert preferences.value('appearance/language') == 'ca'
    assert not edit.changed


def test_discarding_leaves_the_store_alone(preferences):
    """Cancel."""

    edit = preferences.edit()
    edit.set_value('appearance/language', 'ca')
    edit.discard()
    assert not edit.changed
    assert preferences.value('appearance/language') == SYSTEM_LANGUAGE


def test_moving_a_value_back_leaves_nothing_to_commit(preferences):
    """A control moved and moved again is not a change."""

    edit = preferences.edit()
    edit.set_value('appearance/language', 'ca')
    edit.set_value('appearance/language', SYSTEM_LANGUAGE)
    assert not edit.changed
    assert edit.commit() == ()


def test_an_edit_refuses_a_value_outside_the_choices(preferences):
    """The check is at the edit, so a page hears about it before OK is pressed."""

    with pytest.raises(ValueError, match='appearance/theme'):
        preferences.edit().set_value('appearance/theme', 'sepia')


# ----------------------------------------------------------------------
# The identifier of this installation
# ----------------------------------------------------------------------


def test_an_installation_identifier_is_made_once(path):
    """The same one on every call, so a project's history is consistent."""

    settings = QSettings(str(path), QSettings.Format.IniFormat)
    first = install_id(settings)
    second = install_id(settings)

    assert first == second
    assert uuid.UUID(first)


def test_the_identifier_outlives_the_settings_object(path):
    """It is stored, not held: it identifies the installation, not the run."""

    first = install_id(QSettings(str(path), QSettings.Format.IniFormat))
    reread = install_id(QSettings(str(path), QSettings.Format.IniFormat))

    assert reread == first


def test_two_installations_are_told_apart(tmp_path):
    """Which is what makes it worth putting in a project's history."""

    one = install_id(QSettings(str(tmp_path / 'a.ini'), QSettings.Format.IniFormat))
    two = install_id(QSettings(str(tmp_path / 'b.ini'), QSettings.Format.IniFormat))

    assert one != two


def test_the_identifier_is_not_a_preference():
    """Nobody chooses it, so it has no page and no default worth naming."""

    assert INSTALL_KEY not in BY_KEY


# ----------------------------------------------------------------------
# The page
# ----------------------------------------------------------------------


def test_the_page_size_defaults_to_whatever_the_machine_prints_on():
    """Unset means *ask this machine*, so a laptop and a print room differ."""

    assert BY_KEY['appearance/page_size'].default == SYSTEM_PAGE_SIZE
    assert SYSTEM_PAGE_SIZE == ''
    assert BY_KEY['appearance/page_size'].choices == ()


def test_the_orientation_defaults_to_portrait():
    """And it is one of two things, so a hand-edited file cannot invent a third."""

    declared = BY_KEY['appearance/page_orientation']

    assert declared.default == paper.PORTRAIT
    assert declared.choices == paper.ORIENTATIONS


def test_neither_page_preference_asks_for_a_restart():
    """A sheet can be ruled again where it stands, so it is ruled again at once."""

    assert not BY_KEY['appearance/page_size'].restart
    assert not BY_KEY['appearance/page_orientation'].restart
    assert not needs_restart(PAGE_KEYS)


def test_a_drawing_snaps_to_the_millimetre_unless_told_otherwise(preferences):
    """The step everything on the sheet was snapped to before it could be chosen."""

    declared = BY_KEY[GRID_STEP_KEY]

    assert declared.default == DEFAULT_GRID_STEP == 1.0
    assert declared.type is float
    assert not declared.restart
    assert not needs_restart(GRID_KEYS)
    assert grid_step(preferences) == 1.0


def test_the_grid_step_is_asked_for_as_the_page_is(preferences):
    """One question about the paper, one about the points drawn on it."""

    preferences.set_value(GRID_STEP_KEY, 2.5)

    assert grid_step(preferences) == 2.5
    assert GRID_KEYS == (GRID_STEP_KEY,)


@pytest.mark.parametrize('stored', ['0.05', '25', '2,5', 'abc', 'true'])
def test_a_hand_written_grid_step_that_is_not_one_falls_back(path, stored):
    """A settings file edited by hand cannot leave the sheet without a grid.

    The limits are this module's rather than the core's — a grid is how a
    person draws and no document is held to it — but a value outside them is
    refused the same way, and so is a comma Qt reads as a list.
    """

    path.write_text(f'[appearance]\ngrid_step={stored}\n', encoding='utf-8')
    reread = Preferences(QSettings(str(path), QSettings.Format.IniFormat))

    assert grid_step(reread) == DEFAULT_GRID_STEP


def test_a_grid_step_outside_the_limits_is_refused(preferences):
    """Both ways round, and by the edit as well as by the store."""

    assert MIN_GRID_STEP == 0.1
    assert MAX_GRID_STEP == 20.0
    with pytest.raises(ValueError, match=GRID_STEP_KEY):
        preferences.set_value(GRID_STEP_KEY, 0.0)
    with pytest.raises(ValueError, match=GRID_STEP_KEY):
        preferences.edit().set_value(GRID_STEP_KEY, 50.0)


def test_the_page_is_resolved_from_the_two_preferences(preferences):
    """One question — what page is this? — out of two stored answers."""

    edit = preferences.edit()
    edit.set_value('appearance/page_size', 'A3')
    edit.set_value('appearance/page_orientation', paper.LANDSCAPE)
    edit.commit()

    assert page(preferences) == QSizeF(420.0, 297.0)


def test_an_unset_page_size_is_the_machine_s_own(preferences):
    """Which is what the default means, rather than a size written down here."""

    assert page(preferences) == paper.dimensions(paper.default_key(), paper.PORTRAIT)


def test_a_page_size_that_names_nothing_falls_back(preferences):
    """A settings file edited by hand cannot leave the sheet without a page."""

    preferences.settings.setValue('appearance/page_size', 'Papyrus')

    assert page(preferences) == paper.dimensions(paper.default_key(), paper.PORTRAIT)


# ----------------------------------------------------------------------
# Saving
# ----------------------------------------------------------------------


def test_the_autosave_runs_every_five_minutes_unless_told_otherwise():
    """Nought is one of the choices, and it means never."""

    declaration = BY_KEY[AUTOSAVE_KEY]

    assert declaration.default == 5
    assert declaration.type is int
    assert declaration.choices == AUTOSAVE_INTERVALS == (0, 1, 2, 5, 10, 15, 30)
    assert not needs_restart([AUTOSAVE_KEY])


def test_an_interval_reads_back_as_a_number(preferences, path):
    """Stored as text in the file, read back as the declared type."""

    preferences.set_value(AUTOSAVE_KEY, 15)

    assert '15' in written(preferences, path)
    reread = Preferences(QSettings(str(path), QSettings.Format.IniFormat))
    assert reread.value(AUTOSAVE_KEY) == 15


@pytest.mark.parametrize('stored', ['abc', '7', '-3', ''])
def test_a_hand_written_interval_that_is_not_one_falls_back(path, stored):
    """Not a number at all, which Qt refuses to convert, or not one of the choices."""

    path.write_text(f'[saving]\nautosave_interval={stored}\n', encoding='utf-8')
    reread = Preferences(QSettings(str(path), QSettings.Format.IniFormat))

    assert reread.value(AUTOSAVE_KEY) == 5


# ----------------------------------------------------------------------
# What a net is drawn like
# ----------------------------------------------------------------------


def test_the_appearance_of_a_net_is_a_group_of_its_own():
    """One group, so the file and the settings tree read the same way."""

    assert APPEARANCE_KEYS == tuple(key for key in KEYS if key.startswith('petri_net/'))
    assert APPEARANCE_KEYS


def test_no_appearance_setting_waits_for_a_restart():
    """A sheet is drawn again where it stands, as it is ruled again where it stands."""

    assert not needs_restart(APPEARANCE_KEYS)


def test_an_unset_font_means_whatever_this_machine_offers():
    """The idiom the page size already uses: unset is a question, not a value."""

    assert BY_KEY['petri_net/font'].default == SYSTEM_FONT == ''
    assert BY_KEY['petri_net/font'].choices == ()


def test_the_default_size_keeps_a_caption_the_size_it_is_today():
    """Agreed with Jaume: nothing changes size until he has printed a net."""

    declaration = BY_KEY['petri_net/font_size']

    assert declaration.default == DEFAULT_FONT_SIZE == 2.4
    assert declaration.type is float


def test_the_default_width_is_what_an_item_is_drawn_with_today():
    """What every item and arc was drawn with before there were styles, so a net
    drawn then is drawn the same way now."""

    declaration = BY_KEY['petri_net/line_width']

    assert declaration.default == DEFAULT_LINE_WIDTH == 0.3
    assert declaration.type is float


def test_a_guard_and_a_time_function_are_italic_and_nothing_else_is():
    """They do not exist yet; the typefaces they will take are decided."""

    italic = {key for key in APPEARANCE_KEYS if BY_KEY[key].default is True}

    assert italic == {'petri_net/guard_italic', 'petri_net/time_function_italic'}


def test_every_colour_follows_the_theme_until_one_is_chosen():
    """Only *Automatic* reads on both schemes, so only it can be the default."""

    assert BY_KEY['petri_net/text_colour'].default == AUTOMATIC
    assert BY_KEY['petri_net/line_colour'].default == AUTOMATIC


def test_the_alignment_is_one_of_the_four_there_are():
    """The core's list, so a hand-edited file cannot invent a fifth."""

    from simtwin_core.petri_net import ALIGNMENTS

    assert BY_KEY['petri_net/alignment'].default == 'left'
    assert BY_KEY['petri_net/alignment'].choices == ALIGNMENTS


def test_a_size_reads_back_as_a_number(preferences, path):
    """The first preference that is not a whole number."""

    preferences.set_value('petri_net/font_size', 3.5)

    assert '3.5' in written(preferences, path)
    reread = Preferences(QSettings(str(path), QSettings.Format.IniFormat))
    assert reread.value('petri_net/font_size') == 3.5


@pytest.mark.parametrize(
    'stored',
    ['abc', '', '0.5', '99', '2,4', 'true'],
    ids=['words', 'nothing', 'too-small', 'too-large', 'comma', 'flag'],
)
def test_a_hand_written_size_that_is_not_one_falls_back(path, stored):
    """A number Qt refuses to convert, one outside the limits, or a list.

    ``font_size=2,4`` is the one worth naming: Qt reads a comma as a separator
    and gives back ``[2.0, 4.0]`` rather than refusing, so what checks the
    limits has to refuse what is not a number rather than compare it.
    """

    path.write_text(f'[petri_net]\nfont_size={stored}\n', encoding='utf-8')
    reread = Preferences(QSettings(str(path), QSettings.Format.IniFormat))

    assert reread.value('petri_net/font_size') == DEFAULT_FONT_SIZE


@pytest.mark.parametrize('stored', ['red', '#12345', '#aabbccdd', ''])
def test_a_hand_written_colour_that_is_not_one_falls_back(path, stored):
    """The core says what a colour is; this is the settings file held to it."""

    path.write_text(f'[petri_net]\ntext_colour={stored}\n', encoding='utf-8')
    reread = Preferences(QSettings(str(path), QSettings.Format.IniFormat))

    assert reread.value('petri_net/text_colour') == AUTOMATIC


def test_a_colour_may_be_chosen(preferences):
    """Automatic is the default, not the only thing allowed."""

    preferences.set_value('petri_net/line_colour', '#aa0000')

    assert preferences.value('petri_net/line_colour') == '#aa0000'


def test_a_size_outside_the_limits_is_refused(preferences):
    """As a value outside a list of choices is, and for the same reason."""

    with pytest.raises(ValueError, match='petri_net/font_size'):
        preferences.set_value('petri_net/font_size', 40.0)
    with pytest.raises(ValueError, match='petri_net/line_width'):
        preferences.edit().set_value('petri_net/line_width', 0.0)


def test_a_range_refuses_what_is_not_a_number():
    """Which is what a hand-edited file hands it, and a ``bool`` is not a size."""

    allowed = within(1.0, 20.0)

    assert allowed(1.0) and allowed(20.0) and allowed(3)
    assert not allowed(0.9) and not allowed(20.1)
    assert not allowed([2.0, 4.0])
    assert not allowed('3')
    assert not allowed(True)
    assert not allowed(float('nan'))


# ----------------------------------------------------------------------
# The defaults and an item's own style, resolved into what is drawn
# ----------------------------------------------------------------------


def test_an_item_with_no_style_of_its_own_is_drawn_the_default_way(preferences):
    """Which is the whole of what ``None`` on an item means."""

    assert text_appearance(None, 'place', preferences) == TextStyle(
        fonts.default_family(), DEFAULT_FONT_SIZE, False, False, 'left', AUTOMATIC
    )
    assert line_appearance(None, preferences) == LineStyle(AUTOMATIC, DEFAULT_LINE_WIDTH)


def test_the_defaults_are_what_the_user_chose(preferences):
    """One resolved style out of the several keys it is stored in."""

    edit = preferences.edit()
    edit.set_value('petri_net/font', 'DejaVu Sans')
    edit.set_value('petri_net/font_size', 4.0)
    edit.set_value('petri_net/alignment', 'center')
    edit.set_value('petri_net/text_colour', '#AA00FF')
    edit.set_value('petri_net/place_bold', True)
    edit.set_value('petri_net/line_colour', '#00aa00')
    edit.set_value('petri_net/line_width', 1.5)
    edit.commit()

    assert text_appearance(None, 'place', preferences) == TextStyle(
        'DejaVu Sans', 4.0, True, False, 'center', '#aa00ff'
    )
    assert line_appearance(None, preferences) == LineStyle('#00aa00', 1.5)


def test_each_kind_of_text_takes_its_own_typeface(preferences):
    """A guard and a time function are italic; a place and a transition are not."""

    preferences.set_value('petri_net/transition_bold', True)

    assert not text_appearance(None, 'place', preferences).italic
    assert text_appearance(None, 'transition', preferences).bold
    assert text_appearance(None, 'guard', preferences).italic
    assert text_appearance(None, 'time_function', preferences).italic


def test_an_arcs_weight_is_written_normally_whatever_the_defaults_say(preferences):
    """A weight is never bold, italic or aligned — the rule ``ArcData`` keeps."""

    edit = preferences.edit()
    edit.set_value('petri_net/alignment', 'justified')
    edit.set_value('petri_net/place_bold', True)
    edit.commit()

    style = text_appearance(None, 'arc', preferences)

    assert style.normal
    assert style.font == fonts.default_family()
    assert 'arc' in ROLES


def test_a_role_that_is_not_one_says_so(preferences):
    """A mistyped role is a mistake, like a mistyped key."""

    with pytest.raises(ValueError, match='not a kind of text'):
        text_appearance(None, 'transitions', preferences)


def test_an_item_with_a_style_of_its_own_is_drawn_in_it(preferences):
    """The defaults are what an item without one follows, and nothing more."""

    preferences.set_value('petri_net/font_size', 6.0)
    own = TextStyle('DejaVu Sans', 2.0, italic=True, colour='#123456')
    line = LineStyle('#654321', 2.0)

    assert text_appearance(own, 'place', preferences) == own
    assert line_appearance(line, preferences) == line


def test_a_font_this_machine_lacks_is_fallen_back_on_silently(preferences):
    """A net drawn elsewhere opens here, lettered in something that exists."""

    own = TextStyle('No Such Font At All', 3.0, bold=True, colour='#123456')

    drawn = text_appearance(own, 'place', preferences)

    assert drawn == dataclasses.replace(own, font=fonts.default_family())
    assert drawn.font == fonts.default_family()


def test_a_default_font_that_has_gone_is_fallen_back_on_too(preferences):
    """The settings file outlives the fonts that were installed when it was written."""

    preferences.set_value('petri_net/font', 'No Such Font At All')

    assert text_appearance(None, 'place', preferences).font == fonts.default_family()
