"""The About dialog.

The layout is :mod:`~masafi_simtwin.dialogs.forms.about`, compiled from
``forms/about.ui``.  What the form cannot hold stays here: the two lines that
have to be formatted with a name and a version, and the logo, which the form
reserves the space for but cannot fill because the SVG is addressed through
:mod:`importlib.resources` rather than by a path.
"""

from __future__ import annotations

from importlib import resources

from PyQt6.QtWidgets import QDialog, QWidget

from masafi_simtwin import APPLICATION_NAME, __version__
from masafi_simtwin.dialogs.forms.ui_about import Ui_AboutDialog


class AboutDialog(QDialog, Ui_AboutDialog):
    """What the application is, which version of it, and under what licence.

    Parameters
    ----------
    parent : PyQt6.QtWidgets.QWidget, optional
        Parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowTitle(self.tr('About {0}').format(APPLICATION_NAME))
        self.version_label.setText(self.tr('Version {0}').format(__version__))
        self._load_logo()
        self.button_box.rejected.connect(self.reject)

    def _load_logo(self) -> None:
        """Render the logo shipped in ``resources`` into the space the form left."""

        path = resources.files('masafi_simtwin.resources') / 'logo.svg'
        with resources.as_file(path) as svg_path:
            self.logo_widget.load(str(svg_path))
