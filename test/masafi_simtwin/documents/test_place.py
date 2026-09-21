"""Tests for the place: the circle, and how it is drawn.

What a place shares with a transition is in :mod:`test_net_item`; what is here
is the circle itself.
"""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor

from masafi_simtwin.documents.ink import glyph_path
from masafi_simtwin.documents.label import LABEL_GAP
from masafi_simtwin.documents.net_item import PORT_RADIUS
from masafi_simtwin.documents.place import (
    MAX_TOKEN_DOTS,
    PLACE_DIAMETER,
    PLACE_RADIUS,
    PORT_COUNT,
    PORT_STEP_DEGREES,
    TOKEN_LAYOUTS,
    TOKEN_NUMBER_HEIGHT,
    TOKEN_NUMBER_WIDTH,
    TOKEN_RADIUS,
    Place,
)
from masafi_simtwin.preferences import DEFAULT_LINE_WIDTH
from masafi_simtwin.theme import DARK_COLORS, LIGHT_COLORS
from simtwin_core.petri_net import LineStyle

#: The two schemes every pixel test is run against.
SCHEMES = [LIGHT_COLORS, DARK_COLORS]

#: What each is called, so a failure names the scheme it happened in.
SCHEME_NAMES = ['light', 'dark']


# ----------------------------------------------------------------------
# The shape of a place
# ----------------------------------------------------------------------


def test_a_place_is_a_centimetre_across(place):
    """In millimetres of the sheet, so it is a centimetre on paper as well."""

    assert PLACE_DIAMETER == 10.0
    assert PLACE_RADIUS == 5.0


def test_a_place_is_taken_hold_of_by_its_circle(place):
    """Its bounding rectangle is a square, and its corners are not the place."""

    shape = place.shape()

    assert shape.contains(QPointF(0.0, 0.0))
    assert not shape.contains(QPointF(PLACE_RADIUS, PLACE_RADIUS))


def test_there_is_a_connecting_point_every_thirty_degrees(place):
    """Which comes to twelve of them, right round the circle.

    Angles are the right answer for a circle and only for a circle: it is even
    the whole way round, so points spread evenly by angle are points spread
    evenly on the paper.  A bar is not, and says where its own go.
    """

    assert PORT_STEP_DEGREES == 30.0
    assert PORT_COUNT == 12
    assert place.port_angles() == [angle * 30.0 for angle in range(12)]
    assert len(place.ports()) == 12


def test_a_place_snaps_by_its_centre_and_four_points_of_its_rim(place):
    """Due east, north, west and south, and the centre first."""

    expected = [
        (0.0, 0.0),
        (PLACE_RADIUS, 0.0),
        (0.0, -PLACE_RADIUS),
        (-PLACE_RADIUS, 0.0),
        (0.0, PLACE_RADIUS),
    ]
    anchors = place.snap_anchors()

    assert len(anchors) == 5
    for anchor, (x, y) in zip(anchors, expected):
        assert anchor.x() == pytest.approx(x, abs=1e-12)
        assert anchor.y() == pytest.approx(y, abs=1e-12)
    assert anchors == Place.anchors_for(vertical=True)


def test_every_connecting_point_is_one_radius_out(place):
    """A circle has the easy answer: the angle is the whole of the question."""

    for point in place.ports():
        assert math.hypot(point.x(), point.y()) == pytest.approx(PLACE_RADIUS)


def test_the_connecting_points_are_where_a_protractor_puts_them(place):
    """Due east, then up and round: 90° is the top of the circle."""

    east, ninety = place.ports()[0], place.ports()[3]

    assert east == QPointF(PLACE_RADIUS, 0.0)
    assert ninety.x() == pytest.approx(0.0)
    assert ninety.y() == pytest.approx(-PLACE_RADIUS)


