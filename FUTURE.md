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

**Now.** No user-facing string uses `%n`. The first one will fail `make test-i18n`. The first string
that counts something — the arc tool bar's *Selected Arcs: {0}* — is worded as a label and a number
for exactly that reason, where *3 selected arcs* would have read better.

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

**Why.** It was true that `simtwin_core` did not exist. It does now — it holds `petri_net.py`, the
description of a drawn net — so what keeps `project.py` where it is is only that moving it is a piece
of work of its own, and there has been a feature in flight ever since.

**Cost of waiting: none.** The module is stdlib only — `zipfile` and `json` — and a test asserts that
no Qt name appears in it, so the move is a rename when the time comes.

---

## The archive holds models, and nothing else yet

**Now.** A `.mfstz` holds its manifest, the four folders, the history log and one `.pnml` file per
model. `simulations/` and `statistics/` are empty, and nothing in the archive records which version of
which library a project's models were built against.

**Why.** A simulation and a statistic are what running a net leaves behind, and nothing runs one yet.
The library question waits until there is more than one library to be built against.

**Still to design.** What a simulation is as a file — its parameters, its seed, and how much of a run
is worth keeping — and what a statistic is beside it. And whether a project records the library it was
built for, which is what would let a net saved today be read with certainty in five years.

---

## Geometry is not remembered

**Now.** The main window opens at `DEFAULT_WINDOW_SIZE` every time; the splitter in the settings
dialog starts at the same place every time; dialogs open wherever the window manager puts them.

**Why.** `QSettings` can hold a `saveGeometry()` blob perfectly well, but it was never asked for.

**Related decision, still open.** Whether a `SimTwinDialog` base class is worth having for remembered
geometry, once there are enough dialogs to show what they actually share. There are four of them now —
About, Settings, New Project and Model — beside the message boxes, which is about the point at which
the question can be answered honestly. Only two are worth remembering the size of, which is itself
part of the answer.

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
history — kept in `logs/history.jsonl`, one entry to a line, and not in the manifest — whose entries are
chained: each `log_item_id` is a truncated SHA-256 of the
entry together with the identifier of the entry before it, so altering or removing any entry
invalidates every entry after it. Each entry names the author, the installation, the application
version and the project's own UUID. Verification is deliberately **not** in this repository.

**What that catches.** A project copied and edited keeps the UUID and the original author's name in
its history. A history edited by hand breaks the chain. Two submissions edited on one machine share
an installation identifier.

**What it does not catch.** A student who rebuilds the model in a project of their own. Nothing in
the manifest can see that, because nothing in the manifest looks at the model.

**What would.** A fingerprint of the model's *topology*. There is a model to fingerprint now — a
`NetDocument` is a value, and `encode_net()` already writes one as plain data — so this is buildable
rather than hypothetical. Renaming nodes and moving the layout changes names and coordinates but not
the graph, so: strip everything cosmetic — names, coordinates, descriptions, the way the arcs bend —
then canonicalise with
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

**Where.** `masafi_simtwin/project.py` — `link()`, `history_entry()`, `record()`, `read_history()`. The auditor is `src/bonus/mfstz-audit/`, which `.gitignore` excludes.

---

## Saving happens at boundaries and on a timer, not as the work is done

**Now.** What a project *holds* — a model added, renamed, removed — is written as it is made. What a
model *is* — the net drawn on its sheet — is written at **boundaries**: *File → Save* (`Ctrl+S`),
closing a tab, closing the project, opening another, and quitting — and **every few minutes**, by the
autosave timer. A **journal** beside the archive holds every change not yet saved, so a session that
ends badly loses nothing; every save that changes the archive first keeps the project as it was, as a
numbered version. All of that is built; see *The journal*, *Saving* and *Versions are counted, not
thinned*.

**Why the drawing is not written as it is drawn.** Not because saving is slow — because **a zip must
be rewritten whole**. A single entry cannot be updated in place. Adding a model is a rare, deliberate
act, so paying a full-archive write for it is right; dragging a place three millimetres is not, and a
canvas produces hundreds of small changes a minute against an archive that may be tens of megabytes.
The journal is what makes the gap safe: O(1) per change rather than O(project), replayed when the
project is opened.

**Two things that must not be buffered.** The **authorship history** is tiny and rare — session
open/close, model added/updated/removed — so it was never the cost, but buffering it puts gaps in the
chain, which is exactly the evidence that matters. It goes in the journal instead, folded into the
history log at the next full write, ordered because the journal is append-only. Note that a *save*
writes no history entry at all, and should not: how often somebody pressed `Ctrl+S` is not evidence of
anything. **Simulation output**, when there is any, streams straight into `logs/` beside the history
log as it is produced; it is large, write-once, and a crashed run is re-run rather than recovered.

**What is still open.** Nothing about the model's own file. The undo stack stays in memory only — see
*Undo dies with the session* — and recovering *to* the crash point is enough.

---

## Versions are counted, not thinned

**Now.** Every save that changes the archive — by hand, at a boundary or by the autosave — first copies
the project **as it was** into `Bottling Line.mfstz.versions/`, in the manner of VMS's `NAME.EXT;n`:

- **In a sibling folder** rather than as sibling files. Loose siblings would be listed by the Open
  dialog's `*.mfstz` filter and could fill the recent projects list; a folder is just as visible and
  restorable by hand, and deletes as one unit.
- **Ascending numbers, newest highest**, four digits at least (`0007.mfstz`), the next being the highest
  there plus one — so the numbering goes on after a purge. Logrotate-style descending numbering would
  rename every file on every save; ascending writes exactly one new file and touches nothing else.
- **The state before the save, not after it** — decided with Jaume. No version is ever the same as the
  project, and the newest is always one step back.
- **No version when nothing changed.** A save or an autosave tick on an untouched project writes nothing.
- **A version that cannot be kept does not stop the save**; the sentence saying the project was saved
  says so.
- **Only files named as versions count**, and nothing else in the folder is ever deleted.

