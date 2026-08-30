"""The transition of a Petri net: a solid bar on the sheet.

A transition is a bar :data:`TRANSITION_LENGTH` millimetres long and
:data:`TRANSITION_HEIGHT` high — a centimetre and a half again by two
millimetres — drawn on the same sheet the rulers measure, so those are
millimetres on paper as much as on the screen.

Everything it shares with a place — being dropped, being moved, being held to
the paper, and how its connecting points are drawn and found — is
:class:`~masafi_simtwin.documents.net_item.NetItem`.  What is here is the bar,
and where an arc may be attached to it.

Its **connecting points** are laid out along the edges rather than by angle,
because a bar eight times as long as it is high is not even the way a circle is:

* one in the **middle of each of the four edges** — the two ends, and the middle
  of the top and of the bottom, which is where an arc between two places stacked
  above one another meets it;
* on each **long** edge, :data:`PORTS_EACH_SIDE_OF_MIDDLE` more at each side of
  that middle one, so nine along the top and nine along the bottom, evenly
  spread.

That makes :data:`PORT_COUNT` of them.  *Evenly spread* is taken to the corners
as well as between the points: the edge is divided into
:data:`PORTS_ALONG_A_SIDE` + 1 equal parts and a point put at every division, so
the gap from the outermost point to the corner is the gap between any two
points, and nothing sits **on** a corner — a point on a corner belongs to two
edges and to neither.

============  ===========================  ==========================
Part          Palette role                 Light / dark
============  ===========================  ==========================
Fill          ``Text``                     ``#1e1f22`` / ``#dfe1e5``
Outline       ``Text``                     ``#1e1f22`` / ``#dfe1e5``
Selected      ``Link``, both               ``#3574f0`` / ``#548af7``
============  ===========================  ==========================

**A transition is filled with its own outline colour**, which is what makes it
black in the light scheme: a bar two millimetres high has no inside worth
seeing, so it is drawn as one solid stroke of ink rather than as an outline
around a sliver of paper.  The fill follows the outline wherever the outline
goes, so a selected transition is a solid bar of the accent rather than an
accent rim around a black one — which at this height would read as a bar that
had merely changed shade.

That is also the whole of the difference from a place, and it is the reason both
take their colours from the palette rather than from constants: a place is the
paper with ink around it, a transition is the ink, and both follow the theme
without being told which scheme they are in.

The bar lies **across** the sheet and cannot be stood up; see ``FUTURE.md``.
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QPainterPath

from masafi_simtwin.documents.net_item import (
    ITEM_PEN,
    ITEM_PEN_SELECTED,
    PORT_RADIUS,
    NetItem,
)

#: How long a transition is, in millimetres.  A centimetre and six.
TRANSITION_LENGTH = 16.0

#: How high it is, in millimetres.  Two of them.
TRANSITION_HEIGHT = 2.0

#: Half of each, which is what everything is drawn from — the item's position is
#: its centre, so the bar reaches this far each way.
TRANSITION_HALF_LENGTH = TRANSITION_LENGTH / 2.0
TRANSITION_HALF_HEIGHT = TRANSITION_HEIGHT / 2.0

#: How many connecting points a long edge carries at each side of its middle one.
PORTS_EACH_SIDE_OF_MIDDLE = 4

#: How many one long edge carries altogether: the middle one and the rest.
PORTS_ALONG_A_SIDE = PORTS_EACH_SIDE_OF_MIDDLE * 2 + 1

#: How far apart they are along it, in millimetres.  The edge is divided into
#: one more part than there are points, so the gap to each corner is the same as
#: the gap between two points and no point lands on a corner.
PORT_SPACING = TRANSITION_LENGTH / (PORTS_ALONG_A_SIDE + 1)

#: How many connecting points a transition has: the two ends, and a long edge's
#: worth along the top and along the bottom.
PORT_COUNT = PORTS_ALONG_A_SIDE * 2 + 2


class Transition(NetItem):
    """One transition of a Petri net, drawn as a solid bar.

    See :class:`~masafi_simtwin.documents.net_item.NetItem` for the parameters
    and for everything a transition shares with the rest of a net.
    """

    @staticmethod
    def port_offsets_along_an_edge() -> list[float]:
        """Give how far along a long edge each of its points is, from the middle.

        Returns
        -------
        list of float
            :data:`PORTS_ALONG_A_SIDE` offsets in millimetres, the leftmost
            first, nought among them — negative to the left of the middle and
            positive to the right.
        """

        return [
            (index - PORTS_EACH_SIDE_OF_MIDDLE) * PORT_SPACING
            for index in range(PORTS_ALONG_A_SIDE)
        ]

    def ports(self) -> list[QPointF]:
        """Give every connecting point, in the item's own coordinates.

        They are walked round the bar the way the angles of a place turn — from
        the right-hand end, up over the top, round to the left-hand end and back
        along the bottom — so the first of them is due east on both shapes and
        an arc tool reading the list finds them in the order they are drawn in.

        Returns
        -------
        list of PyQt6.QtCore.QPointF
            :data:`PORT_COUNT` points, in millimetres from the centre.
        """

        along = self.port_offsets_along_an_edge()
        return [
            QPointF(TRANSITION_HALF_LENGTH, 0.0),
            *(QPointF(offset, -TRANSITION_HALF_HEIGHT) for offset in reversed(along)),
            QPointF(-TRANSITION_HALF_LENGTH, 0.0),
            *(QPointF(offset, TRANSITION_HALF_HEIGHT) for offset in along),
        ]

    def bar(self) -> QRectF:
        """Give the bar itself, in the item's own coordinates.

        Returns
        -------
        PyQt6.QtCore.QRectF
            The rectangle, centred on the item's position.
        """

        return QRectF(
            -TRANSITION_HALF_LENGTH,
            -TRANSITION_HALF_HEIGHT,
            TRANSITION_LENGTH,
            TRANSITION_HEIGHT,
        )

    def boundingRect(self) -> QRectF:  # noqa: N802  (Qt naming)
        """Give what the transition is drawn inside.

        Returns
        -------
        PyQt6.QtCore.QRectF
            The bar, its thickest outline and its connecting points, which stand
            on the edges and so reach half their own width beyond them.
        """

        reach = max(PORT_RADIUS, ITEM_PEN_SELECTED / 2.0)
        return self.bar().adjusted(-reach, -reach, reach, reach)

    def shape(self) -> QPainterPath:
        """Give what can be taken hold of, which is the bar itself.

        The bounding rectangle stands a connecting point's width off every edge,
        and a bar picked up out there is a bar picked up where nothing is drawn.

        Returns
        -------
        PyQt6.QtGui.QPainterPath
            The bar, out to the middle of its outline.
        """

        path = QPainterPath()
        reach = ITEM_PEN / 2.0
        path.addRect(self.bar().adjusted(-reach, -reach, reach, reach))
        return path

    def paint_item(self, painter, option) -> None:
        """Draw the bar, filled with the colour it is outlined in.

        The pen is mitered, so the four corners come to a point;
        :meth:`~masafi_simtwin.documents.net_item.NetItem.pen` says why that has
        to be asked for.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the view.
        option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
            What the view knows about drawing this item, its palette included.
        """

        painter.setPen(self.pen(option))
        painter.setBrush(self.outline_colour(option))
        painter.drawRect(self.bar())
