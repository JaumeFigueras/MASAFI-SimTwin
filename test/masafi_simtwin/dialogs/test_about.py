"""Tests for the About dialog."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QDialogButtonBox

from masafi_simtwin import APPLICATION_NAME, __version__
from masafi_simtwin.dialogs.about import AboutDialog


@pytest.fixture
def dialog(qtbot):
    """Build the About dialog.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    masafi_simtwin.dialogs.about.AboutDialog
        The dialog.
    """

    widget = AboutDialog()
    qtbot.addWidget(widget)
    return widget


def test_the_form_is_what_built_the_dialog(dialog):
    """Every widget the form declares is there under the name it was given."""

    assert dialog.name_label.text() == APPLICATION_NAME
    assert dialog.summary_label.wordWrap()
    assert dialog.licence_label.text()
    assert dialog.isModal()


def test_the_formatted_lines_are_filled_in_by_the_class(dialog):
    """The two lines the form cannot hold are written by the dialog."""

    assert dialog.windowTitle() == f'About {APPLICATION_NAME}'
    assert dialog.version_label.text() == f'Version {__version__}'


def test_the_logo_is_loaded_into_the_space_the_form_reserved(dialog):
    """The form leaves the logo empty; the class renders the shipped SVG."""

    assert dialog.logo_widget.renderer().isValid()
    assert dialog.logo_widget.width() == 64


def test_the_close_button_is_a_standard_one(dialog):
    """Standard buttons are translated by Qt's own catalogue, not by ours."""

    box = dialog.button_box
    assert box.standardButtons() == QDialogButtonBox.StandardButton.Close
    assert box.button(QDialogButtonBox.StandardButton.Close) is not None


def test_closing_rejects_the_dialog(dialog, qtbot):
    """The close button ends the dialog rather than only hiding the button."""

    dialog.show()
    qtbot.waitExposed(dialog)
    dialog.button_box.button(QDialogButtonBox.StandardButton.Close).click()
    assert not dialog.isVisible()
    assert dialog.result() == int(AboutDialog.DialogCode.Rejected)
