"""Tests for the New Project dialog."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QDialogButtonBox

from masafi_simtwin import project
from masafi_simtwin.dialogs.new_project import NewProjectDialog, default_location


@pytest.fixture
def dialog(qtbot, tmp_path):
    """Build the dialog over a directory of this test's own.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.
    tmp_path : pathlib.Path
        The temporary directory pytest made.

    Returns
    -------
    masafi_simtwin.dialogs.new_project.NewProjectDialog
        The dialog, with the location filled in and no name.
    """

    widget = NewProjectDialog(location=str(tmp_path))
    qtbot.addWidget(widget)
    return widget


def ok_button(dialog):
    """Give the OK button of a dialog.

    Parameters
    ----------
    dialog : masafi_simtwin.dialogs.new_project.NewProjectDialog
        The dialog.

    Returns
    -------
    PyQt6.QtWidgets.QAbstractButton
        The button.
    """

    return dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)


# ----------------------------------------------------------------------
# What it offers
# ----------------------------------------------------------------------


def test_a_location_is_offered_before_anything_is_typed(dialog, tmp_path):
    """The dialog opens somewhere sensible rather than empty."""

    assert dialog.location == str(tmp_path)
    assert default_location()


def test_nothing_can_be_created_before_a_name_is_given(dialog):
    """OK stays disabled, and the dialog says what it is waiting for."""

    assert not ok_button(dialog).isEnabled()
    assert dialog.message_label.text() == 'Give the project a name.'


def test_the_path_is_shown_as_it_is_typed(dialog, tmp_path):
    """Where the file lands is never a surprise."""

    dialog.name_edit.setText('Bottling Line')
    assert dialog.path_label.text() == str(tmp_path / 'Bottling Line.mfstz')
    assert ok_button(dialog).isEnabled()
    assert dialog.message_label.text() == ''


def test_the_name_is_taken_without_the_spaces_around_it(dialog, tmp_path):
    """A trailing space is a typing accident, not part of the name."""

    dialog.name_edit.setText('  Bottling Line  ')
    assert dialog.name == 'Bottling Line'
    assert dialog.path_label.text() == str(tmp_path / 'Bottling Line.mfstz')


# ----------------------------------------------------------------------
# What it refuses
# ----------------------------------------------------------------------


def test_a_location_that_is_not_a_directory_is_refused(dialog, tmp_path):
    """Typed by hand, or left behind by a directory that has since gone."""

    dialog.name_edit.setText('Bottling Line')
    dialog.location_edit.setText(str(tmp_path / 'nowhere'))

    assert not ok_button(dialog).isEnabled()
    assert 'not a directory' in dialog.message_label.text()


def test_an_existing_project_is_refused(dialog, tmp_path):
    """The dialog says so rather than leaving it to the write to fail."""

    project.create(project.path_for(tmp_path, 'Bottling Line'), 'Bottling Line')
    dialog.name_edit.setText('Bottling Line')

    assert not ok_button(dialog).isEnabled()
    assert 'already there' in dialog.message_label.text()


def test_an_empty_location_is_refused(dialog):
    """Both fields are needed before there is a path at all."""

    dialog.name_edit.setText('Bottling Line')
    dialog.location_edit.setText('')

    assert not ok_button(dialog).isEnabled()
    assert dialog.target() is None


def test_accepting_a_dialog_with_a_problem_does_nothing(dialog):
    """Belt and braces: the Return key reaches accept past a disabled button."""

    dialog.accept()

    assert dialog.project_path is None
    assert dialog.result() != int(NewProjectDialog.DialogCode.Accepted)


# ----------------------------------------------------------------------
# What it answers with
# ----------------------------------------------------------------------


def test_accepting_settles_on_the_path_and_writes_nothing(dialog, tmp_path):
    """The dialog decides where; the window that opened it does the writing."""

    dialog.name_edit.setText('Bottling Line')
    dialog.accept()

    assert dialog.project_path == tmp_path / 'Bottling Line.mfstz'
    assert not dialog.project_path.exists()


def test_cancelling_settles_on_nothing(dialog):
    """There is no path to act on after a Cancel."""

    dialog.name_edit.setText('Bottling Line')
    dialog.reject()

    assert dialog.project_path is None
