"""A Petri net as it is drawn, with nothing of how it is shown.

This is what the Petri net editor hands over and is handed back: the places, the
transitions, the arcs and the guides of one model, with everything that decides
what the drawing looks like — positions, connecting points, shapes — and nothing
of Qt.  The editor turns its sheet into a :class:`NetDocument` and a
:class:`NetDocument` back into a sheet; an adapter turns one into a file, or into
a net of a backend library, and back.  Neither of them ever sees the other.

**Everything is plain.**  A position is ``(x, y)`` in millimetres on the sheet.  A
shape, a kind and an orientation are the text the editor's own enums carry as
their values — :data:`SHAPES`, :data:`KINDS`, :data:`ORIENTATIONS` — so this
module needs nothing from the editor, and a test on the editor's side holds that
the two name them alike.  Every class is **frozen** and holds tuples, so a
document is a value: two documents of the same drawing are equal, and nothing
that holds one can change what another sees.  A list given where a tuple belongs
is made a tuple.

**A document is a net that can be drawn, or it is not made.**  A
:class:`NetDocument` refuses, with :class:`InvalidNet`, to hold

* two things with the same UUID, or two nodes with the same name ignoring case — a
  place and a transition included, since a backend knows a node by its name;
* a node whose name is not an ASCII Python identifier, or is a keyword —
  :func:`name_problem` is the rule;
* an arc with an end that is not one of its nodes, or that joins a node to one of
  its own kind — a Petri net is bipartite;
* an arc of a kind running the wrong way — an inhibitor arc runs from a place to
  a transition, :data:`DIRECTIONS`;
* two arcs of one kind running the same way between the same two nodes.

Nor does a node hold tokens that are not a whole number of nought or more, or a
description of more than one line.  A place's **tokens** are its initial
marking, which a backend runs from; a node's **description** is a person's words
about it, which no backend ever sees; and a node's **label offset** is where the
box holding both has been moved to, or ``None`` for where the editor puts it; and
its **label width** how wide that box has been made, or ``None`` for the editor's
own width.

**Every place, transition and arc may have a style of its own** — a
:class:`TextStyle` for what is written beside it and a :class:`LineStyle` for
what is drawn — or ``None``, which follows the application's defaults.  A style
is complete or not there: the defaults are the application's, kept per machine,
and a document says only what an item was given of its own.  None of it is part
of the net, and no backend ever sees it.

**A document holds everything in one order**, whatever order it is given in:
nodes by name with numbers counted as numbers (:func:`reading_order`), arcs by
the names of their ends and their kind, guides by the way they lie and where.  So
two documents of one drawing are equal however each was put together.

These are the rules the editor keeps as a net is drawn.  Holding them here as
well means a file that breaks one is refused when it is read, rather than turned
into a drawing the editor could never have made.

**How an arc bends is kept the way the editor keeps it**, in the arc's own chord
frame — how far along the line between its two connecting points and how far
across it, as fractions of its length — so that it is independent of where the
nodes happen to be.  ``None`` for the controls or for the points means
*untouched*: the shape's own default, which is the editor's to know and is not
repeated here.  An S whose every point has been taken out is ``()``, not
``None``, and is drawn as a straight line.

Two more things are left to the editor, for files it did not write.  A
**connecting point** of ``None`` is the point facing the other end that no arc is
on yet, which only the editor, knowing where its points are, can work out.  And an
arc's **route** — where the points it is led through are on the sheet — is the
editor's to give and is never used to draw: it is there for readers that know
nothing of the chord frame, which is every other PNML tool.
"""

from __future__ import annotations

import keyword
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

#: A position on the sheet, or a place in an arc's chord frame.
Point = tuple[float, float]

#: The shapes an arc is drawn in, as the editor's ``ArcShape`` names them.
SHAPES: tuple[str, ...] = ('straight', 'curved', 's-curved', 'l-shaped')

#: The kinds of arc, as the editor's ``ArcKind`` names them.
KINDS: tuple[str, ...] = ('normal', 'inhibitor')