**The purge is a question, asked when the project opens** — decided with Jaume: more than fifty versions
(`VERSIONS_BEFORE_ASKING`) and the user is asked whether to delete the oldest and keep the last ten
(`VERSIONS_KEPT`). *No* keeps them all and the question comes back next time. Nothing else ever deletes
a version.

**Why a count and not thinning.** A count is the place to start, and a question means nothing is lost
behind the user's back. Note that the limit and the interval interact: at the default five minutes a
busy afternoon passes fifty versions in about four hours, and *the last ten* is then fifty minutes of
history. An autosave every two minutes on a 50 MB project is about 1.5 GB an hour.

**Options, when a count is not enough.**

- **Thinning**: everything from the last hour, then one an hour, then one a day. Beats a flat count for
  the same disk, and it is what a person restoring actually wants.
- A limit in megabytes rather than in versions, since a project's size is what fills a disk.
- A *Versions* entry in the *Project* menu: list them with their dates, restore one, delete some — which
  would also let the purge stop being a question at start-up.

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
*Delete* after it takes the guide away with whatever else was caught.

**The cost has arrived.** This was left when the sheet held nothing but guides, on the grounds that
nothing could be lost by it. There is a net on the sheet now, so a band drawn round three places on a
sheet with a guide across it deletes the guide as well — and *Cut* takes the places and leaves the
guide, guides not being copied, which is a second way the two disagree. It is now worth picking one of
the answers below rather than leaving it; it stays here because which answer is right is a decision
about how the editor selects, not about guides.

**A caption answered this for itself**, and the answer is worth reading here: a `Label` refuses a
selection nobody asked for, so a band never picks one up, while a click still does. That is the third
option below in miniature — the thing decides rather than the band — and it works because a caption is
never *wanted* from a band. A guide sometimes is, which is why the same trick is not simply copied
over.

**Why guides are scene items at all.** Because selecting one, dragging one, drawing one at any zoom
and picking one out from under the pointer are then the scene's work rather than hit-testing,
dragging and z-ordering written again by hand over the view. That is worth a great deal more than the
rubber band is worth, and none of the answers below gives it up.

**Options.**

- `QGraphicsView.setRubberBandSelectionMode(ContainsItemShape)`. One line, and a guide can then never
  be caught, since no rubber band contains a line that runs off the sheet. It also changes how the
  net's own items are selected — they would have to be enclosed rather than touched, and an arc, whose
  shape is a band along the whole line, would have to be enclosed end to end — which is a decision
  about the editor, not about guides.
- Deselect the guides at the end of a rubber-band drag, leaving a click on a guide as the only way to
  select one. Small, and it keeps both selections behaving the way each should.
- Take the guides off the selection model altogether and keep them in a layer of their own, selected
  by hand. Most control, most code, and it gives back the reason they are scene items.

The second is the one to reach for first; the first is worth having only if the editor wants
enclosing selection anyway, which for arcs it probably does not.

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

## Undo dies with the session

**Now.** Every change to a net can be undone and done again — one history per open document, *Undo*
and *Redo* in the *Edit* menu on `Ctrl+Z` and `Ctrl+Shift+Z`, acting on the tab being looked at. The
history lives **in memory only**: closing a tab, closing the project or quitting throws it away, so a
mistake made before the last save cannot be reached the next morning.

**Why it was done this way.** Persisting undo is a great deal of machinery for almost none: what a
person needs after a crash is their work back, not the ability to undo past it, and that is the
journal's job (see *Saving happens at boundaries and on a timer, not as the work is done*).

**When it will not be enough.** The day somebody wants yesterday's state back rather than the last
saved one.

**Options.**

- Keep the undo stack across a session of the project rather than of a tab, so that closing a tab and
  opening it again does not forget. Cheap, and it makes *Undo* reach into a document nobody is
  looking at, which is why it was not done.
- Write the undo history into the journal and read it back on open. Rejected above, and recorded so
  that it is a decision rather than an oversight.

---

## What the clipboard carries, and what it does not

**Now.** *Cut*, *Copy* and *Paste* carry the **nodes selected and the arcs between them**, as a
`NetDocument` under a MIME type of the application's own, and everything pasted is new: new UUIDs and
newly invented names. What that leaves out:

- **Guides are not copied**, nor cut when they are selected among what is.
- **An arc alone cannot be copied**, so there is no way to carry the shape and weight of an arc from one
  pair of nodes to another.
- **A paste always invents names.** Pasting into an empty model gives `P1` and `T1` there, but pasting a
  `Filler` into a model that has no `Filler` still gives `P3`: the name a person chose is lost even
  where it was free.
- **Two pastes with the pointer off the sheet land on top of one another**, both ten millimetres down
  and to the right of the original. What is pasted is left selected, so the second one can be dragged
  off the first, but nothing cascades.
- **Nothing else can read what is copied.** The clipboard carries one flavour, SimTwin's own — no PNML
  for another Petri net tool, no image for a document, no text for a mail.
- ***Edit* still has no *Delete***: deleting is the key and the context menus. It belongs beside these
  three when it comes, and `CanvasView.delete_selection()` is already the one place that does it.

**Why it was done this way.** Each of them is a decision that can be made once there is a reason to
prefer one answer, and each would be wrong to guess at. A guide is not part of the drawing anywhere
else in the application, so copying one would be the odd case rather than the rule. A name is a net's
identity and re-using one is how two nets come to disagree about what a name means; inventing every
time is the rule that cannot surprise. And a second flavour on the clipboard is a second thing to keep
in step with the first.

**When it will not be enough.** A person laying out the same subnet a dozen times, who will want the
paste to walk down the sheet; a person moving a whole model into another and finding every name
changed; and the first time somebody wants a net in a document or a mail.

**Options.**

- **Cascade a repeated paste**, remembering the last place a fragment landed and adding the offset
  again while the clipboard has not changed.
- **Keep a name when it is free**, inventing only for the clash. It is the friendlier rule and the
  harder one to explain, since whether a paste renames then depends on what is already there.
