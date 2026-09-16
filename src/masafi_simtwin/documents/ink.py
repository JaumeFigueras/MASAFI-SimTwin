"""The colours and the lettering things on the sheet are drawn with.

A scene is **painted** rather than styled, so everything drawn on the sheet takes
its colours from the *palette* — one rule that reads on both schemes — and its
lettering from a **path** rather than from a font drawn with a pen: the scene is
measured in millimetres and a font is measured in points, so a path scaled to a
size in millimetres is the same size on the paper at every zoom and on every
machine.

**A block of text is lettered in a style**, which is a
:class:`~simtwin_core.petri_net.TextStyle` already resolved — the family, the
size of its em in millimetres, the typeface, the alignment and the colour, with
nothing left to look up.  Resolving one is
:func:`masafi_simtwin.preferences.text_appearance`, and it is the *owner* of a
caption that does it: this module is what a painter needs and nothing else, so
it reads no preferences of its own.

There are two kinds of lettering, and the difference matters.
:func:`glyph_path` scales one piece of text so that **its own ink** is the height
asked for, which is what a single number wants — an arc's weight, a place's
tokens — and exactly what a block of several lines must not have, since a line
with a ``g`` in it would then come out smaller than a line without one.
:func:`text_block` scales the **font's own line height**, once, for the whole
block, and wraps it to a width.

**The size is the font's em, as a word processor measures it**, and the line it
makes is the font's own business: :func:`line_height` is what a line of a style
comes to, and two families at one size letter lines of different heights.

**Both are filled by the winding rule.**  A path is filled odd-even unless it is
told otherwise, and many fonts — Cantarell, the GNOME default, among them — draw
a letter out of contours that overlap: the crossbar of a ``t``, the dot of an
``i``, the loops of ``g`` and ``&``.  Filled odd-even, every overlap is a hole,
which on the sheet is a hairline dash through the text.  DejaVu Sans, the
offscreen platform's font, does not overlap, which is why the tests that hold
this letter in Cantarell.

Nothing here is an item or knows about one: this is what a painter needs, and it
is in a module of its own so that the things that paint — the items, the arcs and
:class:`~masafi_simtwin.documents.label.Label` — can all reach it without
reaching for one another.
"""

from __future__ import annotations

from PyQt6.QtCore import QSizeF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainterPath,
    QPalette,
    QTransform,
)

from simtwin_core.petri_net import AUTOMATIC

#: How many units of a font one em is measured in while a block is laid out.
#: A font is asked for at this pixel size and the whole layout is scaled from it,
#: so the numbers a font gives back are integers big enough that rounding them
#: costs nothing: a size in millimetres is a fraction of a pixel at any size a
#: person would letter a net in.
FONT_UNITS = 1000

#: How wide a label may grow, in millimetres, before it goes onto another line.
#: Three places across: wide enough for a few words, narrow enough that a box
#: belongs to the item under it rather than floating between two.
LABEL_WIDTH = 30.0

#: How big a handle is drawn, in millimetres of side.  A square, so that a
#: handle is never mistaken for a connecting point, which is a ring; and as
#: small as a connecting point is, because both are marks put on the drawing to
#: be aimed at rather than parts of the drawing itself.  Here rather than with
#: the arcs because a caption carries handles too.
HANDLE_SIZE = 0.7

#: How far from a handle, in millimetres, the pointer may be and still take hold
#: of it.  Well beyond the square it is drawn as: a handle is aimed at, and a
#: handle that has to be hit exactly is a handle nobody can use.  Drawing it
#: smaller is a change to the picture and not to the aiming, which is why the
#: two are separate numbers.
HANDLE_GRAB = 1.3


def font_of(style) -> QFont:
    """Build the font a style is lettered in.

    Parameters
    ----------
    style : simtwin_core.petri_net.TextStyle
        The style, already resolved: its family is one this machine has.

    Returns
    -------
    PyQt6.QtGui.QFont
        The font, at :data:`FONT_UNITS` to the em, so that everything measured
        from it is scaled by one number.
    """

    font = QFont(style.font)
    font.setPixelSize(FONT_UNITS)
    font.setBold(style.bold)
    font.setItalic(style.italic)
    return font


def line_height(style) -> float:
    """Give how tall one line of a style is, in millimetres.

    The **size** of a style is the font's em, which is how a size is chosen
    everywhere else in the world; how tall a *line* of it is — ascender to
    descender, with the leading between two lines — is the font's own business,
    so two families at one size letter lines of different heights.

    Parameters
    ----------
    style : simtwin_core.petri_net.TextStyle
        The style.

    Returns
    -------
    float
        Millimetres.
    """

    return QFontMetricsF(font_of(style)).height() * style.size / FONT_UNITS