#: Which way a guide lies: across the sheet, or up it.
ORIENTATIONS: tuple[str, ...] = ('horizontal', 'vertical')

#: Which way round a kind of arc may run, as the kinds of node at its source and
#: at its target.  A kind not named here runs whichever way the net allows.
DIRECTIONS: dict[str, tuple[str, str]] = {
    'inhibitor': ('place', 'transition'),
}

#: How the lines of a box of text are laid against its sides.  ``justified``
#: stretches every line but the last, which is left-aligned as in any editor.
ALIGNMENTS: tuple[str, ...] = ('left', 'right', 'center', 'justified')

#: The colour that follows the theme: the sheet's own ink, dark on the light
#: scheme and light on the dark one.  Every other colour is ``#rrggbb`` and stays
#: what it is whichever scheme it is shown in.
AUTOMATIC = 'automatic'

#: How small and how large a font may be, in millimetres.
MIN_FONT_SIZE = 1.0
MAX_FONT_SIZE = 20.0

#: How thin and how thick a line may be drawn, in millimetres.
MIN_LINE_WIDTH = 0.1
MAX_LINE_WIDTH = 3.0


class InvalidNet(ValueError):
    """Raised when a document does not describe a net that can be drawn."""


class NameProblem(Enum):
    """Why a name cannot be given to a place or a transition.

    A code rather than a sentence: the words belong to the application, which
    has the translations.  The value is what the code is called in a message
    that is not translated, such as the one :class:`InvalidNet` carries.
    """

    #: No name at all.
    EMPTY = 'empty'
    #: A letter outside ASCII — ``Estació`` — which file systems and tools
    #: handle unevenly.
    NOT_ASCII = 'not-ascii'
    #: A digit first — ``1st`` — which no Python name may begin with.
    DIGIT_FIRST = 'digit-first'
    #: Anything else that is not a Python identifier — a space, a hyphen.
    NOT_IDENTIFIER = 'not-identifier'
    #: A Python keyword — ``class``, ``None`` — which looks like a name and
    #: cannot be one.
    KEYWORD = 'keyword'
    #: Another node's name, ignoring case.
    TAKEN = 'taken'


def name_problem(name: str, taken: Iterable[str] = ()) -> NameProblem | None:
    """Say why a name cannot be given to a place or a transition, if it cannot.

    The one place the rule for a node's name is written.  A name is an **ASCII
    Python identifier that is not a keyword**, because a net is to become Python
    — a name that already is one needs no mangling to be a module, a class or an
    attribute — and it is **unique in its net ignoring case**, because
    ``Buffer`` and ``buffer`` are one file on Windows and macOS.  Soft keywords
    such as ``match`` and the names of standard modules such as ``random`` are
    allowed: both are valid names for a module.

    Every name this allows is one MASAFI-sim-petri accepts, which asks only that
    a name is not blank and that no two places, or two transitions, share one.

    Parameters
    ----------
    name : str
        The name.
    taken : collections.abc.Iterable of str, optional
        The names of the **other** nodes of the net — not of the node being
        named, which may keep its own name or change its case.

    Returns
    -------
    NameProblem, optional
        The first rule the name breaks, in the order of :class:`NameProblem`, or
        ``None`` when it breaks none.
    """

    if not name:
        return NameProblem.EMPTY
    if not name.isascii():
        return NameProblem.NOT_ASCII
    if name[0].isdigit():
        return NameProblem.DIGIT_FIRST
    if not name.isidentifier():
        return NameProblem.NOT_IDENTIFIER
    if keyword.iskeyword(name):
        return NameProblem.KEYWORD
    folded = name.casefold()
    if any(other.casefold() == folded for other in taken):
        return NameProblem.TAKEN
    return None


def reading_order(name: str) -> list:
    """Give the key a name sorts by, numbers counted as numbers.

    ``P2`` comes before ``P10``, which is the order a person reads a net in, and
    the order a document holds its nodes in — so a file written twice from the
    same net comes out the same, and a change to a net is a small change to its
    file.

    Parameters
    ----------
    name : str
        The name.

    Returns
    -------
    list
        Its runs of letters and of digits, the digits as integers.  Splitting on
        the digits always alternates text and number, starting with text, so two
        keys compare element by element without mixing the two.
    """

    return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', name)]


