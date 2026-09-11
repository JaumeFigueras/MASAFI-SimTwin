"""Tests for the tool bar a Petri net's arcs are chosen from."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from PyQt6.QtCore import QEvent, QPointF, QSize, Qt
from PyQt6.QtGui import QColor, QMouseEvent, QPalette
from PyQt6.QtWidgets import QApplication, QLabel

from masafi_simtwin.documents import petri_net
from masafi_simtwin.documents.arc import (
    IMPLEMENTED_ARC_KINDS,
    ArcKind,
    ArcShape,
    kind_label,
    shape_label,
)
from masafi_simtwin.documents.arc_toolbar import ICON_SIZE, ArcToolBar


@pytest.fixture
def net(editor):
    """Put a place and a transition on the sheet, a little apart.

    Parameters
    ----------
    editor : masafi_simtwin.documents.petri_net.PetriNetEditor
        The document.

    Returns
    -------
    tuple
        The place and the transition.
    """

    place = editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))
    transition = editor.add_element('pt-petri-net', 'transition', QPointF(60.0, 20.0))
    return place, transition


def mouse(kind: QEvent.Type, position: QPointF) -> QMouseEvent:
    """Build a left-button mouse event.

    Parameters
    ----------
    kind : PyQt6.QtCore.QEvent.Type
        Press, move or release.
    position : PyQt6.QtCore.QPointF
        Where it happened, in the viewport's coordinates.

    Returns
    -------
    PyQt6.QtGui.QMouseEvent
        The event.
    """

    return QMouseEvent(
        kind,
        position,
        position,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def drag_arc(view, source, target) -> None:
    """Draw an arc from the first connecting point of one item onto another.

    Parameters
    ----------
    view : masafi_simtwin.documents.canvas.CanvasView
        The view.
    source, target : masafi_simtwin.documents.net_item.NetItem
        The two ends.
    """

    start = QPointF(view.mapFromScene(source.scene_ports()[0]))
    end = QPointF(view.mapFromScene(target.scenePos()))
    view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    view.mouseMoveEvent(mouse(QEvent.Type.MouseMove, end))
    view.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, end))


def image_of(action):
    """Give what an action's icon looks like, at the size it is shown.

    Parameters
    ----------
    action : PyQt6.QtGui.QAction
        The action.

    Returns
    -------
    PyQt6.QtGui.QImage
        The icon's pixels.
    """

    return action.icon().pixmap(QSize(ICON_SIZE, ICON_SIZE)).toImage()


# ----------------------------------------------------------------------
# What the bar holds
# ----------------------------------------------------------------------


def layout_of(bar) -> list:
    """Read the bar from left to right.

    Parameters
    ----------
    bar : masafi_simtwin.documents.arc_toolbar.ArcToolBar
        The bar.

    Returns
    -------
    list
        ``'|'`` for a separator, the text of a label, and what a button stands
        for.
    """

    found = []
    for action in bar.actions():
        widget = bar.widgetForAction(action)
        if action.isSeparator():
            found.append('|')
        elif isinstance(widget, QLabel):
            found.append(widget.text())
        else:
            found.append(action.data())
    return found


def test_the_bar_says_what_it_acts_on_then_offers_two_captioned_groups(qtbot):
    """What a press acts on, then the shapes under their caption, then the
    kinds under theirs, a separator between each."""

    bar = ArcToolBar()
    qtbot.addWidget(bar)

    assert layout_of(bar) == [
        'New Arc',
        '|',
        'Arc Shape',
        *ArcShape,
        '|',
        'Arc Type',
        *ArcKind,
    ]


def test_a_kind_is_named_without_saying_arc_again(qtbot):
    """Its caption already says it."""

    bar = ArcToolBar()
    qtbot.addWidget(bar)

    assert bar.captions == ('Arc Shape', 'Arc Type')
    assert kind_label(ArcKind.INHIBITOR) == 'Inhibitor'
    assert bar.kind_action(ArcKind.NORMAL).toolTip() == 'Normal'


def test_the_bar_counts_the_arcs_a_press_acts_on(qtbot):
    """As a label and a number, which needs no plural."""

    bar = ArcToolBar()
    qtbot.addWidget(bar)

    bar.show_target(3)
    assert bar.target_text == 'Selected Arcs: 3'

    bar.show_target(0)
    assert bar.target_text == 'New Arc'


def test_the_label_is_as_wide_as_the_widest_thing_it_says(qtbot):
    """So the buttons after it stay where they are."""

    bar = ArcToolBar()
    qtbot.addWidget(bar)
    label = bar.widgetForAction(bar.actions()[0])

    for selected in (0, 1, 42, 99):
        bar.show_target(selected)
        assert label.minimumWidth() >= label.sizeHint().width()


def test_each_button_is_named_as_the_menu_names_it(qtbot):
    """One name for a shape, wherever it is said."""

    bar = ArcToolBar()
    qtbot.addWidget(bar)

    for shape in ArcShape:
        assert bar.shape_action(shape).toolTip() == shape_label(shape)
    for kind in IMPLEMENTED_ARC_KINDS:
        assert bar.kind_action(kind).toolTip() == kind_label(kind)


def test_the_shapes_and_the_kinds_are_two_choices(qtbot):
    """Exclusive each, and not one of the other."""

    bar = ArcToolBar()
    qtbot.addWidget(bar)
    shapes = {bar.shape_action(shape).actionGroup() for shape in ArcShape}
    kinds = {bar.kind_action(kind).actionGroup() for kind in ArcKind}

    assert len(shapes) == len(kinds) == 1
    assert shapes != kinds
    assert next(iter(shapes)).isExclusive()
    assert next(iter(kinds)).isExclusive()


def test_a_group_can_be_shown_with_nothing_checked(qtbot):
    """Which is how a selection of arcs of two shapes is shown."""

    bar = ArcToolBar()
    qtbot.addWidget(bar)
    bar.show_choice(ArcShape.CURVED, ArcKind.INHIBITOR)
    assert (bar.checked_shape, bar.checked_kind) == (ArcShape.CURVED, ArcKind.INHIBITOR)

    bar.show_choice(None, None)

    assert bar.checked_shape is None
    assert bar.checked_kind is None


def test_a_press_says_what_was_chosen(qtbot):
    """And does nothing else: the editor decides what a press means."""

    bar = ArcToolBar()
    qtbot.addWidget(bar)
    shapes, kinds = [], []
    bar.shape_chosen.connect(shapes.append)
    bar.kind_chosen.connect(kinds.append)

    bar.shape_action(ArcShape.L_SHAPED).trigger()
    bar.kind_action(ArcKind.INHIBITOR).trigger()

    assert shapes == [ArcShape.L_SHAPED]
    assert kinds == [ArcKind.INHIBITOR]


def test_every_button_has_an_icon_of_its_own(qtbot):
    """Six icons, and no two alike."""

    bar = ArcToolBar()
    qtbot.addWidget(bar)
    actions = [bar.shape_action(shape) for shape in ArcShape]
    actions += [bar.kind_action(kind) for kind in ArcKind]
    images = [image_of(action) for action in actions]

    assert all(not action.icon().isNull() for action in actions)
    assert all(
        images[one] != images[other]
        for one in range(len(images))
        for other in range(one + 1, len(images))
    )


def test_the_icons_are_painted_again_when_the_theme_changes(qtbot):
    """A painted icon does not follow the palette of its own accord."""

    bar = ArcToolBar()
    qtbot.addWidget(bar)
    palette = QPalette(bar.palette())
    palette.setColor(QPalette.ColorRole.ButtonText, QColor('#ff0000'))

    bar.setPalette(palette)

    image = image_of(bar.shape_action(ArcShape.STRAIGHT))
    colours = {
        QColor(image.pixel(x, y)).name()
        for x in range(image.width())
        for y in range(image.height())
        if QColor(image.pixel(x, y)).alpha() == 255
    }
    assert '#ff0000' in colours


# ----------------------------------------------------------------------
# The bar on the editor
# ----------------------------------------------------------------------


@pytest.fixture
def every_kind_built(monkeypatch, editor):
    """Pretend every kind of arc is built.

    Only the normal arc is built today, so the inhibitor's button is greyed out
    and a press on it does nothing.  What the bar does with a kind that *is*
    built — the next arc drawn, a selection that may not be of it — is tested by
    pretending they all are.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The pytest patcher.
    editor : masafi_simtwin.documents.petri_net.PetriNetEditor
        The document, whose bar is shown again under the pretence.
    """

    monkeypatch.setattr(petri_net, 'IMPLEMENTED_ARC_KINDS', tuple(ArcKind))
    editor.show_arc_choice()


def test_a_kind_not_built_yet_is_greyed_out_and_says_so(editor):
    """Offered and refused, as the kinds of model are."""

    inhibitor = editor.arc_tool_bar.kind_action(ArcKind.INHIBITOR)

    assert not inhibitor.isEnabled()
    assert inhibitor.toolTip() == 'Inhibitor (not available yet)'
    assert editor.arc_tool_bar.kind_action(ArcKind.NORMAL).isEnabled()


def test_a_kind_not_built_yet_stays_greyed_out_over_a_selection(editor, net):
    """An arc that could be an inhibitor still cannot be made one yet."""

    place, transition = net
    editor.add_arc(place, transition).setSelected(True)

    assert not editor.arc_tool_bar.kind_action(ArcKind.INHIBITOR).isEnabled()


def test_the_bar_sits_along_the_top_of_the_sheet(editor):
    """Above the rulers, where the choice is made before the arc is drawn."""

    bar = editor.arc_tool_bar

    assert bar.isVisible()
    assert bar.geometry().bottom() < editor.horizontal_ruler.geometry().top()


def test_with_nothing_selected_the_bar_shows_the_next_arc(editor):
    """Straight and normal, to begin with."""

    bar = editor.arc_tool_bar

    assert bar.checked_shape is ArcShape.STRAIGHT
    assert bar.checked_kind is ArcKind.NORMAL


def test_the_next_arc_is_drawn_as_the_bar_says(editor, net, every_kind_built):
    """Which is the whole of what the bar is for."""

    place, transition = net
    editor.arc_tool_bar.shape_action(ArcShape.CURVED).trigger()
    editor.arc_tool_bar.kind_action(ArcKind.INHIBITOR).trigger()

    drag_arc(editor.view, place, transition)

    assert editor.arcs[0].shape_kind is ArcShape.CURVED
    assert editor.arcs[0].kind is ArcKind.INHIBITOR
    assert editor.arc_tool_bar.checked_shape is ArcShape.CURVED


def test_the_bar_shows_the_selected_arc(editor, net):
    """What a press would act on is what is shown."""

    place, transition = net
    arc = editor.add_arc(place, transition, shape_kind=ArcShape.S_CURVED, kind=ArcKind.INHIBITOR)

    arc.setSelected(True)

    assert editor.arc_tool_bar.checked_shape is ArcShape.S_CURVED
    assert editor.arc_tool_bar.checked_kind is ArcKind.INHIBITOR


def test_putting_the_selection_down_shows_the_next_arc_again(editor, net):
    """The bar goes back to what it shows with nothing to act on."""

    place, transition = net
    arc = editor.add_arc(place, transition, shape_kind=ArcShape.S_CURVED)
    arc.setSelected(True)

    editor.scene().clearSelection()

    assert editor.arc_tool_bar.checked_shape is ArcShape.STRAIGHT


def test_a_press_changes_every_selected_arc(editor, net):
    """And only the arcs: a place selected with them is left alone."""

    place, transition = net
    one = editor.add_arc(place, transition)
    other = editor.add_arc(transition, place)
    for item in (one, other, place):
        item.setSelected(True)

    editor.arc_tool_bar.shape_action(ArcShape.L_SHAPED).trigger()

    assert one.shape_kind is other.shape_kind is ArcShape.L_SHAPED


def test_a_press_on_a_selection_sets_the_next_arc_as_well(editor, net):
    """Or the bar would jump back to an older choice when the selection is put
    down, and read as the press not having taken."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.setSelected(True)

    editor.arc_tool_bar.shape_action(ArcShape.CURVED).trigger()
    editor.scene().clearSelection()

    assert editor.view.new_arc_shape is ArcShape.CURVED
    assert editor.arc_tool_bar.checked_shape is ArcShape.CURVED


