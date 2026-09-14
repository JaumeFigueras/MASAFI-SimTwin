"""Tests for writing a drawn Petri net as PNML, and reading it back."""

from __future__ import annotations

import uuid
from dataclasses import replace
from xml.etree import ElementTree

import pytest
from PyQt6.QtCore import QPointF, Qt

from masafi_sim_petri.io import PT_NET_TYPE, element_for, graphics_of, qname
from masafi_sim_petri.io import from_pnml as library_reads
from simtwin_adapters.sim_petri import pnml
from simtwin_core.petri_net import (
    ArcData,
    GuideData,
    NetDocument,
    PlaceData,
    TransitionData,
)

#: A net of everything a file has to carry.
DRAWN = NetDocument(
    model_uuid='7f3f9c6a-model',
    places=(
        PlaceData('p1', 'P1', (20.0, 20.0), 3, 'Bottles waiting'),
        PlaceData('p2', 'P2', (20.5, 80.0)),
    ),
    transitions=(TransitionData('t1', 'T1', (70.0, 20.0), 'Fill a bottle & cap it'),),
    arcs=(
        ArcData('a1', 'p1', 't1', 0, 10, 3, 'normal', 'straight', ((1 / 3, 0.12), (2 / 3, 0.12)), ()),
        ArcData(
            'a2',
            't1',
            'p1',
            15,
            6,
            1,
            'normal',
            's-curved',
            ((0.3, 0.4), (2 / 3, 0.12)),
            ((0.25, 0.1), (0.5, -0.2), (0.75, 0.1)),
            route=((30.0, 25.5), (45.1, 18.0), (60.0, 25.5)),
        ),
        ArcData('a3', 'p2', 't1', None, None, 2, 'normal', 'l-shaped', None, None, route=((70.0, 80.0),)),
    ),
    guides=(GuideData('horizontal', 50.0), GuideData('vertical', 45.5)),
)

#: A net written by some other PNML tool: no graphics, no tool data of ours.
FROM_ANOTHER_TOOL = b"""<?xml version='1.0' encoding='UTF-8'?>
<pnml xmlns="http://www.pnml.org/version-2009/grammar/pnml">
  <net id="n" type="http://www.pnml.org/version-2009/grammar/ptnet">
    <page id="pg">
      <place id="p"><name><text>buffer</text></name></place>
      <place id="q"><name><text>done</text></name></place>
      <transition id="t"><name><text>work</text></name></transition>
      <arc id="a" source="p" target="t"><inscription><text>2</text></inscription></arc>
      <arc id="b" source="t" target="q"/>
    </page>
  </net>
</pnml>
"""


def tree_of(data: bytes) -> ElementTree.Element:
    """Parse a written document, to look inside it.

    Parameters
    ----------
    data : bytes
        The document.

    Returns
    -------
    xml.etree.ElementTree.Element
        Its root.
    """

    return ElementTree.fromstring(data)


# ----------------------------------------------------------------------
# A file SimTwin writes
# ----------------------------------------------------------------------


def test_a_net_read_back_is_the_net_written():
    """Every node, arc, bend, route and guide, and *untouched* told apart from
    *emptied*."""

    assert pnml.from_pnml(pnml.to_pnml(DRAWN)) == DRAWN


def test_an_empty_net_is_written_and_read_back():
    """A model nobody has drawn on yet."""

    empty = NetDocument(model_uuid='m')

    assert pnml.from_pnml(pnml.to_pnml(empty)) == empty


def test_the_library_alone_reads_the_file_as_the_net():
    """Nothing SimTwin adds is in the library's way, and none of it is taken for
    part of the net."""

    net = library_reads(pnml.to_pnml(DRAWN).decode('utf-8'))

    assert [place.name for place in net.places] == ['P1', 'P2']
    assert [transition.name for transition in net.transitions] == ['T1']
    assert [(arc.source.name, arc.target.name, arc.weight) for arc in net.arcs] == [
        ('P1', 'T1', 3),
        ('P2', 'T1', 2),
        ('T1', 'P1', 1),
    ]


def test_the_file_is_a_pt_net():
    """The type PNML knows it by."""

    net = tree_of(pnml.to_pnml(DRAWN)).find(qname('net'))

    assert net.get('type') == PT_NET_TYPE
    assert pnml.net_type(DRAWN) == PT_NET_TYPE


def test_every_node_stands_where_pnml_graphics_says():
    """Which every PNML tool reads."""

    element = element_for(tree_of(pnml.to_pnml(DRAWN)), 'P2')
    position = graphics_of(element).find(qname('position'))

    assert (position.get('x'), position.get('y')) == ('20.5', '80')


