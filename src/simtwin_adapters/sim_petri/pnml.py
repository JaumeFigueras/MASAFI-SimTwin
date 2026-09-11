"""A drawn Petri net written as PNML through MASAFI-sim-petri, and read back.

A model of a project is a PNML file — ISO/IEC 15909-2, the Petri Net Markup
Language — and it is **written by the library**, not by this module: the net is
built as a MASAFI-sim-petri net, the library turns it into a PNML tree, and what
the library does not hold is hung on that tree before it is written.  So the file
is the library's own P/T net, which the library, and any other PNML tool, reads
as it is, and what SimTwin adds rides along without being in anyone's way.  That
is the pattern MASAFI-sim-petri documents for the projects built on it:
``to_element`` → ``element_for`` → ``set_graphics`` to write,
``pnml_to_element`` → ``from_element`` → ``nodes_by_element`` to read.

**What goes where.**

* PNML's own ``graphics``, which every PNML tool reads: the centre of every place
  and transition, and — as the ``position`` elements PNML gives an arc for the
  points it bends at — the route of an S or an L on the sheet.  In millimetres,
  the unit the sheet is measured in.  No ``dimension`` is written: how big a
  place is drawn is the editor's constant rather than a fact about this net.
* ``<toolspecific tool="MASAFI-SimTwin" version="1">``, which PNML sets aside
  for exactly this and every other tool passes over: the model's UUID on the
  ``net``, the guides on the ``page``, each node's UUID, and each arc's UUID,
  kind, shape, connecting points, control points and points in its chord frame
  — which is what the editor draws from, and which wins over the route.

**The tool's elements are in a namespace of their own**, :data:`TOOL_NAMESPACE`,
and are **named unlike any element of PNML** — ``node``, ``link``, ``guide``,
``model``, ``controls``, ``points``.  Both were found necessary rather than
assumed.  An element with no namespace inside a PNML document is read back in
PNML's namespace, so it would come back as something else.  And the library
finds a net's places, transitions and arcs by their local name at any depth, so
an element of the tool's called ``arc`` would be read as an arc of the net.

**What can be written is decided here.**  :func:`net_type` looks at what a net
holds: a net of normal arcs is a P/T net, and a net holding an inhibitor arc
cannot be written yet — MASAFI-sim-petri has none until its P/T nets are
finished — so :class:`UnsupportedNet` refuses it rather than writing a net that
is not the one drawn.

**A file SimTwin did not write still opens.**  A node without the tool's UUID is
given a new one and a node without a position is laid out in a row, an arc
without the tool's data is a straight normal arc whose connecting points are left
to the editor, and another tool's ``toolspecific`` is passed over.  A file that is
not a net that can be drawn — not PNML, an arc to nothing, a place and a transition
of one name — is refused with :class:`UnreadableNet`.

The library is built when it is needed, by :func:`to_net`, rather than kept in
step with the drawing: a second copy of a net to keep correct at every drag buys
nothing until a net is simulated or analysed, which is when it is built.
"""

from __future__ import annotations

from uuid import uuid4
from xml.etree import ElementTree

from masafi_sim_petri import Arc, PetriNet, Place, Transition
from masafi_sim_petri.io import (
    PT_NET_TYPE,
    PnmlError,
    element_for,
    element_to_pnml,
    from_element,
    graphics_of,
    nodes_by_element,
    pnml_to_element,
    qname,
    set_graphics,
    to_element,
)
from simtwin_core.petri_net import (
    ArcData,
    GuideData,
    InvalidNet,
    NetDocument,
    PlaceData,
    TransitionData,
)

#: The name SimTwin's data goes under, as PNML's ``toolspecific`` asks a tool to
#: give.
TOOL_NAME = 'MASAFI-SimTwin'

#: The version of the layout of that data — not of the application, which may
#: change a great deal without changing a single element here.
TOOL_VERSION = '1'

#: The namespace SimTwin's own elements are in.  A URI names a namespace rather
#: than locating anything, so it need not resolve.
TOOL_NAMESPACE = 'https://github.com/JaumeFigueras/MASAFI-SimTwin'

#: The prefix the namespace is written with, for a person reading the file.
TOOL_PREFIX = 'simtwin'

