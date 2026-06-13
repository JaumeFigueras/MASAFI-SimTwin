"""
Model editor tab.

Composes a :class:`~masafi_simtwin.ui.tabs.model_scene.ModelScene` and a
:class:`~masafi_simtwin.ui.tabs.canvas_view.CanvasView` into a single tab
widget and exposes the zoom interface required by :class:`TDIArea`.
"""

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.masafi_simtwin.ui.tabs.canvas_view import CanvasView
from src.masafi_simtwin.ui.tabs.model_scene import ModelScene


class ModelTab(QWidget):
    """
    Tab widget for the process-flow model editor.

    Parameters
    ----------
    parent : QWidget, optional
        Parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = ModelScene(self)
        self._view  = CanvasView(self._scene, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._view)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def scene(self) -> ModelScene:
        """The underlying model scene."""
        return self._scene

    @property
    def view(self) -> CanvasView:
        """The canvas view displaying the scene."""
        return self._view

    # ------------------------------------------------------------------
    # Zoom delegation (satisfies TDIArea's duck-typed zoom interface)
    # ------------------------------------------------------------------

    def zoom_in(self) -> None:
        """Zoom in on the canvas."""
        self._view.zoom_in()

    def zoom_out(self) -> None:
        """Zoom out on the canvas."""
        self._view.zoom_out()

    def zoom_fit(self) -> None:
        """Fit the entire scene into the visible viewport."""
        self._view.zoom_fit()