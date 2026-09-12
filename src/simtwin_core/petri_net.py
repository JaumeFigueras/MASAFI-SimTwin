"""A Petri net as it is drawn, with nothing of how it is shown.

This is what the Petri net editor hands over and is handed back: the places, the
transitions, the arcs and the guides of one model, with everything that decides
what the drawing looks like — positions, connecting points, shapes — and nothing
of Qt.  The editor turns its sheet into a :class:`NetDocument` and a
:class:`NetDocument` back into a sheet; an adapter turns one into a file, or into
a net of a backend library, and back.  Neither of them ever sees the other.

**Everything is plain.**  A position is ``(x, y)`` in millimetres on the sheet.  A
shape, a kind and an orientation are the text the editor's own enums carry as
their values — :data:`SHAPES`, :data:`KINDS`, :data:`ORIENTATIONS` — so this
module needs nothing from the editor, and a test on the editor's side holds that
the two name them alike.  Every class is **frozen** and holds tuples, so a
document is a value: two documents of the same drawing are equal, and nothing
that holds one can change what another sees.  A list given where a tuple belongs
is made a tuple.

**A document is a net that can be drawn, or it is not made.**  A
:class:`NetDocument` refuses, with :class:`InvalidNet`, to hold

* two things with the same UUID, or two nodes with the same name — a place and a
  transition included, since a backend knows a node by its name;
* an arc with an end that is not one of its nodes, or that joins a node to one of
  its own kind — a Petri net is bipartite;
* an arc of a kind running the wrong way — an inhibitor arc runs from a place to
  a transition, :data:`DIRECTIONS`;
* two arcs of one kind running the same way between the same two nodes.

These are the rules the editor keeps as a net is drawn.  Holding them here as
well means a file that breaks one is refused when it is read, rather than turned
into a drawing the editor could never have made.

**How an arc bends is kept the way the editor keeps it**, in the arc's own chord
frame — how far along the line between its two connecting points and how far
across it, as fractions of its length — so that it is independent of where the
nodes happen to be.  ``None`` for the controls or for the points means
*untouched*: the shape's own default, which is the editor's to know and is not
repeated here.  An S whose every point has been taken out is ``()``, not
``None``, and is drawn as a straight line.

Two more things are left to the editor, for files it did not write.  A
**connecting point** of ``None`` is the point facing the other end that no arc is
on yet, which only the editor, knowing where its points are, can work out.  And an
arc's **route** — where the points it is led through are on the sheet — is the
editor's to give and is never used to draw: it is there for readers that know
nothing of the chord frame, which is every other PNML tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: A position on the sheet, or a place in an arc's chord frame.
Point = tuple[float, float]

#: The shapes an arc is drawn in, as the editor's ``ArcShape`` names them.
SHAPES: tuple[str, ...] = ('straight', 'curved', 's-curved', 'l-shaped')

#: The kinds of arc, as the editor's ``ArcKind`` names them.
KINDS: tuple[str, ...] = ('normal', 'inhibitor')

#: Which way a guide lies: across the sheet, or up it.
ORIENTATIONS: tuple[str, ...] = ('horizontal', 'vertical')

#: Which way round a kind of arc may run, as the kinds of node at its source and
#: at its target.  A kind not named here runs whichever way the net allows.
DIRECTIONS: dict[str, tuple[str, str]] = {
    'inhibitor': ('place', 'transition'),
}


class InvalidNet(ValueError):
    """Raised when a document does not describe a net that can be drawn."""


def _point(value, what: str) -> Point:
    """Make a pair of numbers of anything that holds two.

    Parameters
    ----------
    value : collections.abc.Sequence
        The pair.
    what : str
        What it is, for the message when it is not a pair.

    Returns
    -------
    tuple of float
        The pair, as floats.

    Raises
    ------
    InvalidNet
        When it is not two numbers.
    """

    try:
        x, y = value
        return float(x), float(y)
    except (TypeError, ValueError) as error:
        raise InvalidNet(f'{what} is not a pair of numbers: {value!r}') from error


def _points(values, what: str) -> tuple[Point, ...]:
    """Make a tuple of points of anything that holds some.

    Parameters
    ----------
    values : collections.abc.Iterable
        The points.
    what : str
        What they are, for the message when one is not a point.

    Returns
    -------
    tuple
        The points, as pairs of floats.
    """

    return tuple(_point(value, what) for value in values)


@dataclass(frozen=True)
class PlaceData:
    """One place.

    Attributes
    ----------
    uuid : str
        What an arc names it by.
    name : str
        What the net calls it.
    position : tuple of float
        Its centre, in millimetres on the sheet.
    """

    uuid: str
    name: str
    position: Point

    def __post_init__(self) -> None:
        object.__setattr__(self, 'position', _point(self.position, f'place {self.name!r}'))


@dataclass(frozen=True)
class TransitionData:
    """One transition.

    Attributes
    ----------
    uuid : str
        What an arc names it by.
    name : str
        What the net calls it.
    position : tuple of float
        Its centre, in millimetres on the sheet.
    """

    uuid: str
    name: str
    position: Point

    def __post_init__(self) -> None:
        object.__setattr__(
            self, 'position', _point(self.position, f'transition {self.name!r}')
        )


@dataclass(frozen=True)
class ArcData:
    """One arc, and how it is drawn.

    Attributes
    ----------
    uuid : str
        The arc's own identity.
    source, target : str
        The UUIDs of the node it leaves and of the node it enters.
    source_port, target_port : int, optional
        Which connecting point of each it is attached to, by index, or ``None``
        for the point facing the other end that no arc is on yet — what a file
        from another tool, which knows nothing of connecting points, gives.
    weight : int
        How many tokens it carries, one at least.
    kind : str
        One of :data:`KINDS`.
    shape : str
        One of :data:`SHAPES`.
    controls : tuple, optional
        The two control points of a single bow, in the chord's frame, or
        ``None`` for the shape's default.
    points : tuple, optional
        The points an S or an L is led through, in the chord's frame and in
        order from the source, or ``None`` for the shape's default.  Kept
        whatever the shape, as the editor keeps them, so that an arc made
        straight and made an S again is the S it was.
    route : tuple
        Where the points an S or an L is led through are on the sheet, in
        millimetres and in order from the source.  Written for readers that
        know nothing of the chord frame, and never used to draw — the editor
        draws from ``points``.  Empty for a straight arc and a single bow, which
        are led through nothing.

        It is **worked out rather than kept**: it says again, in another frame,
        what ``points`` already says, and only something that knows where the
        connecting points are — the editor — can work it out.  So it takes no
        part in comparing two arcs, and no operation and no journal line carries
        it: two descriptions of one drawing are equal whether or not the route
        has been filled in.

    Raises
    ------
    InvalidNet
        When the kind or the shape is not one of those there are, the weight
        is below one, a connecting point is negative, or the controls are not
        two points.
    """

    uuid: str
    source: str
    target: str
    source_port: int | None
    target_port: int | None
    weight: int = 1
    kind: str = 'normal'
    shape: str = 'straight'
    controls: tuple[Point, Point] | None = None
    points: tuple[Point, ...] | None = None
    route: tuple[Point, ...] = field(default=(), compare=False)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise InvalidNet(f'arc {self.uuid!r} is of no kind there is: {self.kind!r}')
        if self.shape not in SHAPES:
            raise InvalidNet(f'arc {self.uuid!r} has no shape there is: {self.shape!r}')
        if self.weight < 1:
            raise InvalidNet(f'arc {self.uuid!r} carries a weight below one: {self.weight}')
        if any(port is not None and port < 0 for port in (self.source_port, self.target_port)):
            raise InvalidNet(f'arc {self.uuid!r} is attached to a negative connecting point')
        if self.controls is not None:
            controls = _points(self.controls, f'a control of arc {self.uuid!r}')
            if len(controls) != 2:
                raise InvalidNet(f'arc {self.uuid!r} has {len(controls)} controls, not two')
            object.__setattr__(self, 'controls', controls)
        if self.points is not None:
            object.__setattr__(
                self, 'points', _points(self.points, f'a point of arc {self.uuid!r}')
            )
        object.__setattr__(self, 'route', _points(self.route, f'the route of arc {self.uuid!r}'))


@dataclass(frozen=True)
class GuideData:
    """One guide, the line a drawing is lined up against.

    Attributes
    ----------
    orientation : str
        One of :data:`ORIENTATIONS`.
    position : float
        Where it crosses its ruler, in millimetres.
    """

    orientation: str
    position: float

    def __post_init__(self) -> None:
        if self.orientation not in ORIENTATIONS:
            raise InvalidNet(f'a guide lies no way there is: {self.orientation!r}')
        object.__setattr__(self, 'position', float(self.position))


@dataclass(frozen=True)
class NetDocument:
    """One Petri net as it is drawn.

    Attributes
    ----------
    model_uuid : str
        The UUID of the model the net is, which is its identity in the project.
    places : tuple of PlaceData
        The places, in the order they are to be read.
    transitions : tuple of TransitionData
        The transitions, likewise.
    arcs : tuple of ArcData
        The arcs, likewise.
    guides : tuple of GuideData
        The guides across the sheet.  Not part of the net, but part of the
        drawing of it.

    Raises
    ------
    InvalidNet
        When the net breaks one of the rules a net that can be drawn keeps —
        see the description of :mod:`simtwin_core.petri_net`.
    """

    model_uuid: str = ''
    places: tuple[PlaceData, ...] = ()
    transitions: tuple[TransitionData, ...] = ()
    arcs: tuple[ArcData, ...] = ()
    guides: tuple[GuideData, ...] = ()

    def __post_init__(self) -> None:
        for field in ('places', 'transitions', 'arcs', 'guides'):
            object.__setattr__(self, field, tuple(getattr(self, field)))
        self._check()

    def node(self, uuid: str) -> PlaceData | TransitionData | None:
        """Find a place or a transition by its UUID.

        Parameters
        ----------
        uuid : str
            What to look for.

        Returns
        -------
        PlaceData or TransitionData, optional
            The node, or ``None`` when the net holds none by that UUID.
        """

        for node in (*self.places, *self.transitions):
            if node.uuid == uuid:
                return node
        return None

    @property
    def names(self) -> tuple[str, ...]:
        """tuple of str: The names of the places, then of the transitions."""

        return tuple(node.name for node in (*self.places, *self.transitions))

    def _check(self) -> None:
        """Refuse a net that could not have been drawn.

        Raises
        ------
        InvalidNet
            At the first rule broken.
        """

        nodes: dict[str, str] = {}
        for group, members in (('place', self.places), ('transition', self.transitions)):
            for node in members:
                if node.uuid in nodes:
                    raise InvalidNet(f'two nodes share the UUID {node.uuid!r}')
                nodes[node.uuid] = group

        names = self.names
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise InvalidNet(f'two nodes share the name {repeated[0]!r}')

        seen_uuids = set(nodes)
        seen_arcs: set[tuple[str, str, str]] = set()
        for arc in self.arcs:
            if arc.uuid in seen_uuids:
                raise InvalidNet(f'the UUID {arc.uuid!r} is used twice')
            seen_uuids.add(arc.uuid)

            source, target = nodes.get(arc.source), nodes.get(arc.target)
            if source is None or target is None:
                raise InvalidNet(f'arc {arc.uuid!r} has an end that is not in the net')
            if source == target:
                raise InvalidNet(f'arc {arc.uuid!r} joins a {source} to a {target}')
            wanted = DIRECTIONS.get(arc.kind)
            if wanted is not None and (source, target) != wanted:
                raise InvalidNet(
                    f'arc {arc.uuid!r} is {arc.kind} and runs from a {source} to a {target}'
                )

            key = (arc.source, arc.target, arc.kind)
            if key in seen_arcs:
                raise InvalidNet(
                    f'two {arc.kind} arcs run the same way between the same two nodes'
                )
            seen_arcs.add(key)
