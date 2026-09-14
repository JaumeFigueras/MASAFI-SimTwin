"""Tests for the colours and the lettering things on the sheet are drawn with.

Two kinds of lettering, and the difference between them is the point:
``glyph_path`` scales one piece of text so that its own ink is a height, and
``text_block`` scales the font's line height once for a whole block and wraps it.
"""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPainterPath
from PyQt6.QtWidgets import QApplication

from masafi_simtwin.documents.ink import (
    LABEL_LINE_HEIGHT,
    LABEL_WIDTH,
    glyph_path,
    text_block,
)

#: Letters whose strokes overlap in fonts drawn with overlapping contours —
#: Cantarell, the GNOME default, among them: the crossbar of a ``t``, the dot of
#: an ``i``, the loops of ``g``, ``@``, ``&`` and ``%``.
OVERLAPPING = 'tig@&%'


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


def test_lettering_is_filled_by_the_winding_rule():
    """A path is filled odd-even unless it is told otherwise, and odd-even punches
    a hairline hole wherever two strokes of one letter overlap."""

    assert text_block(OVERLAPPING, LABEL_WIDTH)[0].fillRule() == Qt.FillRule.WindingFill
    assert glyph_path(OVERLAPPING, 3.0).fillRule() == Qt.FillRule.WindingFill


@pytest.fixture
def overlapping_font():
    """Letter in a font whose strokes overlap, for as long as a test lasts.

    The tests run on the offscreen platform, whose default font is DejaVu Sans:
    its letters are drawn without overlapping contours, so there odd-even and
    winding fill give the very same pixels and a test of the fill rule could
    never fail.  Cantarell — the GNOME default, which is where the dashes
    through the text were seen — overlaps.  Lettering is laid out in the
    application's font, so that is what is set, and set back.
    """

    if 'Cantarell' not in QFontDatabase.families():
        pytest.skip('Cantarell, a font with overlapping contours, is not installed')
    was = QApplication.font()
    QApplication.setFont(QFont('Cantarell'))
    try:
        yield
    finally:
        QApplication.setFont(was)


@pytest.mark.parametrize('lettering', ['block', 'glyphs'])
def test_no_overlap_of_strokes_leaves_a_hole_in_a_letter(qapp, overlapping_font, lettering):
    """Read in the pixels, close up: the letters as drawn are the letters filled
    whole.  This is what was seen on the sheet as dashes through the text."""

    path = text_block(OVERLAPPING, LABEL_WIDTH)[0] if lettering == 'block' else glyph_path(OVERLAPPING, 3.0)

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


# ----------------------------------------------------------------------
# Laying out a block of text
# ----------------------------------------------------------------------


def test_a_block_of_one_line_is_one_line_high():
    """The font's own line height, scaled to millimetres, so a block is as many
    lines tall as it has lines."""

    _glyphs, box = text_block('P1', LABEL_WIDTH)

    assert box.height() == pytest.approx(LABEL_LINE_HEIGHT)
    assert 0.0 < box.width() <= LABEL_WIDTH


def test_a_block_goes_onto_another_line_rather_than_growing_wider():
    """Which is what makes a label a box rather than a line of text running off
    across the sheet."""

    _glyphs, box = text_block(
        'P1: bottles waiting to be filled, capped and taken away', LABEL_WIDTH
    )

    assert box.width() <= LABEL_WIDTH
    assert box.height() == pytest.approx(LABEL_LINE_HEIGHT * round(box.height() / LABEL_LINE_HEIGHT))
    assert box.height() > LABEL_LINE_HEIGHT * 2


def test_a_word_wider_than_the_whole_box_is_broken():
    """Rather than left to hang off the side, where it would run across whatever
    is drawn beside it."""

    _glyphs, box = text_block('P1: ' + 'x' * 200, LABEL_WIDTH)

    assert box.width() <= LABEL_WIDTH
    assert box.height() > LABEL_LINE_HEIGHT


def test_a_block_is_centred_on_nought_by_its_box_and_not_by_its_ink():
    """So where a label sits does not depend on which letters happen to be in
    it: a line with a ``g`` in it hangs below the line, and that must not move
    the box."""

    plain, box = text_block('nn nn', LABEL_WIDTH)
    tails, other = text_block('gg gg', LABEL_WIDTH)

    assert box.height() == other.height()
    assert plain.boundingRect().center().y() < tails.boundingRect().center().y()
    assert abs(plain.boundingRect().center().y()) < LABEL_LINE_HEIGHT


def test_a_block_of_nothing_is_nothing():
    """An item made outside the editor has no name, and writes nothing."""

    glyphs, box = text_block('', LABEL_WIDTH)

    assert glyphs.isEmpty()
    assert box.isEmpty()
