"""Tests for which editor a model opens as."""

from __future__ import annotations

from masafi_simtwin import project
from masafi_simtwin.documents import EDITORS, PetriNetEditor, editor_for


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