def _point(value, what: str) -> Point:
    """Make a pair of numbers of anything that holds two.

    Parameters
    ----------
    value : collections.abc.Sequence
        The pair.
    what : str
        What it is, for the message when it is not a pair.

    Returns
    -------
    tuple of float
        The pair, as floats.

    Raises
    ------
    InvalidNet
        When it is not two numbers.
    """

    try:
        x, y = value
        return float(x), float(y)
    except (TypeError, ValueError) as error:
        raise InvalidNet(f'{what} is not a pair of numbers: {value!r}') from error


def _tokens(value, what: str) -> int:
    """Check how many tokens a place holds.

    Parameters
    ----------
    value : int
        The tokens.
    what : str
        What holds them, for the message when they are not tokens.

    Returns
    -------
    int
        The tokens, as given.

    Raises
    ------
    InvalidNet
        When they are not a whole number of nought or more.  A ``bool`` is not a
        number of tokens, though Python counts it as an ``int``.
    """

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidNet(f'{what} holds tokens that are not a whole number of nought or more: {value!r}')
    return value


def _description(value, what: str) -> str:
    """Check what a node is described as.

    Parameters
    ----------
    value : str
        The description.
    what : str
        What it describes, for the message when it is not a description.

    Returns
    -------
    str
        The description, as given.

    Raises
    ------
    InvalidNet
        When it is not text, or is more than one line — a description is drawn
        on the sheet beside its node, on one line.
    """

    if not isinstance(value, str):
        raise InvalidNet(f'the description of {what} is not text: {value!r}')
    if '\n' in value or '\r' in value:
        raise InvalidNet(f'the description of {what} is more than one line')
    return value


def _upright(value, what: str) -> bool:
    """Check which way round a transition is drawn.

    Parameters
    ----------
    value : bool
        Whether it stands up the sheet rather than lying across it.
    what : str
        What is drawn that way, for the message when the answer is not one.

    Returns
    -------
    bool
        The answer, as given.

    Raises
    ------
    InvalidNet
        When it is not ``True`` or ``False``.  A transition either stands up or
        lies across; there is no angle between the two, and a number is not an
        answer to the question.
    """

    if not isinstance(value, bool):
        raise InvalidNet(f'{what} is not drawn one way round or the other: {value!r}')
    return value


def _offset(value, what: str) -> Point | None:
    """Check where a node's caption has been put.

    Parameters
    ----------
    value : collections.abc.Sequence, optional
        The centre of the caption relative to the centre of the node, or
        ``None`` for where the editor puts it.
    what : str
        Whose caption it is, for the message when it is not a place.

    Returns
    -------
    tuple of float, optional
        The offset as a pair of floats, or ``None``.

    Raises
    ------
    InvalidNet
        When it is neither ``None`` nor two numbers.
    """

    return None if value is None else _point(value, f'the caption of {what}')


def _width(value, what: str) -> float | None:
    """Check how wide a node's caption has been made.

    Parameters
    ----------
    value : float, optional
        The width in millimetres, or ``None`` for the editor's own.
    what : str
        Whose caption it is, for the message when it is not a width.

    Returns
    -------
    float, optional
        The width as a float, or ``None``.

    Raises
    ------
    InvalidNet
        When it is neither ``None`` nor a finite number above nought.  A
        ``bool`` is not a width, though Python counts it as a number.
    """

    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise InvalidNet(f'the caption of {what} is not a width: {value!r}')
    return float(value)


def _flag(value, what: str) -> bool:
    """Check a yes-or-no answer.

    Parameters
    ----------
    value : bool
        The answer.
    what : str
        What it answers, for the message when it is not an answer.

    Returns
    -------
    bool
        The answer, as given.

    Raises
    ------
    InvalidNet
        When it is not ``True`` or ``False``.
    """

    if not isinstance(value, bool):
        raise InvalidNet(f'{what} is neither true nor false: {value!r}')
    return value


