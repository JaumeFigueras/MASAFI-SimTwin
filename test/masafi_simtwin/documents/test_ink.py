"""Tests for the colours and the lettering things on the sheet are drawn with.

Two kinds of lettering, and the difference between them is the point:
``glyph_path`` scales one piece of text so that its own ink is a height, and
``text_block`` lays a whole block out in a **style** — a family, a size in
millimetres, a typeface and an alignment — and wraps it to a width.

Laying a block out and marking it are parted: ``text_layout`` decides which
words go on which line and where each sits, and ``block_path`` is the sheet's
way of marking that out.  So the tests of the layout read the pieces, and the
tests of the lettering read the ink.
"""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QImage,
    QPainter,
    QPainterPath,
    QTransform,
)
from PyQt6.QtWidgets import QApplication, QStyleOptionGraphicsItem

from masafi_simtwin import fonts
from masafi_simtwin.documents.ink import (
    LABEL_WIDTH,
    block_path,
    font_of,
    glyph_path,
    ink_colour,
    line_height,
    on_paper,
    paper_colour,
    printing,
    text_block,
    text_layout,
    write_block,
)
from masafi_simtwin.theme import (
    DARK_COLORS,
    LIGHT_COLORS,
    PAPER,
    PAPER_INK,
    build_palette,
    paper_palette,
)
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
# Laying a block out, apart from marking it
# ----------------------------------------------------------------------


def test_a_layout_is_a_piece_a_line_and_says_where_each_line_sits(style):
    """Which is the whole of what a painter needs to write a block out: what to
    write and where, in the font's own units."""

    metrics = QFontMetricsF(font_of(style))

    one = text_layout(ONE_LINE, ROOMY, style)
    several = text_layout(TWO_LINES, ROOMY, style)
    baselines = [piece[1] for piece in several.pieces]

    assert [piece[2] for piece in one.pieces] == [ONE_LINE]
    assert one.pieces[0][1] == pytest.approx(metrics.ascent())
    assert len(several.pieces) > 1
    assert ' '.join(piece[2] for piece in several.pieces) == TWO_LINES
    assert baselines[1] - baselines[0] == pytest.approx(metrics.height())


def test_the_box_is_as_tall_as_the_lines_the_layout_holds(style):
    """The box is measured in millimetres and the pieces in font units, and the
    two have to say the same thing about how many lines there are."""

    block = text_layout(TWO_LINES, ROOMY, style)
    lines = {piece[1] for piece in block.pieces}

    assert len(lines) > 1
    assert block.box.height() == pytest.approx(len(lines) * line_height(style))


def test_a_justified_line_is_laid_out_word_by_word(style):
    """There is no one place a justified line starts from — the slack is shared
    between the gaps — so every word is a piece of its own.  The last line is
    laid against the left, so it stays one piece."""

    block = text_layout(TWO_LINES, ROOMY, aligned(style, 'justified'), fit=False)
    left = text_layout(TWO_LINES, ROOMY, aligned(style, 'left'), fit=False)
    first = [piece for piece in block.pieces if piece[1] == block.pieces[0][1]]
    last = [piece for piece in block.pieces if piece[1] == block.pieces[-1][1]]

    assert len(first) > 1
    assert all(' ' not in piece[2] for piece in first)
    assert [piece[0] for piece in first] == sorted(piece[0] for piece in first)
    assert len(last) == 1
    assert ' ' in left.pieces[0][2]


def test_a_block_is_its_pieces_marked_with_the_font_and_scaled_once(style):
    """What is drawn on the sheet is what the layout says, marked with the
    block's own font and scaled by the one number, the middle of its box on the
    origin — so the two halves cannot drift apart, whichever of them is changed.

    The paths are compared rather than their ink: ``inked`` draws a path against
    its own bounding rectangle, which is exactly what makes it blind to where
    the block was put, and where the block was put is half of what is held
    here."""

    block = text_layout(TWO_LINES, ROOMY, style)

    marked = QPainterPath()
    for along, baseline, piece in block.pieces:
        marked.addText(along, baseline, block.font, piece)
    marked = QTransform().scale(block.scale, block.scale).map(marked)
    marked.translate(-block.box.width() / 2.0, -block.box.height() / 2.0)

    assert text_block(TWO_LINES, ROOMY, style)[0] == winding(marked)


