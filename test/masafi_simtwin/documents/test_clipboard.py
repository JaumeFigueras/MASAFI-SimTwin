"""Tests for what a piece of a net is while it is on the clipboard."""

from __future__ import annotations

import json

import pytest
from PyQt6.QtCore import QMimeData
from PyQt6.QtWidgets import QApplication

from masafi_simtwin.documents import clipboard
from simtwin_core.petri_net import ArcData, NetDocument, PlaceData, TransitionData

#: A place, a transition and the arc between them: the smallest piece worth
#: copying.
PIECE = NetDocument(
    model_uuid='7f3f9c6a',
    places=(PlaceData('p', 'P1', (20.0, 20.0), 3, 'Bottles waiting'),),
    transitions=(TransitionData('t', 'T1', (60.0, 20.0), 'Fill', True),),
    arcs=(ArcData('a', 'p', 't', 0, 10, 2),),
)


@pytest.fixture(autouse=True)
def empty_clipboard(qapp):
    """Leave the clipboard as it was found, so no test reads another's copy.

    Parameters
    ----------
    qapp : PyQt6.QtWidgets.QApplication
        The application, which is what owns the clipboard.
    """

    QApplication.clipboard().clear()
    yield
    QApplication.clipboard().clear()


def test_a_piece_of_net_survives_the_clipboard(qapp):
    """Everything about it: the tokens, the descriptions, which way round the
    transition is, and how the arc is attached and weighted."""

    clipboard.put(PIECE)

    assert clipboard.taken() == PIECE
    assert clipboard.holds_a_net()


def test_the_payload_is_the_applications_own_type(qapp):
    """So that text copied out of anything else is not mistaken for a net."""

    data = clipboard.mime_data(PIECE)

    assert data.hasFormat(clipboard.NET_MIME)
    assert clipboard.NET_MIME.startswith('application/x-masafi')


def test_an_empty_clipboard_holds_no_net(qapp):
    """Which is what *Paste* asks before it offers itself."""

    assert clipboard.taken() is None
    assert not clipboard.holds_a_net()


def test_text_copied_out_of_another_application_is_not_a_net(qapp):
    """A clipboard is anybody's to write into."""

    QApplication.clipboard().setText('P1, T1 and an arc between them')

    assert clipboard.taken() is None
    assert not clipboard.holds_a_net()


def test_nothing_at_all_is_not_a_net():
    """There is no clipboard to ask when a drop carries no data."""

    assert clipboard.from_mime(None) is None


@pytest.mark.parametrize(
    'payload',
    [b'not json at all', b'"a net, honestly"', b'{"places": []}', b'\xff\xfe'],
    ids=['not-json', 'not-a-net', 'half-a-net', 'not-text'],
)
def test_rubbish_under_the_right_type_is_no_net_either(payload):
    """Read the way a file is read: nothing at all rather than an error."""

    data = QMimeData()
    data.setData(clipboard.NET_MIME, payload)

    assert clipboard.from_mime(data) is None


def test_a_net_that_could_not_be_drawn_is_refused_as_it_is_read():
    """An arc to a node that is not there never reaches a sheet."""

    written = json.loads(bytes(clipboard.mime_data(PIECE).data(clipboard.NET_MIME)))
    written['arcs'][0]['target'] = 'gone'
    data = QMimeData()
    data.setData(clipboard.NET_MIME, json.dumps(written).encode('utf-8'))

    assert clipboard.from_mime(data) is None
