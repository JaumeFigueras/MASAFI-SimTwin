# Future improvements

Things that are known, deliberate and deferred — not bugs to be discovered later. Each entry says
what happens now, why it was left, and what the options are, so that picking one up does not mean
rediscovering the reasoning.

Something belongs here when it was **decided** rather than overlooked. A defect nobody chose is a
thing to fix, not to record.

---

## The file dialog does not follow the application theme

**Now.** *Browse…* in the New Project dialog, and *Open Project*, use Qt's native file dialog. On
Linux with the GTK 3 platform theme that is the GTK file chooser, which decides light or dark from
`gtk-theme` and `gtk-application-prefer-dark-theme`. GNOME 42 and later signal dark through
`color-scheme` alone, which GTK 3 ignores — so on a GNOME desktop set to dark, with the plain
`Adwaita` theme, the chooser comes up light while the rest of the application is dark. This is the
same root cause as the colour-scheme detection that `theme.detect_color_scheme()` now works around by
reading the XDG desktop portal.

**Why it is more than one desktop's problem.** A native dialog follows the *desktop*. The application
has a theme preference of its own, so choosing Dark on a light desktop — or Light on a dark one —
leaves the native chooser mismatched on every platform. That is what "native" means, not a defect to
be fixed.

**Options.**

- `QFileDialog.Option.DontUseNativeDialog`, behind one helper both call sites share. Qt draws the
  dialog, so the palette and style sheet apply and it matches in every combination. Verified working.
  The cost is a plainer dialog — no places sidebar, no type-ahead search — and it would replace the
  genuinely good native dialogs on Windows and macOS.
- `QT_QPA_PLATFORMTHEME=xdgdesktopportal` before the application is built. On GNOME the portal's
  chooser is the GTK 4 one, which does honour `prefer-dark`. Fixes only the *System default* case,
  cannot follow an in-app override, is Linux only, and changes Qt's platform theme for everything
  else too — including which file chooser is used at all.
- Native while the theme follows the desktop, Qt's own once it is overridden. Rejected for now: the
  dialog would change appearance because of a setting made somewhere else, and the System default
  case would still be wrong on GNOME.

**Where.** `masafi_simtwin/dialogs/new_project.py::NewProjectDialog.browse`,
`masafi_simtwin/main_window.py::MainWindow.open_project`.

---

## Changing the theme asks for a restart, though it need not

**Now.** `appearance/theme` is declared `restart=True`, so changing it raises the restart notice and
the Restart Now / Later question.

**Why.** A product decision, not a technical limit. `ThemeManager.apply()` repaints a running
application — palette, style sheet and icons — which is how the light and dark screenshots of this
project are taken from a single process.

**To change it.** Clear `restart=True` on that one declaration in `masafi_simtwin/preferences.py` and
apply the scheme when the settings are committed. The notice and the question then stop appearing for
it on their own, because both are driven by the flag. `appearance/language` genuinely does need the
restart and must keep it.

---

## Plural strings would break the translation gate

**Now.** No user-facing string uses `%n`. The first one will fail `make test-i18n`.

**Why.** `pylupdate6` emits a numerus message as `<translation type="unfinished"><numerusform /></translation>`
— an element with no text of its own. Two things then go wrong: `fill_from_source` in
`tools/update_translations.py` fills the English catalogue by substituting the whole `<translation>`
element with the source text, which would destroy the numerus forms; and
`test_every_message_is_translated` reads `translation.text`, which is empty for a numerus message, so
the message reads as untranslated in every language.

**To change it.** Teach both the tool and the test about `numerus="yes"`: fill each `<numerusform>`
of the source catalogue rather than the `<translation>`, and read the forms rather than the text.
Worth doing before the first statistic that counts something is shown.

---

## `project.py` belongs in `simtwin_core`

**Now.** The `.mfstz` container lives in `masafi_simtwin/project.py`, inside the GUI package.

**Why.** `simtwin_core` does not exist yet, and creating it for one module would settle more about
that package than has been designed.

**Cost of waiting: none.** The module is stdlib only — `zipfile` and `json` — and a test asserts that
no Qt name appears in it, so the move is a rename when the time comes.

---