- **Copy the guides that cross what is copied**, or the selected ones, if a person ever says which they
  meant.
- **A second flavour**: PNML for another tool, `image/png` for a document, plain text for a mail. PNML
  is nearly free — the adapter already writes it — but it would refuse a piece holding an inhibitor
  arc, which the application's own flavour carries happily.

---

## A net drawn by another tool loses the way its arcs were drawn

**Now.** A PNML file gives an arc the points it bends at, and `from_pnml()` reads them into
`ArcData.route` — where the editor never looks. An arc carrying no tool data of SimTwin's own is drawn
**straight**, between the connecting points that face each other. Saved again, the route written is
the editor's own, so the corners the other tool drew are gone for good.

**Why it was done this way.** A route on the sheet and what SimTwin keeps are not the same thing. The
editor keeps a shape, two control points and a run of points in the arc's own chord frame, with its
ends attached to numbered connecting points. Turning a run of absolute positions back into that means
guessing which shape was meant — straight legs through the points, or a curve through them — and where
on each item the arc was attached. Reading a foreign net and drawing it *tidily* was judged better
than reading it and drawing it *wrongly*.

**When it will not be enough.** Importing a net laid out by hand in another tool, where the routes are
the work that was done.

**Options.**

- Take a foreign arc's positions as the points of an L: `route` is already read, one conversion puts
  them in the frame the editor wants, and straight legs are the safest reading of a polyline. A dozen
  lines in the adapter.
- Ask, once per file: *keep the routes as corners, or draw the arcs straight?*
- Leave it, on the grounds that a net from elsewhere is read to be worked on rather than preserved.

---

## What a model file does not remember

**Now.** A model's file holds the net and the guides — everything that decides what the drawing looks
like. It does not hold which models were open, which tab was on top, or where each sheet was scrolled
and at what zoom. Opening a project opens no tabs at all, and a model opened again opens on the top
left corner of its sheet.

**Why it was done this way.** That is the state of a *session*, not of a model. A file that changed
because somebody scrolled would be a file that cannot be compared, and two people sharing a project
would trade scroll positions in every diff — against a history whose whole value is that a change to
it means something.

**When it will not be enough.** A sheet four metres wide on which finding the part being worked on is
itself work, and a project of a dozen models where opening the right four is the first minute of every
session.

**Options.**

- Per machine, in `QSettings`, keyed by the project's UUID — the idiom the recent projects list already
  uses. Nothing enters the file, and it follows the person rather than the project.
- In the project, under a section per user, so that it follows the project between machines. It puts
  session state into a file whose point is that it changes only when the work does.
- In the model file, as `toolspecific`. Simplest, and rejected: it shares one person's scroll position
  with everybody.

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

## A drawn arc cannot be given a bend until it is made an S or an L

**Now.** An arc can be **routed as it is drawn**: while it is drawn click by click, a click on the bare
sheet lays a point, and the arc comes out led through the points laid — an L when *Straight* is
chosen on the tool bar, an S when *Curved* is. Once an arc is on the sheet, though, *Add Point* and
*Delete Point* are offered on the S and the L and on no other shape. A person who wants a bend in a
straight arc already drawn chooses one of them first, which gives that shape's own default points, and
then adds points where they want them. Two visits to the same menu for what feels like one wish.

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

## Every net is offered inhibitor arcs, and there are no reset arcs

**Now.** The arc tool bar along the top of a Petri net document offers two kinds of arc — normal and
inhibitor — on every net, whatever it is, and greys the inhibitor out with a *not available yet* tool tip:
`IMPLEMENTED_ARC_KINDS` is the normal arc alone, because a net holding an inhibitor arc could not be saved
while MASAFI-sim-petri has none, and none will be added until its P/T nets are finished. `add_arc()` still builds one when asked, for the tests and for later, and
`pnml.to_pnml()` refuses a net holding one with `UnsupportedNet`, so saving names the model rather than
writing a file that is not the net drawn. `ArcKind` has no reset member. Nothing records which type
of net a model is, P/T, timed or attributed timed, so nothing could say that a plain P/T net has no
business with an inhibitor arc. The kind is chosen on the bar and nowhere else: an arc's context menu
offers its shapes, its points and *Delete Arc* but not its kind, and the Libraries pane still lists no
arcs, an arc being a relation rather than an element taken from a palette.

**Why it was done this way.** The libraries are going to be simplified: every kind of Petri net will be
available on every sheet, and the type of a net will be **inferred from the elements it holds** rather
than chosen when the model is made — a net with an inhibitor arc in it is a net with inhibitor arcs.
Offering the inhibitor arc everywhere is that decision taken early. Reset arcs were left for later. The
kind was kept off the context menu because the bar already shows what a selected arc is and changes
it, and a menu of six checkable entries before *Delete Arc* is a menu to read rather than to use.

**When it will not be enough.** When the type of a net is inferred and something — a backend, a
validation, the model's properties — needs to be told it; and the first time a reset arc is wanted.

**Options.**

- Infer the type in one function over the items and the `ArcKind`s on the sheet, beside the editor,
  and let whatever needs the type ask it rather than keep a copy.
- Reset arcs as `ArcKind.RESET`: an entry in `KIND_DIRECTIONS` (a place to a transition, as for an
  inhibitor), an end mark of its own — a double arrowhead is the usual one — and a label. The bar builds
  its buttons from `ArcKind`, so the button comes with the kind.
- The kind on the context menu after all, as a second exclusive group under the shapes, if the bar
  turns out to be too far from where people work.

---

## Two arcs may join the same pair only when they are of different kinds

**Now.** SimTwin refuses a second arc of one kind from the same place to the same transition, or from the
same transition to the same place — as MASAFI-sim-petri does: *An arc already joins place 'P1' to
transition 'T1'; change its weight instead of adding a second arc*. `arc_between()` in `arc.py` is the one
place the rule is written.