def _measure(value, low: float, high: float, what: str) -> float:
    """Check a length in millimetres against its limits.

    Parameters
    ----------
    value : float
        The length.
    low, high : float
        The shortest and the longest it may be, both allowed.
    what : str
        What it measures, for the message when it is not allowed.

    Returns
    -------
    float
        The length, as a float.

    Raises
    ------
    InvalidNet
        When it is not a finite number between the two, or is a ``bool``.
    """

    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise InvalidNet(f'{what} is not between {low:g} and {high:g} mm: {value!r}')
    return float(value)


def is_colour(value) -> bool:
    """Say whether something is a colour a style may be drawn in.

    The rule is written here, beside the styles that keep it, because the
    application's **defaults** keep it too: a colour held in the settings file
    and a colour held in a document are the same thing, and one rule in one
    place is what makes them so.

    Parameters
    ----------
    value : object
        What is offered as a colour.

    Returns
    -------
    bool
        True for :data:`AUTOMATIC` and for ``#rrggbb`` written either way round
        in case, false for anything else — a colour named in words included,
        there being no list of names here to look one up in.
    """

    if value == AUTOMATIC:
        return True
    return isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value) is not None


def _colour(value, what: str) -> str:
    """Check a colour.

    Parameters
    ----------
    value : str
        :data:`AUTOMATIC`, or ``#rrggbb``.
    what : str
        What is drawn in it, for the message when it is not a colour.

    Returns
    -------
    str
        The colour, a hexadecimal one in lower case, so that two spellings of
        one colour are one colour.

    Raises
    ------
    InvalidNet
        When it is neither.
    """

    if not is_colour(value):
        raise InvalidNet(f'{what} is not a colour: {value!r}')
    return value if value == AUTOMATIC else value.lower()


def _style(value, kind: type, what: str):
    """Check that an item's own style is one, or that it has none.

    Parameters
    ----------
    value : TextStyle or LineStyle, optional
        The style, or ``None`` for the application's defaults.
    kind : type
        :class:`TextStyle` or :class:`LineStyle`.
    what : str
        Whose style it is, for the message when it is not one.

    Returns
    -------
    TextStyle or LineStyle, optional
        The style, as given.

    Raises
    ------
    InvalidNet
        When it is something else.
    """

    if value is not None and not isinstance(value, kind):
        raise InvalidNet(f'the {kind.__name__} of {what} is not one: {value!r}')
    return value


def _points(values, what: str) -> tuple[Point, ...]:
    """Make a tuple of points of anything that holds some.

    Parameters
    ----------
    values : collections.abc.Iterable
        The points.
    what : str
        What they are, for the message when one is not a point.

    Returns
    -------
    tuple
        The points, as pairs of floats.
    """

    return tuple(_point(value, what) for value in values)


@dataclass(frozen=True)
class TextStyle:
    """How an item's text is written, when it is not written the default way.

    **Complete or not there at all.**  An item either follows the application's
    defaults — its style is ``None`` — or has a style of its own, and then every
    field is its own: unticking *Use app default text appearance* fills them in
    with the defaults of that moment, and ticking it again throws them away.

    Attributes
    ----------
    font : str
        The family, as a font is named on the machine that set it.  One this
        machine lacks is drawn in the default font, which is the application's
        business rather than a document's.
    size : float
        In millimetres, from :data:`MIN_FONT_SIZE` to :data:`MAX_FONT_SIZE`.
    bold, italic : bool
        The typeface, the two being combined as they are in any editor.
    alignment : str
        One of :data:`ALIGNMENTS`.
    colour : str
        :data:`AUTOMATIC`, or ``#rrggbb``.

    Raises
    ------
    InvalidNet
        When any of them is not what it says.
    """

    font: str
    size: float
    bold: bool = False
    italic: bool = False
    alignment: str = 'left'
    colour: str = AUTOMATIC

    def __post_init__(self) -> None:
        if not isinstance(self.font, str) or not self.font.strip():
            raise InvalidNet(f'a text style names no font: {self.font!r}')
        object.__setattr__(
            self, 'size', _measure(self.size, MIN_FONT_SIZE, MAX_FONT_SIZE, 'a font size')
        )
        object.__setattr__(self, 'bold', _flag(self.bold, 'bold'))
        object.__setattr__(self, 'italic', _flag(self.italic, 'italic'))
        if self.alignment not in ALIGNMENTS:
            raise InvalidNet(f'text is aligned no way there is: {self.alignment!r}')
        object.__setattr__(self, 'colour', _colour(self.colour, 'text'))

    @property
    def normal(self) -> bool:
        """bool: Whether it is upright, unemphasised and left-aligned — the one
        way an arc's weight is ever written."""

        return not self.bold and not self.italic and self.alignment == 'left'