## The project archive holds only its manifest

**Now.** A new `.mfstz` contains `manifest.json` and nothing else: `format`, `format_version`, the
name, when it was made and by which version.

**Why.** There is no model to put in it. What matters is that `format_version` is written from the
first file onwards, so a reader can always tell what it is looking at.

**Still to design.** Everything else: where the flow model goes, how sub-models are laid out, whether
the block library a project was built against is recorded in it. Also **Save** — the word means
nothing until there is something to write.

---

## Geometry is not remembered

**Now.** The main window opens at `DEFAULT_WINDOW_SIZE` every time; the splitter in the settings
dialog starts at the same place every time; dialogs open wherever the window manager puts them.

**Why.** `QSettings` can hold a `saveGeometry()` blob perfectly well, but it was never asked for.

**Related decision, still open.** Whether a `SimTwinDialog` base class is worth having for remembered
geometry, once there are enough dialogs to show what they actually share. There are four now — About,
Settings, New Project, and the two restart message boxes — which is about the point at which the
question can be answered honestly.

---

## The recent projects list bypasses the preferences layer

**Now.** `MainWindow` reads and writes `recent_projects` through a plain `QSettings`, while everything
else goes through `masafi_simtwin/preferences.py`.

**Why.** It is per-machine state rather than a declared preference: it has no page in the settings
dialog, no default worth naming, and it is a list rather than a choice.

**If it moves.** `Preference` would need a type the list round-trips through, and the settings file
would gain a key nobody edits by hand. Not obviously an improvement — recorded so the inconsistency
is a decision rather than an oversight.

---

## Copies are detected by identity, not yet by content

**Now.** A project carries a `uuid` generated once and never regenerated, and an append-only
`history` in its manifest whose entries are chained: each `log_item_id` is a truncated SHA-256 of the
entry together with the identifier of the entry before it, so altering or removing any entry
invalidates every entry after it. Each entry names the author, the installation, the application
version and the project's own UUID. Verification is deliberately **not** in this repository.

**What that catches.** A project copied and edited keeps the UUID and the original author's name in
its history. A history edited by hand breaks the chain. Two submissions edited on one machine share
an installation identifier.

**What it does not catch.** A student who rebuilds the model in a project of their own. Nothing in
the manifest can see that, because nothing in the manifest looks at the model.

**What would.** A fingerprint of the model's *topology*, once there is a model to fingerprint.
Renaming blocks and moving the layout changes names and coordinates but not the graph, so: strip
everything cosmetic — names, coordinates, colours, comments — then canonicalise with
Weisfeiler–Lehman refinement (each block labelled with its *type*, then
`label ← hash(label, sorted(neighbour labels))` for three or four rounds), and store both the digest
of the sorted final labels and the multiset of per-node labels. The digest catches identical networks
however renamed or reordered; the multiset gives a Jaccard similarity, which is what is actually
wanted — a copy with two blocks added should score 0.9, not "different". Hash the numeric parameters
separately: students who restructure usually keep the numbers, and an identical non-default random
seed is close to conclusive on its own.

**Deliberate non-goals.** None of this is tamper-*proof*, and it should not pretend to be: the format
is a readable zip and the chaining is in the source, so a determined student can rebuild the whole
chain. What the chain changes is the cost — they must forge every link and a plausible sequence of
timestamps, authors and versions, rather than delete one line. Against a history deleted outright,
the signal is its *shape*: three entries from the night before the deadline against a class average
of forty over two weeks. And no measure here should rely on secrecy of the *algorithm*; the topology
fingerprint works even when fully understood, because evading it means genuinely building a different
model.

**Where.** `masafi_simtwin/project.py` — `link()`, `history_entry()`, `record()`. The auditor is `src/bonus/mfstz-audit/`, which `.gitignore` excludes.

---

## Saving is write-through, and will not stay that way

**Now.** Every change to a project is written as it is made: adding, renaming or deleting a model
rewrites the whole archive at once. There is no Save, and none is wanted.

**Why it will not last.** The cost is not that saving is slow — it is that **a zip must be rewritten
whole**. A single entry cannot be updated in place. Adding a model is a rare, deliberate act, so
paying a full-archive write for it is right. Dragging a place three pixels is not, and once a model
canvas exists there will be hundreds of small mutations a minute against an archive that may be tens
of megabytes.