**Decided.** At most **one arc per source, target and kind**. Between a place and a transition that
allows one normal arc from the place to the transition, one normal arc back, and — once inhibitor arcs
are built — one inhibitor arc from the place to the transition beside the normal one. A second arc of
the same kind the same way round is refused **silently**, the way an arc between two places is, in every
gesture that can make one: drawing an arc, moving an end of one, and `add_arc()`. Wanting *more* of an
arc is what its weight is for.

**Why.** A second identical arc says nothing a weight does not, and PNML and the library both hold one
arc per pair and direction.

**What has to change when inhibitor arcs arrive.** The library's rule does not look at the kind: it
refuses any second arc between a pair in one direction, so the normal and inhibitor pair cannot be built
until it does. `element_for()` matches an arc on its two ends alone and has the same limit.

---

## Names are unique

**Now.** The names of a net's places and transitions are unique **ignoring case**, every node against
every other, a place and a transition included — `name_problem()` in `simtwin_core/petri_net.py` is the
rule, and a `NetDocument` breaking it is refused. `Line` and `line` are two names to Python but one file on
Windows and macOS, and these names are meant to become modules. Two models of a project may still share a
name — the second file is given `_2`.

**Decided.** Equal names are forbidden, ignoring case, across all the nodes of a net.

**Still open.**

- The models of a project against each other, which would retire the `_2` suffix.
- MASAFI-sim-petri accepts a place and a transition of **the same** name, writing both with one PNML `id`,
  so the file holds a duplicate identifier. SimTwin never gives it such a net; the library should still
  refuse one.

---

## Names are Python identifiers

**Now.** A project and a model may be called anything, spaces and digits included — `Bottling Line`,
`Filling Station` — and a file name is made from a model's name by turning spaces into underscores.
MASAFI-sim-petri accepts names such as `Buffer 1` and `1st` and writes them as PNML ids, which a PNML id
may not be.

**Decided.** **No spaces anywhere in a project** — the project, its models, its places and transitions —
only underscores and CamelCase, and **no digit as the first character**, because the Petri nets built here
will be turned into Python modules. A name that is already a valid identifier needs no mangling to become a module, a class or
an attribute, so the name a person chose is the name in the generated code. It also makes every name a
valid PNML id.

A digit anywhere else is allowed — `Buffer_2`, `Station3` — which is exactly Python's own rule for an
identifier, so the names the editor invents meanwhile, `P1` and `T1`, already keep it.

**Enforced for places and transitions**, as decided with Jaume: `name_problem()` refuses a name that is
empty, holds a letter outside ASCII (`Estació`), starts with a digit, is otherwise not an identifier, or is
a Python keyword (`class`, `None`). Soft keywords (`match`, `type`) and the names of standard modules
(`random`, `time`) are allowed — both are valid module names, and shadowing a module is the generated
code's to avoid. Every name allowed is one MASAFI-sim-petri accepts; the library asks only that a name is
not blank.

**A PNML file from another tool whose names break the rule is not opened** — `buffer 1` makes it
`UnreadableNet`, though the library reads it. Chosen because the rule is the net's, not the editor's.
Options, when such files turn up: rename on import (`buffer_1`, with a clash made unique) and say which
names were changed; or open read-only until every name is fixed.

**Still open.** The New Project and Model dialogs do not enforce the rule yet, so a project and its models
may still be called anything. Projects made before the rule are development versions and are not converted.

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

## A node is described in one line

**Now.** A place or a transition carries a `description` — a person's words about what it is for, seen
by no backend — and it is **one line**: `NetDocument` refuses text holding a newline or a carriage
return, the Properties pane offers a single-line field, and the editor refuses the change as well, so
the rule holds wherever it is asked for. The line may be long; the label on the sheet wraps it.

**Why it was done this way.** A description is drawn on the sheet beside its node, and something that
can be twenty lines is something that can bury the net it describes. One line also survives every
place it has to pass through unremarked — a PNML attribute, a JSON string in the journal and on the
clipboard, a field in a form — where a paragraph would want a text area in the pane, a decision about
how much of it to draw, and an answer to what a line break means in an XML attribute.

**When it will not be enough.** The first model somebody documents properly: the reason a transition is
there, what its rate means, and where the number came from, which is a paragraph and not a line.

**Options.**

- **Two fields**: keep the one-line description as the caption and add a `note` of any length, edited
  in a text area on the Properties pane and never drawn on the sheet. It keeps the label short by
  construction, which is the property worth keeping.
- **Let the description be many lines** and draw only the first on the sheet, with the rest in the pane
  and in a tool tip. One field, and the sheet no longer shows all of what is there — which is the thing
  to be sure about before choosing it.
- **Nothing on the node, and a notes pane for the model as a whole.** Least in the way of the drawing,
  and it loses the attachment to the thing being described.

---

## A label is moved and resized by hand, and nothing puts it back or out of the way

**Now.** A node's name and description are written in one box, `Name: Description`, wrapped to
`LABEL_WIDTH`. Until it is moved the box is in a fixed place: under a place, centred; across a
transition, which is under a bar lying across the sheet and beside one standing up. It can be
**selected** and **dragged**, and a dragged box keeps a `label_offset` — its centre relative to the
node's — which is written where PNML keeps one (`<name><graphics><offset>`). It can be **given another
width** by the handles on its sides, which keeps a `label_width` in SimTwin's own tool data, PNML having
no width for a label. Only the width: the height is what the wrap makes of it.

A resized box is **drawn as wide as it was made**, however little text is in it, and is **not held on
the paper** while it is resized — only while it is moved — so a box widened at the edge of the sheet can
reach off it. It cannot be made narrower than `MIN_LABEL_WIDTH` (5 mm), and a word wider than the box is
broken. Like a move, there is no way back to the editor's own width except *Undo*.

