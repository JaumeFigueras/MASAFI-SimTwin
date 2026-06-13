"""
Canvas QGraphicsView with zoom and pan.

Provides a zoomable, pannable viewport for the model and animation canvases.
Zoom anchors under the mouse cursor; panning is activated by the middle
mouse button.  Keyboard shortcuts are also supported.
"""

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QPainter, QWheelEvent
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView, QWidget


class CanvasView(QGraphicsView):
    """
    Zoomable and pannable graphics view for the model canvas.

    Parameters
    ----------
    scene : QGraphicsScene
        The scene to display.
    parent : QWidget, optional
        Parent widget.

    Signals
    -------
    zoom_changed : float
        Emitted whenever the zoom level changes.
        The argument is the new zoom factor (1.0 = 100 %).
    cursor_moved : float, float
        Emitted on mouse movement over the viewport.
        Arguments are the scene-coordinate *(x, y)* of the cursor.

    Attributes
    ----------
    ZOOM_FACTOR : float
        Multiplicative step applied per zoom-in / zoom-out action.
    ZOOM_MIN : float
        Minimum permitted zoom factor.
    ZOOM_MAX : float
        Maximum permitted zoom factor.
    """

    ZOOM_FACTOR: float = 1.15
    ZOOM_MIN:    float = 0.05
    ZOOM_MAX:    float = 20.0

    zoom_changed = pyqtSignal(float)          # new zoom level
    cursor_moved = pyqtSignal(float, float)   # scene x, y

    def __init__(
        self,
        scene: QGraphicsScene,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(scene, parent)
        self._zoom: float             = 1.0
        self._pan_last_pos: QPoint | None = None

        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setMouseTracking(True)

    # ------------------------------------------------------------------
    # Public zoom API
    # ------------------------------------------------------------------

    @property
    def zoom(self) -> float:
        """Current zoom factor (read-only). 1.0 corresponds to 100 %."""
        return self._zoom

    def zoom_in(self) -> None:
        """Increase the zoom level by one step."""
        self._apply_zoom(self.ZOOM_FACTOR)

    def zoom_out(self) -> None:
        """Decrease the zoom level by one step."""
        self._apply_zoom(1.0 / self.ZOOM_FACTOR)

    def zoom_fit(self) -> None:
        """Scale and centre the view so the entire scene rect is visible."""
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = self.transform().m11()    # read back the resulting scale
        self.zoom_changed.emit(self._zoom)

    def zoom_reset(self) -> None:
        """Reset zoom to 100 % and centre the origin."""
        self.resetTransform()
        self._zoom = 1.0
        self.centerOn(0.0, 0.0)
        self.zoom_changed.emit(self._zoom)

    # ------------------------------------------------------------------
    # Event overrides
    # ------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        """
        Zoom with *Ctrl + scroll*; scroll normally otherwise.

        Parameters
        ----------
        event : QWheelEvent
            The wheel event.
        """
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta  = event.angleDelta().y()
            factor = self.ZOOM_FACTOR if delta > 0 else 1.0 / self.ZOOM_FACTOR
            self._apply_zoom(factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Activate middle-button pan or delegate to the base class.

        Parameters
        ----------
        event : QMouseEvent
            The mouse press event.
        """
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_last_pos = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Pan on middle-button drag; emit cursor position otherwise.

        Parameters
        ----------
        event : QMouseEvent
            The mouse move event.
        """
        if (
            event.buttons() & Qt.MouseButton.MiddleButton
            and self._pan_last_pos is not None
        ):
            current = event.position().toPoint()
            delta   = current - self._pan_last_pos
            self._pan_last_pos = current
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            event.accept()
        else:
            scene_pos = self.mapToScene(event.position().toPoint())
            self.cursor_moved.emit(scene_pos.x(), scene_pos.y())
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Deactivate middle-button pan on button release.

        Parameters
        ----------
        event : QMouseEvent
            The mouse release event.
        """
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_last_pos = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        """
        Keyboard zoom shortcuts.

        ``+`` / ``=``  zoom in  |  ``-``  zoom out  |
        ``0``  reset   |  ``F``  fit to window

        Parameters
        ----------
        event : QKeyEvent
            The key event.
        """
        key = event.key()
        if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_in()
        elif key == Qt.Key.Key_Minus:
            self.zoom_out()
        elif key == Qt.Key.Key_0:
            self.zoom_reset()
        elif key == Qt.Key.Key_F:
            self.zoom_fit()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_zoom(self, factor: float) -> None:
        """
        Apply a multiplicative zoom *factor*, clamped to the allowed range.

        Parameters
        ----------
        factor : float
            Multiplicative zoom step (> 1 zooms in, < 1 zooms out).
        """
        new_zoom = self._zoom * factor
        if not (self.ZOOM_MIN <= new_zoom <= self.ZOOM_MAX):
            return
        self._zoom = new_zoom
        self.scale(factor, factor)
        self.zoom_changed.emit(self._zoom)