def test_a_layout_of_nothing_lays_nothing_out(style):
    """An item made outside the editor has no name, and there is nothing to
    write and nothing to mark."""

    block = text_layout('', LABEL_WIDTH, style)

    assert block.pieces == ()
    assert block.box.isEmpty()
    assert block_path(block).isEmpty()


class WritingPainter:
    """A stand-in for the painter, which keeps how a block was written out.

    ``write_block`` asks the painter for one of two things and nothing else: to
    fill a path, which is what the sheet is lettered with, or to take a font and
    write pieces of text, which is what paper is — so which of the two it chose
    can be read off without a screen or a file to put it on.

    Attributes
    ----------
    paths : list
        Every path it was asked to fill.
    written : list of tuple
        Every piece of text it was asked to write, as ``(point, text)``.
    font : PyQt6.QtGui.QFont or None
        The font it was told to write in.
    pen : object or None
        The pen it was left with when the writing was done.
    brush : object or None
        The brush it was left with.
    moves : list of tuple
        What it was asked to do to its transform, so that where the writing
        would land can be read off.
    depth : int
        How many saves are still open, which must be nought when it is over.
    """

    def __init__(self) -> None:
        self.paths = []
        self.written = []
        self.font = None
        self.pen = None
        self.brush = None
        self.moves = []
        self.depth = 0

    def save(self) -> None:
        """Keep what the painter was set to."""

        self.depth += 1

    def restore(self) -> None:
        """Put back what the painter was set to."""

        self.depth -= 1

    def setPen(self, pen) -> None:  # noqa: N802  (Qt naming)
        """Take the pen.

        Parameters
        ----------
        pen : object
            The pen, or a style meaning there is none.
        """

        self.pen = pen

    def setBrush(self, brush) -> None:  # noqa: N802  (Qt naming)
        """Take the brush.

        Parameters
        ----------
        brush : object
            The brush.
        """

        self.brush = brush

    def setFont(self, font) -> None:  # noqa: N802  (Qt naming)
        """Take the font.

        Parameters
        ----------
        font : PyQt6.QtGui.QFont
            The font.
        """

        self.font = font

    def translate(self, *where) -> None:
        """Keep a move of the transform.

        Parameters
        ----------
        *where
            Whatever the caller passes.
        """

        self.moves.append(('translate', where))

    def scale(self, *by) -> None:
        """Keep a scaling of the transform.

        Parameters
        ----------
        *by
            Whatever the caller passes.
        """

        self.moves.append(('scale', by))

    def drawPath(self, path) -> None:  # noqa: N802  (Qt naming)
        """Keep a path it was asked to fill.

        Parameters
        ----------
        path : PyQt6.QtGui.QPainterPath
            The path.
        """

        self.paths.append(path)

    def drawText(self, point, text) -> None:  # noqa: N802  (Qt naming)
        """Keep a piece of text it was asked to write.

        Parameters
        ----------
        point : PyQt6.QtCore.QPointF
            Where the piece starts, on its baseline.
        text : str
            What it says.
        """

        self.written.append((point, text))


def written_out(block, glyphs, colour, paper=None) -> WritingPainter:
    """Write a block out and give back what the painter was asked for.

    Parameters
    ----------
    block : masafi_simtwin.documents.ink.Block
        What was laid out.
    glyphs : PyQt6.QtGui.QPainterPath
        The same block marked as a path.
    colour : PyQt6.QtGui.QColor
        The ink.
    paper : PyQt6.QtGui.QPalette, optional
        What paper looks like.  Left out, it is written on a screen.

    Returns
    -------
    WritingPainter
        What it was asked to do.
    """

    painter = WritingPainter()
    if paper is None:
        write_block(painter, block, glyphs, colour)
        return painter
    with on_paper(paper):
        write_block(painter, block, glyphs, colour)
    return painter


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