An **arc's weight** is the same kind of box, moved but never resized. A moved number is kept in the
arc's **chord frame** — how far along and across, as fractions of the chord, the way its bends are — so
it turns and scales with the arc: a number put 5 mm off a long arc is 2 mm off once the arc is dragged to
half its length, and on a very short arc it all but sits on the line. The chord frame is SimTwin's own
(`<simtwin:caption>` in the arc's tool data). PNML's `<inscription><graphics><offset>` is **written for
other tools and never read back**, as an arc's route is not: it is in millimetres from the middle of the
drawn arc, which only the editor can work out, and it exists only while the weight is not one, since the
library writes no `inscription` for a weight of one. So an offset another tool wrote for a weight is
passed over, and the number sits beside the middle of the line.

A moved box is **where the person put it, and nothing moves it again**: not a longer description (the
box grows about its centre, so it can grow over its own node), not a transition turned (a box put beside
a bar lying across stays there when the bar stands up), and not a node dragged near it. There is **no
way back** to the fixed place except *Undo*, which gives back `None` rather than the place the box
happened to be in. The box is drawn straight onto the sheet with nothing behind it, so an arc can still
run across the words.

**Why it was done this way.** A box nobody moved costs nothing — no offset stored, nothing in the file —
and follows its text and its bar as it always did; that is what `None` keeps. A box somebody moved is a
decision, and a rule that shifted it afterwards would be undoing that decision behind their back. The
offset is kept relative to the node, so the pair go about the sheet together, and it is PNML's own
element, so another tool's offset is read and ours is read by another tool. The fixed places were
chosen for where each shape's arcs are: a transition is met at its ends, so its box goes across it, and
a place is met from every side, so its box goes where a drawn net has always put a name — under it.

Backing each box with the colour of the paper was considered and left: it would hide the arcs that run
under it, and a net where the lines disappear behind captions is worse than one where a line crosses a
word.

**When it will not be enough.** A dense net, where boxes collide with each other and with the arcs; a
long description of a moved box, which grows over its node; a box moved beside a bar that is later
stood up; and anybody who wants a box back where it started long after *Undo* has stopped reaching.

**Options.**

- **A *Reset Label Position* entry** on the item's context menu, recording a `MoveLabel` to `None`
  (and a *Reset Label Width* beside it, a `SetLabelWidth` to `None`, or one entry doing both). Small,
  and the obvious first addition if a person asks for it.
- **Reading another tool's inscription offset**, by handing it to the editor as millimetres from the
  middle of the arc and turning it into the chord frame there, the way a node without positions is laid
  out. Worth it once files from other tools with placed weights are met.
- **Keeping a moved weight a fixed distance off the line** rather than scaling with the chord — an
  offset from the middle of the arc, turned with the arc. It would not follow the curve's shape the way
  the chord frame does.
- **Holding a resized box on the paper**, by capping the width at what reaches the sheet's edge from
  the side held still. Left while a box off the edge is something nobody has met.
- **Keeping the offset from the fixed place** rather than from the node's centre, so a moved box follows
  its text and its bar the way an unmoved one does. It would no longer be PNML's offset, which is from
  the node, so the file would have to convert both ways.

**Options.**

- **A choice of side** — above, below, left, right — one enumerated value per node rather than a
  position. Much less to store and to explain than an offset, and it covers most of what a person
  dragging a label is trying to do. It was passed over in favour of a free offset, which is being
  built; it is still the smaller answer if the offset turns out to be more freedom than anybody wants.
- **Laying them out**, moving each box off whatever it collides with. Nothing to store at all, and no
  two people would agree about where a box should have gone.

---

## A transition stands one of two ways round, and nothing else turns at all

**Now.** A transition lies across the sheet or stands up it — `Transition.vertical`, *Rotate* on its
context menu, swapping the two half-sizes and giving the connecting points a quarter turn with them.
There is nothing between the two, no other item turns (a circle has no way round), and nothing turns
a whole selection from the menu bar: `PetriNetEditor.rotate()` takes as many nodes as it is given, but
the only thing that calls it is a context menu, which is aimed at one item.

**Why it was done this way.** It is the case that actually comes up — a net laid out from top to
bottom, where a horizontal bar between two places stacked above one another is the wrong way round —
and it settles none of the questions a real rotation asks. Qt's own `setRotation()` would have cost
nothing to write, but it rotates the snapping with the item, so a turned item no longer lands on the
millimetre grid the way an unturned one does; a free angle needs a handle to drag and somewhere to show
the angle, which is an editor feature rather than an item one. Two ways round need neither: the bar is
an upright rectangle or a flat one, and everything on the sheet goes on snapping to the millimetre.

**What follows from it, and was chosen.** An arc keeps the *index* of the connecting point it was drawn
to, so turning a bar takes the arc round with it: an arc that came into the middle of the top edge comes
into the middle of the right-hand edge once the bar is upright, rather than being re-aimed at whatever
now faces it. That is the same rule that makes a net laid out by hand stay laid out — see *Nothing puts an arc's
ends back on the points that face each other* — and the way to put such an arc where it is wanted is to
drag its end handle. Re-choosing the points on a turn would be re-drawing arcs nobody asked to have
re-drawn.

**When it will not be enough.** A model drawn at an angle — a diagonal flow, a shop floor plan the net
is laid over — or a net where the transitions are labelled along their length. Also the first time a
person selects a dozen items and wants them all turned at once.

**Options.**

- *Rotate* in the *Edit* menu, on the whole selection, over the `rotate()` that already takes many.
  Small, and the recorded change is already one change for as many nodes as are given.
- A free rotation with a handle, once there is somewhere to show the angle. It brings back the snapping
  question the two ways round avoid, and every item would then need a rotation rather than one item
  needing a flag.

---

## A project's companions do not follow it when it is renamed or moved

**Now.** A project is one file, but three things live beside it under its name: the lock
(`Bottling Line.mfstz.lock`), the journal (`.journal`) and the versions (`.versions/`). Renaming or
moving the `.mfstz` in a file manager leaves them behind. A lock or a journal left behind is harmless or
nearly so — the lock names a process that is gone, and a journal left behind is simply not found — but a
versions folder left behind is history the renamed project no longer knows it has, and a new project of
the old name would take it over and number on from it.

**Why it was done this way.** Beside rather than inside, for the reason each of them gives: a zip cannot
be appended to or updated in place, and a crash must leave something that can be cleared without opening
the project it blocks. The application never sees a file being renamed, so it cannot carry anything
along.

**Options.**

- *Save As…* / *Move Project…* in the application, carrying the three along. It fixes the case the
  application takes part in and no other.
- Recognise a versions folder by the project's UUID rather than by its name: every version holds the
  manifest, so a folder whose versions carry another UUID can be told apart and left alone.
- Say it in the documentation, and leave it.

---

## An item's own style is written for SimTwin alone

**Now.** A place, a transition or an arc with a text or line style of its own carries it in SimTwin's
tool data, as `<simtwin:lettering>` and `<simtwin:stroke>`. PNML has places of its own for both — a
node's `<graphics><line color width/>` and an annotation's `<graphics><font family size weight style
align/>` — and nothing is written there, so another PNML tool opening the file draws the net in its own
colours and fonts, and a style another tool wrote there is not read.

**Why it was done this way.** SimTwin's styles do not map onto PNML's cleanly. *Automatic* — the theme's
own ink — has no PNML colour; PNML's `size` is a CSS length rather than millimetres; its `align` has no
*justified* that leaves the last line to the left; and a style in SimTwin is complete or absent, where
PNML's attributes each stand alone. Writing ours alone keeps one meaning for each field and makes the file
read back exactly.

**When it will not be enough.** Exchanging coloured nets with a tool such as PIPE or Tina, in either
direction.

**Options.**

- **Write PNML's own graphics as well**, the way an arc's route and its inscription offset are: millimetres
  as `mm` lengths, an explicit colour as it is, *Automatic* left out. Written for other tools, never read
  back.
- **Read PNML's graphics** when the tool's data is absent, turning a foreign `line` and `font` into a
  complete style from the defaults of the moment.

---

## A version opened by itself is a second copy of the project

**Now.** A version is a whole `.mfstz`, and nothing stops it being opened from inside its folder. It
then carries the same UUID as the project it was kept from, and opening it gives it a lock, a journal
and a versions folder of its own — inside the versions folder — and adds an *opened* entry to its
history, so the version no longer is what was kept.

**Why it was done this way.** Keeping versions was the step; restoring one was not designed, and until it
is, opening one by hand is how a person gets something back.

**Options.**

- Recognise a version on opening — a file inside a `.versions` folder — and offer *Restore* (copy it over
  the project, itself keeping a version first) or *Open a copy* (a new UUID, somewhere else) rather than
  opening it in place.
- Open a version read-only: no lock, no journal, no history entry, nothing saved.

---

## A selection of more than one kind cannot be given an appearance

**Now.** The Properties pane shows the appearance of what is selected while that is **places alone,
transitions alone, or arcs alone** — the node page and the arc page. Select a place and an arc together
and the pane shows the *selection* page, which counts what is in the selection and offers nothing to
edit, so the way to colour a net is one kind at a time.

**Why it was done this way.** The pane was built that way before there were styles: a page shows the
properties of one kind of thing, because a name, a marking and a weight are not the same questions. The
appearance is the first thing every kind of item has in common, and it sits in a box of its own below
the pages; putting that box on the selection page as well would mean deciding what the *name* of the
kind of text is for a mixed selection — a place's caption and an arc's weight take their typefaces from
different preferences, and an arc may take no typeface at all.

**When it will not be enough.** Colouring a whole subnet: a person selects the three places, the two
transitions and the arcs between them, and has to do it in three passes.

**Options.**

- **Show the appearance box on the selection page too**, resolving each item against its own kind and
  offering only what they all can take — no typeface and no alignment as soon as an arc is among them,
  which is the rule the arc page already keeps.
- **Ask what the selection has in common** and show the rest as partly ticked, which is what the box
  already does for several items of one kind.
- **Leave it**, and let *Reset* and the context menu (the step after this one) carry the quick cases.

---

## The mark an arc ends in does not grow with the line it is drawn with

**Now.** An arc's line takes the width it is given — anything from a tenth of a millimetre to three —
but the arrowhead and the inhibitor ring stay the size they always were: `ARROW_LENGTH` 2.4 mm by
`ARROW_WIDTH` 1.8 mm, and a ring of half that across. So a hairline arc ends in a head that looks large
for it, and an arc drawn three millimetres thick ends in a head barely wider than its own line, which
at that width reads as the line simply stopping.

**Why it was done this way.** The head is *what an arc is* rather than how it was drawn: one size on
every arc of a net is what makes a normal arc and an inhibitor arc tell themselves apart at a glance,
and it is the rule that was decided when the heads were built — a curved arc's head must be neither
stubbier nor longer than a straight one's. Widths arrived afterwards, and making the head follow the
width would have changed every net drawn so far. Line patterns and arrow sizes were named from the
start as a later piece of work, so this is where that piece begins.

**When it will not be enough.** A net drawn thick for a projector or a poster, where the heads
disappear into the lines; a net drawn hairline-fine, where they overwhelm them.

**Options.**

- **Measure the head from the width**, as a multiple of it, held between a smallest and a largest size
  so that a hairline arc still ends in something visible.
- **Give the head its own size** in the line style, beside the width, which is what a drawing program
  usually offers and what the *line patterns and arrow sizes* work will need anyway.
- **Leave it**, and let a person who wants a heavier head say so when arrow sizes exist.

---

## A place's tokens take the family its caption is written in and nothing else

**Now.** The number of tokens inside a place is lettered in the **family** of that place's caption and
in nothing else of its style: the size is `TOKEN_NUMBER_HEIGHT` (4 mm, narrowed to
`TOKEN_NUMBER_WIDTH` when the number is long), it is always upright and unemphasised, and it is drawn
in the place's *line* colour rather than its text colour. So giving a place bigger, bold or coloured
lettering changes the caption beside it and leaves the number in the circle where it was.

**Why it was done this way.** Decided with Jaume. A count inside a circle is not a caption: it is sized
to fit the circle it sits in, and a number at whatever size a description happens to be would run out
of the place or shrink to nothing. Bold and italic say something about a *name*; on a count they read
as a different count. The family is taken so that a net lettered in one family does not show a second
one inside its places, which is the one part of the style a number can honour without fighting the
circle.

**When it will not be enough.** A net whose places are drawn much larger or much smaller than a
centimetre; a house style that wants the marking set apart from the drawing; a printed net where 4 mm
is not the right size for a number.

**Options.**

- **Measure the number from the place** rather than from a constant — a fraction of the diameter — so
  that it follows if a place's size ever becomes a thing that can be chosen.
- **Give the tokens a style of their own** on the item, as a guard would have, which is the same answer
  as the entry above and the same cost.
- **Take the size from the caption** and clamp it to what the circle holds, which honours the choice as
  far as it can be honoured and silently stops honouring it after that.

---

## A guard and a time function are written one way for the whole application

**Now.** `petri_net/guard_bold`, `petri_net/guard_italic`, `petri_net/time_function_bold` and
`petri_net/time_function_italic` say how a guard and a time function are written, and they say it for
every transition of every model. Italic for both is what they start as. Neither exists yet: a
transition has no guard and no time function to write, so these are stored and shown and nothing reads
them, which is deliberate — the typefaces were decided with Jaume while the decision was being made,
and storing them now is what keeps them from being decided twice.

**Why it was done this way.** A guard is a piece of code and a time function is a piece of mathematics,
and both are conventionally set apart from a plain name by being written in italics; that is a
typographic convention of the whole drawing rather than a property of one transition. An item's own
`TextStyle` covers its **name and description** — one style per item, which is what the Properties pane
offers — so there is nowhere on a single transition for a *second* style to live without either a second
style field on every node or a style that knows which of an item's several texts it applies to.

**When it will not be enough.** Marking one transition's guard out from the others — a guard under
discussion, a time function that is provisional — or a model whose guards should read as plain text
because they are being shown to people who do not read code.

**Options.**

- **A second style on a transition**, `guard_style`, `None` meaning the application's default, written
  to the file beside the item's own `lettering`. It is the existing mechanism once more, at the cost of
  a second *Use app default …* pair on the Properties pane for transitions alone.
- **Give a style a part to apply to**, so one item may carry several, each naming the text it dresses.
  More general and more to explain; it is what a word processor's character styles are.
- **Leave it application-wide** and let a person who wants one guard to stand out say so in the guard
  itself, when guards have a syntax that allows it.

---

## How a net is drawn by default is settled per machine, not per model

**Now.** The defaults a net is drawn the way of — the font, its size, the typefaces of each kind
of text, the alignment, the two colours and the line width — are preferences, under `petri_net/` in
this user's settings file on this machine. A model carries only what an item was given **of its
own**. So a project opened on another desk is drawn in that desk's defaults, and a net that reads one
way here can read another way there with nothing in the file having changed. A font is the sharpest
case: one this machine has not got is fallen back on silently, so even an item's *own* style is drawn
in something else here.

**Why it was done this way.** Decided with Jaume, option *c* of three. Defaults are a way of working
rather than a property of a net — a person who likes large lettering likes it in every model they
open — and the thing they are read against, the fonts a machine has, is a property of the machine and
not of the document. Keeping them per machine is also what lets the settings dialog stay one dialog:
a preference that could be set in two places needs to say which one is in force.

**When it will not be enough.** Handing a model to students or to a colleague and wanting it to look
as it looked here; a house style that belongs to a project rather than to whoever opens it; printing
from a machine other than the one the net was drawn on.

**Options.**

- **Keep the defaults in the project**, in the manifest, with the preferences becoming what a *new*
  project starts from. A model would then be drawn the same anywhere, and the settings dialog would
  grow a second column or a second page for *this project*.
- **Keep them with the model**, in SimTwin's own tool data beside the per-item styles, which is where
  the per-item ones already are. It is the same answer one model at a time rather than one project at
  a time, and it costs a net nothing where nobody has chosen anything.
- **Leave them per machine and add *Apply my defaults to this model***, which fills in every item's
  own style once. The drawing becomes explicit and travels intact, and the defaults go on being a way
  of working; the cost is that every item then carries a style, and a later change to the defaults
  reaches none of them.

---

## Printing is to a file and never to a printer

**Now.** *File → Export to PDF…* writes a PDF and that is the whole of printing. There is no *Print…*,
no `QPrintDialog`, no printer chosen, no copies and no page range. `Ctrl+P` is deliberately unbound —
`Ctrl+Shift+E` is the export's key — so that the one key everybody reaches for is still free for the
thing it actually means.

**Why it was done this way.** Decided with Jaume: a file was what was asked for, and it is the whole of
what a report, a thesis or a colleague needs. A print dialog brings a page-range and copies interface
that would have to be written and translated, and a printer's own driver to misbehave; and every
platform's *Print to File* reaches the same PDF the export writes directly, by a longer route.

**When it will not be enough.** Printing a net on paper without saving a file first; a plotter, which is
where a sheet four metres wide is going; a printer whose paper is not the paper the settings say.

**Options.**

- **Add *Print…* on `Ctrl+P` over the same renderer.** `masafi_simtwin.documents.printing` already takes
  a `QPageSize`, an orientation and a `QPainter`; a `QPrinter` is one in place of the `QPdfWriter`, and
  `QPrintDialog`'s page range is a slice of what `pages_of()` returns. The work is the dialog and what
  it is allowed to change, not the drawing.
- **Print the preview first**, since `draw_page()` already draws onto any painter — a `QPrintPreviewDialog`
  is the same call onto its own.
- **Leave it as it is** and let the operating system's *Print* on the written file do it, which is what
  anybody printing a PDF does anyway.

---

## A printed page carries the drawing and nothing else

**Now.** A page is the net on white paper: no margins (the layout is set to nought all round), no
header, no footer, no page number, no model name, no date, no crop marks, and no guides. A net drawn
across a seam is printed in part on each page, and nothing on either page says which page it is or
which edge joins which.

**Why it was done this way.** Decided with Jaume: *just the net*. The page is then exactly the picture,
which is what goes into a report; anything else is furniture that has to be placed, sized, lettered and
translated, and that would be drawn in a margin the sheet does not have. The guides go for the reason
*Copy* leaves them out — a guide is what the drawing is lined up against rather than part of it.

**When it will not be enough.** A net over several pages that has to be laid out on a table and
assembled — the pages cannot be told apart. A printer whose unprintable margin eats the edge of a
drawing laid out to the paper's edge, which nought margins invite. A working print, where the guides
are the point.

**Options.**

- **A footer, behind a setting**, saying the model's name and *2 of 5*. It needs a margin to live in,
  which means the sheet's pages and the file's pages stop being the same rectangle — or the footer is
  drawn over the drawing, which is worse.
- **Crop marks in the corners**, which assemble without lettering and need far less room than a footer.
- **Print the guides**, behind a setting, for a working print. `as_printed()` is the one place that
  hides them.
- **A margin of its own**, so that a drawing at the edge of a page is not clipped by the printer. It
  would have to shrink the drawing or move it, and either breaks *true millimetres* — see below.

---

## Only the pages that hold something are printed, so a sparse net does not tile

**Now.** `pages_of()` gives every tile of the sheet that anything drawn reaches into, in reading order,
and nothing else. A net in one corner is one page; a net across a seam is two. But two nets at opposite
corners of the sheet are **two pages with nothing between them**, and nothing in the file says how far
apart they were.

**Why it was done this way.** The answer chosen when it was asked: no blank pages, ever. The sheet is
two hundred pages and almost all of it is empty, so printing the rectangular block that spans the
drawing would mean sixty blank pages for two nets in opposite corners, and printing the whole sheet is
absurd.

**When it will not be enough.** Exactly the case above: a drawing meant to be assembled out of its
pages, where the blanks are what carry the spacing.

**Options.**

- **The rectangular block of tiles**, behind a setting — the same function with `min`/`max` over the
  occupied rows and columns instead of a test per tile. A dozen lines.
- **Blank pages only *between* occupied ones on a row**, which assembles a row without paying for a
  column of empty pages.
- **Say what was left out**: a sentence in the status bar naming how many pages were skipped, so the
  ragged set is at least not a surprise.

---

## Nothing scales a print, and the page cannot be fitted to the drawing

**Now.** A print is at **true millimetres**: a place drawn 10 mm across measures 10 mm on the paper, and
the page of the file is the page the sheet was ruled into, as the settings say. There is no *fit to
page*, no percentage, and no way to print a net larger than a page on one sheet.

**Why it was done this way.** *Paper size will be kept as in the setup*, which is what was asked for, and
one scene unit being one millimetre is the promise the whole sheet is built on. Scaling would also make
the file disagree with the sheet: a net measured against the page boundaries on screen would come out
somewhere else on the paper.

**When it will not be enough.** A net drawn a little wider than a page, which now takes two pages to show
a picture that would fit at 95%. A drawing wanted at a known scale — half size for a handout.

**Options.**

- **A scale the print is taken at**, one number given to `draw_page()`, which already takes the dots to
  the millimetre as an argument. *Fit to page* is that number worked out from the drawing's bounding
  rectangle rather than typed.
- **Print the drawing rather than the pages** — one page the size of what is drawn, which is what an
  illustration for a document usually wants and is a different feature from tiling a sheet.
- **Leave it**, and let whoever is printing the PDF scale it in their own print dialog, which every one
  of them can do.

---

## A place's tokens are printed as a drawing rather than as text

**Now.** Every caption in a printed file is real text — a name, a description, an arc's weight — and a
reader takes them back out as words. A place's **token count** is the one exception: it is a
`QPainterPath` on the sheet and a path in the file, so it is vector and bears any zoom, but it cannot
be selected, searched or copied.

**Why it was done this way.** `glyph_path()` scales a piece of text so that **its own ink** is a height,
which is what makes a number fit the circle it sits in; `text_layout()`, which is what
`ink.write_block()` writes as text, scales the font's own line height. They are different measurements
on purpose — see *A place's tokens take the family its caption is written in and nothing else* — so
writing the number as text would mean a second layout to keep in step with the first, for a count of
one or two digits that nobody searches a document for.

**When it will not be enough.** A net whose markings are being read out of the PDF by something rather
than by somebody — a diff of two printed nets, a script pulling the marking out of a report.

**Options.**

- **Give `glyph_path()` a layout of its own**, as `text_block()` now has: the measurement stays what it
  is and `write_block()` learns a second kind of block. It is about twenty lines and one more thing to
  keep in step.
- **Letter the number from `text_layout()`** and clamp it to the circle, which is the same trade the
  tokens entry above already describes, and would make it text for free.

---

## There is no way out but PDF

**Now.** A drawing leaves the application as a PDF and in no other way. There is no SVG, no PNG, no
copying the drawing to the clipboard as a picture, and no printing a net into another document.

**Why it was done this way.** PDF was what was asked for, and it is the one that is vector, carries real
text, holds several pages and opens everywhere. The rest are one feature each and none was needed yet.

**When it will not be enough.** A net going into a web page or a slide, which wants SVG or PNG; a net
going into a drawing program to be finished by hand, which wants SVG; pasting a net into a chat.

**Options.**

- **SVG through `QSvgGenerator`**, which is another paged paint device in the same shape as `QPdfWriter`:
  `draw_page()` would draw onto it unchanged, one file per page. `QtSvg` is already a dependency.
- **PNG through a `QImage`** at a resolution the person chooses — `painted()` in the printing tests is
  already that function, written for the tests rather than for the application.
- **The clipboard**, which is the same image or the same SVG put on it instead of written to a file.
