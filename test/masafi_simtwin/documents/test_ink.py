"""Tests for the colours and the lettering things on the sheet are drawn with.

Two kinds of lettering, and the difference between them is the point:
``glyph_path`` scales one piece of text so that its own ink is a height, and
``text_block`` lays a whole block out in a **style** — a family, a size in
millimetres, a typeface and an alignment — and wraps it to a width.
"""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPainterPath
from PyQt6.QtWidgets import QApplication, QStyleOptionGraphicsItem

from masafi_simtwin import fonts
from masafi_simtwin.documents.ink import (
    LABEL_WIDTH,
    font_of,
    glyph_path,
    ink_colour,
    line_height,
    text_block,
)
from masafi_simtwin.theme import DARK_COLORS, LIGHT_COLORS, build_palette
from simtwin_core.petri_net import AUTOMATIC, TextStyle

#: Letters whose strokes overlap in fonts drawn with overlapping contours —
#: Cantarell, the GNOME default, among them: the crossbar of a ``t``, the dot of
#: an ``i``, the loops of ``g``, ``@``, ``&`` and ``%``.
OVERLAPPING = 'tig@&%'

#: A caption that fits on one line of a box of :data:`ROOMY`, so that where it
#: is laid against the sides can be read off the ink.
ONE_LINE = 'P1: bottles'

#: A caption long enough to go onto a second line in a box of :data:`ROOMY`,
#: which is what justifying needs: it is every line **but the last** that is
#: stretched, so a block of one line would show nothing at all.
TWO_LINES = (
    'P1: bottles waiting to be filled, capped and taken away by the conveyor'
)

#: A box wide enough that no line of :data:`TWO_LINES` fills it, so that where
#: each line is laid against the sides can be read off the ink.
ROOMY = 60.0


@pytest.fixture
def style():
    """Give the style a net is lettered in by default.

    Returns
    -------
    simtwin_core.petri_net.TextStyle
        A complete style in a family this machine has.
    """

    return TextStyle(fonts.default_family(), 2.4)


def aligned(style, alignment: str) -> TextStyle:
    """Give the same style laid against the sides another way.

    Parameters
    ----------
    style : simtwin_core.petri_net.TextStyle
        The style.
    alignment : str
        One of the core's alignments.

    Returns
    -------
    simtwin_core.petri_net.TextStyle
        The style, aligned that way.
    """

    return TextStyle(style.font, style.size, style.bold, style.italic, alignment)


def palette_option(colors):
    """Give what a painter is told about a scheme.

    Parameters
    ----------
    colors : masafi_simtwin.theme.ThemeColors
        The scheme.

    Returns
    -------
    PyQt6.QtWidgets.QStyleOptionGraphicsItem
        The option, carrying that scheme's palette.
    """

    option = QStyleOptionGraphicsItem()
    option.palette = build_palette(colors)
    return option


def inked(path: QPainterPath, zoom: float = 40.0) -> bytes:
    """Fill a path close up, with no antialiasing, and give the pixels.

    Parameters
    ----------
    path : PyQt6.QtGui.QPainterPath
        What to fill, in millimetres.
    zoom : float, optional
        Pixels to the millimetre.

    Returns
    -------
    bytes
        The image, so that two fillings can be compared exactly.
    """

    area = path.boundingRect()
    image = QImage(
        math.ceil(area.width() * zoom) + 4,
        math.ceil(area.height() * zoom) + 4,
        QImage.Format.Format_ARGB32,
    )
    image.fill(QColor('white'))
    painter = QPainter(image)
    painter.scale(zoom, zoom)
    painter.translate(-area.left() + 2.0 / zoom, -area.top() + 2.0 / zoom)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor('black'))
    painter.drawPath(path)
    painter.end()
    return image.constBits().asstring(image.sizeInBytes())


def winding(path: QPainterPath) -> QPainterPath:
    """Give a copy of a path filled by the winding rule.

    Parameters
    ----------
    path : PyQt6.QtGui.QPainterPath
        The path.

    Returns
    -------
    PyQt6.QtGui.QPainterPath
        The copy.
    """

    copy = QPainterPath(path)
    copy.setFillRule(Qt.FillRule.WindingFill)
    return copy


# ----------------------------------------------------------------------
# How the letters are filled
# ----------------------------------------------------------------------


def test_lettering_is_filled_by_the_winding_rule(style):
    """A path is filled odd-even unless it is told otherwise, and odd-even punches
    a hairline hole wherever two strokes of one letter overlap."""

    assert text_block(OVERLAPPING, LABEL_WIDTH, style)[0].fillRule() == Qt.FillRule.WindingFill
    assert glyph_path(OVERLAPPING, 3.0).fillRule() == Qt.FillRule.WindingFill


