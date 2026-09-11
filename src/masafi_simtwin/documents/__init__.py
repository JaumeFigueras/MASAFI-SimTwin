"""The document types the tabbed area holds.

One module per kind of document, over the sheet they share:
:mod:`~masafi_simtwin.documents.canvas` is the ruled canvas every drawn document
is built on and :mod:`~masafi_simtwin.documents.ruler` is what rules it.  One
place — :func:`editor_for` — says which kind a model opens as.  A kind with no editor yet has no entry, and the
window reports that rather than opening an empty tab: three of the four kinds
of :class:`~masafi_simtwin.project.ModelKind` are offered before they are built,
so *not yet* is an ordinary answer here rather than an error.

These widgets are the view of a model and nothing more.  Reading a model out of
a project and writing one back belongs to the document layer that is still to
come, and when it arrives an editor is given the document rather than reaching
for the archive itself.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import QWidget

from masafi_simtwin.documents.arc import Arc
from masafi_simtwin.documents.canvas import Canvas
from masafi_simtwin.documents.petri_net import PetriNetEditor
from masafi_simtwin.documents.place import Place
from masafi_simtwin.documents.transition import Transition
from masafi_simtwin.project import ModelKind
from simtwin_adapters.sim_petri import pnml
from simtwin_core.petri_net import NetDocument

#: The editor each kind of model opens as.  A kind that is absent cannot be
#: opened yet, which is what :data:`~masafi_simtwin.project.IMPLEMENTED_KINDS`
#: says on the other side of the same fact.
EDITORS: dict[ModelKind, type[QWidget]] = {
    ModelKind.PETRI_NET: PetriNetEditor,
}


def empty_petri_net(identifier: str) -> bytes:
    """Give the file of a new Petri net model: an empty P/T net.

    Written by the adapter, like every later save of it, and carrying its
    model's UUID from the first file onwards.

    Parameters
    ----------
    identifier : str
        The model's UUID.

    Returns
    -------
    bytes
        The PNML document.
    """

    return pnml.to_pnml(NetDocument(model_uuid=identifier))


#: What the file of a new model of each kind holds, made from its UUID.  A kind
#: that is absent cannot be made yet, the same fact
#: :data:`~masafi_simtwin.project.IMPLEMENTED_KINDS` and :data:`EDITORS` state.
NEW_MODEL_FILES: dict[ModelKind, Callable[[str], bytes]] = {
    ModelKind.PETRI_NET: empty_petri_net,
}

__all__ = [
    'EDITORS',
    'Arc',
    'Canvas',
    'NEW_MODEL_FILES',
    'PetriNetEditor',
    'Place',
    'Transition',
    'editor_for',
    'file_of',
    'load_file',
    'new_model_file',
]


def file_of(document: QWidget) -> bytes | None:
    """Give what an open document is saved as.

    The one place that knows a Petri net editor is saved as PNML, so the window
    saves documents without knowing what any of them is.

    Parameters
    ----------
    document : PyQt6.QtWidgets.QWidget
        The document.

    Returns
    -------
    bytes, optional
        The file, or ``None`` for a document that is not saved.

    Raises
    ------
    ValueError
        When the document holds something that cannot be written yet — a Petri
        net holding an inhibitor arc, which is
        :class:`~simtwin_adapters.sim_petri.pnml.UnsupportedNet`.
    """

    if isinstance(document, PetriNetEditor):
        return pnml.to_pnml(document.to_document())
    return None


def load_file(document: QWidget, data: bytes) -> None:
    """Draw a saved file in a document that has just been made for it.

    Parameters
    ----------
    document : PyQt6.QtWidgets.QWidget
        The document, as :func:`editor_for` made it.
    data : bytes
        The file, as :func:`file_of` gave it.

    Raises
    ------
    ValueError
        When the file is not one the document can draw —
        :class:`~simtwin_adapters.sim_petri.pnml.UnreadableNet`.
    """

    if isinstance(document, PetriNetEditor):
        document.load_document(pnml.from_pnml(data))


def new_model_file(kind: ModelKind, identifier: str) -> bytes:
    """Give what the file of a new model of a kind holds.

    Parameters
    ----------
    kind : masafi_simtwin.project.ModelKind
        The kind of model.
    identifier : str
        Its UUID.

    Returns
    -------
    bytes
        The file.

    Raises
    ------
    ValueError
        When that kind of model cannot be made yet — which the model dialog
        refuses before this is ever reached.
    """

    make = NEW_MODEL_FILES.get(ModelKind(kind))
    if make is None:
        raise ValueError(f'a {ModelKind(kind).value} model cannot be made yet')
    return make(identifier)


def editor_for(model: dict, parent: QWidget | None = None) -> QWidget | None:
    """Build the editor a model opens as.

    Parameters
    ----------
    model : dict
        The model's entry in the project manifest.
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.  The tab widget takes ownership as soon as the document
        is added, so this is normally left out.

    Returns
    -------
    PyQt6.QtWidgets.QWidget, optional
        The editor, or ``None`` when that kind of model cannot be opened yet —
        which includes a manifest naming a kind this version does not know.
    """

    try:
        kind = ModelKind(model.get('kind'))
    except ValueError:
        return None
    editor = EDITORS.get(kind)
    return None if editor is None else editor(model, parent)