# ----------------------------------------------------------------------
# How a place is drawn, in both schemes
# ----------------------------------------------------------------------


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_place_is_filled_with_the_colour_of_the_sheet(place, ink, colors):
    """White on white in the light scheme, and the same *relation* in the dark.

    The fill is the palette's ``Base``, which is what the sheet itself is filled
    with, so a place is the colour of the paper with a rim round it in either
    scheme.  Inverting the light scheme literally would give a black disc, which
    reads as a hole cut in a dark sheet rather than as a place on it.
    """

    assert ink.at(ink.painted(place, colors)) == QColor(colors.editor)


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_place_is_drawn_with_an_outline_that_can_be_seen(place, ink, colors):
    """Near-black on white, near-white on the dark sheet: the palette's ``Text``."""

    rim = ink.at(ink.painted(place, colors), across=PLACE_RADIUS)

    assert ink.nearest(
        rim, QColor(colors.text), QColor(colors.editor)
    ) == QColor(colors.text)


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_selected_place_keeps_its_paper_and_changes_its_rim(place, ink, colors):
    """``Link`` is where the accent is kept — ``Highlight`` is the pale wash."""

    place.setSelected(True)
    image = ink.painted(place, colors)

    assert ink.at(image) == QColor(colors.editor)
    assert ink.nearest(
        ink.at(image, across=PLACE_RADIUS), QColor(colors.accent), QColor(colors.text)
    ) == QColor(colors.accent)


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_connecting_point_is_a_ring_and_not_a_dot(place, ink, colors):
    """Hollow: a hairline of the accent round the colour of the paper.

    A connecting point is not part of the drawing — it is somewhere to aim at,
    shown while it is being aimed at — so it is a ring rather than a mark.  What
    is read is the middle of the point, which is the paper, and the ring around
    it, which is the accent; and while the points are hidden there is no accent
    there at all.
    """

    accent = QColor(colors.accent)
    hidden = ink.window(ink.painted(place, colors), PLACE_RADIUS, 0.0, PORT_RADIUS)

    place.ports_visible = True
    image = ink.painted(place, colors)

    assert not ink.holds(hidden, accent)
    assert ink.holds(ink.window(image, PLACE_RADIUS, 0.0, PORT_RADIUS), accent)
    assert ink.at(image, across=PLACE_RADIUS) == QColor(colors.editor)


# ----------------------------------------------------------------------
# The tokens
# ----------------------------------------------------------------------


def test_a_place_holds_no_tokens_and_draws_none(place):
    """Until it is given some."""

    assert place.tokens == 0
    assert place.token_marks().isEmpty()


@pytest.mark.parametrize('count', range(1, MAX_TOKEN_DOTS + 1))
def test_up_to_five_tokens_are_drawn_as_that_many_dots(place, count):
    """In the pattern of a die's face, each dot where the layout puts it."""

    place.tokens = count
    marks = place.token_marks()

    assert len(TOKEN_LAYOUTS[count]) == count
    for across, down in TOKEN_LAYOUTS[count]:
        assert marks.contains(QPointF(across, down))


@pytest.mark.parametrize('count', range(1, MAX_TOKEN_DOTS + 1))
def test_every_dot_is_clear_of_the_others_and_of_the_rim(count):
    """So a count is read at a glance rather than guessed from a blot."""

    layout = TOKEN_LAYOUTS[count]
    for index, (across, down) in enumerate(layout):
        assert math.hypot(across, down) + TOKEN_RADIUS < PLACE_RADIUS - 1.0
        for other_across, other_down in layout[index + 1:]:
            assert math.hypot(across - other_across, down - other_down) > 2.0 * TOKEN_RADIUS


def test_there_is_a_layout_for_every_count_of_dots():
    """And none beyond, more tokens being written as a number."""

    assert MAX_TOKEN_DOTS == 5
    assert sorted(TOKEN_LAYOUTS) == list(range(1, MAX_TOKEN_DOTS + 1))


def test_more_than_five_tokens_are_written_as_a_number(place):
    """Centred on the place, a size on the paper."""

    place.tokens = MAX_TOKEN_DOTS + 1
    drawn = place.token_marks().boundingRect()

    assert drawn.height() == pytest.approx(TOKEN_NUMBER_HEIGHT, abs=0.01)
    assert drawn.width() < TOKEN_NUMBER_WIDTH
    assert drawn.center().x() == pytest.approx(0.0, abs=0.01)
    assert drawn.center().y() == pytest.approx(0.0, abs=0.01)