@dataclass(frozen=True)
class LineStyle:
    """How an item's lines are drawn, when they are not drawn the default way.

    Complete or not there at all, as a :class:`TextStyle` is.

    Attributes
    ----------
    colour : str
        :data:`AUTOMATIC`, or ``#rrggbb``: a place's outline and its tokens, a
        transition's bar, an arc's line and the mark it ends in.
    width : float
        In millimetres, from :data:`MIN_LINE_WIDTH` to :data:`MAX_LINE_WIDTH`.
        What a selected item is drawn with is this and a fixed amount more.

    Raises
    ------
    InvalidNet
        When either is not what it says.
    """

    colour: str
    width: float

    def __post_init__(self) -> None:
        object.__setattr__(self, 'colour', _colour(self.colour, 'a line'))
        object.__setattr__(
            self, 'width', _measure(self.width, MIN_LINE_WIDTH, MAX_LINE_WIDTH, 'a line width')
        )


@dataclass(frozen=True)
class PlaceData:
    """One place.

    Attributes
    ----------
    uuid : str
        What an arc names it by.
    name : str
        What the net calls it.
    position : tuple of float
        Its centre, in millimetres on the sheet.
    tokens : int
        How many tokens it holds before the net is run — its initial marking.
        Nought or more.
    description : str
        What it is for, in a person's words, on one line.  Not part of the net:
        a backend never sees it.
    label_offset : tuple of float, optional
        Where the box holding its name and description has been moved to: the
        centre of the box relative to the centre of the place, in millimetres.
        ``None`` for a box nobody has moved, which goes where the editor puts
        it — under the place, however tall the text makes it.
    label_width : float, optional
        How wide that box has been made, in millimetres: the text wraps to it
        and the box is drawn that wide.  ``None`` for a box nobody has resized,
        which wraps to the editor's own width and fits its text.
    text_style : TextStyle, optional
        How its name and description are written, or ``None`` for the
        application's defaults.
    line_style : LineStyle, optional
        How its outline and its tokens are drawn, or ``None`` for the defaults.

    Raises
    ------
    InvalidNet
        When the tokens are not a whole number of nought or more, the
        description is not one line of text, the offset is not a pair, or the
        width is not a number above nought.
    """

    uuid: str
    name: str
    position: Point
    tokens: int = 0
    description: str = ''
    label_offset: Point | None = None
    label_width: float | None = None
    text_style: TextStyle | None = None
    line_style: LineStyle | None = None

    def __post_init__(self) -> None:
        what = f'place {self.name!r}'
        object.__setattr__(self, 'position', _point(self.position, what))
        object.__setattr__(self, 'tokens', _tokens(self.tokens, what))
        object.__setattr__(self, 'description', _description(self.description, what))
        object.__setattr__(self, 'label_offset', _offset(self.label_offset, what))
        object.__setattr__(self, 'label_width', _width(self.label_width, what))
        _style(self.text_style, TextStyle, what)
        _style(self.line_style, LineStyle, what)


