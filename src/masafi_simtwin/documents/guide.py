"""The guides a sheet is aligned against.

A guide is the line dragged off a ruler and dropped on the sheet: it is drawn
across the whole of it, it belongs to the drawing rather than to the model, and
nothing is simulated by it.  Its one job is to be somewhere exact for things to
be lined up against, which is why it snaps as it moves.

A guide is a scene item rather than something painted over the view, so that
selecting one, dragging one and picking one out from under the pointer are the
scene's own work rather than hit-testing written again here.  It carries no
position of its own beyond :attr:`Guide.position` — the item's ``pos`` is the
position — and :meth:`Guide.itemChange` is where both the axis lock and the
snapping live, so a guide moved by the hand and a guide moved by the ruler it
came from are moved by exactly the same rule.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QPalette, QPen
from PyQt6.QtWidgets import QGraphicsItem

#: How far from a guide, in millimetres, the pointer may be and still take hold
#: of it.  A line one pixel wide is a line nobody can click on.
GUIDE_GRAB = 1.5

#: Guides are drawn over everything on the sheet: they are what the rest is
#: lined up against, so they are never hidden by it.
GUIDE_Z = 1000.0

#: Opacity, out of 255, of a guide that is not selected.
GUIDE_ALPHA = 185


class Guide(QGraphicsItem):
    """One alignment guide, across the whole sheet.

    Parameters
    ----------
    orientation : PyQt6.QtCore.Qt.Orientation
        ``Horizontal`` for a guide lying across the sheet, which is what the top
        ruler gives and what moves up and down; ``Vertical`` for one standing up
        it, from the left ruler.
    position : float
        Where it is, in scene millimetres: the ``y`` of a horizontal guide and
        the ``x`` of a vertical one.
    sheet : PyQt6.QtCore.QRectF
        The sheet the guide is drawn across.
    snap : collections.abc.Callable, optional
        What to round a position to as the guide moves.  The canvas passes its
        own, which follows the zoom; without one a guide goes where it is put.
    parent : PyQt6.QtWidgets.QGraphicsItem, optional
        Parent item.

    Attributes
    ----------
    orientation : PyQt6.QtCore.Qt.Orientation
        Which way the guide lies.
    """

    def __init__(
        self,
        orientation: Qt.Orientation,
        position: float,
        sheet: QRectF,
        snap: Callable[[float], float] | None = None,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self.orientation = orientation
        self._sheet = QRectF(sheet)
        self._snap = snap

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(GUIDE_Z)
        self.setCursor(
            Qt.CursorShape.SizeVerCursor if self.horizontal else Qt.CursorShape.SizeHorCursor
        )
        self.position = position

    def set_sheet(self, sheet: QRectF) -> None:
        """Draw across a sheet of a different size from now on.

        The sheet changes size when the page it is ruled into does.  A guide
        runs the length of it, so its geometry changes with it — and the scene
        has to be told before it does, or it goes on looking for the guide where
        the guide no longer is.

        Parameters
        ----------
        sheet : PyQt6.QtCore.QRectF
            The sheet as it now stands.
        """

        self.prepareGeometryChange()
        self._sheet = QRectF(sheet)

    @property
    def horizontal(self) -> bool:
        """bool: Whether the guide lies across the sheet rather than up it."""

        return self.orientation == Qt.Orientation.Horizontal

    @property
    def position(self) -> float:
        """float: Where the guide is, in scene millimetres, across its own axis."""

        return self.pos().y() if self.horizontal else self.pos().x()

    @position.setter
    def position(self, value: float) -> None:
        """Move the guide, which snaps and locks its axis on the way.

        Parameters
        ----------
        value : float
            Where to put it, in scene millimetres.
        """

        self.setPos(QPointF(0.0, value) if self.horizontal else QPointF(value, 0.0))

    # ------------------------------------------------------------------
    # Where the guide may go
    # ------------------------------------------------------------------

    def itemChange(self, change, value):  # noqa: N802  (Qt naming)
        """Hold a moving guide to its own axis, and to the snapping grid.

        This is the one place a guide's position is decided, so that one dragged
        by hand and one dragged off its ruler cannot end up under different
        rules.

        Parameters
        ----------
        change : PyQt6.QtWidgets.QGraphicsItem.GraphicsItemChange
            What is being changed.
        value : object
            What it is being changed to.

        Returns
        -------
        object
            What it is changed to instead.
        """

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            along = value.y() if self.horizontal else value.x()
            if self._snap is not None:
                along = self._snap(along)
            return QPointF(0.0, along) if self.horizontal else QPointF(along, 0.0)
        return super().itemChange(change, value)

    # ------------------------------------------------------------------
    # What the guide covers, and how it is drawn
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:  # noqa: N802  (Qt naming)
        """Give the band the guide is drawn and clicked in.

        Returns
        -------
        PyQt6.QtCore.QRectF
            The sheet's length by twice :data:`GUIDE_GRAB`, in the guide's own
            coordinates, so that the line can be taken hold of at all.
        """

        if self.horizontal:
            return QRectF(self._sheet.left(), -GUIDE_GRAB, self._sheet.width(), GUIDE_GRAB * 2.0)
        return QRectF(-GUIDE_GRAB, self._sheet.top(), GUIDE_GRAB * 2.0, self._sheet.height())

    def paint(self, painter, option, widget=None) -> None:
        """Draw the guide, dashed while it is selected.

The colour is the palette's ``Link``, which is where
        :data:`~masafi_simtwin.theme.ThemeColors.accent` is kept — ``Highlight``
        is the pale wash behind selected text, and a guide drawn in it is a
        guide nobody can see.  It is taken from the option rather than from a
        widget, an item having none, so that a guide follows the theme like
        everything else painted on the sheet.

        The pen is width nought, which is Qt's cosmetic hairline: one pixel at
        every zoom, rather than a line 1 mm thick.

        Parameters
        ----------
        painter : PyQt6.QtGui.QPainter
            The painter of the view.
        option : PyQt6.QtWidgets.QStyleOptionGraphicsItem
            What the view knows about drawing this item, its palette included.
        widget : PyQt6.QtWidgets.QWidget, optional
            The widget being painted on.
        """

        colour = option.palette.color(QPalette.ColorRole.Link)
        pen = QPen(colour, 0.0)
        if self.isSelected():
            pen.setStyle(Qt.PenStyle.DashLine)
        else:
            colour.setAlpha(GUIDE_ALPHA)
            pen.setColor(colour)

        painter.setPen(pen)
        if self.horizontal:
            painter.drawLine(QPointF(self._sheet.left(), 0.0), QPointF(self._sheet.right(), 0.0))
        else:
            painter.drawLine(QPointF(0.0, self._sheet.top()), QPointF(0.0, self._sheet.bottom()))
