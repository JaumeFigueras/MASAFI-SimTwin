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

One preference is not a value but a question put to the machine:
``appearance/page_size`` is unset by default, and unset means *whatever this
machine prints on*.  :func:`page` is where the two page preferences and the
machine's own answer are resolved into the one thing every caller wants — a
page in millimetres, the right way round.  ``petri_net/font`` is the same idiom
for lettering: unset means whatever this machine offers, which
:mod:`~masafi_simtwin.fonts` answers.

**How far apart the points a drawing snaps to are** is
``appearance/grid_step``, and :func:`grid_step` is the one question asked about
it, as :func:`page` is the one question asked about the paper.  It is a
distance on the *sheet* rather than anything a document holds — a net carries
the positions its nodes were dragged to, not the grid they were dragged on — so
its limits are declared here and no file is ever held to them.

**How a net is drawn** is the ``petri_net`` group, and it is the application's
half of the styles in :mod:`simtwin_core.petri_net`: an item with no style of
its own is drawn the way these say.  :func:`text_appearance` and
:func:`line_appearance` are where the several keys and an item's own style
become the one thing a painter wants — a complete ``TextStyle`` or
``LineStyle``.  The defaults are kept per machine, which is decision *c*; a
model that carries its own is in ``FUTURE.md``.

Two of these are the first preferences that are not a string or a whole number,
and they are why a :class:`Preference` can say more than a list of ``choices``:
a size is any number between two limits and a colour is *Automatic* or
``#rrggbb``, neither of which is a list.  :attr:`Preference.allows` is that
question, :func:`within` builds it for a range, and the colour asks the core's
own :func:`~simtwin_core.petri_net.is_colour`, so the settings file and a
document are held to one rule.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from PyQt6.QtCore import QSettings, QSizeF

from masafi_simtwin import fonts, paper
from masafi_simtwin.theme import ColorScheme
from masafi_simtwin.translations import LANGUAGES
from simtwin_core.petri_net import (
    ALIGNMENTS,
    AUTOMATIC,
    MAX_FONT_SIZE,
    MAX_LINE_WIDTH,
    MIN_FONT_SIZE,
    MIN_LINE_WIDTH,
    LineStyle,
    TextStyle,
    is_colour,
)

#: The value of ``appearance/language`` that means "whatever the desktop says".
SYSTEM_LANGUAGE = ''

#: The value of ``appearance/theme`` that means "follow the desktop".
SYSTEM_THEME = 'system'

#: The value of ``appearance/page_size`` that means "whatever this machine
#: prints on".  It is the default, so a machine that has never been told keeps
#: following its own printer rather than a size written down here once.
SYSTEM_PAGE_SIZE = ''