def test_a_long_number_is_narrowed_to_fit_inside_the_circle(place):
    """Rather than running out of it."""

    place.tokens = 1234567
    drawn = place.token_marks().boundingRect()

    assert drawn.width() == pytest.approx(TOKEN_NUMBER_WIDTH, abs=0.01)
    assert drawn.height() < TOKEN_NUMBER_HEIGHT
    assert drawn.width() < PLACE_DIAMETER


def test_tokens_below_nought_are_held_at_nought(place):
    """Nought is the fewest a place can hold."""

    place.tokens = -3

    assert place.tokens == 0


def test_changing_the_tokens_repaints_the_place(place, monkeypatch):
    """And giving the same number again does not."""

    repainted = []
    monkeypatch.setattr(place, 'update', lambda *arguments: repainted.append(True))

    place.tokens = 2
    place.tokens = 2

    assert repainted == [True]


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_token_is_a_dot_of_the_ink_on_the_paper(place, ink, colors):
    """The ink of the rim, on the colour of the sheet."""

    place.tokens = 1
    image = ink.painted(place, colors)

    assert ink.nearest(ink.at(image), QColor(colors.text), QColor(colors.editor)) == QColor(
        colors.text
    )
    assert ink.at(image, across=2.5) == QColor(colors.editor)


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_the_tokens_of_a_selected_place_are_drawn_in_the_accent(place, ink, colors):
    """With its rim: a selected thing is drawn in the accent."""

    place.tokens = 1
    place.setSelected(True)

    centre = ink.at(ink.painted(place, colors))

    assert ink.nearest(
        centre, QColor(colors.accent), QColor(colors.text), QColor(colors.editor)
    ) == QColor(colors.accent)


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_number_of_tokens_is_drawn_in_the_ink(place, ink, colors):
    """Somewhere in the middle of the place there is ink, and at its edge none."""

    place.tokens = 88
    image = ink.painted(place, colors)

    assert ink.holds(ink.window(image, 0.0, 0.0, TOKEN_NUMBER_HEIGHT / 2.0), QColor(colors.text))
    assert ink.at(image, across=PLACE_RADIUS - 1.0) == QColor(colors.editor)


# ----------------------------------------------------------------------
# What is written beside it
# ----------------------------------------------------------------------


def test_a_places_label_is_under_it_and_centred(place):
    """Which is where the name of a place goes on a drawn net."""

    box = place.label_rect()

    assert box.center().x() == pytest.approx(0.0)
    assert box.top() == pytest.approx(place.boundingRect().bottom() + LABEL_GAP)


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_the_tokens_are_drawn_in_the_places_line_colour(place, ink, colors):
    """Decided with Jaume: the dots and the number take the colour of the rim,
    not of the caption — they are part of the drawing rather than a word about
    it."""

    place.tokens = 1
    place.line_style = LineStyle('#aa0000', DEFAULT_LINE_WIDTH)
    place.restyle()
    image = ink.painted(place, colors)

    assert ink.nearest(
        ink.at(image), QColor('#aa0000'), QColor(colors.text), QColor(colors.editor)
    ) == QColor('#aa0000')
    assert ink.nearest(
        ink.at(image, across=PLACE_RADIUS), QColor('#aa0000'), QColor(colors.editor)
    ) == QColor('#aa0000')


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_number_of_tokens_takes_the_line_colour_too(place, ink, colors):
    """The number is the same marking as the dots, written instead of drawn."""

    place.tokens = 88
    place.line_style = LineStyle('#aa0000', DEFAULT_LINE_WIDTH)
    place.restyle()

    written = ink.window(
        ink.painted(place, colors), 0.0, 0.0, TOKEN_NUMBER_HEIGHT / 2.0
    )

    assert ink.holds(written, QColor('#aa0000'))


def test_a_place_letters_as_a_place(place):
    """Which is what decides the typeface its caption is written in."""

    assert place.ROLE == 'place'
    assert place.appearance().font


def test_a_number_of_tokens_takes_the_familys_of_the_caption(place):
    """Agreed with Jaume: the family of the caption, at a size and a typeface of
    the number's own — a count inside a circle is not a caption, and a bold or
    slanted one would read as something else."""

    place.tokens = 88

    assert place.token_marks() == glyph_path(
        '88', TOKEN_NUMBER_HEIGHT, TOKEN_NUMBER_WIDTH, family=place.appearance().font
    )
