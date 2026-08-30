"""Tests for the Arc dialog."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QDialogButtonBox

from masafi_simtwin.dialogs.arc import ArcDialog


@pytest.fixture
def dialog(qtbot):
    """Build the Arc dialog over an arc of weight three.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    masafi_simtwin.dialogs.arc.ArcDialog
        The dialog.
    """

    widget = ArcDialog(3)
    qtbot.addWidget(widget)
    return widget


def test_the_form_is_what_built_the_dialog(dialog):
    """Every widget the form declares is there under the name it was given."""

    assert dialog.weight_spin is not None
    assert dialog.weight_label.text() == 'Weight'
    assert dialog.hint_label.wordWrap()
    assert dialog.isModal()


def test_the_dialog_opens_on_what_the_arc_carries(dialog):
    """A dialog that opened on something else would be a dialog that lied."""

    assert dialog.weight == 3


def test_a_weight_below_one_is_not_offered(qtbot):
    """An arc that carries no tokens is an arc that is not there, so the spin
    box cannot be taken there and a weight from elsewhere is brought up to it."""

    widget = ArcDialog(0)
    qtbot.addWidget(widget)

    assert widget.weight_spin.minimum() == 1
    assert widget.weight == 1


def test_ok_and_cancel_are_both_offered(dialog):
    """Cancel is what makes the dialog safe to open by accident."""

    buttons = dialog.button_box.standardButtons()

    assert buttons & QDialogButtonBox.StandardButton.Ok
    assert buttons & QDialogButtonBox.StandardButton.Cancel


def test_the_weight_that_was_chosen_is_what_comes_back(dialog):
    """Which is the whole of what the dialog is asked."""

    dialog.weight_spin.setValue(7)

    assert dialog.weight == 7
