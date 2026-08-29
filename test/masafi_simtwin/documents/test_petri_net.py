"""Tests for the Petri net document."""

from __future__ import annotations

import pytest

from masafi_simtwin.documents.canvas import Canvas
from masafi_simtwin.documents.petri_net import PetriNetEditor
from masafi_simtwin.documents.ruler import MILLIMETRES

#: The manifest entry the editor is opened over.
MODEL = {
    'uuid': '7f3f9c6a',
    'name': 'Filling Station',
    'kind': 'petri-net',
    'file': 'models/Filling_Station.mfst',
    'units': {'time': 's'},
}


@pytest.fixture
def editor(qtbot):
    """Build a Petri net document over a model.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    masafi_simtwin.documents.petri_net.PetriNetEditor
        The document.
    """

    widget = PetriNetEditor(MODEL)
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    return widget


def test_the_editor_knows_which_model_it_shows(editor):
    """Its UUID is also the key of its tab, so the two cannot drift apart."""

    assert editor.model_id == MODEL['uuid']
    assert editor.model_name == 'Filling Station'


def test_a_net_is_drawn_on_a_ruled_sheet(editor):
    """The same sheet the flow and 2D documents will be drawn on."""

    assert isinstance(editor, Canvas)
    assert all(ruler.unit is MILLIMETRES for ruler in editor.rulers)


def test_an_empty_net_says_it_is_empty(editor):
    """Honestly: there is nothing to put on it yet."""

    assert editor.view.empty_note
