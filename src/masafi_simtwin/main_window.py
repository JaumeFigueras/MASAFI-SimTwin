"""
Main application window.

Provides the top-level shell: menu bar, main toolbar, status bar and
the central :class:`~masafi_simtwin.ui.tdi_area.TDIArea`.
"""

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QToolBar,
    QWidget,
)

from src.masafi_simtwin.ui.tdi_area import TDIArea

_APP_VERSION = "0.1.0"


class MainWindow(QMainWindow):
    """
    Top-level application window.

    Parameters
    ----------
    parent : QWidget, optional
        Parent widget (``None`` for a top-level window).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(
            self.tr("Masafi-SimTwin \u2014 Discrete Event Simulator")
        )
        self.setMinimumSize(QSize(1024, 768))

        # Central TDI widget
        self._tdi = TDIArea(self)
        self.setCentralWidget(self._tdi)

        # Status-bar labels (initialised in _build_status_bar)
        self._lbl_zoom:   QLabel | None = None
        self._lbl_cursor: QLabel | None = None

        self._build_menu_bar()
        self._build_tool_bar()
        self._build_status_bar()

        # Wire TDI signals AFTER status bar exists
        self._tdi.currentChanged.connect(self._on_current_tab_changed)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu_bar(self) -> None:
        """Create and populate the application menu bar."""
        mb = self.menuBar()

        # ── File ──────────────────────────────────────────────────────
        file_menu = mb.addMenu(self.tr("&File"))

        act_new = QAction(self.tr("&New Model"), self)
        act_new.setShortcut(QKeySequence.StandardKey.New)
        act_new.setStatusTip(self.tr("Create a new simulation model"))
        act_new.triggered.connect(self._on_new_model)
        file_menu.addAction(act_new)

        act_open = QAction(self.tr("&Open\u2026"), self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.setStatusTip(self.tr("Open an existing model file"))
        act_open.triggered.connect(self._on_open)
        file_menu.addAction(act_open)

        act_save = QAction(self.tr("&Save"), self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self._on_save)
        file_menu.addAction(act_save)

        act_save_as = QAction(self.tr("Save &As\u2026"), self)
        act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        act_save_as.triggered.connect(self._on_save_as)
        file_menu.addAction(act_save_as)

        file_menu.addSeparator()

        act_quit = QAction(self.tr("&Quit"), self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # ── Edit ──────────────────────────────────────────────────────
        edit_menu = mb.addMenu(self.tr("&Edit"))

        act_undo = QAction(self.tr("&Undo"), self)
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(act_undo)

        act_redo = QAction(self.tr("&Redo"), self)
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(act_redo)

        edit_menu.addSeparator()

        for label, shortcut in (
            (self.tr("Cu&t"),   QKeySequence.StandardKey.Cut),
            (self.tr("&Copy"),  QKeySequence.StandardKey.Copy),
            (self.tr("&Paste"), QKeySequence.StandardKey.Paste),
        ):
            act = QAction(label, self)
            act.setShortcut(shortcut)
            edit_menu.addAction(act)

        # ── View ──────────────────────────────────────────────────────
        view_menu = mb.addMenu(self.tr("&View"))

        act_zi = QAction(self.tr("Zoom &In"),       self)
        act_zo = QAction(self.tr("Zoom &Out"),      self)
        act_zf = QAction(self.tr("&Fit to Window"), self)
        act_zi.setShortcut(QKeySequence.StandardKey.ZoomIn)
        act_zo.setShortcut(QKeySequence.StandardKey.ZoomOut)
        act_zi.triggered.connect(self._tdi.zoom_in)
        act_zo.triggered.connect(self._tdi.zoom_out)
        act_zf.triggered.connect(self._tdi.zoom_fit)
        view_menu.addActions([act_zi, act_zo, act_zf])

        # ── Simulation ────────────────────────────────────────────────
        sim_menu = mb.addMenu(self.tr("&Simulation"))

        act_run   = QAction(self.tr("&Run"),   self)
        act_pause = QAction(self.tr("&Pause"), self)
        act_stop  = QAction(self.tr("&Stop"),  self)
        act_run.setShortcut(Qt.Key.Key_F5)
        act_pause.setShortcut(Qt.Key.Key_F6)
        act_stop.setShortcut(Qt.Key.Key_F7)
        act_run.triggered.connect(self._on_run)
        act_pause.triggered.connect(self._on_pause)
        act_stop.triggered.connect(self._on_stop)
        sim_menu.addActions([act_run, act_pause, act_stop])

        # ── Help ──────────────────────────────────────────────────────
        help_menu = mb.addMenu(self.tr("&Help"))
        act_about = QAction(self.tr("&About Masafi-SimTwin\u2026"), self)
        act_about.triggered.connect(self._on_about)
        help_menu.addAction(act_about)

    def _build_tool_bar(self) -> None:
        """Create the main toolbar."""
        tb = QToolBar(self.tr("Main Toolbar"), self)
        tb.setMovable(False)
        tb.setObjectName("mainToolBar")
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        for label in (self.tr("New"), self.tr("Open"), self.tr("Save")):
            tb.addAction(label)
        tb.addSeparator()
        for label in (self.tr("Run"), self.tr("Pause"), self.tr("Stop")):
            tb.addAction(label)

    def _build_status_bar(self) -> None:
        """
        Create and configure the status bar.

        Adds two permanent right-aligned labels:

        * ``_lbl_cursor`` — scene coordinates under the pointer.
        * ``_lbl_zoom``   — current zoom percentage.
        """
        sb = QStatusBar(self)
        self.setStatusBar(sb)

        self._lbl_cursor = QLabel("x: 0.0   y: 0.0")
        self._lbl_cursor.setMinimumWidth(150)
        self._lbl_cursor.setToolTip(
            self.tr("Cursor position in scene coordinates")
        )

        self._lbl_zoom = QLabel("100 %")
        self._lbl_zoom.setMinimumWidth(60)
        self._lbl_zoom.setToolTip(self.tr("Current zoom level"))

        sb.addPermanentWidget(self._lbl_cursor)
        sb.addPermanentWidget(self._lbl_zoom)
        sb.showMessage(self.tr("Ready"))

    # ------------------------------------------------------------------
    # Public helpers  (called by child widgets via signals)
    # ------------------------------------------------------------------

    def update_zoom_label(self, zoom: float) -> None:
        """
        Update the zoom-level indicator in the status bar.

        Parameters
        ----------
        zoom : float
            Current zoom factor (1.0 = 100 %).
        """
        if self._lbl_zoom is not None:
            self._lbl_zoom.setText(f"{zoom * 100:.0f} %")

    def update_cursor_label(self, x: float, y: float) -> None:
        """
        Update the cursor-position indicator in the status bar.

        Parameters
        ----------
        x : float
            Horizontal scene coordinate.
        y : float
            Vertical scene coordinate.
        """
        if self._lbl_cursor is not None:
            self._lbl_cursor.setText(f"x: {x:,.1f}   y: {y:,.1f}")

    # ------------------------------------------------------------------
    # Slots – File menu
    # ------------------------------------------------------------------

    def _on_new_model(self) -> None:
        """Open a new, empty model tab in the TDI area."""
        self._tdi.add_model_tab()
        self.statusBar().showMessage(self.tr("New model created"), 3000)

    def _on_open(self) -> None:
        """Show the open-file dialog (not yet implemented)."""
        # TODO: QFileDialog → deserialise model
        self.statusBar().showMessage(self.tr("Open: not yet implemented"), 3000)

    def _on_save(self) -> None:
        """Save the active model (not yet implemented)."""
        # TODO: serialise active tab's scene
        self.statusBar().showMessage(self.tr("Save: not yet implemented"), 3000)

    def _on_save_as(self) -> None:
        """Show the save-as dialog (not yet implemented)."""
        # TODO: QFileDialog → serialise model to chosen path
        self.statusBar().showMessage(
            self.tr("Save As: not yet implemented"), 3000
        )

    # ------------------------------------------------------------------
    # Slots – Simulation menu
    # ------------------------------------------------------------------

    def _on_run(self) -> None:
        """Start or resume the simulation (not yet implemented)."""
        self.statusBar().showMessage(self.tr("Simulation started"), 3000)

    def _on_pause(self) -> None:
        """Pause the running simulation (not yet implemented)."""
        self.statusBar().showMessage(self.tr("Simulation paused"), 3000)

    def _on_stop(self) -> None:
        """Stop and reset the simulation (not yet implemented)."""
        self.statusBar().showMessage(self.tr("Simulation stopped"), 3000)

    # ------------------------------------------------------------------
    # Slots – Help menu
    # ------------------------------------------------------------------

    def _on_about(self) -> None:
        """Display the About dialog."""
        QMessageBox.about(
            self,
            self.tr("About Masafi-SimTwin"),
            self.tr(
                "<b>Masafi-SimTwin</b> v{version}<br/><br/>"
                "Discrete Event Simulation modelling and animation tool."
                "<br/><br/>"
                "Licensed under the GNU General Public Licence v3 or later."
            ).format(version=_APP_VERSION),
        )

    # ------------------------------------------------------------------
    # Slots – TDI
    # ------------------------------------------------------------------

    def _on_current_tab_changed(self, index: int) -> None:
        """
        Respond to the active TDI tab changing.

        Resets the status-bar labels to reflect the newly focused tab.

        Parameters
        ----------
        index : int
            Index of the newly selected tab (−1 when all tabs are closed).
        """
        if index < 0:
            if self._lbl_zoom   is not None:
                self._lbl_zoom.setText("— %")
            if self._lbl_cursor is not None:
                self._lbl_cursor.setText("x: —   y: —")
            return

        # Sync zoom label with the newly active tab's current zoom
        widget = self._tdi.currentWidget()
        if hasattr(widget, "view"):
            self.update_zoom_label(widget.view.zoom)
        else:
            if self._lbl_zoom is not None:
                self._lbl_zoom.setText("— %")