def test_a_mixed_selection_checks_no_shape(editor, net):
    """Neither of two shapes is the selection's shape."""

    place, transition = net
    one = editor.add_arc(place, transition, shape_kind=ArcShape.CURVED)
    other = editor.add_arc(transition, place)
    one.setSelected(True)
    other.setSelected(True)

    assert editor.arc_tool_bar.checked_shape is None
    assert editor.arc_tool_bar.checked_kind is ArcKind.NORMAL


def test_inhibitor_is_greyed_out_for_an_arc_that_runs_the_wrong_way(editor, net, every_kind_built):
    """An arc from a transition to a place cannot be an inhibitor, and a button
    that would do nothing is a button that cannot be pressed."""

    place, transition = net
    backwards = editor.add_arc(transition, place)
    backwards.setSelected(True)
    assert not editor.arc_tool_bar.kind_action(ArcKind.INHIBITOR).isEnabled()

    editor.scene().clearSelection()
    assert editor.arc_tool_bar.kind_action(ArcKind.INHIBITOR).isEnabled()


def test_making_a_selection_inhibitor_leaves_the_arcs_that_cannot_be(editor, net):
    """What may change changes; the rest is left as it was."""

    place, transition = net
    forwards = editor.add_arc(place, transition)
    backwards = editor.add_arc(transition, place)
    forwards.setSelected(True)
    backwards.setSelected(True)

    editor.choose_arc_kind(ArcKind.INHIBITOR)

    assert forwards.kind is ArcKind.INHIBITOR
    assert backwards.kind is ArcKind.NORMAL


