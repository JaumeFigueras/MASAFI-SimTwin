"""The Petri net document: the sheet a net is drawn on.

The editor is a :class:`~masafi_simtwin.documents.canvas.Canvas` — the ruled
sheet, its grid, its zoom and its panning — and what it adds is the net: which
model it is showing, and in time the places, transitions, arcs and tokens on it.
Those items are the next piece of work and are deliberately not invented here.

The sheet is measured in millimetres like every other document of the
application.  A Petri net has no distance unit of its own, its places having no
position that means anything to the simulation, but the *drawing* of one has a
size — which is what the rulers show and what a printed sheet would be.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from masafi_simtwin.documents.canvas import Canvas
from masafi_simtwin.documents.ruler import MILLIMETRES, RulerUnit


class PetriNetEditor(Canvas):
    """The sheet one Petri net is drawn on.

    Parameters
    ----------
    model : dict, optional
        The model's entry in the project manifest — its ``uuid``, ``name``,
        ``kind`` and ``units``.  The editor keeps it so that it can say which
        model it is showing; nothing is read back out of the project.
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.
    unit : masafi_simtwin.documents.ruler.RulerUnit, optional
        What the rulers count in, millimetres by default.

    Attributes
    ----------
    model : dict
        The manifest entry the editor was opened for.
    """

    def __init__(
        self,
        model: dict | None = None,
        parent: QWidget | None = None,
        unit: RulerUnit = MILLIMETRES,
    ) -> None:
        super().__init__(unit, parent)
        self.setObjectName('PetriNetEditor')
        self.model = dict(model or {})
        self.view.empty_note = self.tr('The Petri net canvas is not built yet')

    @property
    def model_id(self) -> str:
        """str: The UUID of the model on the sheet, which is also its tab key."""

        return self.model.get('uuid', '')

    @property
    def model_name(self) -> str:
        """str: What the model is called, which is what its tab says."""

        return self.model.get('name', '')
