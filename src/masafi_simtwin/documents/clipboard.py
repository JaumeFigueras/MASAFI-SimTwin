"""What a piece of a net is while it is on the clipboard.

A copy is a **net**: the nodes that were selected and the arcs between them, as
a :class:`~simtwin_core.petri_net.NetDocument` like any other, written as the
plain data :func:`~simtwin_core.operations.encode_net` writes and carried under
:data:`NET_MIME`, a type of SimTwin's own.

It goes on the **system** clipboard rather than into a variable of the
application, which is what makes a copy work between two tabs, between two
windows, and between two projects opened one after the other — and it is why
the payload is bytes that mean something on their own rather than a handful of
scene items, which mean nothing anywhere but the sheet they were taken from.

A clipboard is **anybody's to write into**, so what comes back is read the way a
file is read: something that is not a net written this way is nothing at all
rather than an error, and a net that could not be drawn — an arc to a node that
is not there — is refused as it is read, before it reaches a sheet.

Nothing here knows what a paste *does*.  What a fragment becomes on the sheet it
lands on — new identities, new names, and where it goes — belongs to the
document that receives it; see
:meth:`~masafi_simtwin.documents.petri_net.PetriNetEditor.paste`.
"""

from __future__ import annotations

import json

from PyQt6.QtCore import QMimeData
from PyQt6.QtWidgets import QApplication

from simtwin_core import operations
from simtwin_core.petri_net import NetDocument

#: What a piece of a net is carried as.  A type of the application's own, so
#: that text copied out of anything else is not mistaken for a net.
NET_MIME = 'application/x-masafi-net'


def mime_data(fragment: NetDocument) -> QMimeData:
    """Wrap a piece of a net for the clipboard.

    Parameters
    ----------
    fragment : simtwin_core.petri_net.NetDocument
        The nodes and the arcs between them.

    Returns
    -------
    PyQt6.QtCore.QMimeData
        The payload, under :data:`NET_MIME`.
    """

    data = QMimeData()
    written = json.dumps(operations.encode_net(fragment), sort_keys=True)
    data.setData(NET_MIME, written.encode('utf-8'))
    return data


def from_mime(data: QMimeData | None) -> NetDocument | None:
    """Read a piece of a net back off the clipboard, if that is what it holds.

    The other half of :func:`mime_data`, here rather than where a paste happens
    so that the two cannot drift apart.

    Parameters
    ----------
    data : PyQt6.QtCore.QMimeData, optional
        What the clipboard holds.

    Returns
    -------
    simtwin_core.petri_net.NetDocument, optional
        The net, or ``None`` for anything that is not one — text copied out of
        another application, or bytes under this type that do not read as a net
        that could be drawn.
    """

    if data is None or not data.hasFormat(NET_MIME):
        return None
    try:
        return operations.decode_net(json.loads(bytes(data.data(NET_MIME)).decode('utf-8')))
    except (ValueError, UnicodeDecodeError):
        return None


def put(fragment: NetDocument) -> None:
    """Put a piece of a net on the system clipboard.

    Parameters
    ----------
    fragment : simtwin_core.petri_net.NetDocument
        The nodes and the arcs between them.
    """

    QApplication.clipboard().setMimeData(mime_data(fragment))


def taken() -> NetDocument | None:
    """Give the piece of a net the system clipboard holds, if it holds one.

    Returns
    -------
    simtwin_core.petri_net.NetDocument, optional
        The net, or ``None`` when the clipboard holds anything else.
    """

    return from_mime(QApplication.clipboard().mimeData())


def holds_a_net() -> bool:
    """Say whether there is a piece of a net to paste.

    The bytes are read rather than the type merely looked at, because a *Paste*
    that is offered and does nothing is worse than one that was never offered.

    Returns
    -------
    bool
        Whether the clipboard holds a net that could be drawn.
    """

    return taken() is not None