def test_a_shape_chosen_from_the_menu_shows_on_the_bar(editor, net):
    """The menu and the bar say the same thing about the same arc."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    arc.setSelected(True)

    editor.view.set_arc_shape(arc, ArcShape.S_CURVED)

    assert editor.arc_tool_bar.checked_shape is ArcShape.S_CURVED


def test_a_kind_chosen_while_drawing_changes_what_lights_up(editor, net, every_kind_built):
    """An inhibitor arc drawn out of a transition may be joined to nothing, so
    the place it is aimed at puts its connecting points away at once."""

    place, transition = net
    start = QPointF(editor.view.mapFromScene(transition.scene_ports()[0]))
    over = QPointF(editor.view.mapFromScene(place.scenePos()))
    editor.view.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start))
    editor.view.mouseMoveEvent(mouse(QEvent.Type.MouseMove, over))
    assert editor.view.connection_target is place

    editor.arc_tool_bar.kind_action(ArcKind.INHIBITOR).trigger()

    assert editor.view.connection_target is None
    assert not place.ports_visible


def test_the_bar_says_it_acts_on_the_next_arc_while_nothing_is_selected(editor, net):
    """Which is what a press does then."""

    assert editor.arc_tool_bar.target_text == 'New Arc'


def test_the_bar_says_how_many_selected_arcs_a_press_acts_on(editor, net):
    """Arcs only: a place selected with them is not acted on, so not counted."""

    place, transition = net
    one = editor.add_arc(place, transition)
    other = editor.add_arc(transition, place)
    for item in (one, other, place):
        item.setSelected(True)

    assert editor.arc_tool_bar.target_text == 'Selected Arcs: 2'

    editor.scene().clearSelection()

    assert editor.arc_tool_bar.target_text == 'New Arc'


def test_the_buttons_stay_put_as_the_selection_changes(editor, net):
    """The label before them changes its words and not its width, so a button
    is where it was a moment ago."""

    place, transition = net
    arc = editor.add_arc(place, transition)
    bar = editor.arc_tool_bar
    button = bar.widgetForAction(bar.shape_action(ArcShape.STRAIGHT))
    QApplication.processEvents()
    before = button.x()

    arc.setSelected(True)
    QApplication.processEvents()

    assert bar.target_text == 'Selected Arcs: 1'
    assert button.x() == before


TEARDOWN_SESSION = '''
import gc, sys
from PyQt6.QtCore import QEventLoop, QPointF, QSettings, QTimer
from PyQt6.QtWidgets import QApplication

QSettings.setDefaultFormat(QSettings.Format.IniFormat)

from masafi_simtwin.documents.petri_net import PetriNetEditor

def session():
    application = QApplication(sys.argv[:1])
    editor = PetriNetEditor({'uuid': 'u', 'name': 'Net', 'kind': 'petri-net'})
    place = editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))
    transition = editor.add_element('pt-petri-net', 'transition', QPointF(60.0, 20.0))
    arc = editor.add_arc(place, transition)
    editor.show()
    arc.setSelected(True)
    loop = QEventLoop()
    QTimer.singleShot(50, loop.quit)
    loop.exec()
    editor.close()
    del editor, place, transition, arc
    gc.collect()

session()
gc.collect()
print('survived')
'''


def test_an_editor_with_a_selection_is_torn_down_without_a_crash(tmp_path):
    """The scene puts its selection down as it is destroyed, and the editor
    listens to the selection.  A connection that outlived the editor would call
    into a widget whose C++ side is gone, which kills the interpreter rather
    than raising anything — so the test watches from outside."""

    environment = dict(os.environ)
    environment['QT_QPA_PLATFORM'] = 'offscreen'
    environment['XDG_CONFIG_HOME'] = str(tmp_path / 'config')

    finished = subprocess.run(
        [sys.executable, '-c', TEARDOWN_SESSION],
        capture_output=True,
        text=True,
        timeout=120,
        env=environment,
    )

    assert finished.returncode == 0, finished.stderr
    assert 'survived' in finished.stdout