# ----------------------------------------------------------------------
# On paper
# ----------------------------------------------------------------------


@pytest.mark.parametrize('colors', [LIGHT_COLORS, DARK_COLORS], ids=['light', 'dark'])
def test_paper_has_no_scheme(colors):
    """A drawing printed is black on white whatever the application is running
    in: paper has no dark mode, and a net that came out white on black would be
    a net that costs a cartridge to read."""

    option = palette_option(colors)

    with on_paper(paper_palette()):
        assert ink_colour(False, option, AUTOMATIC) == QColor(PAPER_INK)
        assert paper_colour(option) == QColor(PAPER)


@pytest.mark.parametrize('colors', [LIGHT_COLORS, DARK_COLORS], ids=['light', 'dark'])
def test_a_colour_of_its_own_is_printed_as_it_is(colors):
    """What follows the scheme is what printing changes.  A colour a person
    chose is the thing's own rather than the scheme's, so it is not touched —
    which is what was asked for."""

    option = palette_option(colors)

    with on_paper(paper_palette()):
        assert ink_colour(False, option, '#aa0000') == QColor('#aa0000')


@pytest.mark.parametrize('colors', [LIGHT_COLORS, DARK_COLORS], ids=['light', 'dark'])
def test_nothing_is_printed_in_the_accent(colors):
    """The accent says *this is in hand*, which is a fact about the session and
    not about the net.  A print clears the selection before it draws anything;
    this is the second answer, so that a thing selected could not print blue
    even if one were left."""

    option = palette_option(colors)

    with on_paper(paper_palette()):
        assert ink_colour(True, option, AUTOMATIC) == QColor(PAPER_INK)
        assert ink_colour(True, option, '#aa0000') == QColor(PAPER_INK)


def test_the_screen_is_what_is_painted_on_again_afterwards():
    """The paper is a state of the module, so it has to be given back.

    **Given back when the painting raised as well** — a print that cannot be
    written is an ordinary thing, and one of them must not leave every sheet in
    the application black on white until it is restarted.  The failure is
    raised at the top level here and not inside a second print: nested, the
    outer one puts the paper back on its own way out and the leak cannot be
    seen, which is how this test first passed against a version with no
    ``finally`` in it at all.
    """

    option = palette_option(DARK_COLORS)

    assert not printing()
    with on_paper(paper_palette()):
        assert printing()
    assert not printing()

    with pytest.raises(ValueError):
        with on_paper(paper_palette()):
            raise ValueError('a print that could not be written')

    assert not printing()
    assert ink_colour(False, option, AUTOMATIC) == QColor(DARK_COLORS.text)


def test_a_caption_is_a_path_on_the_sheet(style):
    """Which is what makes it the same size at every zoom and fills it with the
    brush of the thing it belongs to."""

    block = text_layout(TWO_LINES, ROOMY, style)
    glyphs = block_path(block)

    painter = written_out(block, glyphs, QColor('#aa0000'))

    assert painter.paths == [glyphs]
    assert painter.written == []
    assert painter.brush == QColor('#aa0000')
    assert painter.depth == 0


def test_a_caption_is_text_on_paper(style):
    """So a reader can select it, search it and copy it out of the file — which
    a path cannot be.  It is the same pieces in the same places, written with
    the block's own font rather than built into a path."""

    block = text_layout(TWO_LINES, ROOMY, style)
    glyphs = block_path(block)

    painter = written_out(block, glyphs, QColor(PAPER_INK), paper=paper_palette())

    assert painter.paths == []
    assert [text for _where, text in painter.written] == [
        piece[2] for piece in block.pieces
    ]
    assert [
        (where.x(), where.y()) for where, _text in painter.written
    ] == [(piece[0], piece[1]) for piece in block.pieces]
    assert painter.font == block.font
    assert painter.pen == QColor(PAPER_INK)
    assert painter.depth == 0


