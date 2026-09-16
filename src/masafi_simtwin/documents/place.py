"""The place of a Petri net: a circle on the sheet.

A place is a circle of :data:`PLACE_DIAMETER` millimetres, drawn on the same
sheet the rulers measure, so its size is a size on paper rather than a number of
pixels: at life size it is one centimetre across on the screen and one
centimetre across when it is printed.

Everything a place shares with a transition — being dropped, being moved, being
held to the paper, and how its connecting points are drawn and found — is
:class:`~masafi_simtwin.documents.net_item.NetItem`.  What is here is the
circle: how big it is, how it is painted, and where an arc may be attached to
it.

Its **connecting points** are one every :data:`PORT_STEP_DEGREES`, so twelve of
them, counted from due east and turning the way a protractor does — the ``y``
axis of a scene points down, which is why :meth:`Place.port_offset` negates it.
Angles are the right answer here and only here: a circle is even the whole way
round, so points spread evenly by angle are points spread evenly on the paper.
A bar is not, and a transition says where its own go.

============  ===========================  ==========================
Part          Palette role                 Light / dark
============  ===========================  ==========================
Fill          ``Base``                     ``#ffffff`` / ``#1e1f22``
Outline       ``Text``                     ``#1e1f22`` / ``#dfe1e5``
Selected      ``Link``                     ``#3574f0`` / ``#548af7``
============  ===========================  ==========================

``Base`` is the ground the sheet is filled with, so a place is *the colour of
the paper* with a rim around it — white on white in the light scheme, which is
what was asked for, and the same relation rather than the same colours in the
dark one.  Inverting the light scheme literally would give a white rim glaring
off the dark sheet and a black disc reading as a hole cut in it; taking both
colours from the palette gives a place that sits on the paper in either scheme
and follows the theme without being told.

**Its tokens are drawn inside it**, in the ink of its rim — the accent while it
is selected.  Up to :data:`MAX_TOKEN_DOTS` they are dots, laid out in the fixed
patterns of :data:`TOKEN_LAYOUTS` so that a count is read at a glance, the way
the faces of a die are; more than that is the number, written
:data:`TOKEN_NUMBER_HEIGHT` millimetres tall and narrowed to
:data:`TOKEN_NUMBER_WIDTH` when it is long.  The number is a path, as an arc's
weight is — :func:`~masafi_simtwin.documents.net_item.glyph_path` — so it is a size
on the paper rather than in points.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QPainterPath

from masafi_simtwin import preferences
from masafi_simtwin.documents.ink import glyph_path, ink_colour, paper_colour
from masafi_simtwin.documents.net_item import (
    PORT_RADIUS,
    NetItem,
)

#: How far across a place is, in millimetres.  One centimetre.
PLACE_DIAMETER = 10.0

#: Half of it, which is what everything is drawn from.
PLACE_RADIUS = PLACE_DIAMETER / 2.0

#: How far apart the connecting points are, in degrees around the circle.
PORT_STEP_DEGREES = 30.0

#: How many there are, which is what the step comes to.
PORT_COUNT = int(round(360.0 / PORT_STEP_DEGREES))

#: The most tokens a place draws as dots; more are written as a number.
MAX_TOKEN_DOTS = 5

#: How far a token's dot reaches from its middle, in millimetres.
TOKEN_RADIUS = 0.8

#: Where each dot goes, from the centre of the place, by how many there are —
#: fixed patterns, as on the faces of a die, so a count is read at a glance
#: rather than counted.  Every dot is clear of the others and of the rim.
TOKEN_LAYOUTS: dict[int, tuple[tuple[float, float], ...]] = {
    1: ((0.0, 0.0),),
    2: ((-1.5, 0.0), (1.5, 0.0)),
    3: ((0.0, -1.5), (-1.5, 1.2), (1.5, 1.2)),
    4: ((-1.5, -1.5), (1.5, -1.5), (-1.5, 1.5), (1.5, 1.5)),
    5: ((-1.8, -1.8), (1.8, -1.8), (0.0, 0.0), (-1.8, 1.8), (1.8, 1.8)),
}

#: How tall a number of tokens is written, in millimetres.
TOKEN_NUMBER_HEIGHT = 4.0

#: How wide it may grow before it is narrowed to fit inside the circle.
TOKEN_NUMBER_WIDTH = 7.0


class Place(NetItem):
    """One place of a Petri net, drawn as a circle.

    See :class:`~masafi_simtwin.documents.net_item.NetItem` for the parameters
    and for everything a place shares with the rest of a net.

    """

    #: What a place counts as when an arc is drawn to it.
    GROUP = 'place'

    #: Which kind of text its caption is, and so how it is written.
    ROLE = preferences.PLACE

    def __init__(self, *arguments, **keywords) -> None:
        super().__init__(*arguments, **keywords)
        self._tokens = 0

    @property
    def tokens(self) -> int:
        """int: How many tokens the place holds before the net is run — its
        initial marking.  Nought until it is given some."""

        return self._tokens

    @tokens.setter
    def tokens(self, value: int) -> None:
        """Set the tokens, and draw them.

        Parameters
        ----------
        value : int
            The tokens.  Below nought is not a number of tokens, so it is held
            at nought.  They are drawn inside the circle, so the place is
            repainted and its geometry is left as it is.
        """

        value = max(int(value), 0)
        if value != self._tokens:
            self._tokens = value
            self.update()

    def token_marks(self) -> QPainterPath:
        """Build what the tokens are drawn as, to be filled with ink.

        Returns
        -------
        PyQt6.QtGui.QPainterPath
            The dots of :data:`TOKEN_LAYOUTS` for up to :data:`MAX_TOKEN_DOTS`
            tokens, the number centred on the place for more, and an empty path
            for none.
        """

        marks = QPainterPath()
        if self._tokens == 0:
            return marks
        if self._tokens <= MAX_TOKEN_DOTS:
            for across, down in TOKEN_LAYOUTS[self._tokens]:
                marks.addEllipse(QPointF(across, down), TOKEN_RADIUS, TOKEN_RADIUS)
            return marks
        return glyph_path(
            str(self._tokens),
            TOKEN_NUMBER_HEIGHT,
            TOKEN_NUMBER_WIDTH,
            family=self.appearance().font,
        )

    #: What it may be joined to.  A Petri net is bipartite.
    CONNECTS_TO = ('transition',)

    #: What an invented name begins with: ``P1``, ``P2`` and so on.
    NAME_PREFIX = 'P'

    @staticmethod
    def port_angles() -> list[float]:
        """Give the angle of every connecting point, in degrees.

        Returns
        -------
        list of float
            :data:`PORT_COUNT` angles, one every :data:`PORT_STEP_DEGREES`,
            counted from due east and turning the way a protractor does.
        """

        return [index * PORT_STEP_DEGREES for index in range(PORT_COUNT)]

    @staticmethod
    def port_offset(angle: float) -> QPointF:
        """Give where one connecting point is, relative to the centre.

        A circle has the easy answer: every point of its boundary is one radius
        from the centre, so the angle is the whole of the question.  The ``y``
        axis of a scene points down, so it is negated: 90° is the top of the
        circle, which is what anyone reading a protractor expects.

        Parameters
        ----------
        angle : float
            The angle, in degrees from due east.

        Returns
        -------
        PyQt6.QtCore.QPointF
            The offset, in millimetres, from the centre of the place.
        """

        radians = math.radians(angle)
        return QPointF(
            PLACE_RADIUS * math.cos(radians),
            -PLACE_RADIUS * math.sin(radians),
        )

    def ports(self) -> list[QPointF]:
        """Give every connecting point, in the item's own coordinates.

        Returns
        -------
        list of PyQt6.QtCore.QPointF
            The twelve points, in the order of :meth:`port_angles`.
        """

        return [self.port_offset(angle) for angle in self.port_angles()]

    def boundingRect(self) -> QRectF:  # noqa: N802  (Qt naming)
        """Give what the circle itself is drawn inside.

        What is written beside a place is a child item with a rectangle of its
        own and is not in this one.

        Returns
        -------
        PyQt6.QtCore.QRectF
            The circle, its thickest outline and its connecting points, which
            stand on the circle and so reach half their own width beyond it.
        """

        reach = PLACE_RADIUS + max(PORT_RADIUS, self.drawn_width() / 2.0)
        return QRectF(-reach, -reach, reach * 2.0, reach * 2.0)

    def shape(self) -> QPainterPath:
        """Give what can be taken hold of, which is the circle itself.

        The bounding rectangle is a square, and a place picked up by a corner of
        it is a place picked up where nothing is drawn.

        Returns
        -------
        PyQt6.QtGui.QPainterPath
            The disc, out to the middle of its outline.
        """

        path = QPainterPath()
        reach = PLACE_RADIUS + self.outline_width() / 2.0
        path.addEllipse(QPointF(0.0, 0.0), reach, reach)
        return path

    def paint_item(self, painter, option) -> None:
        """Draw the circle — the colour of the paper, with a rim — and its tokens.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the view.
        option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
            What the view knows about drawing this item, its palette included.
        """

        painter.setPen(self.pen(option))
        painter.setBrush(paper_colour(option))
        painter.drawEllipse(QPointF(0.0, 0.0), PLACE_RADIUS, PLACE_RADIUS)

        marks = self.token_marks()
        if not marks.isEmpty():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(
                ink_colour(self.isSelected(), option, self.line_appearance().colour)
            )
            painter.drawPath(marks)
