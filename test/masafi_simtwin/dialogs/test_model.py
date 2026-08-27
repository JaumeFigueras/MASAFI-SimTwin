"""Tests for the New Model and Model Properties dialog."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QDialogButtonBox

from masafi_simtwin import project
from masafi_simtwin.dialogs.model import KIND_VALUES, ModelDialog
from masafi_simtwin.preferences import Preferences


@pytest.fixture
def preferences(tmp_path):
    """Give preferences of this test's own, with nothing chosen.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary directory pytest made.

    Returns
    -------
    masafi_simtwin.preferences.Preferences
        Preferences over an empty file.
    """

    return Preferences(
        QSettings(str(tmp_path / 'preferences.ini'), QSettings.Format.IniFormat)
    )


@pytest.fixture
def dialog(qtbot, preferences):
    """Build the dialog for a new model.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.
    preferences : masafi_simtwin.preferences.Preferences
        Where the default units come from.

    Returns
    -------
    masafi_simtwin.dialogs.model.ModelDialog
        The dialog, with nothing filled in.
    """

    widget = ModelDialog(preferences=preferences)
    qtbot.addWidget(widget)
    return widget


def ok_button(dialog):
    """Give the OK button of a dialog.

    Parameters
    ----------
    dialog : masafi_simtwin.dialogs.model.ModelDialog
        The dialog.

    Returns
    -------
    PyQt6.QtWidgets.QAbstractButton
        The button.
    """

    return dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)


# ----------------------------------------------------------------------
# What it asks
# ----------------------------------------------------------------------


def test_the_four_kinds_are_offered_in_order(dialog):
    """Petri net first, since it is the one that can be built."""

    values = [dialog.kind_combo.itemData(i) for i in range(dialog.kind_combo.count())]

    assert values == [kind.value for kind in KIND_VALUES]
    assert values[0] == project.ModelKind.PETRI_NET.value


def test_the_units_start_at_the_application_settings(qtbot, preferences):
    """A new model agrees with the settings unless it is told otherwise."""

    preferences.set_value('units/time', 'min')
    preferences.set_value('units/distance', 'km')
    dialog = ModelDialog(preferences=preferences)
    qtbot.addWidget(dialog)

    assert dialog.time_combo.currentData() == 'min'
    assert dialog.distance_combo.currentData() == 'km'


def test_a_model_needs_a_name(dialog):
    """OK stays disabled, and the dialog says what it is waiting for."""

    assert not ok_button(dialog).isEnabled()
    assert dialog.message_label.text() == 'Give the model a name.'

    dialog.name_edit.setText('Filling Station')
    assert ok_button(dialog).isEnabled()


def test_a_name_already_taken_is_refused(qtbot, preferences):
    """Two models of one name in a project would be two identical entries."""

    dialog = ModelDialog(preferences=preferences, taken=['Filling Station'])
    qtbot.addWidget(dialog)
    dialog.name_edit.setText('  filling station  ')

    assert not ok_button(dialog).isEnabled()
    assert 'already holds' in dialog.message_label.text()


# ----------------------------------------------------------------------
# Distance follows the kind
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ('kind', 'applies'),
    [
        (project.ModelKind.PETRI_NET, False),
        (project.ModelKind.PROCESS_FLOW, False),
        (project.ModelKind.PROCESS_2D, True),
        (project.ModelKind.PROCESS_3D, True),
    ],
)
def test_a_distance_unit_applies_only_where_there_is_distance(dialog, kind, applies):
    """A graph has no positions, so it has no distance to measure.

    ``isHidden`` rather than ``isVisible``: the dialog itself is not shown, so
    nothing in it is visible, but only the note is hidden on purpose.
    """

    dialog.kind_combo.setCurrentIndex(dialog.kind_combo.findData(kind.value))

    assert dialog.distance_combo.isEnabled() is applies
    assert dialog.distance_label.isEnabled() is applies
    assert dialog.distance_note.isHidden() is applies
    assert ('distance' in dialog.units()) is applies


def test_the_time_unit_always_applies(dialog):
    """Every kind of model runs in time."""

    for kind in KIND_VALUES:
        dialog.kind_combo.setCurrentIndex(dialog.kind_combo.findData(kind.value))
        assert 'time' in dialog.units()


# ----------------------------------------------------------------------
# What cannot be built yet
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    'kind',
    [
        project.ModelKind.PROCESS_FLOW,
        project.ModelKind.PROCESS_2D,
        project.ModelKind.PROCESS_3D,
    ],
)
def test_an_unimplemented_kind_is_refused_with_a_message(dialog, monkeypatch, kind):
    """Offered and refused, rather than hidden from the list."""

    shown = []
    monkeypatch.setattr(
        'masafi_simtwin.dialogs.model.QMessageBox.information',
        lambda *arguments, **keywords: shown.append(arguments[2]),
    )
    dialog.name_edit.setText('Something')
    dialog.kind_combo.setCurrentIndex(dialog.kind_combo.findData(kind.value))

    dialog.accept()

    assert len(shown) == 1
    assert dialog.result() != int(ModelDialog.DialogCode.Accepted)


def test_a_petri_net_is_accepted(dialog):
    """The one kind that can be built."""

    dialog.name_edit.setText('Filling Station')
    dialog.accept()

    assert dialog.result() == int(ModelDialog.DialogCode.Accepted)
    assert dialog.kind is project.ModelKind.PETRI_NET
    assert dialog.units() == {'time': 's'}


# ----------------------------------------------------------------------
# Changing a model rather than making one
# ----------------------------------------------------------------------


@pytest.fixture
def editing(qtbot, preferences):
    """Build the dialog over an existing model.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.
    preferences : masafi_simtwin.preferences.Preferences
        Where the default units would come from.

    Returns
    -------
    masafi_simtwin.dialogs.model.ModelDialog
        The dialog, filled in from a Petri net called *Filling*.
    """

    widget = ModelDialog(
        preferences=preferences,
        model={
            'uuid': 'u-1',
            'name': 'Filling',
            'kind': project.ModelKind.PETRI_NET.value,
            'units': {'time': 'min'},
        },
    )
    qtbot.addWidget(widget)
    return widget


def test_an_existing_model_fills_the_dialog(editing):
    """Its name, its kind and the units it was given."""

    assert editing.editing
    assert editing.name == 'Filling'
    assert editing.kind is project.ModelKind.PETRI_NET
    assert editing.time_combo.currentData() == 'min'


def test_the_kind_is_shown_but_cannot_be_changed(editing):
    """Settled at creation: visible, so that it is clear what it is."""

    assert editing.kind_combo.isEnabled() is False
    assert editing.kind_combo.currentText() == 'Petri Net'


def test_the_dialog_says_which_of_its_two_jobs_it_is_doing(dialog, editing):
    """The title is the only thing telling the two apart at a glance."""

    assert dialog.windowTitle() == 'New Model'
    assert editing.windowTitle() == 'Model Properties'


def test_an_unbuildable_kind_is_not_refused_when_only_being_renamed(
    qtbot, preferences, monkeypatch
):
    """A model that somehow exists can still be renamed; that is not building one."""

    shown = []
    monkeypatch.setattr(
        'masafi_simtwin.dialogs.model.QMessageBox.information',
        lambda *arguments, **keywords: shown.append(arguments[2]),
    )
    widget = ModelDialog(
        preferences=preferences,
        model={
            'uuid': 'u-1',
            'name': 'Flow',
            'kind': project.ModelKind.PROCESS_FLOW.value,
            'units': {'time': 's'},
        },
    )
    qtbot.addWidget(widget)

    widget.accept()

    assert shown == []
    assert widget.result() == int(ModelDialog.DialogCode.Accepted)