**The decided shape**, in the order it should be built:

1. **The document lives in memory.** Full writes happen on a timer *and* at boundaries — closing the
   project, quitting, before a simulation run, and on an explicit save. Keep `Ctrl+S` as "write now"
   even though nothing needs it; people reach for it. The interval is a preference.
2. **Journal every mutation.** An append-only side record, one small entry per edit — O(1) rather
   than O(project). Replayed on open if it is there, and deleted after a successful full write. This
   is what makes a crash lose nothing while keeping writes proportionate; simply lengthening the
   autosave interval widens the loss window without fixing the granularity.
3. **The undo stack stays in memory only.** Recovering *to* the crash point is enough — nobody needs
   to undo past it, and persisting undo is a great deal of machinery for almost none.

**Build it with the editor, not before.** The journal records *operations* and undo inverts them, and
neither exists until the Petri net canvas does. Undo needs `(operation, inverse)` records; the
journal needs `(operation)` — so building undo properly makes journalling one line per push, while
building the journal first means writing the operation representation twice.

**Two things that must not be buffered.** The **authorship history** is tiny and rare — session
open/close, model added/updated/removed — so it was never the cost, but buffering it puts gaps in the
chain, which is exactly the evidence that matters. It goes in the journal instead, folded into the
manifest at the next full write, ordered because the journal is append-only. **Simulation output**
streams straight into `logs/` as it is produced; it is large, write-once, and a crashed run is re-run
rather than recovered.

---

## Project files are not versioned

**Now.** A project has exactly one state on disk. A mistake survives the next write.

**The decided shape.** Keep numbered versions after each save and autosave, in the manner of VMS's
`NAME.EXT;n`:

- **In a sibling folder**, `Bottling Line.mfstz.versions/0007.mfstz`, rather than as sibling files.
  Loose siblings would be listed by the Open dialog's `*.mfstz` filter and could fill the recent
  projects list; a folder is just as visible and restorable by hand, and deletes as one unit.
- **Ascending numbers, newest highest** — true VMS, and not only for nostalgia: logrotate-style
  descending numbering renames every file on every save, which is N copies of a multi-megabyte
  archive per autosave. Ascending writes exactly one new file and touches nothing else.
- **A purge limit is not optional.** VMS had `/VERSION_LIMIT` for the same reason: an autosave every
  two minutes on a 50 MB project is about 1.5 GB an hour. Note that the limit and the interval
  interact — "keep the last ten" with a two-minute autosave is twenty minutes of history. Thinning
  (everything from the last hour, then hourly, then daily) beats a flat count, but a count is the
  place to start.
- **Skip the backup when nothing changed.** An autosave tick on an untouched project writes nothing.

**A side effect worth knowing.** Versions help the copy detection above — a real backup chain is more
evidence — but they also let a student restore an old state and shed inconvenient history. The chain
would then be conspicuously short beside their classmates', which is the same signal as deleting the
log outright.

---

## There is no tool to clear a lock by hand

**Now.** A project is locked while it is open, by a file beside it holding the pid, user, host and
time. `project.acquire()` already takes over a lock left by a process that is **no longer running on
this host**, so an ordinary crash clears itself. What has no answer is the rest: a lock left by a
process that is *hung* rather than gone, a lock written from another machine over a shared
directory, and a lock on a platform where liveness cannot be tested — Windows, where `os.kill(pid, 0)`
terminates a process rather than asking after it.

**What is wanted.** A `src/tools/` directory for utilities that ship with the application but are not
the application, and in it a lock tool that can say who holds a project, and release it.

**Design notes for whoever builds it.**

- **Killing by pid is the dangerous part, and it needs guarding.** Pids are recycled: a lock written
  by a crashed instance names a number that may since have been given to the user's browser. The
  tool must confirm the process really is a MASAFI-SimTwin instance — by its executable and command
  line, not by its pid existing — before it offers to end it, and it should default to *reporting*
  rather than killing.
- **Releasing the lock and ending the process are two different jobs.** Most of the time only the
  first is wanted: the holder is gone, or is on another machine, and the file is simply in the way.
  Ending a live instance is the rarer, more dangerous one and should have to be asked for.