def label_lines(text: str, width: float, metrics: QFontMetricsF, scale: float) -> list[str]:
    """Break a piece of text into the lines a box that wide holds.

    Greedy and by words, which is what a person reading a label expects.  A
    **word wider than the whole box** is broken where it stops fitting rather
    than left to hang off the side: the box is measured from the item it belongs
    to, and one that grows without limit would run across the next item along.

    Parameters
    ----------
    text : str
        The text.  Runs of whitespace part the words and are not kept.
    width : float
        How wide the box may be, in millimetres.
    metrics : PyQt6.QtGui.QFontMetricsF
        The font it is laid out in.
    scale : float
        How many millimetres one unit of that font is.

    Returns
    -------
    list of str
        The lines, none of them empty, and none wider than the box but for a
        single character that is.
    """

    room = width / scale

    def fits(line: str) -> bool:
        return metrics.horizontalAdvance(line) <= room

    lines: list[str] = []
    for word in text.split():
        while not fits(word):
            broken = 1
            while broken < len(word) and fits(word[: broken + 1]):
                broken += 1
            if lines and fits(f'{lines[-1]} {word[:broken]}'):
                lines[-1] = f'{lines[-1]} {word[:broken]}'
            else:
                lines.append(word[:broken])
            word = word[broken:]
        if not word:
            continue
        if lines and fits(f'{lines[-1]} {word}'):
            lines[-1] = f'{lines[-1]} {word}'
        else:
            lines.append(word)
    return lines


def _justified(
    glyphs: QPainterPath, line: str, baseline: float, room: float, font, metrics
) -> None:
    """Write one line with its words spread to both sides of the box.

    Parameters
    ----------
    glyphs : PyQt6.QtGui.QPainterPath
        What to add the line to.
    line : str
        The line, whose words are parted by single spaces.
    baseline : float
        Where the line sits, in font units.
    room : float
        How wide the box is, in font units.
    font : PyQt6.QtGui.QFont
        The font.
    metrics : PyQt6.QtGui.QFontMetricsF
        Its metrics.
    """

    words = line.split(' ')
    space = metrics.horizontalAdvance(' ')
    written = sum(metrics.horizontalAdvance(word) for word in words)
    slack = (room - written - space * (len(words) - 1)) / (len(words) - 1)
    along = 0.0
    for word in words:
        glyphs.addText(along, baseline, font, word)
        along += metrics.horizontalAdvance(word) + space + slack


def _laid(line: str, alignment: str, room: float, metrics) -> float:
    """Say where a line starts, by the way the block is laid against its sides.

    Parameters
    ----------
    line : str
        The line.
    alignment : str
        One of :data:`~simtwin_core.petri_net.ALIGNMENTS`.
    room : float
        How wide the box is, in font units.
    metrics : PyQt6.QtGui.QFontMetricsF
        The font's metrics.

    Returns
    -------
    float
        Where the line starts, in font units.
    """

    slack = room - metrics.horizontalAdvance(line)
    if alignment == 'right':
        return slack
    if alignment == 'center':
        return slack / 2.0
    return 0.0


def text_block(text: str, width: float, style, fit: bool = True):
    """Lay a piece of text out as a path of however many lines it needs.

    A block of text is not :func:`glyph_path`: that scales one piece of text so
    that **its own ink** is a height, which is what a single number wants and
    exactly what a block of several lines must not have — a line with a ``g`` in
    it would come out smaller than a line without one.  Here the font's own line
    height is what is scaled, once, for the whole block, so every line is the
    same size and one line below the last.

    The path is centred on the middle of the **box** rather than of the ink, so
    where a label sits does not depend on which letters are in it.

    **Justified stretches every line but the last**, which is laid against the
    left — as it is in any editor, a last line spread across the box being what
    nobody wants.  A line of one word cannot be stretched and is left where it
    starts.

    Parameters
    ----------
    text : str
        What to write.
    width : float
        How wide it may be, in millimetres, before it goes onto another line.
    style : simtwin_core.petri_net.TextStyle
        What to write it in: the family, the size of the em in millimetres, the
        typeface and the alignment.  Already resolved, so nothing here reads a
        preference.
    fit : bool, optional
        Whether the box is as wide as its widest line, which is what a box
        nobody has resized is, or as wide as ``width`` — what a box a person has
        given a width is, so that the box they drew is the box they get.  A
        single character wider than the width widens it either way.

    Returns
    -------
    tuple
        The glyphs as a :class:`~PyQt6.QtGui.QPainterPath` centred on nought,
        and the size of the box they were laid out in as a
        :class:`~PyQt6.QtCore.QSizeF`.  Both are empty for text that writes
        nothing.
    """

    font = font_of(style)
    metrics = QFontMetricsF(font)
    if metrics.height() <= 0.0:  # pragma: no cover - a font always has a height
        return QPainterPath(), QSizeF(0.0, 0.0)

    scale = style.size / FONT_UNITS
    tall = metrics.height() * scale
    lines = label_lines(text, width, metrics, scale)
    if not lines:
        return QPainterPath(), QSizeF(0.0, 0.0)

    widest = max(metrics.horizontalAdvance(line) for line in lines) * scale
    box = QSizeF(widest if fit else max(width, widest), len(lines) * tall)
    room = box.width() / scale

    glyphs = QPainterPath()
    for row, line in enumerate(lines):
        baseline = metrics.ascent() + row * metrics.height()
        last = row == len(lines) - 1
        if style.alignment == 'justified' and not last and ' ' in line:
            _justified(glyphs, line, baseline, room, font, metrics)
            continue
        alignment = 'left' if style.alignment == 'justified' else style.alignment
        glyphs.addText(_laid(line, alignment, room, metrics), baseline, font, line)
    glyphs = QTransform().scale(scale, scale).map(glyphs)
    glyphs.translate(-box.width() / 2.0, -box.height() / 2.0)
    glyphs.setFillRule(Qt.FillRule.WindingFill)
    return glyphs, box