#: The ``id`` written on the ``net`` element.  The model's identity is its UUID,
#: which a PNML ``id`` could not always carry — an ``id`` may not begin with a
#: digit — so it goes in the tool's data instead.
NET_ID = 'net1'

#: How far apart the nodes of a file without positions are laid out, in
#: millimetres: the places in a row, the transitions in a row below them.
LAYOUT_SPACING = 30.0


class UnsupportedNet(ValueError):
    """Raised when a net can be drawn but cannot be written yet."""


class UnreadableNet(ValueError):
    """Raised when a document is not a Petri net that can be opened."""


def net_type(document: NetDocument) -> str:
    """Decide what type of net a drawing is, from what it holds.

    Parameters
    ----------
    document : simtwin_core.petri_net.NetDocument
        The drawing.

    Returns
    -------
    str
        The PNML type of the net: a P/T net, while every arc is a normal one.

    Raises
    ------
    UnsupportedNet
        When the net holds a kind of arc MASAFI-sim-petri does not have yet.
    """

    unsupported = sorted({arc.kind for arc in document.arcs} - {'normal'})
    if unsupported:
        raise UnsupportedNet(
            f'a net holding {unsupported[0]} arcs cannot be written yet: '
            'MASAFI-sim-petri has P/T nets only'
        )
    return PT_NET_TYPE


def to_net(document: NetDocument) -> tuple[PetriNet, dict[str, Place | Transition | Arc]]:
    """Build MASAFI-sim-petri's net of a drawing.

    Parameters
    ----------
    document : simtwin_core.petri_net.NetDocument
        The drawing.

    Returns
    -------
    tuple
        The net, and what the library made of every node and arc of the drawing,
        by its UUID.

    Raises
    ------
    UnsupportedNet
        When the net is not of a type the library has — see :func:`net_type`.
    """

    net_type(document)
    net = PetriNet()
    made: dict[str, Place | Transition | Arc] = {}
    for place in document.places:
        made[place.uuid] = net.add_place(Place(place.name))
    for transition in document.transitions:
        made[transition.uuid] = net.add_transition(Transition(transition.name))
    for arc in document.arcs:
        made[arc.uuid] = net.add_arc(Arc(made[arc.source], made[arc.target], weight=arc.weight))
    return net, made


def to_pnml(document: NetDocument) -> bytes:
    """Write a drawn net as a PNML document.

    Parameters
    ----------
    document : simtwin_core.petri_net.NetDocument
        The drawing.

    Returns
    -------
    bytes
        The document, UTF-8, with its XML declaration.

    Raises
    ------
    UnsupportedNet
        When the net cannot be written yet — see :func:`net_type`.
    """

    net, made = to_net(document)
    root = to_element(net, net_id=NET_ID)
    net_element = root.find(qname('net'))
    page = net_element.find(qname('page'))

    if document.model_uuid:
        ElementTree.SubElement(
            _tool_data(net_element), _ours('model'), {'uuid': document.model_uuid}
        )
    if document.guides:
        tool = _tool_data(page)
        for guide in document.guides:
            ElementTree.SubElement(
                tool,
                _ours('guide'),
                {'orientation': guide.orientation, 'position': _number(guide.position)},
            )

    for node in (*document.places, *document.transitions):
        element = element_for(root, made[node.uuid])
        set_graphics(element, position=node.position)
        ElementTree.SubElement(_tool_data(element), _ours('node'), {'uuid': node.uuid})

    for arc in document.arcs:
        element = element_for(root, made[arc.uuid])
        if arc.route:
            graphics = set_graphics(element)
            for x, y in arc.route:
                ElementTree.SubElement(
                    graphics, qname('position'), {'x': _number(x), 'y': _number(y)}
                )
        _write_link(_tool_data(element), arc)

    ElementTree.register_namespace(TOOL_PREFIX, TOOL_NAMESPACE)
    return element_to_pnml(root).encode('utf-8')


