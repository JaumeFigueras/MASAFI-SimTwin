"""What the application remembers about this user on this machine.

The storage is ``QSettings``, which is what makes the same code work over an
INI file on Linux, ``%APPDATA%`` on Windows and the user's configuration
directory on macOS.  :class:`~masafi_simtwin.application.SimTwinApplication`
pins the format to ``QSettings.Format.IniFormat`` on every platform, so there is
one readable file everywhere — easy to send in a bug report, easy to diff, and
not subject to the size limits of the Windows registry.

This module is the layer above it, and it owns three things ``QSettings`` does
not:

**A type on every read.** ``QSettings.value()`` gives back whatever it finds,
and a value a user typed into the INI file by hand comes back as a string: a
``follow_os_theme=false`` read without a type is the string ``'false'``, which
is true.  Every preference declares its type, so every read is converted.

**The defaults, in one place.** A default lives in the :class:`Preference` that
declares it and nowhere else, so it can be changed without hunting through call
sites.  Writing a value equal to the default *removes* the key rather than
storing it, which keeps the file down to what the user actually chose and lets
a changed default reach everyone who never chose otherwise.

**A pending copy.** :meth:`Preferences.edit` gives an edit that holds changes
aside until :meth:`PreferenceEdit.commit`, which is what makes OK and Cancel
mean something in the settings dialog.

Choosing a hand-editable file means the file can hold nonsense, so a preference
with a list of ``choices`` falls back to its default when what is stored is not
one of them, rather than carrying a bad value into the application.

Nothing here belongs to :mod:`simtwin_core`: ``QSettings`` is Qt, and the
protocol the adapters implement stays free of it.  When a backend needs a
preference the shell reads it and passes the plain value down.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PyQt6.QtCore import QSettings

from masafi_simtwin.theme import ColorScheme
from masafi_simtwin.translations import LANGUAGES

#: The value of ``appearance/language`` that means "whatever the desktop says".
SYSTEM_LANGUAGE = ''

#: The value of ``appearance/theme`` that means "follow the desktop".
SYSTEM_THEME = 'system'


@dataclass(frozen=True)
class Preference:
    """One thing the application remembers.

    Attributes
    ----------
    key : str
        Where it is stored, ``group/name``.  The group is the settings category
        it belongs to, so that the file reads like the tree in the dialog.
    default : object
        What it is worth when the user has never chosen, and what is restored
        when what is stored is not one of ``choices``.
    type : type
        What it is read back as.  Without this a hand-edited value arrives as a
        string.
    choices : tuple of object
        Everything it is allowed to be, empty when anything of the right type
        will do.
    restart : bool
        Whether the application has to be started again before a change to it
        takes effect.  The settings dialog says so when such a preference is
        changed, and offers the restart once it is closed.
    """

    key: str
    default: Any
    type: type
    choices: tuple[Any, ...] = field(default=())
    restart: bool = False

    def holds(self, value: Any) -> bool:
        """Say whether a value is one this preference is allowed to take.

        Parameters
        ----------
        value : object
            The value to check.

        Returns
        -------
        bool
            True when there are no choices, or the value is one of them.
        """

        return not self.choices or value in self.choices


#: The time units a quantity may be shown in, smallest first.  The values are
#: the symbols, kept to ASCII so that the settings file needs no encoding of its
#: own; ``us`` stands for the microsecond, whose symbol is ``µs``.
TIME_UNITS: tuple[str, ...] = ('us', 'ms', 's', 'min', 'h', 'd')

#: The distance units a length may be shown in, smallest first.
DISTANCE_UNITS: tuple[str, ...] = ('mm', 'cm', 'm', 'dam', 'km')

#: The units an area may be shown in, smallest first.  ``ha`` is the hectare,
#: which is the one that is not a power of ten of the others' names.
SURFACE_UNITS: tuple[str, ...] = ('mm2', 'cm2', 'm2', 'dam2', 'ha', 'km2')

#: Every preference the application has, in the order of the settings tree.
#:
#: Every unit defaults to the SI base unit of its quantity: the second, the
#: metre and the square metre.
PREFERENCES: tuple[Preference, ...] = (
    Preference(
        'appearance/language',
        SYSTEM_LANGUAGE,
        str,
        (SYSTEM_LANGUAGE, *LANGUAGES),
        restart=True,
    ),
    Preference(
        'appearance/theme',
        SYSTEM_THEME,
        str,
        (SYSTEM_THEME, *(scheme.value for scheme in ColorScheme)),
        restart=True,
    ),
    Preference('units/time', 's', str, TIME_UNITS),
    Preference('units/distance', 'm', str, DISTANCE_UNITS),
    Preference('units/surface', 'm2', str, SURFACE_UNITS),
)

#: The preferences by key, which is how they are asked for.
BY_KEY: dict[str, Preference] = {preference.key: preference for preference in PREFERENCES}


def preference(key: str) -> Preference:
    """Find a preference by its key.

    Parameters
    ----------
    key : str
        The key it was declared with.

    Returns
    -------
    Preference
        The declaration.

    Raises
    ------
    KeyError
        When no preference goes by that key, which is a mistyped key rather
        than a missing value.
    """

    try:
        return BY_KEY[key]
    except KeyError:
        raise KeyError(f'{key!r} is not a preference of this application') from None


def needs_restart(keys: tuple[str, ...] | list[str]) -> bool:
    """Say whether changing these preferences calls for a restart.

    Parameters
    ----------
    keys : tuple of str
        The keys that were changed, as :meth:`PreferenceEdit.commit` returns
        them.

    Returns
    -------
    bool
        True when at least one of them only takes effect at start-up.
    """

    return any(preference(key).restart for key in keys)


class Preferences:
    """The stored preferences, read and written by key.

    Parameters
    ----------
    settings : PyQt6.QtCore.QSettings, optional
        Where to store them.  The default is a plain ``QSettings()``, which
        finds the application's own file through the organisation and
        application names the application set on itself; passing one is for the
        tests.
    """

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings if settings is not None else QSettings()

    @property
    def settings(self) -> QSettings:
        """PyQt6.QtCore.QSettings: The store the preferences are kept in."""

        return self._settings

    def value(self, key: str) -> Any:
        """Read a preference.

        Parameters
        ----------
        key : str
            The key of the preference.

        Returns
        -------
        object
            What is stored, converted to the declared type; the default when
            nothing is stored, or when what is stored is not one of the
            preference's choices.
        """

        declaration = preference(key)
        stored = self._settings.value(
            declaration.key, declaration.default, type=declaration.type
        )
        return stored if declaration.holds(stored) else declaration.default

    def set_value(self, key: str, value: Any) -> None:
        """Write a preference.

        Writing the default removes the key instead of storing it, so the file
        holds only what the user chose.

        Parameters
        ----------
        key : str
            The key of the preference.
        value : object
            What to store.

        Raises
        ------
        ValueError
            When the value is not one the preference is allowed to take.
        """

        declaration = preference(key)
        if not declaration.holds(value):
            raise ValueError(
                f'{value!r} is not one of the values {declaration.key} can take: '
                f'{declaration.choices}'
            )
        if value == declaration.default:
            self._settings.remove(declaration.key)
        else:
            self._settings.setValue(declaration.key, value)

    def reset(self, key: str) -> None:
        """Forget what the user chose for one preference.

        Parameters
        ----------
        key : str
            The key of the preference.
        """

        self._settings.remove(preference(key).key)

    def edit(self) -> PreferenceEdit:
        """Begin a set of changes that are not stored until they are committed.

        Returns
        -------
        PreferenceEdit
            The pending changes, empty to start with.
        """

        return PreferenceEdit(self)


class PreferenceEdit:
    """Changes to the preferences, held aside until they are committed.

    This is what a dialog with an OK and a Cancel button edits: reading it gives
    the pending value where there is one and the stored value everywhere else,
    so the pages of the dialog do not have to know which is which.

    Parameters
    ----------
    preferences : Preferences
        The preferences the changes will be written to.
    """

    def __init__(self, preferences: Preferences) -> None:
        self._preferences = preferences
        self._changes: dict[str, Any] = {}

    @property
    def changes(self) -> dict[str, Any]:
        """dict: The pending changes, by key."""

        return dict(self._changes)

    @property
    def changed(self) -> bool:
        """bool: Whether anything is waiting to be written."""

        return bool(self._changes)

    @property
    def needs_restart(self) -> bool:
        """bool: Whether what is pending only takes effect at start-up."""

        return needs_restart(tuple(self._changes))

    def value(self, key: str) -> Any:
        """Read a preference as it stands in this edit.

        Parameters
        ----------
        key : str
            The key of the preference.

        Returns
        -------
        object
            The pending value when there is one, what is stored otherwise.
        """

        if key in self._changes:
            return self._changes[key]
        return self._preferences.value(key)

    def set_value(self, key: str, value: Any) -> None:
        """Change a preference, without storing it.

        Setting a preference back to what is stored takes it out of the pending
        changes again, so moving a control and moving it back leaves nothing to
        commit.

        Parameters
        ----------
        key : str
            The key of the preference.
        value : object
            What it should become.

        Raises
        ------
        ValueError
            When the value is not one the preference is allowed to take.
        """

        declaration = preference(key)
        if not declaration.holds(value):
            raise ValueError(
                f'{value!r} is not one of the values {declaration.key} can take: '
                f'{declaration.choices}'
            )
        if value == self._preferences.value(key):
            self._changes.pop(key, None)
        else:
            self._changes[key] = value

    def commit(self) -> tuple[str, ...]:
        """Write the pending changes and forget them.

        Returns
        -------
        tuple of str
            The keys that were written, so a caller can act on what changed —
            telling the user that the language needs a restart, for one.
        """

        written = tuple(self._changes)
        for key, value in self._changes.items():
            self._preferences.set_value(key, value)
        self._changes.clear()
        return written

    def discard(self) -> None:
        """Throw the pending changes away."""

        self._changes.clear()