@dataclass(frozen=True)
class TransitionData:
    """One transition.

    Attributes
    ----------
    uuid : str
        What an arc names it by.
    name : str
        What the net calls it.
    position : tuple of float
        Its centre, in millimetres on the sheet.
    description : str
        What it is for, in a person's words, on one line.  Not part of the net.
    vertical : bool
        Whether the bar **stands up** the sheet rather than lying across it,
        which is how a net laid out from top to bottom is drawn.  How it is
        drawn and nothing more: a transition is the same transition either way
        round, and no backend is told which.
    label_offset : tuple of float, optional
        Where the box holding its name and description has been moved to,
        relative to the centre of the transition, in millimetres; ``None`` for
        where the editor puts it.  A box that has been moved stays where it was
        put when the bar is turned.
    label_width : float, optional
        How wide that box has been made, in millimetres, or ``None`` for the
        editor's own width.
    text_style : TextStyle, optional
        How its name and description are written, or ``None`` for the
        application's defaults.
    line_style : LineStyle, optional
        How its bar is drawn, or ``None`` for the defaults.

    Raises
    ------
    InvalidNet
        When the description is not one line of text, the bar is neither
        upright nor lying across, the offset is not a pair, or the width is not
        a number above nought.
    """

    uuid: str
    name: str
    position: Point
    description: str = ''
    vertical: bool = False
    label_offset: Point | None = None
    label_width: float | None = None
    text_style: TextStyle | None = None
    line_style: LineStyle | None = None

    def __post_init__(self) -> None:
        what = f'transition {self.name!r}'
        object.__setattr__(self, 'position', _point(self.position, what))
        object.__setattr__(self, 'description', _description(self.description, what))
        object.__setattr__(self, 'vertical', _upright(self.vertical, what))
        object.__setattr__(self, 'label_offset', _offset(self.label_offset, what))
        object.__setattr__(self, 'label_width', _width(self.label_width, what))
        _style(self.text_style, TextStyle, what)
        _style(self.line_style, LineStyle, what)