#: The value of ``petri_net/font`` that means "whatever this machine offers".
#: It is the default, for the reason the page size's is: a machine that has
#: never been told letters in what it has rather than in a name written down
#: here once, which the next machine may not have at all.
SYSTEM_FONT = ''


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
    allows : callable, optional
        What it is allowed to be when that cannot be written as a list — a
        length between two limits, a colour.  It is asked of every value read
        and of every value written, exactly as ``choices`` is.
    """

    key: str
    default: Any
    type: type
    choices: tuple[Any, ...] = field(default=())
    restart: bool = False
    allows: Callable[[Any], bool] | None = None

    def holds(self, value: Any) -> bool:
        """Say whether a value is one this preference is allowed to take.

        Parameters
        ----------
        value : object
            The value to check.

        Returns
        -------
        bool
            True when it is one of the ``choices`` — or there are none — and
            ``allows`` says so too.
        """

        if self.choices and value not in self.choices:
            return False
        return self.allows is None or self.allows(value)


def within(low: float, high: float) -> Callable[[Any], bool]:
    """Build the question *is this a length between these two?*

    It refuses what is **not a number** rather than comparing it, which is not
    pedantry: a hand-edited ``font_size=2,4`` is read by Qt as the list
    ``[2.0, 4.0]`` rather than refused, and a ``bool`` is an ``int`` in Python
    while being no kind of size.

    Parameters
    ----------
    low, high : float
        The smallest and the largest it may be, both allowed.

    Returns
    -------
    callable
        The question, to be given to :attr:`Preference.allows`.
    """

    def allowed(value: Any) -> bool:
        return (
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(value)
            and low <= value <= high
        )

    return allowed


#: How large a net's lettering is by default, in millimetres, measured as a word
#: processor measures it: the font's own em size, not the height of a line.  It
#: is the size at which today's captions come out the height they are now — the
#: 2.8 mm line they are laid out on, divided by what the font makes of an em —
#: so that nothing changes size until it is chosen to.  Agreed with Jaume, to be
#: revisited once a net has been printed.
DEFAULT_FONT_SIZE = 2.4

#: How thick a net's lines are drawn by default, in millimetres, which is
#: what every item and every arc was drawn with before there were styles.
DEFAULT_LINE_WIDTH = 0.3

#: How far apart the points a drawing snaps to are by default, in millimetres,
#: which is what everything on the sheet was snapped to before the distance
#: could be chosen.
DEFAULT_GRID_STEP = 1.0

#: The closest and the furthest apart those points may be put, in millimetres.
#: The limits are here rather than in the core because a grid is how a person
#: draws rather than anything a document holds: nothing written to a file is
#: held to them.  A tenth of a millimetre is as good as no snapping at all at
#: any zoom a sheet is read at, and two centimetres is twice the width of a
#: place.
MIN_GRID_STEP = 0.1
MAX_GRID_STEP = 20.0

#: The kinds of text a net holds, each of which has a typeface of its own.  A
#: guard and a time function do not exist yet; what they will be written in is
#: decided, and is stored from now so that it is there when they do.
PLACE = 'place'
TRANSITION = 'transition'
ARC = 'arc'
GUARD = 'guard'
TIME_FUNCTION = 'time_function'

#: Which preferences say the typeface of each kind of text, and ``None`` for the
#: one that is never anything but plain: an arc's weight takes the font, the size
#: and the colour of everything else and is never bold, italic or aligned, which
#: is the rule :class:`~simtwin_core.petri_net.ArcData` keeps as well.
TYPEFACES: dict[str, tuple[str, str] | None] = {
    PLACE: ('petri_net/place_bold', 'petri_net/place_italic'),
    TRANSITION: ('petri_net/transition_bold', 'petri_net/transition_italic'),
    GUARD: ('petri_net/guard_bold', 'petri_net/guard_italic'),
    TIME_FUNCTION: ('petri_net/time_function_bold', 'petri_net/time_function_italic'),
    ARC: None,
}

#: Every kind of text there are defaults for.
ROLES: tuple[str, ...] = tuple(TYPEFACES)

#: The time units a quantity may be shown in, smallest first.  The values are
#: the symbols, kept to ASCII so that the settings file needs no encoding of its
#: own; ``us`` stands for the microsecond, whose symbol is ``µs``.
TIME_UNITS: tuple[str, ...] = ('us', 'ms', 's', 'min', 'h', 'd')

#: The distance units a length may be shown in, smallest first.
DISTANCE_UNITS: tuple[str, ...] = ('mm', 'cm', 'm', 'dam', 'km')

#: The units an area may be shown in, smallest first.  ``ha`` is the hectare,
#: which is the one that is not a power of ten of the others' names.
SURFACE_UNITS: tuple[str, ...] = ('mm2', 'cm2', 'm2', 'dam2', 'ha', 'km2')

#: How often, in minutes, an open project may be saved automatically, and ``0``
#: for never.  The settings dialog pairs these with its entries by order.
AUTOSAVE_INTERVALS: tuple[int, ...] = (0, 1, 2, 5, 10, 15, 30)

#: The key of the autosave interval, which the window reads when a project opens
#: and whenever the settings dialog writes it.
AUTOSAVE_KEY = 'saving/autosave_interval'

#: The key of the distance between the points a drawing snaps to.
GRID_STEP_KEY = 'appearance/grid_step'

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
    Preference('appearance/page_size', SYSTEM_PAGE_SIZE, str),
    Preference(
        'appearance/page_orientation', paper.PORTRAIT, str, paper.ORIENTATIONS
    ),
    Preference(
        GRID_STEP_KEY,
        DEFAULT_GRID_STEP,
        float,
        allows=within(MIN_GRID_STEP, MAX_GRID_STEP),
    ),
    Preference('petri_net/font', SYSTEM_FONT, str),
    Preference(
        'petri_net/font_size',
        DEFAULT_FONT_SIZE,
        float,
        allows=within(MIN_FONT_SIZE, MAX_FONT_SIZE),
    ),
    Preference('petri_net/alignment', 'left', str, ALIGNMENTS),
    Preference('petri_net/text_colour', AUTOMATIC, str, allows=is_colour),
    Preference('petri_net/place_bold', False, bool),
    Preference('petri_net/place_italic', False, bool),
    Preference('petri_net/transition_bold', False, bool),
    Preference('petri_net/transition_italic', False, bool),
    Preference('petri_net/guard_bold', False, bool),
    Preference('petri_net/guard_italic', True, bool),
    Preference('petri_net/time_function_bold', False, bool),
    Preference('petri_net/time_function_italic', True, bool),
    Preference('petri_net/line_colour', AUTOMATIC, str, allows=is_colour),
    Preference(
        'petri_net/line_width',
        DEFAULT_LINE_WIDTH,
        float,
        allows=within(MIN_LINE_WIDTH, MAX_LINE_WIDTH),
    ),
    Preference('units/time', 's', str, TIME_UNITS),
    Preference('units/distance', 'm', str, DISTANCE_UNITS),
    Preference('units/surface', 'm2', str, SURFACE_UNITS),
    Preference(AUTOSAVE_KEY, 5, int, AUTOSAVE_INTERVALS),
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


def page(settings: Preferences | None = None) -> QSizeF:
    """Give the page a sheet is ruled into, in millimetres and already oriented.

    Two preferences and the machine's own answer come together here, so that
    everything wanting a page asks one question.  An unset size — the default —
    means the one this machine prints on, and a size stored that names nothing
    falls back the same way, because a settings file can be edited by hand.

    Parameters
    ----------
    settings : Preferences, optional
        Where to read them from.  The application's own are used when it is
        omitted.

    Returns
    -------
    PyQt6.QtCore.QSizeF
        The width and height of the page, in millimetres.
    """

    store = settings if settings is not None else Preferences()
    return paper.dimensions(
        store.value('appearance/page_size') or paper.default_key(),
        store.value('appearance/page_orientation'),
    )


def grid_step(settings: Preferences | None = None) -> float:
    """Give how far apart the points a drawing snaps to are, in millimetres.

    It is asked here rather than read as a key so that a sheet takes the grid
    the way it takes its page, through one function — and so that a value a
    hand-edited settings file put outside the limits has already fallen back to
    the default before anything is drawn with it.

    Parameters
    ----------
    settings : Preferences, optional
        Where to read it from.  The application's own are used when it is
        omitted.

    Returns
    -------
    float
        The distance, in millimetres, between one point a drawing may land on
        and the next.
    """

    store = settings if settings is not None else Preferences()
    return store.value(GRID_STEP_KEY)


#: The preferences that decide what :func:`page` gives back, so that a caller
#: watching for a change knows which keys to watch.
PAGE_KEYS: tuple[str, ...] = ('appearance/page_size', 'appearance/page_orientation')

#: The preferences that decide what :func:`grid_step` gives back, beside
#: :data:`PAGE_KEYS` and watched the same way.  A sheet is re-gridded where it
#: stands, so none of them waits for a restart either.
GRID_KEYS: tuple[str, ...] = (GRID_STEP_KEY,)

#: The preferences that say how a net is drawn, so that a caller watching for a
#: change — the window, which draws every open sheet again — knows which keys to
#: watch.  None of them waits for a restart: a setting whose effect can be seen
#: at once is a setting the user can judge.
APPEARANCE_KEYS: tuple[str, ...] = tuple(
    declaration.key
    for declaration in PREFERENCES
    if declaration.key.startswith('petri_net/')
)


def text_appearance(
    style: TextStyle | None,
    role: str = PLACE,
    settings: Preferences | None = None,
) -> TextStyle:
    """Give the style a piece of a net's text is actually written in.

    This is the one place the application's defaults and an item's own style
    come together, so that everything which draws asks one question and nothing
    has to know which half of the answer came from where.

    An item **with a style of its own** is written in it: the defaults are what
    an item without one follows, and nothing more.  The one thing that can still
    stand in the way is a **font this machine has not got** — a net drawn on
    another desk — and that is fallen back on silently, as agreed: the net opens
    and is legible rather than refusing or complaining at every repaint.

    Parameters
    ----------
    style : simtwin_core.petri_net.TextStyle, optional
        The item's own style, or ``None`` to follow the defaults.
    role : str, optional
        Which kind of text it is, one of :data:`ROLES`.  It decides the typeface
        alone; :data:`ARC` is never bold, italic or aligned, whatever is stored.
    settings : Preferences, optional
        Where to read the defaults from.  The application's own are used when it
        is omitted.

    Returns
    -------
    simtwin_core.petri_net.TextStyle
        A complete style, its font one this machine can letter in.

    Raises
    ------
    ValueError
        When the role is not one there are defaults for, which is a mistyped
        role rather than a kind of text with no typeface.
    """

    if role not in TYPEFACES:
        raise ValueError(f'{role!r} is not a kind of text there are defaults for: {ROLES}')

    if style is not None:
        if fonts.installed(style.font):
            return style
        return replace(style, font=fonts.default_family())

    store = settings if settings is not None else Preferences()
    font = store.value('petri_net/font')
    if not fonts.installed(font):
        font = fonts.default_family()

    typeface = TYPEFACES[role]
    if typeface is None:
        bold, italic, alignment = False, False, 'left'
    else:
        bold = store.value(typeface[0])
        italic = store.value(typeface[1])
        alignment = store.value('petri_net/alignment')

    return TextStyle(
        font,
        store.value('petri_net/font_size'),
        bold,
        italic,
        alignment,
        store.value('petri_net/text_colour'),
    )


def line_appearance(
    style: LineStyle | None, settings: Preferences | None = None
) -> LineStyle:
    """Give the style a piece of a net is actually drawn with.

    The line half of :func:`text_appearance`, and simpler: there is nothing in a
    line that the machine can fail to provide, so an item's own style is the
    whole answer whenever it has one.

    Parameters
    ----------
    style : simtwin_core.petri_net.LineStyle, optional
        The item's own style, or ``None`` to follow the defaults.
    settings : Preferences, optional
        Where to read the defaults from.  The application's own are used when it
        is omitted.

    Returns
    -------
    simtwin_core.petri_net.LineStyle
        A complete style.
    """

    if style is not None:
        return style

    store = settings if settings is not None else Preferences()
    return LineStyle(
        store.value('petri_net/line_colour'), store.value('petri_net/line_width')
    )


#: Where the identifier of this installation is kept.  It is not a
#: :class:`Preference`: nobody chooses it, it has no default worth naming and it
#: is never shown in the settings dialog.  It lives here because this is the
#: module that owns what the application remembers about this user on this
#: machine.
INSTALL_KEY = 'identity/install'


def install_id(settings: QSettings | None = None) -> str:
    """Give the identifier of this installation, making one the first time.

    It goes into a project's history, so that two projects edited on the same
    machine can be seen to have been.  It says nothing about who the user is —
    it is a random number generated locally and never sent anywhere — but it is
    written into every project made or opened here, which is worth knowing and
    worth saying out loud.

    Parameters
    ----------
    settings : PyQt6.QtCore.QSettings, optional
        Where to keep it.  The default is a plain ``QSettings()``.

    Returns
    -------
    str
        The identifier, the same one on every call.
    """

    store = settings if settings is not None else QSettings()
    stored = store.value(INSTALL_KEY, '', type=str)
    if not stored:
        stored = str(uuid.uuid4())
        store.setValue(INSTALL_KEY, stored)
    return stored


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
        try:
            stored = self._settings.value(
                declaration.key, declaration.default, type=declaration.type
            )
        except TypeError:
            # Hand-edited into something that is not of the type at all, such as
            # ``abc`` for a number, which Qt refuses to convert.
            return declaration.default
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
