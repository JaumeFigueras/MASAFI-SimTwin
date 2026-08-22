"""Tests for the dockable tool panes."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QWidget

from masafi_simtwin.tool_pane import (
    DEFAULT_PANE_HEIGHT,
    DEFAULT_PANE_WIDTH,
    MINIMUM_PANE_HEIGHT,
    MINIMUM_PANE_WIDTH,
    ToolPane,
)


@pytest.fixture
def pane(qtbot):
    """Build a pane with the default placeholder content.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    masafi_simtwin.tool_pane.ToolPane
        The pane.
    """

    widget = ToolPane('Project')
    qtbot.addWidget(widget)
    return widget


def test_the_title_is_shown_in_the_header(pane):
    """The header carries the title, and so does the dock itself."""

    assert pane.title == 'Project'
    assert pane.windowTitle() == 'Project'
    assert pane.titleBarWidget().objectName() == 'ToolPaneHeader'


def test_an_empty_pane_shows_a_placeholder(pane):
    """A pane with no tool behind it says so rather than showing a blank."""

    placeholder = pane.widget().findChild(QLabel, 'ToolPanePlaceholder')

    assert placeholder is not None
    assert placeholder.text() == 'Not implemented yet'


def test_content_is_held_as_given(qtbot):
    """A pane built with content holds it instead of the placeholder."""

    content = QWidget()
    widget = ToolPane('Libraries', content)
    qtbot.addWidget(widget)

    assert content.parentWidget() is widget.widget()
    assert widget.widget().findChild(QLabel, 'ToolPanePlaceholder') is None


def test_the_header_closes_the_pane(pane, qtbot):
    """The button in the header hides the pane."""

    pane.show()
    qtbot.waitExposed(pane)
    close_button = pane.titleBarWidget().findChild(QWidget, 'ToolPaneClose')

    close_button.click()

    assert not pane.isVisible()


def test_the_close_button_carries_an_icon(pane):
    """The header button is drawn with a Material Symbol like every other icon."""

    close_button = pane.titleBarWidget().findChild(QWidget, 'ToolPaneClose')

    assert not close_button.icon().isNull()


def test_a_pane_at_the_side_is_measured_by_its_width(pane):
    """A side pane is resized horizontally and stops at a readable width."""

    assert pane.area == Qt.DockWidgetArea.LeftDockWidgetArea
    assert pane.resize_orientation == Qt.Orientation.Horizontal
    assert pane.minimumWidth() == MINIMUM_PANE_WIDTH
    assert pane.default_size == DEFAULT_PANE_WIDTH


def test_a_pane_at_the_bottom_is_measured_by_its_height(qtbot):
    """A bottom pane is resized vertically and stops at a usable height."""

    widget = ToolPane('Problems', area=Qt.DockWidgetArea.BottomDockWidgetArea)
    qtbot.addWidget(widget)

    assert widget.area == Qt.DockWidgetArea.BottomDockWidgetArea
    assert widget.resize_orientation == Qt.Orientation.Vertical
    assert widget.minimumHeight() == MINIMUM_PANE_HEIGHT
    assert widget.default_size == DEFAULT_PANE_HEIGHT


@pytest.mark.parametrize(
    'area', [Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.BottomDockWidgetArea]
)
def test_a_pane_is_pinned_to_its_own_area(qtbot, area):
    """A pane is allowed in the area it was built for and in no other."""

    widget = ToolPane('Anywhere', area=area)
    qtbot.addWidget(widget)

    assert widget.allowedAreas() == area
