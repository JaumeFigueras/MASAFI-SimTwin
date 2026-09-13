"""Tests for the colours and the lettering things on the sheet are drawn with.

Two kinds of lettering, and the difference between them is the point:
``glyph_path`` scales one piece of text so that its own ink is a height, and
``text_block`` scales the font's line height once for a whole block and wraps it.
"""

from __future__ import annotations

import pytest

from masafi_simtwin.documents.ink import (
    LABEL_LINE_HEIGHT,
    LABEL_WIDTH,
    glyph_path,
    text_block,
)


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
