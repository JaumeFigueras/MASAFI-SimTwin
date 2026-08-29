"""Tests for the tabbed document area."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QTabBar, QWidget

from masafi_simtwin.document_area import DocumentArea
from masafi_simtwin.theme import PANE_GAP


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
    assert area.showing_placeholder


def test_adding_a_document_shows_the_tabs(area):
    """The first document swaps the placeholder for the tab widget."""

    index = area.add_document(QWidget(), 'Process Flow')

    assert index == 0
    assert area.document_count == 1
    assert not area.showing_placeholder
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
    assert area.showing_placeholder


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


def test_the_documents_are_a_card_inset_from_the_window(area):
    """Tabs and content share one rounded card, held off the edges of the area."""

    margins = area.layout().contentsMargins()
    card = area.findChild(QWidget, 'DocumentCard')

    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        PANE_GAP,
        PANE_GAP,
        PANE_GAP,
        PANE_GAP,
    )
    assert card is not None
    assert card.isAncestorOf(area.tabs)


def test_a_document_opened_under_a_key_is_found_again(area):
    """The key is what makes a document one document rather than several."""

    widget = QWidget()
    area.add_document(widget, 'Filling Station', key='u1')

    assert area.document('u1') is widget
    assert area.document('u2') is None


def test_showing_an_open_document_raises_its_tab(area):
    """Asking for a model already open is a tab change, not a second copy."""

    first, second = QWidget(), QWidget()
    area.add_document(first, 'First', key='u1')
    area.add_document(second, 'Second', key='u2')

    assert area.show_document('u1')
    assert area.tabs.currentWidget() is first
    assert area.document_count == 2


def test_showing_a_document_that_is_not_open_says_so(area):
    """Which is what tells the caller to open it."""

    assert not area.show_document('u1')


def test_a_key_is_never_open_twice(area):
    """Opening one again replaces it, rather than leaving two views of one file."""

    area.add_document(QWidget(), 'First', key='u1')
    second = QWidget()
    area.add_document(second, 'First again', key='u1')

    assert area.document_count == 1
    assert area.document('u1') is second


def test_closing_a_document_forgets_its_key(area):
    """So that the model can be opened again afterwards."""

    area.add_document(QWidget(), 'First', key='u1')
    area.close_document(0)

    assert area.document('u1') is None
    assert not area.show_document('u1')


def test_a_document_can_be_closed_by_its_key(area):
    """Which is how a deleted model takes its tab with it."""

    area.add_document(QWidget(), 'First', key='u1')
    area.add_document(QWidget(), 'Second', key='u2')
    area.close_document_for('u1')

    assert area.document_count == 1
    assert area.tabs.tabText(0) == 'Second'


def test_closing_a_key_that_is_not_open_is_harmless(area):
    """Deleting a model that was never opened closes nothing."""

    area.add_document(QWidget(), 'First', key='u1')
    area.close_document_for('u2')

    assert area.document_count == 1


def test_a_document_can_be_retitled_by_its_key(area):
    """A model renamed keeps the tab it is in, under its new name."""

    area.add_document(QWidget(), 'Filling Station', key='u1')
    area.set_document_title('u1', 'Filling', 'models/Filling_Station.mfst')

    assert area.tabs.tabText(0) == 'Filling'
    assert area.tabs.tabToolTip(0) == 'models/Filling_Station.mfst'


def test_retitling_the_current_document_is_reported(area, qtbot):
    """The status bar shows the current document, so it has to hear the change."""

    area.add_document(QWidget(), 'Filling Station', key='u1')

    with qtbot.waitSignal(area.current_document_changed, timeout=1000) as blocker:
        area.set_document_title('u1', 'Filling')

    assert blocker.args == ['Filling']


def test_closing_every_document_empties_the_area(area):
    """Which is what closing a project comes to."""

    area.add_document(QWidget(), 'First', key='u1')
    area.add_document(QWidget(), 'Second', key='u2')
    area.close_all_documents()

    assert area.document_count == 0
    assert area.showing_placeholder
    assert area.document('u1') is None


def test_a_tab_carries_a_tool_tip(area):
    """A title too long for the tab bar can still be read under the pointer."""

    area.add_document(QWidget(), 'Filling Station', tool_tip='models/Filling_Station.mfst')
    area.add_document(QWidget(), 'Bare')

    assert area.tabs.tabToolTip(0) == 'models/Filling_Station.mfst'
    assert area.tabs.tabToolTip(1) == 'Bare'