def from_pnml(data: bytes | str) -> NetDocument:
    """Read a PNML document as a drawn net.

    Parameters
    ----------
    data : bytes or str
        The document.

    Returns
    -------
    simtwin_core.petri_net.NetDocument
        The drawing — exactly the one written, for a file :func:`to_pnml` wrote.

    Raises
    ------
    UnreadableNet
        When the document is not a Petri net that can be drawn.
    """

    try:
        root = pnml_to_element(data)
        net = from_element(root)
        elements = {node: element for element, node in nodes_by_element(root, net).items()}
    except PnmlError as error:
        raise UnreadableNet(f'not a Petri net that can be opened: {error}') from error

    try:
        net_element = root.find(qname('net'))
        page = net_element.find(qname('page')) if net_element is not None else None
        model = _tool_element(net_element, 'model')

        uuids: dict[Place | Transition, str] = {}
        places = []
        for index, place in enumerate(net.places):
            element = elements[place]
            uuids[place] = _node_uuid(element)
            laid_out = (LAYOUT_SPACING * (index + 1), LAYOUT_SPACING)
            places.append(PlaceData(uuids[place], place.name, _position(element) or laid_out))

        transitions = []
        for index, transition in enumerate(net.transitions):
            element = elements[transition]
            uuids[transition] = _node_uuid(element)
            laid_out = (LAYOUT_SPACING * (index + 1), LAYOUT_SPACING * 2.0)
            transitions.append(
                TransitionData(uuids[transition], transition.name, _position(element) or laid_out)
            )

        arcs = [_read_arc(arc, elements[arc], uuids) for arc in net.arcs]
        guides = [
            GuideData(guide.get('orientation', ''), float(guide.get('position')))
            for guide in _tool_elements(page, 'guide')
        ]
        return NetDocument(
            model_uuid=model.get('uuid', '') if model is not None else '',
            places=places,
            transitions=transitions,
            arcs=arcs,
            guides=guides,
        )
    except (InvalidNet, ValueError, TypeError) as error:
        raise UnreadableNet(f'not a Petri net that can be opened: {error}') from error


# ----------------------------------------------------------------------
# The tool's own data
# ----------------------------------------------------------------------


def _ours(name: str) -> str:
    """Qualify the name of one of the tool's elements with its namespace.

    Parameters
    ----------
    name : str
        The local name.

    Returns
    -------
    str
        The name as :mod:`xml.etree.ElementTree` spells a qualified one.
    """

    return f'{{{TOOL_NAMESPACE}}}{name}'


def _number(value: float) -> str:
    """Write a number so that reading it back gives the same number.

    Parameters
    ----------
    value : float
        The number.

    Returns
    -------
    str
        A whole number without its ``.0``, which keeps a file of snapped
        positions readable, and anything else as its ``repr``, which is exact.
    """

    value = float(value)
    return str(int(value)) if value.is_integer() else repr(value)


def _tool_data(element: ElementTree.Element) -> ElementTree.Element:
    """Give the tool's ``toolspecific`` element of an element, making it if need be.

    Parameters
    ----------
    element : xml.etree.ElementTree.Element
        The element of the net it belongs to.

    Returns
    -------
    xml.etree.ElementTree.Element
        The ``toolspecific`` element whose ``tool`` is :data:`TOOL_NAME`.
    """

    for child in element.findall(qname('toolspecific')):
        if child.get('tool') == TOOL_NAME:
            return child
    return ElementTree.SubElement(
        element, qname('toolspecific'), {'tool': TOOL_NAME, 'version': TOOL_VERSION}
    )


def _tool_elements(element: ElementTree.Element | None, name: str) -> list:
    """Find the tool's elements of one name under an element of the net.

    Only under SimTwin's own ``toolspecific``: another tool's is passed over,
    whatever it holds.

    Parameters
    ----------
    element : xml.etree.ElementTree.Element, optional
        The element of the net, or ``None`` for none.
    name : str
        The local name of the tool's element.

    Returns
    -------
    list of xml.etree.ElementTree.Element
        The elements, in document order.
    """

    if element is None:
        return []
    return [
        found
        for tool in element.findall(qname('toolspecific'))
        if tool.get('tool') == TOOL_NAME
        for found in tool.findall(_ours(name))
    ]


def _tool_element(element: ElementTree.Element | None, name: str):
    """Find the first of the tool's elements of one name under an element.

    Parameters
    ----------
    element : xml.etree.ElementTree.Element, optional
        The element of the net.
    name : str
        The local name of the tool's element.

    Returns
    -------
    xml.etree.ElementTree.Element, optional
        The element, or ``None`` when there is none.
    """

    found = _tool_elements(element, name)
    return found[0] if found else None


