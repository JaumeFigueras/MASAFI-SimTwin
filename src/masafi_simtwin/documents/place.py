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
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QPainterPath, QPalette

from masafi_simtwin.documents.net_item import (
    ITEM_PEN,
    ITEM_PEN_SELECTED,
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


class Place(NetItem):
    """One place of a Petri net, drawn as a circle.

    See :class:`~masafi_simtwin.documents.net_item.NetItem` for the parameters
    and for everything a place shares with the rest of a net.
    """

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
        """Give what the place is drawn inside.

        Returns
        -------
        PyQt6.QtCore.QRectF
            The circle, its thickest outline and its connecting points, which
            stand on the circle and so reach half their own width beyond it.
        """

        reach = PLACE_RADIUS + max(PORT_RADIUS, ITEM_PEN_SELECTED / 2.0)
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
        reach = PLACE_RADIUS + ITEM_PEN / 2.0
        path.addEllipse(QPointF(0.0, 0.0), reach, reach)
        return path

    def paint_item(self, painter, option) -> None:
        """Draw the circle: the colour of the paper, with a rim around it.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the view.
        option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
            What the view knows about drawing this item, its palette included.
        """

        painter.setPen(self.pen(option))
        painter.setBrush(option.palette.color(QPalette.ColorRole.Base))
        painter.drawEllipse(QPointF(0.0, 0.0), PLACE_RADIUS, PLACE_RADIUS)