def test_the_route_of_an_arc_is_written_as_pnml_positions():
    """So another tool draws an S or an L through its points."""

    root = tree_of(pnml.to_pnml(DRAWN))
    arcs = root.find(qname('net')).find(qname('page')).findall(qname('arc'))
    bent = [arc for arc in arcs if arc.get('source') == 'T1'][0]
    straight = [arc for arc in arcs if arc.get('target') == 'T1' and arc.get('source') == 'P1'][0]

    positions = [
        (float(found.get('x')), float(found.get('y')))
        for found in graphics_of(bent).findall(qname('position'))
    ]
    assert positions == [(30.0, 25.5), (45.1, 18.0), (60.0, 25.5)]
    assert graphics_of(straight) is None


def test_simtwins_data_is_under_its_own_tool_and_namespace():
    """Where PNML sets it aside, in elements no PNML reader can mistake."""

    root = tree_of(pnml.to_pnml(DRAWN))
    tools = [element for element in root.iter(qname('toolspecific'))]

    assert tools
    assert {(tool.get('tool'), tool.get('version')) for tool in tools} == {
        (pnml.TOOL_NAME, pnml.TOOL_VERSION)
    }
    children = [child for tool in tools for child in tool.iter() if child is not tool]
    assert children
    assert all(child.tag.startswith(f'{{{pnml.TOOL_NAMESPACE}}}') for child in children)
    local = {child.tag.rpartition('}')[2] for child in children}
    assert not local & {'net', 'page', 'place', 'transition', 'arc', 'name', 'text', 'graphics', 'position'}


def test_whole_numbers_are_written_as_whole_numbers():
    """A file of snapped positions stays readable."""

    assert b'x="20" y="20"' in pnml.to_pnml(DRAWN)


def test_the_library_net_is_built_when_it_is_needed():
    """Every node and arc of the drawing, found by its UUID."""

    net, made = pnml.to_net(DRAWN)

    assert made['p1'].name == 'P1'
    assert made['a1'].weight == 3
    assert len(net.arcs) == 3


# ----------------------------------------------------------------------
# What cannot be written yet
# ----------------------------------------------------------------------


def test_a_net_holding_an_inhibitor_arc_cannot_be_written_yet():
    """Rather than a file that is not the net drawn."""

    inhibited = NetDocument(
        places=(PlaceData('p', 'P1', (0.0, 0.0)),),
        transitions=(TransitionData('t', 'T1', (40.0, 0.0)),),
        arcs=(ArcData('a', 'p', 't', 0, 10, kind='inhibitor'),),
    )

    with pytest.raises(pnml.UnsupportedNet, match='inhibitor'):
        pnml.net_type(inhibited)
    with pytest.raises(pnml.UnsupportedNet):
        pnml.to_pnml(inhibited)


# ----------------------------------------------------------------------
# A file another tool wrote
# ----------------------------------------------------------------------


def test_a_net_from_another_tool_opens():
    """Its names and weights, as the library reads them."""

    document = pnml.from_pnml(FROM_ANOTHER_TOOL)

    assert document.names == ('buffer', 'done', 'work')
    assert [arc.weight for arc in document.arcs] == [2, 1]


def test_what_another_tool_does_not_say_is_left_to_the_editor():
    """Straight normal arcs, their connecting points and bends untouched, and
    new identities for everything."""

    document = pnml.from_pnml(FROM_ANOTHER_TOOL)
    arc = document.arcs[0]

    assert (arc.kind, arc.shape) == ('normal', 'straight')
    assert (arc.source_port, arc.target_port, arc.controls, arc.points) == (None,) * 4
    identities = [node.uuid for node in (*document.places, *document.transitions)]
    identities += [arc.uuid for arc in document.arcs]
    assert len(set(identities)) == 5
    assert all(uuid.UUID(identity) for identity in identities)


def test_nodes_without_positions_are_laid_out_apart():
    """Places in a row, transitions in a row below."""

    document = pnml.from_pnml(FROM_ANOTHER_TOOL)
    positions = [node.position for node in (*document.places, *document.transitions)]

    assert len(set(positions)) == 3
    assert document.transitions[0].position[1] > document.places[0].position[1]