@pytest.fixture
def overlapping_font():
    """Letter in a font whose strokes overlap, for as long as a test lasts.

    The tests run on the offscreen platform, whose default font is DejaVu Sans:
    its letters are drawn without overlapping contours, so there odd-even and
    winding fill give the very same pixels and a test of the fill rule could
    never fail.  Cantarell — the GNOME default, which is where the dashes
    through the text were seen — overlaps.

    Returns
    -------
    str
        The family, to be lettered in.
    """

    if 'Cantarell' not in QFontDatabase.families():
        pytest.skip('Cantarell, a font with overlapping contours, is not installed')
    was = QApplication.font()
    QApplication.setFont(QFont('Cantarell'))
    try:
        yield 'Cantarell'
    finally:
        QApplication.setFont(was)


@pytest.mark.parametrize('lettering', ['block', 'glyphs'])
def test_no_overlap_of_strokes_leaves_a_hole_in_a_letter(qapp, overlapping_font, lettering):
    """Read in the pixels, close up: the letters as drawn are the letters filled
    whole.  This is what was seen on the sheet as dashes through the text."""

    overlapping = TextStyle(overlapping_font, 2.4)
    path = (
        text_block(OVERLAPPING, LABEL_WIDTH, overlapping)[0]
        if lettering == 'block'
        else glyph_path(OVERLAPPING, 3.0, family=overlapping_font)
    )

    assert inked(path) == inked(winding(path))


# ----------------------------------------------------------------------
# What is written on the sheet
# ----------------------------------------------------------------------


def test_text_is_written_a_height_on_the_paper_centred_on_nought():
    """The weight of an arc and the tokens of a place are written the same way."""

    written = glyph_path('42', 3.0).boundingRect()

    assert written.height() == pytest.approx(3.0, abs=0.01)
    assert written.center().x() == pytest.approx(0.0, abs=0.01)
    assert written.center().y() == pytest.approx(0.0, abs=0.01)


def test_text_too_wide_for_its_room_is_narrowed_to_it():
    """Keeping its proportions, so it grows no taller than asked."""

    tall = glyph_path('1234567', 4.0).boundingRect()
    narrowed = glyph_path('1234567', 4.0, 7.0).boundingRect()

    assert narrowed.width() == pytest.approx(7.0, abs=0.01)
    assert narrowed.height() / narrowed.width() == pytest.approx(tall.height() / tall.width(), rel=0.01)


def test_text_that_draws_nothing_is_an_empty_path():
    """Nothing to scale."""

    assert glyph_path('', 3.0).isEmpty()


def test_a_number_can_be_written_in_a_family_of_its_own():
    """A place's tokens take the family its caption is written in, at a size and
    a typeface of their own — which is the whole of what a family is asked for."""

    families = [name for name in ('Nimbus Sans', 'DejaVu Sans') if fonts.installed(name)]
    if len(families) < 2:
        pytest.skip('two families to tell apart are not both installed')

    one = glyph_path('42', 3.0, family=families[0])
    other = glyph_path('42', 3.0, family=families[1])

    assert not one.isEmpty()
    assert one != other


# ----------------------------------------------------------------------
# The size a style is lettered at
# ----------------------------------------------------------------------


def test_a_line_is_as_tall_as_the_font_makes_it_at_that_size(style):
    """The size is the font's em, as a word processor measures it, and the line
    is what that font makes of it — ascender, descender and the leading."""

    height = line_height(style)

    assert height > style.size
    assert height == pytest.approx(line_height(style))
    assert line_height(TextStyle(style.font, style.size * 2.0)) == pytest.approx(
        height * 2.0
    )


def test_a_block_of_one_line_is_one_line_high(style):
    """So a block is as many lines tall as it has lines."""

    _glyphs, box = text_block('P1', LABEL_WIDTH, style)

    assert box.height() == pytest.approx(line_height(style))
    assert 0.0 < box.width() <= LABEL_WIDTH


def test_a_bigger_size_letters_bigger(style):
    """Which is what choosing a size in the settings has to come to."""

    _small, box = text_block('P1', LABEL_WIDTH, style)
    _large, larger = text_block('P1', LABEL_WIDTH, TextStyle(style.font, 5.0))

    assert larger.height() > box.height()
    assert larger.width() > box.width()


def test_a_typeface_is_carried_into_the_lettering(style):
    """Bold and italic are two boxes, and both reach the font the block is laid
    out in."""

    bold = font_of(TextStyle(style.font, style.size, bold=True))
    italic = font_of(TextStyle(style.font, style.size, italic=True))

    assert bold.bold() and not bold.italic()
    assert italic.italic() and not italic.bold()
    assert text_block('P1', LABEL_WIDTH, style)[0] != text_block(
        'P1', LABEL_WIDTH, TextStyle(style.font, style.size, bold=True)
    )[0]


# ----------------------------------------------------------------------
# How the lines are laid against the sides
# ----------------------------------------------------------------------


def test_a_block_is_laid_against_the_left_by_default(style):
    """The ink starts at the left side and stops short of the right."""

    glyphs, box = text_block(ONE_LINE, ROOMY, aligned(style, 'left'), fit=False)
    written = glyphs.boundingRect()

    assert box.width() == pytest.approx(ROOMY)
    assert written.left() == pytest.approx(-ROOMY / 2.0, abs=0.6)
    assert written.right() < ROOMY / 2.0 - 1.0


