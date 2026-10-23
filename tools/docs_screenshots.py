"""Take the screenshots the user manual shows, in every language it is in.

The application is driven offscreen, in the light theme, over a project made
for the purpose in a folder of its own, and every picture is taken of the real
window, menu or dialog — nothing is drawn by hand.  The desktop's own platform
theme, ``gtk3``, is asked for: offscreen Qt's default one knows no shortcut for
*Exit*, so the menus would not show ``Ctrl+Q`` as a desktop does.  The language is settled at
start-up, so each one is a process of its own: run without arguments, this
script runs itself once per language.

The pictures go into ``docs/source/using/manual/images/``.  The English one is
``name.png`` and every other language's ``name.<language>.png`` — what Sphinx's
``figure_language_filename`` looks for, so a page names the English picture
and each build finds its own.

Usage::

    make docs-screenshots
    .venv/bin/python tools/docs_screenshots.py --language ca
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Where the manual's pictures are kept.
IMAGES = ROOT / 'docs' / 'source' / 'using' / 'manual' / 'images'

#: The languages the manual is written in; the first is the one the pages name.
LANGUAGES = ('en', 'ca')

#: Where the example projects are made.  A fixed, short path, because the New
#: Project dialog shows it in full.
WORKSPACE = Path(tempfile.gettempdir()) / 'MASAFI-SimTwin' / 'Projects'

#: The example's words, in each language: the projects, the models, the net.
WORDS = {
    'en': {
        'project': 'Bottling Line',
        'others': ('Packaging Cell', 'Warehouse'),
        'model': 'Filling Station',
        'second': 'Capping Station',
        'new': 'Labelling',
        'waiting': 'Empty',
        'fill': 'Fill',
        'full': 'Full',
        'filler': 'Filler',
    },
    'ca': {
        'project': "Línia d'embotellament",
        'others': ("Cel·la d'embalatge", 'Magatzem'),
        'model': "Estació d'ompliment",
        'second': 'Estació de tapat',
        'new': 'Etiquetatge',
        'waiting': 'Buides',
        'fill': 'Omplir',
        'full': 'Plenes',
        'filler': 'Omplidora',
    },
}

#: How much room is left around a menu cut out of the window, in pixels.
MARGIN = 24


def main() -> int:
    """Take every picture, in one language or in all of them.

    Returns
    -------
    int
        The exit code: nought when every picture was taken.
    """

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--language', choices=LANGUAGES, help='one language only')
    arguments = parser.parse_args()
    if arguments.language:
        return shoot(arguments.language)
    for language in LANGUAGES:
        done = subprocess.run(
            [sys.executable, __file__, '--language', language],
            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_QPA_PLATFORMTHEME': 'gtk3'},
        )
        if done.returncode:
            return done.returncode
    return 0


def shoot(language: str) -> int:
    """Take every picture in one language.

    Parameters
    ----------
    language : str
        One of :data:`LANGUAGES`.

    Returns
    -------
    int
        Nought.
    """

    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PyQt6.QtCore import QSettings

    # Before the application exists: it reads the language as it is built.
    settings_directory = tempfile.mkdtemp(prefix='simtwin-screenshots-')
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, settings_directory)

    from masafi_simtwin.application import SimTwinApplication

    application = SimTwinApplication([sys.argv[0]])
    application.preferences.set_value('appearance/language', language)
    application.preferences.set_value('appearance/theme', 'light')
    application = _restarted(application)

    try:
        Shots(application, language, WORDS[language]).take()
    finally:
        shutil.rmtree(settings_directory, ignore_errors=True)
        shutil.rmtree(WORKSPACE.parent, ignore_errors=True)
    return 0


def _restarted(application):
    """Settle the language and the theme just stored, as a restart would.

    Parameters
    ----------
    application : masafi_simtwin.application.SimTwinApplication
        The application, built before the preferences were written.

    Returns
    -------
    masafi_simtwin.application.SimTwinApplication
        The same application, speaking the stored language in the stored theme.
    """

    from masafi_simtwin.theme import ColorScheme

    application.remove_translators()
    application._install_translators()
    application.theme.override = ColorScheme.LIGHT
    application.theme.apply()
    return application


class Shots:
    """The pictures of one language, taken in the order a person meets them.

    Parameters
    ----------
    application : masafi_simtwin.application.SimTwinApplication
        The application, already in its language and theme.
    language : str
        What the pictures are saved as.
    words : dict
        The example's names in that language.
    """

    def __init__(self, application, language: str, words: dict) -> None:
        self.application = application
        self.language = language
        self.words = words
        self.suffix = '' if language == LANGUAGES[0] else f'.{language}'

    # ------------------------------------------------------------------
    # The pictures
    # ------------------------------------------------------------------

    def take(self) -> None:
        """Take every picture."""

        from masafi_simtwin.main_window import MainWindow

        IMAGES.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(WORKSPACE.parent, ignore_errors=True)
        WORKSPACE.mkdir(parents=True)

        paths = self._make_projects()

        window = MainWindow()
        window.show()
        self.window = window
        self._settle()

        # The window as it opens, with nothing in it.
        self.save('window_start', self._window())
        self.save('start_menu', self._menu_shot(self._menu_bar_menu(0)))

        self.save('new_project', self._new_project_dialog())

        # The history the recent lists show, newest last.
        for path in (*paths[1:], paths[0]):
            window.open_project_path(str(path))
        self._settle()
        self.save('recent_projects', self._recent_projects())

        tree = window._project_tree
        model = self._model_item(self.words['model'])
        window.open_model(tree.model_of(model))
        self._settle()
        self.save('window_project', self._window())
        self.save('menu_bar', self._menu_bar())
        for index, name in ((0, 'file_menu'), (1, 'edit_menu'), (3, 'project_menu')):
            self.save(name, self._menu_shot(self._menu_bar_menu(index)))

        for item, name in (
            (tree.topLevelItem(0), 'tree_project_menu'),
            (self._folder_item(0), 'tree_models_menu'),
            (model, 'tree_model_menu'),
        ):
            self.save(name, self._tree_menu(item))

        self.save('new_model', self._model_dialog(None))
        tree.setCurrentItem(model)
        self.save('model_properties', self._model_dialog(self._model_of(model)))

        self._touch_the_net()
        self.save('tab_modified', self._tabs())

        window._document_area.close_all_documents()
        window.close_project()
        window.close()

    # ------------------------------------------------------------------
    # The example
    # ------------------------------------------------------------------

    def _make_projects(self) -> list[Path]:
        """Make the example project and the two others the history holds.

        Returns
        -------
        list of pathlib.Path
            The example first, then the others.
        """

        from masafi_simtwin import project
        from masafi_simtwin.preferences import install_id
        from masafi_simtwin.project import ModelKind
        from simtwin_adapters.sim_petri import pnml

        install = install_id()
        made = []
        for name in (self.words['project'], *self.words['others']):
            made.append(Path(project.create(WORKSPACE / f'{name}{project.PROJECT_SUFFIX}', name, install=install)))

        example = str(made[0])
        units = {'time': 's'}
        net = project.add_model(
            example,
            self.words['model'],
            ModelKind.PETRI_NET,
            units,
            project.current_user(),
            install,
            document=lambda identifier: pnml.to_pnml(self._net(identifier)),
        )
        project.add_model(
            example,
            self.words['second'],
            ModelKind.PETRI_NET,
            units,
            project.current_user(),
            install,
            document=lambda identifier: pnml.to_pnml(self._empty(identifier)),
        )
        assert net is not None
        return made

    def _net(self, identifier: str):
        """Draw the example net: bottles filled one at a time.

        Parameters
        ----------
        identifier : str
            The model's UUID.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net.
        """

        from simtwin_core.petri_net import ArcData, NetDocument, PlaceData, TransitionData

        words = self.words
        waiting = PlaceData(_uuid(), words['waiting'], (45.0, 60.0), tokens=3)
        self.waiting = waiting.uuid
        filler = PlaceData(_uuid(), words['filler'], (85.0, 25.0), tokens=1)
        full = PlaceData(_uuid(), words['full'], (125.0, 60.0))
        fill = TransitionData(_uuid(), words['fill'], (85.0, 60.0), vertical=True)
        arcs = [
            ArcData(_uuid(), waiting.uuid, fill.uuid, None, None),
            ArcData(_uuid(), fill.uuid, full.uuid, None, None),
            ArcData(_uuid(), filler.uuid, fill.uuid, None, None),
        ]
        return NetDocument(
            model_uuid=identifier,
            places=(waiting, filler, full),
            transitions=(fill,),
            arcs=arcs,
        )

    @staticmethod
    def _empty(identifier: str):
        """Give an empty net.

        Parameters
        ----------
        identifier : str
            The model's UUID.

        Returns
        -------
        simtwin_core.petri_net.NetDocument
            The net.
        """

        from simtwin_core.petri_net import NetDocument

        return NetDocument(model_uuid=identifier)

    def _touch_the_net(self) -> None:
        """Change the open net, so its tab shows that it has not been saved."""

        from masafi_simtwin import documents

        document = self.window._document_area.current_document
        documents.set_tokens(document, [self.waiting], 4)
        self._settle()

    # ------------------------------------------------------------------
    # Finding things in the window
    # ------------------------------------------------------------------

    def _folder_item(self, index: int):
        """Give a folder of the project in the tree: *Models*, *Simulations*…"""

        return self.window._project_tree.topLevelItem(0).child(index)

    def _model_item(self, name: str):
        """Give the tree's node of the model called ``name``."""

        models = self._folder_item(0)
        for row in range(models.childCount()):
            if models.child(row).text(0) == name:
                return models.child(row)
        raise LookupError(name)

    def _model_of(self, item) -> dict:
        """Give the manifest's entry of the model a tree node stands for."""

        from masafi_simtwin import project

        identifier = self.window._project_tree.model_of(item)
        return next(
            model
            for model in project.models_of(self.window._project_path)
            if model['uuid'] == identifier
        )

    def _menu_bar_menu(self, index: int):
        """Open the hamburger and give one of the menu bar's menus.

        Parameters
        ----------
        index : int
            Which menu, counting the hidden ones: *File* is 0, *Project* 3.

        Returns
        -------
        PyQt6.QtWidgets.QMenu
            The menu, not yet open.
        """

        bar = self.window._top_bar
        bar._expand_menu_bar()
        self._settle()
        menu_bar = bar._menu_bar
        action = menu_bar.actions()[index]
        menu = action.menu()
        geometry = menu_bar.actionGeometry(action)
        menu.popup(menu_bar.mapToGlobal(geometry.bottomLeft()))
        return menu

    # ------------------------------------------------------------------
    # Taking a picture
    # ------------------------------------------------------------------

    def _settle(self) -> None:
        """Let the window lay itself out and paint."""

        for _ in range(5):
            self.application.processEvents()

    def _window(self):
        """Picture the whole window, with nothing said in the status bar."""

        self.window.statusBar().clearMessage()
        self._settle()
        return self.window.grab()

    def _menu_bar(self):
        """Picture the top bar with the menu bar unfolded."""

        bar = self.window._top_bar
        bar._expand_menu_bar()
        self._settle()
        picture = bar.grab()
        bar._collapse_menu_bar()
        # The menus and no more: the whole bar is the window's width, and shrunk
        # onto a page the menu names would be too small to read.
        right = bar._menu_bar.geometry().right() + MARGIN
        return picture.copy(0, 0, min(right, picture.width()), picture.height())

    def _menu_shot(self, menu):
        """Picture an open menu over the part of the window it opened from.

        Parameters
        ----------
        menu : PyQt6.QtWidgets.QMenu
            A menu just put up with ``popup()``.

        Returns
        -------
        PyQt6.QtGui.QPixmap
            The window around the menu, the menu drawn over it.
        """

        self._settle()
        picture = self._over_window([menu])
        menu.hide()
        self.window._top_bar._collapse_menu_bar()
        self._settle()
        return picture

    def _over_window(self, popups):
        """Draw open pop-ups over the window, and cut out the part they cover.

        A pop-up is a window of its own, so a picture of the main window does
        not show it; it is drawn where it is on the screen.

        Parameters
        ----------
        popups : list of PyQt6.QtWidgets.QWidget
            The open pop-ups.

        Returns
        -------
        PyQt6.QtGui.QPixmap
            The part of the window from its top left corner to just past the
            pop-ups.
        """

        from PyQt6.QtCore import QRect
        from PyQt6.QtGui import QPainter

        self.window.statusBar().clearMessage()
        self._settle()
        picture = self.window.grab()
        covered = QRect()
        with_popups = QPainter(picture)
        for popup in popups:
            corner = self.window.mapFromGlobal(popup.mapToGlobal(popup.rect().topLeft()))
            with_popups.drawPixmap(corner, popup.grab())
            covered = covered.united(QRect(corner, popup.size()))
        with_popups.end()
        right = min(picture.width(), covered.right() + MARGIN)
        bottom = min(picture.height(), covered.bottom() + MARGIN)
        return picture.copy(QRect(0, 0, right, bottom))

    def _recent_projects(self):
        """Picture the project drop-down on the top bar, open."""

        button = self.window._top_bar._project_button
        menu = button.menu()
        menu.popup(button.mapToGlobal(button.rect().bottomLeft()))
        self._settle()
        picture = self._over_window([menu])
        menu.hide()
        return picture

    def _tree_menu(self, item):
        """Picture the context menu of a node of the project tree, open."""

        tree = self.window._project_tree
        tree.setCurrentItem(item)
        menu = tree.menu_for(item)
        rectangle = tree.visualItemRect(item)
        menu.popup(tree.viewport().mapToGlobal(rectangle.center()))
        self._settle()
        picture = self._over_window([menu])
        menu.hide()
        menu.deleteLater()
        return picture

    def _new_project_dialog(self):
        """Picture the New Project dialog, a name typed in."""

        from masafi_simtwin.dialogs.new_project import NewProjectDialog

        dialog = NewProjectDialog(self.window, str(WORKSPACE))
        dialog.name_edit.setText(self.words['project'] + ' 2')
        return self._dialog(dialog, width=520)

    def _model_dialog(self, model: dict | None):
        """Picture the model dialog: *New Model*, or the properties of one."""

        from masafi_simtwin.dialogs.model import ModelDialog

        dialog = ModelDialog(self.window, model=model)
        if model is None:
            dialog.name_edit.setText(self.words['new'])
        return self._dialog(dialog)

    def _dialog(self, dialog, width: int = 0):
        """Show a dialog without waiting for it, picture it, and close it.

        Parameters
        ----------
        dialog : PyQt6.QtWidgets.QDialog
            The dialog.
        width : int, optional
            How wide to make it, in pixels, when its own width would cut a
            field short.
        """

        dialog.show()
        self._settle()
        dialog.adjustSize()
        if width:
            dialog.resize(max(width, dialog.width()), dialog.height())
        self._settle()
        picture = dialog.grab()
        dialog.reject()
        dialog.deleteLater()
        return picture

    def _tabs(self):
        """Picture the top of the document area, where the tabs are."""

        from PyQt6.QtCore import QRect
        from PyQt6.QtWidgets import QTabBar

        area = self.window._document_area
        bar = area.findChild(QTabBar)
        self._settle()
        picture = area.grab()
        return picture.copy(QRect(0, 0, picture.width() // 2, bar.height() + 2))

    def save(self, name: str, picture) -> None:
        """Keep a picture under its name, in this language.

        Parameters
        ----------
        name : str
            What the manual calls it, without the extension.
        picture : PyQt6.QtGui.QPixmap
            The picture.
        """

        path = IMAGES / f'{name}{self.suffix}.png'
        if not picture.save(str(path)):
            raise OSError(f'{path} could not be written')
        print(path.relative_to(ROOT))


def _uuid() -> str:
    """Give a new identity for something drawn in the example."""

    return str(uuid.uuid4())


if __name__ == '__main__':
    sys.exit(main())