- **Identifying a process across platforms is the awkward part.** `psutil` makes it easy and is a new
  dependency; the standard library makes it possible and platform-specific. Decide that before
  starting, not halfway through.
- **The name will collide.** The repository already has a top-level `tools/` for *development*
  tooling — `build_forms.py`, `update_translations.py` — and `src/bonus/` for tooling that must not
  ship at all. A third directory called `tools` under `src/` is a third meaning of the word. Either
  name it for what it is, or expect to explain the difference every time.
- **It has to be packaged to be of any use.** `src/tools` matches none of the `include` patterns in
  `pyproject.toml`, so it would not ship; a user-facing utility also wants a console entry point
  beside `masafi-simtwin`.

**Where.** `masafi_simtwin/project.py` — `lock_path()`, `holder_of()`, `acquire()`, `release()`.

---

## The canvas is ruled in millimetres and in nothing else

**Now.** A canvas is a sheet whose scene unit is one millimetre, and the rulers along its top and
left count in millimetres. `RulerUnit` names what a ruler counts in — a symbol, how many scene units
one of them is, and the ladder of spacings its labelled ticks may take — and `MILLIMETRES` is the
only one there is. Nothing chooses between them, so there is nothing to choose from.

**Why it is not the `units/distance` preference.** That preference is what a *model* measures in, and
only the two kinds of `KINDS_WITH_DISTANCE` have one at all: a Petri net's places have no position
that means anything to the simulation. The ruler is about the *drawing* — how big the picture is on
the sheet, which is the same question a printed page asks — and every kind of model has one of those.
Wiring the ruler to `units/distance` would tie the size of a picture to the units of the thing it is
a picture of, and would leave a Petri net's rulers with nothing to read.

**Options,** when a second unit is wanted.

- Add it to the table: `CENTIMETRES`, `INCHES` with their own step ladders. That part is one line
  each, and the grid would want a matching step so that the ticks keep falling on it.
- Choose it in the corner box, which is where the symbol already is: a click, a small menu, one
  canvas at a time. That is what drawing programs do, and it needs no preference at all.
- Or declare it a preference — `appearance/ruler` — so that every canvas opens in the same unit. It
  would be the first preference about a document rather than about the application, and it should
  not be `restart=True`: a ruler can change unit while it is on screen.

Inches would be the first unit whose ladder is not decimal (⅛, ¼, ½, 1, 3, 6, 12), which is the one
thing here that is more than a table entry.

---

## A rubber band picks up guides along with what it was aimed at

**Now.** A `Guide` is a scene item with `ItemIsSelectable`, and its shape runs the length of the
sheet. A rubber-band drag anywhere that crosses a guide therefore selects the guide too, and a
*Delete* after it takes the guide away with whatever else was caught. With no net items on the sheet
yet nothing is actually lost by this, which is why it is left.

**Why guides are scene items at all.** Because selecting one, dragging one, drawing one at any zoom
and picking one out from under the pointer are then the scene's work rather than hit-testing,
dragging and z-ordering written again by hand over the view. That is worth a great deal more than
the rubber band is worth, and the trade only bites once there is something else on the sheet to
rubber-band over.

**Options,** when the net's items arrive.

- `QGraphicsView.setRubberBandSelectionMode(ContainsItemShape)`. One line, and a guide can then never
  be caught, since no rubber band contains a line that runs off the sheet. It also changes how the
  net's own items are selected — they would have to be enclosed rather than touched — which is a
  decision about the editor, not about guides.
- Deselect the guides at the end of a rubber-band drag, leaving a click on a guide as the only way to
  select one. Small, and it keeps both selections behaving the way each should.
- Take the guides off the selection model altogether and keep them in a layer of their own, selected
  by hand. Most control, most code, and it gives back the reason they are scene items.

The second is the one to reach for first; the first is worth having only if the editor wants
enclosing selection anyway.

---

## The page is the application's, not the model's

**Now.** What paper a model is drawn on is two preferences of this installation —
`appearance/page_size` and `appearance/page_orientation` — so every model opened on this machine is
ruled into the same page, and the same model opened on another machine may be ruled into another. A
model carries its `units` in the manifest; it carries nothing about paper.