def test_a_block_can_be_laid_against_the_right(style):
    """The other way round: the ink ends at the right side."""

    glyphs, _box = text_block(ONE_LINE, ROOMY, aligned(style, 'right'), fit=False)
    written = glyphs.boundingRect()

    assert written.right() == pytest.approx(ROOMY / 2.0, abs=0.6)
    assert written.left() > -ROOMY / 2.0 + 1.0


def test_a_block_can_be_centred(style):
    """Which leaves the same room at each side."""

    glyphs, _box = text_block(ONE_LINE, ROOMY, aligned(style, 'center'), fit=False)
    written = glyphs.boundingRect()

    assert written.left() + written.right() == pytest.approx(0.0, abs=0.6)
    assert written.left() > -ROOMY / 2.0 + 1.0


def test_justified_stretches_every_line_but_the_last(style):
    """A justified line reaches both sides; a left-aligned one reaches only one."""

    justified, box = text_block(
        TWO_LINES, ROOMY, aligned(style, 'justified'), fit=False
    )
    left, _other = text_block(TWO_LINES, ROOMY, aligned(style, 'left'), fit=False)
    written = justified.boundingRect()

    assert box.height() > line_height(style)  # or there is no line to stretch
    assert written.left() == pytest.approx(-ROOMY / 2.0, abs=0.6)
    assert written.right() == pytest.approx(ROOMY / 2.0, abs=0.6)
    assert left.boundingRect().right() < written.right()


def test_the_last_line_of_a_justified_block_is_laid_against_the_left(style):
    """As it is in any editor: a last line stretched across the box is what
    nobody wants.  One line is its own last line, so it is lettered exactly as a
    left-aligned one."""

    one_line = 'P1: bottles'

    justified, box = text_block(one_line, ROOMY, aligned(style, 'justified'), fit=False)
    left, other = text_block(one_line, ROOMY, aligned(style, 'left'), fit=False)

    assert box == other
    assert justified == left


def test_a_block_goes_onto_another_line_rather_than_growing_wider(style):
    """Which is what makes a label a box rather than a line of text running off
    across the sheet."""

    _glyphs, box = text_block(
        'P1: bottles waiting to be filled, capped and taken away', LABEL_WIDTH, style
    )
    height = line_height(style)

    assert box.width() <= LABEL_WIDTH
    assert box.height() == pytest.approx(height * round(box.height() / height))
    assert box.height() > height * 2


def test_a_word_wider_than_the_whole_box_is_broken(style):
    """Rather than left to hang off the side, where it would run across whatever
    is drawn beside it."""

    _glyphs, box = text_block('P1: ' + 'x' * 200, LABEL_WIDTH, style)

    assert box.width() <= LABEL_WIDTH
    assert box.height() > line_height(style)


def test_a_block_is_centred_on_nought_by_its_box_and_not_by_its_ink(style):
    """So where a label sits does not depend on which letters happen to be in
    it: a line with a ``g`` in it hangs below the line, and that must not move
    the box."""

    plain, box = text_block('nn nn', LABEL_WIDTH, style)
    tails, other = text_block('gg gg', LABEL_WIDTH, style)

    assert box.height() == other.height()
    assert plain.boundingRect().center().y() < tails.boundingRect().center().y()
    assert abs(plain.boundingRect().center().y()) < line_height(style)


def test_a_block_of_nothing_is_nothing(style):
    """An item made outside the editor has no name, and writes nothing."""

    glyphs, box = text_block('', LABEL_WIDTH, style)

    assert glyphs.isEmpty()
    assert box.isEmpty()


# ----------------------------------------------------------------------
# What it is written in
# ----------------------------------------------------------------------


@pytest.mark.parametrize('colors', [LIGHT_COLORS, DARK_COLORS], ids=['light', 'dark'])
def test_automatic_is_the_sheets_own_ink(colors):
    """Which is what makes one rule read on both schemes."""

    option = palette_option(colors)

    assert ink_colour(False, option, AUTOMATIC) == QColor(colors.text)


@pytest.mark.parametrize('colors', [LIGHT_COLORS, DARK_COLORS], ids=['light', 'dark'])
def test_a_colour_of_its_own_is_written_in_that_colour(colors):
    """A colour chosen is the same colour in either scheme, which is the whole
    of the difference between it and *Automatic*."""

    assert ink_colour(False, palette_option(colors), '#aa0000') == QColor('#aa0000')


@pytest.mark.parametrize('colors', [LIGHT_COLORS, DARK_COLORS], ids=['light', 'dark'])
def test_a_selected_thing_keeps_the_accent_whatever_its_colour(colors):
    """Decided with Jaume: the selection is the accent, as it is today, and a
    colour of an item's own does not take that away."""

    option = palette_option(colors)

    assert ink_colour(True, option, AUTOMATIC) == QColor(colors.accent)
    assert ink_colour(True, option, '#aa0000') == QColor(colors.accent)
