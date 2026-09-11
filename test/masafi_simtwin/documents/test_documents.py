"""Tests for which editor a model opens as."""

from __future__ import annotations

from masafi_simtwin import project
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QWidget

from masafi_simtwin.documents import (
    EDITORS,
    NEW_MODEL_FILES,
    PetriNetEditor,
    editor_for,
    file_of,
    load_file,
    new_model_file,
)
from simtwin_adapters.sim_petri import pnml
from simtwin_core.petri_net import NetDocument


def test_a_petri_net_opens_as_the_petri_net_editor(qtbot):
    """The one kind that is built opens on its canvas."""

    editor = editor_for({'uuid': 'u', 'name': 'Net', 'kind': 'petri-net'})
    qtbot.addWidget(editor)

    assert isinstance(editor, PetriNetEditor)
    assert editor.model_name == 'Net'


def test_a_kind_that_is_not_built_yet_has_no_editor():
    """Three of the four kinds are offered before they exist; this is that."""

    assert editor_for({'uuid': 'u', 'name': 'Flow', 'kind': 'process-flow'}) is None


def test_an_unknown_kind_has_no_editor():
    """A manifest written by a later version says nothing this one can open."""

    assert editor_for({'uuid': 'u', 'name': 'Odd', 'kind': 'quantum-flow'}) is None
    assert editor_for({}) is None


def test_the_editors_are_the_implemented_kinds():
    """Two statements of one fact, which have to agree.

    :data:`masafi_simtwin.project.IMPLEMENTED_KINDS` is what the model dialog
    lets a user create; ``EDITORS`` is what the window can open.  A kind in one
    and not the other is either a model that cannot be opened or an editor
    nothing reaches.
    """

    assert set(EDITORS) == set(project.IMPLEMENTED_KINDS)


def test_what_a_new_model_starts_as_is_said_for_the_implemented_kinds():
    """The same fact again: a kind that can be made has a file to start from."""

    assert set(NEW_MODEL_FILES) == set(project.IMPLEMENTED_KINDS)


def test_a_new_petri_net_is_an_empty_net_of_its_own_model():
    """Written by the adapter, and carrying its model's identity from the first
    file onwards."""

    written = new_model_file(project.ModelKind.PETRI_NET, 'model-uuid')

    assert pnml.from_pnml(written) == NetDocument(model_uuid='model-uuid')


def test_a_kind_that_is_not_built_yet_has_no_file_to_start_from():
    """The model dialog refuses one before this is reached."""

    with pytest.raises(ValueError, match='process-flow'):
        new_model_file(project.ModelKind.PROCESS_FLOW, 'model-uuid')



def test_a_petri_net_is_saved_as_the_pnml_of_what_is_drawn(qtbot):
    """What the window writes, without knowing what the document is."""

    editor = editor_for({'uuid': 'model-uuid', 'name': 'Net', 'kind': 'petri-net'})
    qtbot.addWidget(editor)
    editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))

    assert pnml.from_pnml(file_of(editor)) == editor.to_document()


def test_a_saved_petri_net_is_drawn_again_in_a_new_editor(qtbot):
    """What the window reads back into a tab."""

    model = {'uuid': 'model-uuid', 'name': 'Net', 'kind': 'petri-net'}
    editor = editor_for(model)
    qtbot.addWidget(editor)
    editor.add_element('pt-petri-net', 'transition', QPointF(40.0, 20.0))

    again = editor_for(model)
    qtbot.addWidget(again)
    load_file(again, file_of(editor))

    assert again.to_document() == editor.to_document()


def test_a_document_that_is_not_saved_gives_nothing_to_write(qtbot):
    """So the window can pass every document it has."""

    widget = QWidget()
    qtbot.addWidget(widget)

    assert file_of(widget) is None


def test_a_file_that_is_not_a_net_is_refused_as_a_value_error(qtbot):
    """What the window reports instead of opening a tab."""

    editor = editor_for({'uuid': 'u', 'name': 'Net', 'kind': 'petri-net'})
    qtbot.addWidget(editor)

    with pytest.raises(ValueError):
        load_file(editor, b'not a net')