@dataclass(frozen=True)
class ArcData:
    """One arc, and how it is drawn.

    Attributes
    ----------
    uuid : str
        The arc's own identity.
    source, target : str
        The UUIDs of the node it leaves and of the node it enters.
    source_port, target_port : int, optional
        Which connecting point of each it is attached to, by index, or ``None``
        for the point facing the other end that no arc is on yet — what a file
        from another tool, which knows nothing of connecting points, gives.
    weight : int
        How many tokens it carries, one at least.
    kind : str
        One of :data:`KINDS`.
    shape : str
        One of :data:`SHAPES`.
    controls : tuple, optional
        The two control points of a single bow, in the chord's frame, or
        ``None`` for the shape's default.
    points : tuple, optional
        The points an S or an L is led through, in the chord's frame and in
        order from the source, or ``None`` for the shape's default.  Kept
        whatever the shape, as the editor keeps them, so that an arc made
        straight and made an S again is the S it was.
    route : tuple
        Where the points an S or an L is led through are on the sheet, in
        millimetres and in order from the source.  Written for readers that
        know nothing of the chord frame, and never used to draw — the editor
        draws from ``points``.  Empty for a straight arc and a single bow, which
        are led through nothing.

        It is **worked out rather than kept**: it says again, in another frame,
        what ``points`` already says, and only something that knows where the
        connecting points are — the editor — can work it out.  So it takes no
        part in comparing two arcs, and no operation and no journal line carries
        it: two descriptions of one drawing are equal whether or not the route
        has been filled in.
    weight_offset : tuple of float, optional
        Where the box holding the weight has been moved to, in the arc's chord
        frame — how far along and how far across, as fractions of the chord, the
        way the bends are kept — so that a moved number turns and scales with
        the arc.  ``None`` for a box nobody has moved, which sits beside the
        middle of the line.  Kept whatever the weight, so a number moved, set to
        one and set to three again comes back where it was.
    inscription_offset : tuple of float, optional
        Where the weight's box is drawn relative to the middle of the drawn
        arc, in millimetres, which is what PNML's ``inscription`` offset says.
        Like the ``route``, **worked out rather than kept**: written for other
        tools, never used to draw, and no part of comparing two arcs.  ``None``
        when no weight is drawn.
    text_style : TextStyle, optional
        How the weight is written, or ``None`` for the application's defaults.
        Its font, size and colour are the arc's own; it is always
        :attr:`TextStyle.normal`, a weight never being bold, italic or aligned.
    line_style : LineStyle, optional
        How the line and the mark it ends in are drawn, or ``None`` for the
        defaults.

    Raises
    ------
    InvalidNet
        When the kind or the shape is not one of those there are, the weight
        is below one, a connecting point is negative, or the controls are not
        two points.
    """

    uuid: str
    source: str
    target: str
    source_port: int | None
    target_port: int | None
    weight: int = 1
    kind: str = 'normal'
    shape: str = 'straight'
    controls: tuple[Point, Point] | None = None
    points: tuple[Point, ...] | None = None
    route: tuple[Point, ...] = field(default=(), compare=False)
    weight_offset: Point | None = None
    inscription_offset: Point | None = field(default=None, compare=False)
    text_style: TextStyle | None = None
    line_style: LineStyle | None = None

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise InvalidNet(f'arc {self.uuid!r} is of no kind there is: {self.kind!r}')
        if self.shape not in SHAPES:
            raise InvalidNet(f'arc {self.uuid!r} has no shape there is: {self.shape!r}')
        if self.weight < 1:
            raise InvalidNet(f'arc {self.uuid!r} carries a weight below one: {self.weight}')
        if any(port is not None and port < 0 for port in (self.source_port, self.target_port)):
            raise InvalidNet(f'arc {self.uuid!r} is attached to a negative connecting point')
        if self.controls is not None:
            controls = _points(self.controls, f'a control of arc {self.uuid!r}')
            if len(controls) != 2:
                raise InvalidNet(f'arc {self.uuid!r} has {len(controls)} controls, not two')
            object.__setattr__(self, 'controls', controls)
        if self.points is not None:
            object.__setattr__(
                self, 'points', _points(self.points, f'a point of arc {self.uuid!r}')
            )
        object.__setattr__(self, 'route', _points(self.route, f'the route of arc {self.uuid!r}'))
        what = f'arc {self.uuid!r}'
        object.__setattr__(self, 'weight_offset', _offset(self.weight_offset, what))
        object.__setattr__(self, 'inscription_offset', _offset(self.inscription_offset, what))
        _style(self.text_style, TextStyle, what)
        _style(self.line_style, LineStyle, what)
        if self.text_style is not None and not self.text_style.normal:
            raise InvalidNet(
                f'the weight of {what} is written normal and left-aligned, '
                'never bold, italic or aligned otherwise'
            )


@dataclass(frozen=True)
class GuideData:
    """One guide, the line a drawing is lined up against.

    Attributes
    ----------
    orientation : str
        One of :data:`ORIENTATIONS`.
    position : float
        Where it crosses its ruler, in millimetres.
    """

    orientation: str
    position: float

    def __post_init__(self) -> None:
        if self.orientation not in ORIENTATIONS:
            raise InvalidNet(f'a guide lies no way there is: {self.orientation!r}')
        object.__setattr__(self, 'position', float(self.position))


