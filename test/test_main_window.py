# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024  Your Name
"""
Unit tests for the main window and core UI components.
"""

import pytest

from src.masafi_simtwin.main_window import MainWindow
from src.masafi_simtwin.ui.tdi_area import TDIArea
from src.masafi_simtwin.ui.tabs.model_tab import ModelTab


# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------

class TestMainWindow:
    """Tests for :class:`~masafi_simtwin.main_window.MainWindow`."""

    @pytest.fixture()
    def window(self, qtbot):
        """Provide a fresh MainWindow for each test."""
        w = MainWindow()
        qtbot.addWidget(w)
        return w

    def test_title_contains_app_name(self, window):
        assert "Masafi-SimTwin" in window.windowTitle()

    def test_central_widget_is_tdi_area(self, window):
        assert isinstance(window.centralWidget(), TDIArea)

    def test_minimum_size(self, window):
        assert window.minimumWidth()  >= 1024
        assert window.minimumHeight() >= 768

    def test_menu_bar_present(self, window):
        assert window.menuBar() is not None

    def test_status_bar_present(self, window):
        assert window.statusBar() is not None

    def test_update_zoom_label(self, window):
        window.update_zoom_label(1.5)
        assert "150" in window._lbl_zoom.text()

    def test_update_cursor_label(self, window):
        window.update_cursor_label(12.5, -7.3)
        text = window._lbl_cursor.text()
        assert "12" in text
        assert "7"  in text

    def test_new_model_adds_tab(self, window, qtbot):
        before = window._tdi.count()
        window._on_new_model()
        assert window._tdi.count() == before + 1


# ---------------------------------------------------------------------------
# TDIArea
# ---------------------------------------------------------------------------

class TestTDIArea:
    """Tests for :class:`~masafi_simtwin.ui.tdi_area.TDIArea`."""

    @pytest.fixture()
    def tdi(self, qtbot):
        area = TDIArea()
        qtbot.addWidget(area)
        return area

    def test_initially_empty(self, tdi):
        assert tdi.count() == 0

    def test_add_model_tab_increments_count(self, tdi):
        tdi.add_model_tab()
        assert tdi.count() == 1

    def test_add_model_tab_returns_model_tab(self, tdi):
        assert isinstance(tdi.add_model_tab(), ModelTab)

    def test_auto_title_is_non_empty(self, tdi):
        tdi.add_model_tab()
        assert tdi.tabText(0) != ""

    def test_custom_title(self, tdi):
        tdi.add_model_tab(title="MyModel")
        assert tdi.tabText(0) == "MyModel"

    def test_auto_title_increments(self, tdi):
        tdi.add_model_tab()
        tdi.add_model_tab()
        assert tdi.tabText(0) != tdi.tabText(1)

    def test_close_tab_removes_it(self, tdi):
        tdi.add_model_tab()
        tdi.tabCloseRequested.emit(0)
        assert tdi.count() == 0

    def test_zoom_in_delegates_to_active_tab(self, tdi):
        tab = tdi.add_model_tab()
        before = tab.view.zoom
        tdi.zoom_in()
        assert tab.view.zoom > before

    def test_zoom_out_delegates_to_active_tab(self, tdi):
        tab = tdi.add_model_tab()
        before = tab.view.zoom
        tdi.zoom_out()
        assert tab.view.zoom < before


# ---------------------------------------------------------------------------
# ModelTab / CanvasView
# ---------------------------------------------------------------------------

class TestModelTab:
    """Tests for :class:`~masafi_simtwin.ui.tabs.model_tab.ModelTab`."""

    @pytest.fixture()
    def tab(self, qtbot):
        t = ModelTab()
        qtbot.addWidget(t)
        return t

    def test_has_scene(self, tab):
        assert tab.scene is not None

    def test_has_view(self, tab):
        assert tab.view is not None

    def test_zoom_in_increases_zoom(self, tab):
        before = tab.view.zoom
        tab.zoom_in()
        assert tab.view.zoom > before

    def test_zoom_out_decreases_zoom(self, tab):
        before = tab.view.zoom
        tab.zoom_out()
        assert tab.view.zoom < before

    def test_zoom_clamped_at_minimum(self, tab):
        for _ in range(300):
            tab.zoom_out()
        assert tab.view.zoom >= tab.view.ZOOM_MIN

    def test_zoom_clamped_at_maximum(self, tab):
        for _ in range(300):
            tab.zoom_in()
        assert tab.view.zoom <= tab.view.ZOOM_MAX

    def test_zoom_reset_restores_100_percent(self, tab):
        tab.zoom_in()
        tab.zoom_in()
        tab.view.zoom_reset()
        assert tab.view.zoom == pytest.approx(1.0)