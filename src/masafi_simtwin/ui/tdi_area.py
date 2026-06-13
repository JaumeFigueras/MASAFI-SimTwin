"""
Tabbed Document Interface (TDI) area.

The :class:`TDIArea` is the central widget of the main window.  It
manages document tabs – model-editor, 2-D animation and 3-D animation –
and exposes a uniform zoom interface that delegates to whichever tab is
currently active.
"""

from PyQt6.QtWidgets import QTabWidget, QWidget

from src.masafi_simtwin.ui.tabs.model_tab import ModelTab

# Uncomment when implemented:
# from masafi_simtwin.ui.tabs.animation_2d_tab import Animation2DTab
# from masafi_simtwin.ui.tabs.animation_3d_tab import Animation3DTab


class TDIArea(QTabWidget):
    """
    Tabbed Document Interface central area.

    Parameters
    ----------
    parent : QWidget, optional
        Parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.setTabPosition(QTabWidget.TabPosition.North)
        self.tabCloseRequested.connect(self._on_tab_close_requested)

    # ------------------------------------------------------------------
    # Tab factory methods
    # ------------------------------------------------------------------

    def add_model_tab(self, title: str = "") -> ModelTab:
        """
        Open a new model-editor tab.

        Parameters
        ----------
        title : str, optional
            Tab label.  Defaults to ``"Model <n>"`` where *n* is the
            one-based count of existing model tabs.

        Returns
        -------
        ModelTab
            The newly created tab widget.
        """
        if not title:
            n = sum(
                1 for i in range(self.count())
                if isinstance(self.widget(i), ModelTab)
            ) + 1
            title = self.tr("Model {}").format(n)

        tab = ModelTab(self)
        index = self.addTab(tab, title)
        self.setCurrentIndex(index)
        return tab

    def add_animation_2d_tab(self, title: str = "") -> QWidget:
        """
        Open a new 2-D animation tab (stub).

        Parameters
        ----------
        title : str, optional
            Tab label.  Defaults to ``"2D Animation"``.

        Returns
        -------
        QWidget
            Placeholder – replace with ``Animation2DTab`` when implemented.
        """
        if not title:
            title = self.tr("2D Animation")
        # TODO: replace QWidget with Animation2DTab(self)
        placeholder = QWidget(self)
        index = self.addTab(placeholder, title)
        self.setCurrentIndex(index)
        return placeholder

    def add_animation_3d_tab(self, title: str = "") -> QWidget:
        """
        Open a new 3-D animation tab (stub).

        Parameters
        ----------
        title : str, optional
            Tab label.  Defaults to ``"3D Animation"``.

        Returns
        -------
        QWidget
            Placeholder – replace with ``Animation3DTab`` when implemented.
        """
        if not title:
            title = self.tr("3D Animation")
        # TODO: replace QWidget with Animation3DTab(self)
        placeholder = QWidget(self)
        index = self.addTab(placeholder, title)
        self.setCurrentIndex(index)
        return placeholder

    # ------------------------------------------------------------------
    # Zoom delegation
    # ------------------------------------------------------------------

    def zoom_in(self) -> None:
        """Delegate *zoom in* to the active tab."""
        w = self.currentWidget()
        if hasattr(w, "zoom_in"):
            w.zoom_in()

    def zoom_out(self) -> None:
        """Delegate *zoom out* to the active tab."""
        w = self.currentWidget()
        if hasattr(w, "zoom_out"):
            w.zoom_out()

    def zoom_fit(self) -> None:
        """Delegate *fit to window* to the active tab."""
        w = self.currentWidget()
        if hasattr(w, "zoom_fit"):
            w.zoom_fit()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_tab_close_requested(self, index: int) -> None:
        """
        Handle a tab-close request.

        Parameters
        ----------
        index : int
            Index of the tab to close.

        Notes
        -----
        TODO: prompt for unsaved changes before closing.
        """
        self.removeTab(index)