def test_a_printed_caption_is_scaled_and_centred_like_the_path(style):
    """The pieces are in the font's own units and the box is in millimetres, so
    the painter is moved to the middle of the box and scaled by the block's one
    number — which is exactly what ``block_path`` does to the path, and is what
    makes a printed caption land where the sheet puts it."""

    block = text_layout(TWO_LINES, ROOMY, style)

    painter = written_out(block, block_path(block), QColor(PAPER_INK), paper_palette())

    assert painter.moves == [
        ('translate', (-block.box.width() / 2.0, -block.box.height() / 2.0)),
        ('scale', (block.scale, block.scale)),
    ]


def test_a_block_of_nothing_is_written_neither_way(style):
    """An item made outside the editor has no name, and a caption that says
    nothing must not leave a pen, a brush or a font behind it."""

    block = text_layout('', LABEL_WIDTH, style)

    on_sheet = written_out(block, block_path(block), QColor(PAPER_INK))
    on_the_paper = written_out(block, block_path(block), QColor(PAPER_INK), paper_palette())

    for painter in (on_sheet, on_the_paper):
        assert painter.paths == []
        assert painter.written == []
        assert painter.font is None
        assert painter.depth == 0


#: Pixels to the millimetre a caption is written at to be read back.  Small
#: enough that a box thirty millimetres across fits in the image with room to
#: spare, big enough that a line of lettering is several pixels tall.
WRITING_ZOOM = 12.0


def marked(block, glyphs, paper=None) -> QImage:
    """Write a block out with a real painter and give what it came to.

    Parameters
    ----------
    block : masafi_simtwin.documents.ink.Block
        What was laid out.
    glyphs : PyQt6.QtGui.QPainterPath
        The same block marked as a path.
    paper : PyQt6.QtGui.QPalette, optional
        What paper looks like.  Left out, it is written on a screen.

    Returns
    -------
    PyQt6.QtGui.QImage
        The image, the middle of the block on the middle of it.
    """

    image = QImage(600, 400, QImage.Format.Format_ARGB32)
    image.fill(QColor('white'))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    painter.translate(image.width() / 2.0, image.height() / 2.0)
    painter.scale(WRITING_ZOOM, WRITING_ZOOM)
    if paper is None:
        write_block(painter, block, glyphs, QColor('black'))
    else:
        with on_paper(paper):
            write_block(painter, block, glyphs, QColor('black'))
    painter.end()
    return image


def ink_box(image: QImage) -> tuple[int, int, int, int]:
    """Give the corners of what was actually marked on an image.

    Parameters
    ----------
    image : PyQt6.QtGui.QImage
        The image, white where nothing was marked.

    Returns
    -------
    tuple
        Left, top, right and bottom, in pixels.
    """

    pixels = image.constBits().asstring(image.sizeInBytes())
    width = image.width()
    marks = [
        divmod(at // 4, width)
        for at in range(0, len(pixels), 4)
        if pixels[at] < 128
    ]
    assert marks, 'nothing was marked at all'
    return (
        min(across for _down, across in marks),
        min(down for down, _across in marks),
        max(across for _down, across in marks),
        max(down for down, _across in marks),
    )


def test_a_printed_caption_lands_where_the_sheet_puts_it(style):
    """The two markings are not the same pixels — a glyph written with a font is
    hinted and a glyph built into a path is not — but they must occupy the same
    place, or a net would print somewhere other than where it was drawn.

    This is the claim the stand-in painter cannot make: it reads the calls, and
    where the ink lands is what a real painter answers.
    """

    block = text_layout(TWO_LINES, LABEL_WIDTH, style)
    glyphs = block_path(block)

    on_sheet = ink_box(marked(block, glyphs))
    on_the_paper = ink_box(marked(block, glyphs, paper_palette()))

    for sheet_edge, paper_edge in zip(on_sheet, on_the_paper):
        assert paper_edge == pytest.approx(sheet_edge, abs=1)
