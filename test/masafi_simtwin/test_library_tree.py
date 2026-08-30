"""Tests for the tree of libraries and the elements in them."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QMimeData, Qt
from PyQt6.QtGui import QColor, QPalette

from masafi_simtwin.library_tree import (
    ELEMENT_ICON_SIZE,
    ELEMENT_MIME,
    LibraryTree,
    element_from_mime,
    element_mime_data,
)

#: What the pane holds, as a shape: a library and the keys of its elements.
SHAPE = {
    'pt-petri-net': ['place', 'transition'],
    'timed-petri-net': ['place', 'transition', 'timed-transition'],
    'attributed-timed-petri-net': [
        'place',
        'transition',
        'timed-transition',
        'attribute',
    ],
    'process-flow': ['unimplemented'],
}


@pytest.fixture
def tree(qtbot):
    """Build the library tree.

    Parameters
    ----------
    qtbot : pytestqt.qtbot.QtBot
        The pytest-qt bot.

    Returns
    -------
    masafi_simtwin.library_tree.LibraryTree
        The tree, already filled.
    """

    widget = LibraryTree()
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_the_libraries_are_the_families_of_elements(tree):
    """Four of them, in the order they are declared."""

    assert [tree.library_of(item) for item in tree.nodes() if tree.element_of(item) is None] == list(
        SHAPE
    )


def test_every_library_holds_its_own_elements(tree):
    """The timed net adds a timed transition; the attributed one adds an attribute."""

    held: dict[str, list[str]] = {}
    for item in tree.nodes():
        element = tree.element_of(item)
        if element is not None:
            held.setdefault(tree.library_of(item), []).append(element)

    assert held == SHAPE


def test_an_element_is_named_by_its_library_and_its_key(tree):
    """A place in a P/T net and a place in a timed net are shown the same and
    are not the same thing, so neither key names one on its own."""

    places = [
        (tree.library_of(item), tree.element_of(item))
        for item in tree.nodes()
        if tree.element_of(item) == 'place'
    ]

    assert len(places) == 3
    assert len({library for library, _ in places}) == 3


def test_a_library_node_stands_for_no_element(tree):
    """Which is what tells a library apart from what is in it."""

    libraries = [item for item in tree.nodes() if item.parent() is None]

    assert libraries
    assert all(tree.element_of(item) is None for item in libraries)
    assert all(tree.library_of(item) for item in libraries)


def test_every_node_is_shown_under_a_name_and_an_icon(tree):
    """Every one of them, libraries included."""

    for item in tree.nodes():
        assert item.text(0)
        assert not item.icon(0).isNull()
        assert item.icon(0).availableSizes()[0].width() == ELEMENT_ICON_SIZE


def test_the_libraries_open_expanded(tree):
    """A palette that has to be opened first is a palette nobody sees."""

    assert all(item.isExpanded() for item in tree.nodes() if item.parent() is None)


def test_what_is_not_built_yet_is_shown_and_cannot_be_taken(tree):
    """The shape of what is coming stays visible without pretending it works."""

    unimplemented = [
        item for item in tree.nodes() if tree.element_of(item) == 'unimplemented'
    ]

    assert len(unimplemented) == 1
    assert unimplemented[0].isDisabled()


def test_everything_that_is_built_can_be_taken(tree):
    """Only the placeholder is refused."""

    usable = [
        item
        for item in tree.nodes()
        if tree.element_of(item) not in (None, 'unimplemented')
    ]

    assert usable
    assert all(not item.isDisabled() for item in usable)


def test_the_icons_are_built_again_when_the_theme_changes(tree, qapp):
    """A Material Symbol is tinted with the palette it was made under.

    A tree item cannot be registered with :mod:`masafi_simtwin.icons` — it takes
    ``setIcon(column, icon)`` rather than ``setIcon(icon)`` — so the tree has to
    answer for its own, and this is the check that it does.  The palette is the
    *application's*, which is what a theme change moves and what an icon is
    tinted from; it is put back afterwards, the application being shared by
    every test in the run.
    """

    item = tree.nodes()[1]
    before = item.icon(0).pixmap(ELEMENT_ICON_SIZE).toImage()
    original = QPalette(qapp.palette())

    try:
        changed = QPalette(original)
        for role in (
            QPalette.ColorRole.WindowText,
            QPalette.ColorRole.Text,
            QPalette.ColorRole.ButtonText,
        ):
            changed.setColor(role, QColor('#ff00ff'))
        qapp.setPalette(changed)
        qapp.processEvents()
        after = item.icon(0).pixmap(ELEMENT_ICON_SIZE).toImage()
    finally:
        qapp.setPalette(original)

    assert after != before


# ----------------------------------------------------------------------
# Taking an element out of the pane
# ----------------------------------------------------------------------


def node(tree, library: str, element: str):
    """Find one element's row.

    Parameters
    ----------
    tree : masafi_simtwin.library_tree.LibraryTree
        The tree.
    library : str
        The key of the library it is in.
    element : str
        The key of the element.

    Returns
    -------
    PyQt6.QtWidgets.QTreeWidgetItem
        The row.
    """

    for item in tree.nodes():
        if tree.library_of(item) == library and tree.element_of(item) == element:
            return item
    raise AssertionError(f'no {element} in {library}')


def test_the_pane_offers_its_elements_and_nothing_else(tree):
    """Not the text of a row: a place dropped in a text field means nothing."""

    assert tree.mimeTypes() == [ELEMENT_MIME]
    assert tree.dragEnabled()


def test_a_dragged_element_carries_its_library_and_its_key(tree):
    """An element is named by both together, a place in a timed net not being
    a place in a plain one."""

    data = tree.mimeData([node(tree, 'timed-petri-net', 'place')])

    assert element_from_mime(data) == ('timed-petri-net', 'place')


def test_a_library_cannot_be_dragged(tree):
    """A family of elements is not a thing to put on a sheet."""

    root = tree.topLevelItem(0)

    assert not root.flags() & Qt.ItemFlag.ItemIsDragEnabled
    assert tree.mimeData([root]) is None


def test_an_element_that_is_not_built_cannot_be_dragged(tree):
    """The shape of what is coming stays visible without pretending it works."""

    item = node(tree, 'process-flow', 'unimplemented')

    assert not item.flags() & Qt.ItemFlag.ItemIsDragEnabled


def test_the_payload_reads_back_the_way_it_was_written(tree):
    """The two halves of the format are declared together so they cannot drift."""

    assert element_from_mime(element_mime_data('a', 'b')) == ('a', 'b')
    assert element_from_mime(None) is None
    assert element_from_mime(QMimeData()) is None


def test_a_payload_that_names_only_half_an_element_is_no_element(tree):
    """A key without a library is a name of nothing in particular."""

    half = QMimeData()
    half.setData(ELEMENT_MIME, b'place')

    assert element_from_mime(half) is None