**Why it was done this way.** It is what was asked for, and it is the right default: the paper a
person prints on is a fact about their desk rather than about their model, and the machine already
knows it. The tiling is a guide to the eye, and nothing is written into a project by it — so
disagreeing machines disagree about a drawn line and about nothing else.

**When it will not be enough.** The moment a model is printed or exported to a fixed size, or the
moment two people share a project and want the same page breaks in it. Then the page belongs in the
model document, beside `units`, with the preference as the default for a *new* model rather than the
answer for every model.

**Options.**

- `page_size` and `page_orientation` in the model's manifest entry, defaulted from the preferences
  when the model is created, and shown in the Model Properties dialog beside the units. The
  preference becomes what a new model starts with.
- The same, but with an explicit *follow the application* value, so a model can be left to whatever
  the reader's desk prints on. That keeps the current behaviour available and makes it a choice.
- Leave it here and put the page in the export dialog instead, when there is one. That is the
  smallest change, and it says the tiling is only ever a hint.

---

## Deleting is *Delete*, and there is no undo

**Now.** `CanvasView.delete_selection()` removes whatever is selected — guides, places, transitions
and arcs alike — on *Delete* or *Backspace*, and `remove()` takes an item's arcs off with it. There
is no *Edit* menu, no context menu over an item, no *Cut*, *Copy* or *Paste*, and **nothing can be
undone**: a place deleted by accident is a place drawn again by hand, with the arcs that hung off it.

**Why it was done this way.** Arcs made deleting necessary — an arc drawn by mistake has to be
removable — but they did not make undo necessary, and undo is not a key handler. It is a command
stack that every change to the sheet has to go through, and writing one before there is a document
for it to restore *into* would be designing the model layer from the wrong end.

**When it will not be enough.** As soon as a net is big enough that redrawing part of it is real
work, which is the same moment saving matters. The two arrive together.

**Options.**

- A `QUndoStack` on the document, with every change to the net expressed as a `QUndoCommand`: add,
  remove, move, reweight. That is the whole answer and it is the one Qt already provides; the cost is
  that nothing may change the scene directly any more, which is a rule the code does not keep yet.
- *Delete* only, plus a confirmation for anything that removes an item with arcs on it. Cheap, and it
  turns a mistake into a question rather than into a loss.
- Wait for the model document and build the two together, so that an undo restores a thing with an
  identity rather than a new thing that looks the same.

---

## Nothing on the sheet is saved

**Now.** A place, a transition or an arc drawn on a Petri net document lives on the
`QGraphicsScene` and nowhere else. An item carries a `uuid` — arcs name their ends by it, so identity
now exists — but nothing writes it anywhere.
Closing the tab loses it; there is no `content` in the `.mfst` model document for it to be written
to, and `PetriNetEditor` does not mark the model as changed, because there is nothing to change.
Guides are in the same position, and for the same reason.

**Why it was done this way.** The document format is the piece that has not been designed, and a
drawing written into a format chosen in passing is a format that has to be migrated later. The
drawing layer can be built and looked at without it, which is what this is.

**When it will not be enough.** The moment a net is worth more than the session it was drawn in.

**Options.**

- Give the model document a `content` holding the net — the places and transitions with their UUIDs
  and their positions in millimetres, then the arcs, which are two UUIDs and a weight and no geometry
  at all — and the guides beside it, since a guide is part of the drawing even though it is not part
  of the net. That an arc has nothing to store but its ends is the clearest sign the split is the
  right one. Write-through, like the rest of
  the project (see *Saving is write-through*).
- Put the drawing in `simtwin_core` from the start, as the document the adapters will read, so that
  the editor is given a document rather than being one. That is where a document format belongs and
  it is where `project.py` is going anyway.

---

## An S bends where its points are and nowhere else