def test_positions_another_tool_gives_are_kept():
    """PNML's graphics are PNML's, whoever wrote them."""

    placed = FROM_ANOTHER_TOOL.replace(
        b'<place id="p"><name><text>buffer</text></name></place>',
        b'<place id="p"><name><text>buffer</text></name>'
        b'<graphics><position x="12.5" y="7"/></graphics></place>',
    )

    assert pnml.from_pnml(placed).places[0].position == (12.5, 7.0)


def test_another_tools_own_data_is_passed_over():
    """Only SimTwin's ``toolspecific`` is read as SimTwin's."""

    foreign = FROM_ANOTHER_TOOL.replace(
        b'<place id="p"><name><text>buffer</text></name></place>',
        b'<place id="p"><name><text>buffer</text></name>'
        b'<toolspecific tool="SomeTool" version="5"><node uuid="not-ours"/></toolspecific></place>',
    )

    assert pnml.from_pnml(foreign).places[0].uuid != 'not-ours'


# ----------------------------------------------------------------------
# What is refused
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    'data',
    [
        b'not xml at all',
        b'<other/>',
        FROM_ANOTHER_TOOL.replace(b'target="t"', b'target="nowhere"'),
        FROM_ANOTHER_TOOL.replace(b'<text>work</text>', b'<text>buffer</text>'),
        pnml.to_pnml(DRAWN).replace(b'shape="straight"', b'shape="zigzag"'),
        pnml.to_pnml(DRAWN).replace(b'source-port="0"', b'source-port="first"'),
    ],
    ids=['not-xml', 'not-pnml', 'arc-to-nothing', 'shared-name', 'bad-shape', 'bad-port'],
)
def test_a_file_that_is_not_a_net_that_can_be_drawn_is_refused(data):
    """With one error, whatever was wrong with it."""

    with pytest.raises(pnml.UnreadableNet):
        pnml.from_pnml(data)


def test_both_errors_are_value_errors():
    """So a caller that knows only the standard exceptions still catches them."""

    assert issubclass(pnml.UnreadableNet, ValueError)
    assert issubclass(pnml.UnsupportedNet, ValueError)


# ----------------------------------------------------------------------
# From the sheet to a file and back
# ----------------------------------------------------------------------


def test_a_net_drawn_on_the_sheet_survives_a_file(qtbot):
    """The editor's net, written and read into another editor, is the same net."""

    from masafi_simtwin.documents.arc import ArcShape
    from masafi_simtwin.documents.petri_net import PetriNetEditor

    model = {'uuid': '7f3f9c6a', 'name': 'Filling Station', 'kind': 'petri-net'}
    editor = PetriNetEditor(model)
    qtbot.addWidget(editor)
    place = editor.add_element('pt-petri-net', 'place', QPointF(20.0, 20.0))
    other = editor.add_element('pt-petri-net', 'place', QPointF(20.0, 80.0))
    transition = editor.add_element('pt-petri-net', 'transition', QPointF(70.0, 20.0))
    editor.add_arc(place, transition).weight = 4
    curved = editor.add_arc(transition, place, shape_kind=ArcShape.CURVED)
    curved.move_handle('middle', curved.chord_point(0.5, 0.3))
    ess = editor.add_arc(other, transition, shape_kind=ArcShape.S_CURVED)
    ess.insert_point(ess.path().pointAtPercent(0.4))
    editor.add_guide(Qt.Orientation.Vertical, 45.0)
    document = editor.to_document()

    again = PetriNetEditor(model)
    qtbot.addWidget(again)
    again.load_document(pnml.from_pnml(pnml.to_pnml(document)))

    assert again.to_document() == document


# ----------------------------------------------------------------------
# Tokens, descriptions and which way round a transition is
# ----------------------------------------------------------------------


def test_the_tokens_are_the_initial_marking_the_library_writes():
    """PNML's own ``initialMarking``, which every PNML tool reads."""

    data = pnml.to_pnml(DRAWN)
    net = library_reads(data.decode('utf-8'))

    assert [place.initial_marking for place in net.places] == [3, 0]
    marking = element_for(tree_of(data), 'P1').find(qname('initialMarking'))
    assert marking is not None
    assert element_for(tree_of(data), 'P2').find(qname('initialMarking')) is None


def test_a_description_rides_in_the_tools_own_data():
    """No backend sees it, and a node without one writes nothing for it."""

    root = tree_of(pnml.to_pnml(DRAWN))
    namespace = f'{{{pnml.TOOL_NAMESPACE}}}'

    def node_of(name):
        tool = element_for(root, name).find(qname('toolspecific'))
        return tool.find(f'{namespace}node')

    assert node_of('T1').get('description') == 'Fill a bottle & cap it'
    assert node_of('P1').get('description') == 'Bottles waiting'
    assert 'description' not in node_of('P2').attrib