def _write_link(tool: ElementTree.Element, arc: ArcData) -> None:
    """Write what the editor keeps of an arc into the tool's data.

    A connecting point of ``None`` is left out, and so are controls or points of
    ``None``; points of ``()`` are an empty ``points`` element.  So *untouched* and
    *emptied* are told apart on reading, as they are in the drawing.

    Parameters
    ----------
    tool : xml.etree.ElementTree.Element
        The arc's ``toolspecific`` element.
    arc : simtwin_core.petri_net.ArcData
        The arc.
    """

    attributes = {'uuid': arc.uuid, 'kind': arc.kind, 'shape': arc.shape}
    if arc.source_port is not None:
        attributes['source-port'] = str(arc.source_port)
    if arc.target_port is not None:
        attributes['target-port'] = str(arc.target_port)
    link = ElementTree.SubElement(tool, _ours('link'), attributes)

    for wrapper, item, frames in (
        ('controls', 'control', arc.controls),
        ('points', 'point', arc.points),
    ):
        if frames is None:
            continue
        holder = ElementTree.SubElement(link, _ours(wrapper))
        for along, across in frames:
            ElementTree.SubElement(
                holder, _ours(item), {'along': _number(along), 'across': _number(across)}
            )


def _read_frames(link: ElementTree.Element, wrapper: str, item: str):
    """Read the controls or the points of an arc out of the tool's data.

    Parameters
    ----------
    link : xml.etree.ElementTree.Element
        The arc's ``link`` element.
    wrapper : str
        ``controls`` or ``points``.
    item : str
        ``control`` or ``point``.

    Returns
    -------
    tuple, optional
        The places in the chord's frame, or ``None`` when the wrapper is not
        there — *untouched*.
    """

    holder = link.find(_ours(wrapper))
    if holder is None:
        return None
    return tuple(
        (float(found.get('along')), float(found.get('across')))
        for found in holder.findall(_ours(item))
    )


def _node_uuid(element: ElementTree.Element) -> str:
    """Give the UUID of a node, as written or new.

    Parameters
    ----------
    element : xml.etree.ElementTree.Element
        The node's element.

    Returns
    -------
    str
        The UUID in the tool's data, or a new one for a node another tool wrote.
    """

    node = _tool_element(element, 'node')
    return (node.get('uuid') if node is not None else None) or str(uuid4())


def _position(element: ElementTree.Element):
    """Read the centre of a node out of PNML's graphics.

    Parameters
    ----------
    element : xml.etree.ElementTree.Element
        The node's element.

    Returns
    -------
    tuple of float, optional
        The position, or ``None`` when the file gives none.
    """

    graphics = graphics_of(element)
    found = graphics.find(qname('position')) if graphics is not None else None
    if found is None:
        return None
    return float(found.get('x')), float(found.get('y'))


def _read_arc(arc: Arc, element: ElementTree.Element, uuids: dict) -> ArcData:
    """Read one arc, from the library's net and from the tool's data.

    Parameters
    ----------
    arc : masafi_sim_petri.Arc
        The library's arc, which has the ends and the weight.
    element : xml.etree.ElementTree.Element
        The arc's element, which has the route and the tool's data.
    uuids : dict
        The UUID of every node, by the library's node.

    Returns
    -------
    simtwin_core.petri_net.ArcData
        The arc, a straight normal arc with its connecting points left to the
        editor when the file says nothing more.
    """

    graphics = graphics_of(element)
    route = (
        tuple(
            (float(found.get('x')), float(found.get('y')))
            for found in graphics.findall(qname('position'))
        )
        if graphics is not None
        else ()
    )
    source, target = uuids[arc.source], uuids[arc.target]
    link = _tool_element(element, 'link')
    if link is None:
        return ArcData(str(uuid4()), source, target, None, None, arc.weight, route=route)

    def port(name: str) -> int | None:
        text = link.get(name)
        return None if text is None else int(text)

    return ArcData(
        link.get('uuid') or str(uuid4()),
        source,
        target,
        port('source-port'),
        port('target-port'),
        arc.weight,
        link.get('kind', 'normal'),
        link.get('shape', 'straight'),
        _read_frames(link, 'controls', 'control'),
        _read_frames(link, 'points', 'point'),
        route,
    )
