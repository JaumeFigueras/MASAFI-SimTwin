"""Tests for the place: the circle, and how it is drawn.

What a place shares with a transition is in :mod:`test_net_item`; what is here
is the circle itself.
"""

from __future__ import annotations

import math

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor

from masafi_simtwin.documents.net_item import PORT_RADIUS
from masafi_simtwin.documents.place import (
    PLACE_DIAMETER,
    PLACE_RADIUS,
    PORT_COUNT,
    PORT_STEP_DEGREES,
)
from masafi_simtwin.theme import DARK_COLORS, LIGHT_COLORS

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