def glyph_path(
    text: str, height: float, width: float | None = None, family: str = ''
) -> QPainterPath:
    """Build a piece of text as a path a height in millimetres, centred on nought.

    What is written on the sheet — an arc's weight, a place's tokens — is a
    **path** rather than text drawn with a font, because the scene is measured in
    millimetres and a font in points: a path is scaled to a height on the paper,
    so it is the same size at every zoom and on every machine, and it is filled
    with the same brush as the thing it belongs to.

    Parameters
    ----------
    text : str
        What to write.
    height : float
        How tall it is to be, in millimetres.
    width : float, optional
        How wide it may be.  Text that would be wider at that height is
        narrowed to it instead, keeping its proportions.
    family : str, optional
        What to letter it in.  A place's tokens take the family its caption is
        written in — at a size and a typeface of the number's own, a count
        inside a circle not being a caption — and nothing else is asked of the
        style.  The application's own font is used when it is left out.

    Returns
    -------
    PyQt6.QtGui.QPainterPath
        The glyphs, their bounding box centred on the origin, or an empty path
        for text that draws nothing.
    """

    glyphs = QPainterPath()
    glyphs.addText(0.0, 0.0, QFont(family) if family else QFont(), text)
    drawn = glyphs.boundingRect()
    if drawn.isEmpty():
        return QPainterPath()

    glyphs.translate(-drawn.center().x(), -drawn.center().y())
    scale = height / drawn.height()
    if width is not None and drawn.width() * scale > width:
        scale = width / drawn.width()
    lettering = QTransform().scale(scale, scale).map(glyphs)
    lettering.setFillRule(Qt.FillRule.WindingFill)
    return lettering


def ink_colour(selected: bool, option, colour: str = AUTOMATIC) -> QColor:
    """Give the colour a thing of the net is drawn in.

    ``Text`` is the ink of the sheet and ``Link`` is the accent — where
    :data:`~masafi_simtwin.theme.ThemeColors.accent` is kept, ``Highlight`` being
    the pale wash behind selected text — so a selected thing is drawn in the
    accent.  It is one rule for the items and the arcs alike, which is why it is
    a function here rather than a method of either.

    **A selected thing keeps the accent whatever colour it was given**, which was
    decided with Jaume: the selection has to be visible, and a thing drawn in its
    own red while selected would say nothing about being in hand.

    Parameters
    ----------
    selected : bool
        Whether the thing is selected.
    option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
        What the view knows about drawing it, its palette included.  An item has
        no widget to take a palette from, so this is where the palette comes
        from.
    colour : str, optional
        :data:`~simtwin_core.petri_net.AUTOMATIC`, which follows the theme, or
        the ``#rrggbb`` the thing was given.

    Returns
    -------
    PyQt6.QtGui.QColor
        The colour.
    """

    if selected:
        return option.palette.color(QPalette.ColorRole.Link)
    if colour != AUTOMATIC:
        return QColor(colour)
    return option.palette.color(QPalette.ColorRole.Text)


def paper_colour(option) -> QColor:
    """Give the colour of the sheet a thing of the net is drawn on.

    ``Base`` is what :meth:`CanvasView.drawBackground` fills the sheet with, so
    this is what a thing is filled with to read as a hole in whatever it is
    over — a connecting point on a transition, a handle on a curve — and what a
    place is filled with to be the colour of the paper it sits on.

    Parameters
    ----------
    option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
        What the view knows about drawing it, its palette included.

    Returns
    -------
    PyQt6.QtGui.QColor
        The colour.
    """

    return option.palette.color(QPalette.ColorRole.Base)
