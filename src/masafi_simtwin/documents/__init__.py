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

from PyQt6.QtWidgets import QWidget

from masafi_simtwin.documents.arc import Arc
from masafi_simtwin.documents.canvas import Canvas
from masafi_simtwin.documents.petri_net import PetriNetEditor
from masafi_simtwin.documents.place import Place
from masafi_simtwin.documents.transition import Transition
from masafi_simtwin.project import ModelKind

#: The editor each kind of model opens as.  A kind that is absent cannot be
#: opened yet, which is what :data:`~masafi_simtwin.project.IMPLEMENTED_KINDS`
#: says on the other side of the same fact.
EDITORS: dict[ModelKind, type[QWidget]] = {
    ModelKind.PETRI_NET: PetriNetEditor,
}

__all__ = [
    'EDITORS',
    'Arc',
    'Canvas',
    'PetriNetEditor',
    'Place',
    'Transition',
    'editor_for',
]


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
