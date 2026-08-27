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

**Where.** `masafi_simtwin/project.py` — `link()`, `history_entry()`, `record()`.