**Now.** `ArcShape.S_CURVED` is led through as many points as it is given, and the curve between them
is worked out rather than drawn: a uniform Catmull-Rom spline, with the control points of each
segment fixed at a sixth of the neighbours' chords. So the *route* is a person's to choose and the
*curvature* is not. Two consequences follow. Every corner of one arc is **either all smooth or all
sharp**: `ArcShape.L_SHAPED` is the same route with straight legs, so a right angle is had by
choosing it, but an arc with one sharp corner and the rest rounded cannot be drawn. And a spline
through points far apart **overshoots**: pull one point hard away from the line and the curve swings
past it before coming back, which is the spline doing what a spline does and not a bug.

**Why it was done this way.** Points that are *on* the curve are the ones a person can aim: putting a
point on a line means *the line goes here*. A poly-Bézier with its own pair of control handles at
every point is the general answer, and it is three handles per point to explain, place and keep
sensible — Inkscape's node editor, in a Petri net editor. The spline gives the whole of what the
gesture was asked for, *lead this arc round that item*, with one handle per point.

**When it will not be enough.** A net drawn in the orthogonal style, where arcs turn square corners;
or a layout so tight that an overshoot puts an arc through the item it was routed around.

**Options.**

- A per-point tension, or a *sharp / smooth* on each point's context menu, cutting the spline at that
  knot. Small, it is where a corner would go, and it is what would let one arc have both — the S and
  the L would then be defaults for what every point of an arc is rather than two shapes.
- Centripetal Catmull-Rom rather than uniform, which is the standard fix for the overshoot and is a
  change to one function, `catmull_rom()`.
- Control handles per point after all, as a fourth shape rather than in place of this one, so the
  simple gesture stays simple.

---

## An arc cannot be led round anything until it is made an S or an L

**Now.** *Add Point* and *Delete Point* are offered on the shapes that are led through points — the S
and the L — and on no other. A person who wants a bend in a straight arc chooses one of them first,
which gives that shape's own default points, and then adds points where they want them. Two visits to
the same menu for what feels like one wish.

**Why it was done this way.** A menu entry that silently changes what a thing *is* is worse than one
that asks. *Add Point* on a straight arc would have to turn it into an S to have anywhere to put the
point, and the arc would come back curved when all that was asked for was a bend.

**When it will not be enough.** The first time it is used in anger on a net that needs a dozen arcs
routed: the shape is chosen a dozen times to no purpose, the default S always being thrown away by
the points that follow.

**Options.**

- Offer *Add Point* on every shape and let it make the arc an S, starting from **no** points but the
  one being added — so a straight arc gains exactly the bend that was asked for and nothing else.
  That is the smallest change and probably the right one; it was left out only because it makes one
  gesture do two things.
- Give the S and the L no default points, so choosing one changes nothing until a point is put in.
  Honest, but then a shape named after its look does not look like it when chosen.
- Leave it, on the grounds that choosing a shape and shaping it are two decisions.

---

## Nothing keeps a hand-shaped curve sensible

**Now.** A control handle, and a point of an S, can be dragged anywhere at all — behind its own end,
miles off the sheet, on top of the other control. The curve follows, and a curve whose controls are wild is a curve that
loops back on itself or vanishes off the paper. Nothing prevents it and nothing puts it right.

**Why it was done this way.** A handle that fights the hand is worse than one that lets a person make
a mess and undo it. The bounds and the snapping that hold an *item* on the sheet are about where a
thing **is**; a control point is not where anything is, it is how a line bends.

**When it will not be enough.** The first time someone flings a handle and cannot find it again —
which is more likely than it sounds, the handles being small and the sheet being four metres wide.

**Options.**

- Hold a control point inside the sheet the way an item is held, through the same `bounds` callable.
  Cheap, and it means a handle can always be found.
- A *reset shape* on the arc's context menu, putting both controls back to `DEFAULT_CONTROLS` — and
  an S's points back to `DEFAULT_S_POINTS`. One line, and it is the way out of any mess rather than a
  rule against making one.
- Both. The second is worth having whatever happens to the first.

---

## There is nowhere to choose a kind of arc

**Now.** Every arc is an ordinary arc. `Arc` has no `kind`, and the Libraries pane deliberately does
not list arcs at all — an arc is a relation, not an element taken from a palette, which is the rule
that was chosen.

**Why it was done this way.** The P/T library has one kind of arc, so there is nothing to choose
between, and inventing a chooser for a choice of one is inventing chrome.

