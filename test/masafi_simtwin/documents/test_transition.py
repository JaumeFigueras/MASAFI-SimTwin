"""Tests for the transition: the bar, and how it is drawn.

What a transition shares with a place is in :mod:`test_net_item`; what is here
is the bar itself, and the one thing that makes it look unlike a place — it is
filled with the colour it is outlined in.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor

from masafi_simtwin.documents.net_item import ITEM_PEN, PORT_RADIUS
from masafi_simtwin.documents.transition import (
    PORT_COUNT,
    PORT_SPACING,
    PORTS_ALONG_A_SIDE,
    PORTS_EACH_SIDE_OF_MIDDLE,
    TRANSITION_HALF_HEIGHT,
    TRANSITION_HALF_LENGTH,
    TRANSITION_HEIGHT,
    TRANSITION_LENGTH,
)
from masafi_simtwin.theme import DARK_COLORS, LIGHT_COLORS

#: The two schemes every pixel test is run against.
SCHEMES = [LIGHT_COLORS, DARK_COLORS]

#: What each is called, so a failure names the scheme it happened in.
SCHEME_NAMES = ['light', 'dark']


# ----------------------------------------------------------------------
# The shape of a transition
# ----------------------------------------------------------------------


def test_a_transition_is_a_centimetre_and_six_by_two_millimetres(transition):
    """In millimetres of the sheet, so it is that size on paper as well."""

    assert TRANSITION_LENGTH == 16.0
    assert TRANSITION_HEIGHT == 2.0
    assert transition.bar().width() == 16.0
    assert transition.bar().height() == 2.0


def test_a_transition_is_centred_on_its_position(transition):
    """The centre is what a drop puts under the pointer, on every item."""

    assert transition.bar().center() == QPointF(0.0, 0.0)


def test_a_transition_is_taken_hold_of_by_its_bar(transition):
    """Its bounding rectangle stands a connecting point off every edge."""

    shape = transition.shape()

    assert shape.contains(QPointF(0.0, 0.0))
    assert shape.contains(QPointF(TRANSITION_HALF_LENGTH - 0.5, 0.0))
    assert not shape.contains(QPointF(TRANSITION_HALF_LENGTH + 0.5, 0.0))
    assert not shape.contains(QPointF(0.0, TRANSITION_HALF_HEIGHT + 0.5))


def edge_points(transition, down: float) -> list[float]:
    """Give how far along one edge each of its connecting points is.

    Parameters
    ----------
    transition : masafi_simtwin.documents.transition.Transition
        The item.
    down : float
        Which edge: the ``y`` its points are at.

    Returns
    -------
    list of float
        Their ``x``, in millimetres from the centre, in order.
    """

    found = [point.x() for point in transition.ports() if point.y() == pytest.approx(down)]
    return sorted(found)


def test_every_edge_has_a_connecting_point_in_its_middle(transition):
    """All four of them: the two ends, and the middle of the top and the bottom.

    The middle of a long edge is where an arc between two places stacked above
    one another meets a transition, which is how a great many nets are drawn.
    """

    ports = set((point.x(), point.y()) for point in transition.ports())

    assert (TRANSITION_HALF_LENGTH, 0.0) in ports
    assert (-TRANSITION_HALF_LENGTH, 0.0) in ports
    assert (0.0, -TRANSITION_HALF_HEIGHT) in ports
    assert (0.0, TRANSITION_HALF_HEIGHT) in ports


def test_each_long_edge_carries_four_points_at_each_side_of_its_middle(transition):
    """So nine along the top and nine along the bottom."""

    assert PORTS_EACH_SIDE_OF_MIDDLE == 4
    assert PORTS_ALONG_A_SIDE == 9

    for down in (-TRANSITION_HALF_HEIGHT, TRANSITION_HALF_HEIGHT):
        along = edge_points(transition, down)
        assert len(along) == 9
        assert len([x for x in along if x < 0.0]) == 4
        assert len([x for x in along if x > 0.0]) == 4


def test_the_points_along_a_long_edge_are_evenly_spread(transition):
    """Evenly to the corners as well as between themselves.

    The edge is divided into one more part than there are points, so the gap
    from the outermost point to the corner is the gap between any two points —
    and nothing lands **on** a corner, which would be a point belonging to two
    edges and to neither.
    """

    along = edge_points(transition, -TRANSITION_HALF_HEIGHT)
    gaps = [second - first for first, second in zip(along, along[1:])]

    assert all(gap == pytest.approx(PORT_SPACING) for gap in gaps)
    assert along[0] + TRANSITION_HALF_LENGTH == pytest.approx(PORT_SPACING)
    assert TRANSITION_HALF_LENGTH - along[-1] == pytest.approx(PORT_SPACING)
    assert max(abs(x) for x in along) < TRANSITION_HALF_LENGTH


def test_the_two_edges_carry_the_same_points(transition):
    """A bar is the same read from above and from below."""

    assert edge_points(transition, -TRANSITION_HALF_HEIGHT) == edge_points(
        transition, TRANSITION_HALF_HEIGHT
    )


def test_a_transition_has_twenty_connecting_points(transition):
    """Nine along each long edge and one at each end."""

    assert PORT_COUNT == 20
    assert len(transition.ports()) == 20
    assert len({(point.x(), point.y()) for point in transition.ports()}) == 20


def test_only_the_two_ends_are_off_the_long_edges(transition):
    """Which is what a bar eight times as long as it is high looks like."""

    ends = [
        point
        for point in transition.ports()
        if abs(point.y()) != pytest.approx(TRANSITION_HALF_HEIGHT)
    ]

    assert [(point.x(), point.y()) for point in ends] == [
        (TRANSITION_HALF_LENGTH, 0.0),
        (-TRANSITION_HALF_LENGTH, 0.0),
    ]


def test_no_connecting_point_leaves_the_bar(transition):
    """They are on its edges, not in the air beside it."""

    for point in transition.ports():
        assert abs(point.x()) <= TRANSITION_HALF_LENGTH + 1e-9
        assert abs(point.y()) <= TRANSITION_HALF_HEIGHT + 1e-9


def test_the_walk_starts_at_the_right_hand_end_and_goes_up_and_round(transition):
    """The same way the angles of a place turn, so both lists read alike."""

    ports = transition.ports()

    assert ports[0] == QPointF(TRANSITION_HALF_LENGTH, 0.0)
    assert ports[1].y() == pytest.approx(-TRANSITION_HALF_HEIGHT)
    assert ports[1].x() > ports[2].x()
    assert ports[PORTS_ALONG_A_SIDE + 1] == QPointF(-TRANSITION_HALF_LENGTH, 0.0)
    assert ports[-1].y() == pytest.approx(TRANSITION_HALF_HEIGHT)


# ----------------------------------------------------------------------
# How a transition is drawn, in both schemes
# ----------------------------------------------------------------------


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_transition_is_filled_with_its_own_outline_colour(transition, ink, colors):
    """Black in the light scheme, which is what a transition is.

    A bar two millimetres high has no inside worth seeing, so it is one solid
    stroke of ink: the middle of it is the same colour as its edge, and neither
    is the colour of the paper.
    """

    image = ink.painted(transition, colors)
    middle = ink.at(image)
    edge = ink.at(image, across=TRANSITION_HALF_LENGTH - 0.5)

    assert ink.nearest(middle, QColor(colors.text), QColor(colors.editor)) == QColor(
        colors.text
    )
    assert ink.distance(middle, edge) == 0


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_transition_is_not_the_colour_of_the_sheet(transition, ink, colors):
    """Which is the whole of the difference from a place, in either scheme."""

    middle = ink.at(ink.painted(transition, colors))

    assert middle != QColor(colors.editor)
    assert ink.distance(middle, QColor(colors.editor)) > 200


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_selected_transition_is_a_solid_bar_of_the_accent(transition, ink, colors):
    """The fill follows the outline wherever it goes.

    An accent rim around a black bar two millimetres high would read as a bar
    that had changed shade, which is not a thing anybody can see across a sheet.
    """

    transition.setSelected(True)
    middle = ink.at(ink.painted(transition, colors))

    assert ink.nearest(middle, QColor(colors.accent), QColor(colors.text)) == QColor(
        colors.accent
    )


#: How many pixels a millimetre is drawn as when a corner is read.  A corner is
#: a tenth of a millimetre of detail and needs the room.
CORNER_SCALE = 120.0

#: How far inside the outer corner the pixel that tells a sharp corner from a
#: chamfered one is, in millimetres.  Two thirds of the way out along the
#: diagonal of the stroke's own corner: inside a mitered join and outside a
#: bevelled one.
CORNER_PROBE = ITEM_PEN / 3.0


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_the_corners_of_the_bar_are_sharp(transition, ink, colors):
    """A transition is a rectangle, not a rectangle with its corners taken off.

    Qt joins a stroke at a corner with a *bevel* unless it is told otherwise,
    and a bevel chamfers the corner by the width of the pen — on a bar this is a
    cut across each corner rather than a corner.  What is read is a pixel just
    inside where the outer corner ought to be: ink if the join comes to a point,
    paper if it has been taken off.  It has to be read close up, a chamfer being
    a tenth of a millimetre across.
    """

    for across in (TRANSITION_HALF_LENGTH, -TRANSITION_HALF_LENGTH):
        for down in (TRANSITION_HALF_HEIGHT, -TRANSITION_HALF_HEIGHT):
            corner = ink.close_up(across, down, CORNER_SCALE)
            probe = corner.at(
                corner.painted(transition, colors),
                across=CORNER_PROBE * (1 if across > 0 else -1),
                down=CORNER_PROBE * (1 if down > 0 else -1),
            )
            assert probe == QColor(colors.text)


@pytest.mark.parametrize('colors', SCHEMES, ids=SCHEME_NAMES)
def test_a_connecting_point_shows_as_a_hole_in_the_ink(transition, ink, colors):
    """Which is why a ring is filled rather than left open.

    A transition is solid ink, so an open ring drawn on one is a rim around
    black and reads as a dot again.  Filled with the colour of the paper it is a
    hole in the bar with an accent rim, which can be seen and aimed at.
    """

    accent = QColor(colors.accent)
    before = ink.at(ink.painted(transition, colors), down=-TRANSITION_HALF_HEIGHT)

    transition.ports_visible = True
    image = ink.painted(transition, colors)
    around = ink.window(image, 0.0, -TRANSITION_HALF_HEIGHT, PORT_RADIUS)

    assert ink.nearest(before, QColor(colors.text), QColor(colors.editor)) == QColor(
        colors.text
    )
    assert ink.at(image, down=-TRANSITION_HALF_HEIGHT) == QColor(colors.editor)
    assert ink.holds(around, accent)
