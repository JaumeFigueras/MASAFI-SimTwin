"""
Model QGraphicsScene.

Provides the 2-D drawing canvas scene for the process-flow model editor.
The scene draws an adaptive two-level dot/line grid in the background and
will host model blocks (``QGraphicsSvgItem``) and connectors
(``QGraphicsPathItem``) as child items.
"""

from PyQt6.QtCore import QLineF, QRectF
from PyQt6.QtGui import QColor, QPainter, QPalette, QPen
from PyQt6.QtWidgets import QApplication, QGraphicsScene, QWidget


class ModelScene(QGraphicsScene):
    """
    Graphics scene for the process-flow model canvas.

    The background renders a two-level grid (minor and major lines) whose
    colour adapts automatically to the active light/dark palette.

    Parameters
    ----------
    parent : QWidget, optional
        Parent object.

    Attributes
    ----------
    GRID_MINOR : int
        Spacing in scene units between adjacent minor grid lines.
    GRID_MAJOR : int
        Spacing in scene units between adjacent major grid lines.
        Must be an integer multiple of ``GRID_MINOR``.
    """

    GRID_MINOR: int = 20
    GRID_MAJOR: int = 100   # every 5 minor lines

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSceneRect(-5_000.0, -5_000.0, 10_000.0, 10_000.0)
        self._grid_visible: bool = True

        # Repaint whenever the OS colour scheme changes
        app = QApplication.instance()
        if app is not None and hasattr(app.styleHints(), "colorSchemeChanged"):
            app.styleHints().colorSchemeChanged.connect(self.update)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def grid_visible(self) -> bool:
        """
        Whether the background grid is rendered.

        Setting this property triggers a full scene repaint.
        """
        return self._grid_visible

    @grid_visible.setter
    def grid_visible(self, value: bool) -> None:
        if value != self._grid_visible:
            self._grid_visible = value
            self.update()

    # ------------------------------------------------------------------
    # Background rendering
    # ------------------------------------------------------------------

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        """
        Paint the scene background (solid fill + optional grid).

        Parameters
        ----------
        painter : QPainter
            Active painter provided by the graphics framework.
        rect : QRectF
            The exposed rectangle in scene coordinates.
        """
        # Theme-aware background fill
        palette  = QApplication.palette()
        bg_color = palette.color(QPalette.ColorRole.Base)
        painter.fillRect(rect, bg_color)

        if not self._grid_visible:
            return

        # Adaptive grid colours: light lines on dark, dark on light
        is_dark = bg_color.lightness() < 128
        minor_color = QColor(255, 255, 255, 25) if is_dark else QColor(0, 0, 0, 25)
        major_color = QColor(255, 255, 255, 60) if is_dark else QColor(0, 0, 0, 60)

        self._draw_grid(painter, rect, minor_color, major_color)

    def _draw_grid(
        self,
        painter: QPainter,
        rect: QRectF,
        minor_color: QColor,
        major_color: QColor,
    ) -> None:
        """
        Draw minor and major grid lines inside *rect*.

        Parameters
        ----------
        painter : QPainter
            Active painter.
        rect : QRectF
            Visible rectangle in scene coordinates.
        minor_color : QColor
            Pen colour for minor grid lines.
        major_color : QColor
            Pen colour for major grid lines.
        """
        left  = int(rect.left())   - (int(rect.left())   % self.GRID_MINOR)
        top   = int(rect.top())    - (int(rect.top())    % self.GRID_MINOR)
        right = int(rect.right())  + self.GRID_MINOR
        bot   = int(rect.bottom()) + self.GRID_MINOR

        minor_lines: list[QLineF] = []
        major_lines: list[QLineF] = []

        x = left
        while x <= right:
            line = QLineF(x, rect.top(), x, rect.bottom())
            (major_lines if x % self.GRID_MAJOR == 0 else minor_lines).append(line)
            x += self.GRID_MINOR

        y = top
        while y <= bot:
            line = QLineF(rect.left(), y, rect.right(), y)
            (major_lines if y % self.GRID_MAJOR == 0 else minor_lines).append(line)
            y += self.GRID_MINOR

        minor_pen = QPen(minor_color)
        minor_pen.setCosmetic(True)       # 1 px regardless of zoom
        major_pen = QPen(major_color)
        major_pen.setCosmetic(True)

        if minor_lines:
            painter.setPen(minor_pen)
            painter.drawLines(minor_lines)

        if major_lines:
            painter.setPen(major_pen)
            painter.drawLines(major_lines)