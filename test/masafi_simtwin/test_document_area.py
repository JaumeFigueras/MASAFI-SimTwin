"""Tests for the tabbed document area."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QTabBar, QWidget

from masafi_simtwin.document_area import DocumentArea


@pytest.fixture
def area(qtbot):
    """Build an empty document area.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    masafi_simtwin.document_area.DocumentArea
        The area.
    """

    widget = DocumentArea()
    qtbot.addWidget(widget)
    return widget


def test_starts_on_the_placeholder(area):
    """With nothing open the area shows its placeholder, not an empty tab bar."""

    assert area.document_count == 0
    assert area.currentWidget() is area._placeholder


def test_adding_a_document_shows_the_tabs(area):
    """The first document swaps the placeholder for the tab widget."""

    index = area.add_document(QWidget(), 'Process Flow')

    assert index == 0
    assert area.document_count == 1
    assert area.currentWidget() is area.tabs
    assert area.tabs.tabText(0) == 'Process Flow'


def test_adding_a_document_makes_it_current(area):
    """A newly opened document takes the focus of the tab bar."""

    area.add_document(QWidget(), 'First')
    area.add_document(QWidget(), 'Second')

    assert area.tabs.currentIndex() == 1


def test_current_document_is_reported(area, qtbot):
    """The area announces which document became current."""

    with qtbot.waitSignal(area.current_document_changed, timeout=1000) as blocker:
        area.add_document(QWidget(), 'Process Flow')

    assert blocker.args == ['Process Flow']


def test_closing_the_last_document_restores_the_placeholder(area):
    """Closing every tab puts the placeholder back."""

    area.add_document(QWidget(), 'Process Flow')
    area.close_document(0)

    assert area.document_count == 0
    assert area.currentWidget() is area._placeholder


def test_closing_an_absent_document_is_harmless(area):
    """Closing an index that holds nothing changes nothing."""

    area.add_document(QWidget(), 'Process Flow')
    area.close_document(7)

    assert area.document_count == 1


def test_each_tab_carries_a_themed_close_button(area, qtbot):
    """Tabs are closed with a Material Symbol button, not the style's own cross."""

    area.add_document(QWidget(), 'Process Flow')
    button = area.tabs.tabBar().tabButton(0, QTabBar.ButtonPosition.RightSide)

    assert button is not None
    assert not button.icon().isNull()


def test_the_close_button_closes_its_own_tab(area, qtbot):
    """A close button follows its document when the tabs are reordered."""

    first, second = QWidget(), QWidget()
    area.add_document(first, 'First')
    area.add_document(second, 'Second')
    area.tabs.tabBar().moveTab(0, 1)

    button = area.tabs.tabBar().tabButton(
        area.tabs.indexOf(first), QTabBar.ButtonPosition.RightSide
    )
    button.click()

    assert area.document_count == 1
    assert area.tabs.tabText(0) == 'Second'