**When it will not be enough.** The attributed timed library, which has inhibitor and reset arcs.
They are genuinely different elements of a family, and something has to say which one the next arc
will be.

**Options.**

- A small chooser on the document — a segmented control or a drop-down over the canvas — holding the
  kinds the open model's library offers. It is where the choice is used, and it does not make the
  Libraries pane lie about what an arc is.
- Draw an ordinary arc and change its kind afterwards, in the properties pane. No chooser at all, one
  more step per inhibitor arc, and it keeps every gesture the same.
- Relax the rule and let the pane list arcs after all, as kinds rather than as drags. It was
  considered and turned down; it would have to be turned down again for the same reason or accepted
  for a new one.

---

## Nothing puts an arc's ends back on the points that face each other

**Now.** An arc keeps the connecting point it was attached to at each end until a person moves it:
dragging the handle at either end of a selected arc puts that end on another point, of the same item
or of another item the arc may be joined to. What there is no way to ask for is the *automatic*
answer — put both ends back on the points that face each other now — which is what `free_port_towards`
works out when an arc is first drawn and never again.

**Why it was done this way.** Fixed ends are what was asked for, twice: an arc that rearranged itself
whenever a place was nudged meant a net could never be laid out by hand and left alone. Now that an
end can be moved by hand the cost of that is small, and an action that does it automatically is a
convenience rather than a repair.

**When it will not be enough.** A net rearranged wholesale rather than nudged — every arc then has
ends facing the way they used to, and putting a dozen of them right by hand is a dozen drags.

**Options.**

- *Re-route* on the arc's context menu: `free_port_towards()` at each end, which is one line, and it
  is the old automatic behaviour offered as an action rather than imposed as a rule.
- The same over a selection rather than one arc, so a rearranged net is put right in one go.
- A *follow* flag per arc — automatic until a handle is dragged, fixed thereafter. It is the most
  convenient and the least predictable, an arc changing its mind about what it does.

---

## An arc has no elbow room when its two items overlap

**Now.** Two items dropped on top of one another, or dragged there, are joined by an arc a
millimetre long with an arrowhead as big as it is. Nothing prevents the overlap: `itemChange` holds
an item inside the sheet and snaps it to the millimetre, and has no opinion about what else is there.

**Why it was done this way.** Keeping items apart is a layout rule, and layout rules that push things
around are worse than a person who can see the picture. Nothing about a net is wrong when two items
touch; only the drawing is.

**When it will not be enough.** Never, quite — it is a thing a person does and undoes in the same
second. It is here because it is the one way the arcs can be made to look broken, so that the next
person to see it knows it was noticed.

**Options.**

- Refuse to drop an item where it would overlap another, which is easy and occasionally infuriating.
- Draw nothing when the two ends are closer together than the arrowhead is long, so the picture goes
  quiet instead of going wrong.
- Leave it, and let the person move the item.

---

## A transition always lies across the sheet

**Now.** A transition is 16 mm by 2 mm and drawn that way round, always. There is no rotation, no
*stand it up*, and `TRANSITION_LENGTH` and `TRANSITION_HEIGHT` are module constants rather than
anything the item carries.

**Why it was done this way.** It is the size and the orientation that were asked for, and rotation is
not one question but three — what turns (an item, or a selection), by how much (ninety degrees, or
freely), and what happens to the connecting points and to the snapping when it does. Answering those
by adding a `rotation` to the item would settle them in passing.

**When it will not be enough.** As soon as a net is laid out vertically, which is how a great many of
them are drawn: a horizontal bar between two places stacked above one another is the wrong way round.

**Options.**

- A `vertical` flag on the transition, swapping the two half-sizes, with *Rotate* on its context menu.
  Smallest, and it covers the case that actually comes up; the connecting points follow of their own
  accord, `port_offset()` being computed from the half-sizes.
- Qt's own `setRotation()` on the item, which rotates the drawing and the connecting points together
  and costs nothing to implement — but it rotates the snapping with it, so a turned item no longer
  lands on the millimetre grid the way an unturned one does.
- A free rotation with a handle, when there is a selection model and a properties pane to show the
  angle in. That is an editor feature rather than an item feature.
