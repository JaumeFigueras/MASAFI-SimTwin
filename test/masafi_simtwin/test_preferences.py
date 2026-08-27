"""Tests for the stored preferences."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings

from masafi_simtwin.preferences import (
    BY_KEY,
    PREFERENCES,
    needs_restart,
    SYSTEM_LANGUAGE,
    SYSTEM_THEME,
    Preference,
    Preferences,
)

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
        'units/time',
        'units/distance',
        'units/surface',
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