def test_a_transition_standing_up_rides_in_the_tools_own_data():
    """Written only when it stands up, since lying across is what a transition
    does unless a file says otherwise — a foreign file included."""

    upright = TransitionData('t2', 'T2', (70.0, 60.0), '', True)
    document = replace(DRAWN, transitions=(*DRAWN.transitions, upright))
    written = pnml.to_pnml(document)
    root = tree_of(written)
    namespace = f'{{{pnml.TOOL_NAMESPACE}}}'

    def node_of(name):
        tool = element_for(root, name).find(qname('toolspecific'))
        return tool.find(f'{namespace}node')

    assert node_of('T2').get('vertical') == 'true'
    assert 'vertical' not in node_of('T1').attrib
    assert pnml.from_pnml(written) == document


def test_a_moved_caption_is_written_where_pnml_keeps_one():
    """The ``offset`` in the ``graphics`` of the node's ``name``, which is PNML's
    own, so another tool reads it too — and only for a caption that was moved."""

    moved = replace(
        DRAWN,
        places=(replace(DRAWN.places[0], label_offset=(0.0, 7.5)), DRAWN.places[1]),
        transitions=(replace(DRAWN.transitions[0], label_offset=(-12.25, 3.0)),),
    )
    written = pnml.to_pnml(moved)
    root = tree_of(written)

    def offset_of(name):
        graphics = graphics_of(element_for(root, name).find(qname('name')))
        return None if graphics is None else graphics.find(qname('offset'))

    assert offset_of('P1').attrib == {'x': '0', 'y': '7.5'}
    assert offset_of('T1').attrib == {'x': '-12.25', 'y': '3'}
    assert offset_of('P2') is None
    assert pnml.from_pnml(written) == moved
    assert [place.name for place in library_reads(written.decode('utf-8')).places] == ['P1', 'P2']


def test_a_resized_caption_rides_in_the_tools_own_data():
    """PNML has no width for a label, so it is ours — written only for a caption
    that was resized, and read back."""

    resized = replace(
        DRAWN,
        places=(DRAWN.places[0], replace(DRAWN.places[1], label_width=12.5)),
        transitions=(replace(DRAWN.transitions[0], label_width=40.0),),
    )
    written = pnml.to_pnml(resized)
    root = tree_of(written)
    namespace = f'{{{pnml.TOOL_NAMESPACE}}}'

    def node_of(name):
        return element_for(root, name).find(qname('toolspecific')).find(f'{namespace}node')

    assert node_of('P2').get('label-width') == '12.5'
    assert node_of('T1').get('label-width') == '40'
    assert 'label-width' not in node_of('P1').attrib
    assert pnml.from_pnml(written) == resized


def test_a_caption_offset_another_tool_writes_is_read():
    """PNML's place for it is everybody's."""

    written = FROM_ANOTHER_TOOL.replace(
        b'<place id="p"><name><text>buffer</text></name></place>',
        b'<place id="p"><name><text>buffer</text>'
        b'<graphics><offset x="4" y="-6"/></graphics></name></place>',
    )

    document = pnml.from_pnml(written)

    assert {place.name: place.label_offset for place in document.places} == {
        'buffer': (4.0, -6.0),
        'done': None,
    }


def test_a_marking_another_tool_writes_is_read_as_tokens():
    """And its nodes have no description, and its bars lie across the sheet."""

    written = FROM_ANOTHER_TOOL.replace(
        b'<place id="p"><name><text>buffer</text></name></place>',
        b'<place id="p"><name><text>buffer</text></name>'
        b'<initialMarking><text>4</text></initialMarking></place>',
    )

    document = pnml.from_pnml(written)

    assert {place.name: place.tokens for place in document.places} == {'buffer': 4, 'done': 0}
    assert all(node.description == '' for node in (*document.places, *document.transitions))
    assert all(transition.vertical is False for transition in document.transitions)



def test_a_file_whose_names_are_not_names_is_refused():
    """The library reads it; SimTwin does not draw a net it could not have made."""

    written = FROM_ANOTHER_TOOL.replace(b'<text>buffer</text>', b'<text>buffer 1</text>')

    assert [place.name for place in library_reads(written.decode('utf-8')).places][0] == 'buffer 1'
    with pytest.raises(pnml.UnreadableNet, match='not a name'):
        pnml.from_pnml(written)