@dataclass(frozen=True)
class NetDocument:
    """One Petri net as it is drawn.

    Attributes
    ----------
    model_uuid : str
        The UUID of the model the net is, which is its identity in the project.
    places : tuple of PlaceData
        The places, by name in :func:`reading_order` whatever order they were
        given in.
    transitions : tuple of TransitionData
        The transitions, likewise.
    arcs : tuple of ArcData
        The arcs, by the names of their source and their target, then by kind.
    guides : tuple of GuideData
        The guides across the sheet, those lying across it first and then by
        where they are.  Not part of the net, but part of the drawing of it.

    Raises
    ------
    InvalidNet
        When the net breaks one of the rules a net that can be drawn keeps —
        see the description of :mod:`simtwin_core.petri_net`.
    """

    model_uuid: str = ''
    places: tuple[PlaceData, ...] = ()
    transitions: tuple[TransitionData, ...] = ()
    arcs: tuple[ArcData, ...] = ()
    guides: tuple[GuideData, ...] = ()

    def __post_init__(self) -> None:
        for field in ('places', 'transitions', 'arcs', 'guides'):
            object.__setattr__(self, field, tuple(getattr(self, field)))
        self._check()
        self._order()

    def _order(self) -> None:
        """Hold everything in the one order a net is read in.

        A document is then the same value however it was put together — by an
        editor reading its scene in stacking order, by an operation leaving a
        renamed node where it was, by a journal replayed onto a file — and a net
        written twice is the same file, which is what tells a model that has not
        changed from one that has.  Called after the rules are checked, so every
        arc's ends are known to be there and no two names are equal.
        """

        places = tuple(sorted(self.places, key=lambda node: reading_order(node.name)))
        transitions = tuple(sorted(self.transitions, key=lambda node: reading_order(node.name)))
        names = {node.uuid: node.name for node in (*places, *transitions)}
        arcs = tuple(
            sorted(
                self.arcs,
                key=lambda arc: (
                    reading_order(names[arc.source]),
                    reading_order(names[arc.target]),
                    arc.kind,
                ),
            )
        )
        guides = tuple(sorted(self.guides, key=lambda guide: (guide.orientation, guide.position)))
        for field, ordered in (
            ('places', places),
            ('transitions', transitions),
            ('arcs', arcs),
            ('guides', guides),
        ):
            object.__setattr__(self, field, ordered)

    def node(self, uuid: str) -> PlaceData | TransitionData | None:
        """Find a place or a transition by its UUID.

        Parameters
        ----------
        uuid : str
            What to look for.

        Returns
        -------
        PlaceData or TransitionData, optional
            The node, or ``None`` when the net holds none by that UUID.
        """

        for node in (*self.places, *self.transitions):
            if node.uuid == uuid:
                return node
        return None

    @property
    def names(self) -> tuple[str, ...]:
        """tuple of str: The names of the places, then of the transitions."""

        return tuple(node.name for node in (*self.places, *self.transitions))

    def _check(self) -> None:
        """Refuse a net that could not have been drawn.

        Raises
        ------
        InvalidNet
            At the first rule broken.
        """

        nodes: dict[str, str] = {}
        for group, members in (('place', self.places), ('transition', self.transitions)):
            for node in members:
                if node.uuid in nodes:
                    raise InvalidNet(f'two nodes share the UUID {node.uuid!r}')
                nodes[node.uuid] = group

        for name in self.names:
            problem = name_problem(name)
            if problem is not None:
                raise InvalidNet(f'{name!r} is not a name a node may have: {problem.value}')
        folded = [name.casefold() for name in self.names]
        repeated = sorted({name for name in self.names if folded.count(name.casefold()) > 1})
        if repeated:
            raise InvalidNet(f'two nodes share the name {repeated[0]!r}, ignoring case')

        seen_uuids = set(nodes)
        seen_arcs: set[tuple[str, str, str]] = set()
        for arc in self.arcs:
            if arc.uuid in seen_uuids:
                raise InvalidNet(f'the UUID {arc.uuid!r} is used twice')
            seen_uuids.add(arc.uuid)

            source, target = nodes.get(arc.source), nodes.get(arc.target)
            if source is None or target is None:
                raise InvalidNet(f'arc {arc.uuid!r} has an end that is not in the net')
            if source == target:
                raise InvalidNet(f'arc {arc.uuid!r} joins a {source} to a {target}')
            wanted = DIRECTIONS.get(arc.kind)
            if wanted is not None and (source, target) != wanted:
                raise InvalidNet(
                    f'arc {arc.uuid!r} is {arc.kind} and runs from a {source} to a {target}'
                )

            key = (arc.source, arc.target, arc.kind)
            if key in seen_arcs:
                raise InvalidNet(
                    f'two {arc.kind} arcs run the same way between the same two nodes'
                )
            seen_arcs.add(key)
