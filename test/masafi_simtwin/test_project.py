"""Tests for the project file."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import uuid
import zipfile
from pathlib import Path

import pytest

from masafi_simtwin import __version__, project


def empty_net(identifier: str) -> bytes:
    """Stand in for the file of a new model.

    What a model's file holds is its kind's business; the project only keeps it.
    So the tests of the project give it something that says whose file it is and
    nothing else.

    Parameters
    ----------
    identifier : str
        The model's UUID.

    Returns
    -------
    bytes
        The file.
    """

    return f'<net model="{identifier}"/>'.encode('utf-8')


@pytest.fixture
def created(tmp_path):
    """Write a project to work on.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary directory pytest made.

    Returns
    -------
    pathlib.Path
        The project file.
    """

    return project.create(project.path_for(tmp_path, 'Bottling Line'), 'Bottling Line')


# ----------------------------------------------------------------------
# What a project is called
# ----------------------------------------------------------------------


def test_a_project_is_one_file_with_the_projects_suffix(tmp_path):
    """``mfstz``: near enough to *manifest*, with the ``z`` for the zip."""

    assert project.PROJECT_SUFFIX == '.mfstz'
    assert project.path_for(tmp_path, 'Bottling Line').name == 'Bottling Line.mfstz'


def test_the_suffix_is_not_doubled(tmp_path):
    """A name typed with the suffix already on it is taken as it is."""

    assert project.path_for(tmp_path, 'Line.mfstz').name == 'Line.mfstz'


# ----------------------------------------------------------------------
# What is inside one
# ----------------------------------------------------------------------


def test_a_new_project_is_a_zip_holding_its_manifest_its_folders_and_its_history(created):
    """The container is an ordinary archive, openable with any zip tool."""

    assert zipfile.is_zipfile(created)
    with zipfile.ZipFile(created) as archive:
        assert archive.namelist() == [
            project.MANIFEST_NAME,
            *project.FOLDERS,
            project.HISTORY_NAME,
        ]


def test_the_folders_are_the_shape_a_project_will_fill(created):
    """One for each thing a project is made of, plus the logs of running it."""

    assert project.FOLDERS == ('models/', 'simulations/', 'statistics/', 'logs/')

    with zipfile.ZipFile(created) as archive:
        folders = [info for info in archive.infolist() if info.is_dir()]

    assert [info.filename for info in folders] == list(project.FOLDERS)
    assert all(info.file_size == 0 for info in folders)


def test_the_folders_are_real_directories_to_an_archive_tool(created):
    """Without the directory bit they would show as empty files."""

    with zipfile.ZipFile(created) as archive:
        models = archive.getinfo('models/')

    assert models.is_dir()
    assert models.external_attr & 0x10


def test_the_manifest_says_what_the_file_is(created):
    """A zip that merely holds a ``manifest.json`` is not a project."""

    found = project.read_manifest(created)

    assert found['format'] == project.FORMAT_NAME
    assert found['format_version'] == project.FORMAT_VERSION
    assert found['name'] == 'Bottling Line'
    assert found['created_by'] == __version__
    assert found['created']


def test_every_project_carries_a_uuid_of_its_own(tmp_path):
    """Which is what tells two projects apart however they are renamed."""

    first = project.create(project.path_for(tmp_path, 'One'), 'One')
    second = project.create(project.path_for(tmp_path, 'Two'), 'Two')

    identifiers = {project.read_manifest(path)['uuid'] for path in (first, second)}

    assert len(identifiers) == 2
    assert all(uuid.UUID(identifier) for identifier in identifiers)


def test_the_uuid_belongs_to_the_project_not_to_the_file(created):
    """A copied or renamed project keeps the identity it was made with."""

    before = project.read_manifest(created)['uuid']
    renamed = created.with_name(f'copy{project.PROJECT_SUFFIX}')
    created.rename(renamed)

    assert project.read_manifest(renamed)['uuid'] == before


def test_the_author_is_whoever_made_the_project(created):
    """Filled from the account running the application, and overridable."""

    assert project.read_manifest(created)['author'] == project.current_user()


def test_the_author_can_be_given_outright(tmp_path):
    """Which is what a preference for it will use when there is one."""

    path = project.create(project.path_for(tmp_path, 'Named'), 'Named', author='jaume')

    assert project.read_manifest(path)['author'] == 'jaume'


def test_the_company_is_blank_until_there_is_one_to_put_there(created):
    """The field exists from the first project so that adding it is not a change."""

    assert project.read_manifest(created)['company'] == ''


def test_the_company_can_be_given_outright(tmp_path):
    """As the author can."""

    path = project.create(
        project.path_for(tmp_path, 'Hired'), 'Hired', company='UPC'
    )

    assert project.read_manifest(path)['company'] == 'UPC'


def test_the_format_is_versioned(created):
    """Nothing else about the contents is settled, so this one thing must be."""

    assert project.read_manifest(created)['format_version'] == project.FORMAT_VERSION
    assert project.FORMAT_VERSION >= 1


def test_the_name_comes_out_of_the_manifest(created):
    """A renamed file still knows what the project inside it is called."""

    renamed = created.with_name(f'copy{project.PROJECT_SUFFIX}')
    created.rename(renamed)
    assert project.name_of(renamed) == 'Bottling Line'


def test_a_manifest_without_a_name_falls_back_to_the_file(tmp_path):
    """Something has to be shown in the title bar either way."""

    path = tmp_path / f'Nameless{project.PROJECT_SUFFIX}'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(
            project.MANIFEST_NAME, json.dumps({'format': project.FORMAT_NAME})
        )

    assert project.name_of(path) == 'Nameless'


# ----------------------------------------------------------------------
# What is refused
# ----------------------------------------------------------------------


def test_an_existing_file_is_never_overwritten(created):
    """A project is not created over one that is already there."""

    with pytest.raises(project.ProjectError, match='already there'):
        project.create(created, 'Bottling Line')


def test_a_project_cannot_be_written_where_there_is_no_directory(tmp_path):
    """The failure is reported rather than raised as an OSError."""

    with pytest.raises(project.ProjectError):
        project.create(tmp_path / 'nowhere' / f'a{project.PROJECT_SUFFIX}', 'a')


@pytest.mark.parametrize(
    ('name', 'content'),
    [
        ('not a zip', b'hello'),
        ('empty', b''),
    ],
)
def test_a_file_that_is_not_an_archive_is_not_a_project(tmp_path, name, content):
    """Whatever the suffix says."""

    path = tmp_path / f'{name}{project.PROJECT_SUFFIX}'
    path.write_bytes(content)
    with pytest.raises(project.ProjectError, match='not a project file'):
        project.read_manifest(path)


def test_an_archive_without_a_manifest_is_not_a_project(tmp_path):
    """A zip of something else, renamed."""

    path = tmp_path / f'other{project.PROJECT_SUFFIX}'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('notes.txt', 'nothing to see')

    with pytest.raises(project.ProjectError, match='not a project file'):
        project.read_manifest(path)


def test_an_archive_whose_manifest_claims_another_format_is_refused(tmp_path):
    """Which is what ``format`` is in the manifest for."""

    path = tmp_path / f'other{project.PROJECT_SUFFIX}'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(project.MANIFEST_NAME, json.dumps({'format': 'something-else'}))

    with pytest.raises(project.ProjectError, match='not a project file'):
        project.read_manifest(path)


def test_an_unreadable_manifest_is_reported_as_such(tmp_path):
    """The message distinguishes a broken project from a foreign file."""

    path = tmp_path / f'broken{project.PROJECT_SUFFIX}'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(project.MANIFEST_NAME, '{not json')

    with pytest.raises(project.ProjectError, match='unreadable manifest'):
        project.read_manifest(path)


def test_a_missing_file_is_reported_rather_than_raised(tmp_path):
    """A stale entry in the recent list reaches this."""

    with pytest.raises(project.ProjectError, match='not a project file'):
        project.read_manifest(tmp_path / f'gone{project.PROJECT_SUFFIX}')


# ----------------------------------------------------------------------
# The seam
# ----------------------------------------------------------------------


def test_the_project_file_knows_nothing_of_qt():
    """It is stdlib only, so it can move to ``simtwin_core`` unchanged."""

    source = Path(project.__file__).read_text(encoding='utf-8')
    assert 'PyQt6' not in source
    assert 'QtCore' not in source


# ----------------------------------------------------------------------
# How a project is named in a list of them
# ----------------------------------------------------------------------


def test_a_project_is_named_by_its_manifest(created):
    """Not by its file, which is the point of keeping a name in there."""

    renamed = created.with_name(f'copy{project.PROJECT_SUFFIX}')
    created.rename(renamed)

    assert project.label_for(renamed) == 'Bottling Line'


def test_a_broken_project_falls_back_to_its_file_name(tmp_path):
    """It is there but unreadable, so it keeps its place under some name."""

    path = tmp_path / f'broken{project.PROJECT_SUFFIX}'
    path.write_bytes(b'not a zip')

    assert project.label_for(path) == 'broken'


def test_projects_with_distinct_names_are_shown_by_name_alone(tmp_path):
    """Which is the whole improvement: no paths in the common case."""

    one = str(project.create(project.path_for(tmp_path, 'One'), 'One'))
    two = str(project.create(project.path_for(tmp_path, 'Two'), 'Two'))

    assert project.labels_for([one, two]) == [('One', one), ('Two', two)]


def test_projects_sharing_a_name_carry_their_path(tmp_path):
    """Otherwise the two would be one entry repeated."""

    here, there = tmp_path / 'here', tmp_path / 'there'
    here.mkdir()
    there.mkdir()
    first = str(project.create(project.path_for(here, 'Line'), 'Line'))
    second = str(project.create(project.path_for(there, 'Line'), 'Line'))

    assert project.labels_for([first, second]) == [
        (f'Line ({first})', first),
        (f'Line ({second})', second),
    ]


def test_only_the_names_that_clash_carry_a_path(tmp_path):
    """A third project of its own name is left alone."""

    here, there = tmp_path / 'here', tmp_path / 'there'
    here.mkdir()
    there.mkdir()
    first = str(project.create(project.path_for(here, 'Line'), 'Line'))
    second = str(project.create(project.path_for(there, 'Line'), 'Line'))
    other = str(project.create(project.path_for(here, 'Other'), 'Other'))

    labels = dict((path, label) for label, path in project.labels_for([first, second, other]))

    assert labels[other] == 'Other'
    assert labels[first].startswith('Line (')


def test_the_order_given_is_the_order_returned(tmp_path):
    """The history is most recent first and must stay that way."""

    paths = [
        str(project.create(project.path_for(tmp_path, name), name))
        for name in ('One', 'Two', 'Three')
    ]

    assert [path for _label, path in project.labels_for(paths)] == paths


def test_naming_nothing_gives_nothing(tmp_path):
    """An empty history is not a special case anywhere else."""

    assert project.labels_for([]) == []


# ----------------------------------------------------------------------
# The history, and the chain through it
# ----------------------------------------------------------------------


def history(path):
    """Read a project's history.

    Parameters
    ----------
    path : pathlib.Path
        The project file.

    Returns
    -------
    list of dict
        Its entries, oldest first.
    """

    return project.read_history(path)


def test_a_new_project_starts_its_history(created):
    """The first entry is the creation, and it names who made it."""

    entries = history(created)

    assert len(entries) == 1
    assert entries[0]['event'] == project.EVENT_CREATED
    assert entries[0]['author'] == project.current_user()
    assert entries[0]['previous'] is None


def test_every_entry_carries_the_projects_uuid(created):
    """Regenerating the UUID leaves a history that no longer belongs to it."""

    identifier = project.read_manifest(created)['uuid']
    project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')

    assert {entry['project'] for entry in history(created)} == {identifier}


def test_recording_appends_and_chains(created):
    """Each entry's identifier covers the one before it."""

    first = history(created)[0]
    second = project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')
    third = project.record(created, project.EVENT_CLOSED, 'jaume', 'install-1', 120)

    assert [entry['log_item_id'] for entry in history(created)] == [
        first['log_item_id'],
        second['log_item_id'],
        third['log_item_id'],
    ]
    assert second['previous'] == first['log_item_id']
    assert third['previous'] == second['log_item_id']
    assert third['duration'] == 120


def test_an_identifier_is_a_truncated_sha256(created):
    """Not a checksum a forger can steer by nudging a timestamp."""

    entry = history(created)[0]
    body = {key: value for key, value in entry.items() if key != 'log_item_id'}
    expected = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()

    assert entry['log_item_id'] == expected[: project.LOG_ITEM_ID_LENGTH]
    assert len(entry['log_item_id']) == 16


def test_altering_an_entry_invalidates_every_entry_after_it(created):
    """One link deep is the whole history deep.

    This is the property the chain exists for, so it is checked here rather
    than assumed: the identifier of an entry covers the identifier before it,
    which covers everything before that.
    """

    for _ in range(4):
        project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')
    entries = history(created)

    # rewrite the first entry as another author would have to
    tampered = dict(entries[0], author='someone-else')
    body = {key: value for key, value in tampered.items() if key != 'log_item_id'}
    rebuilt = project.link(
        {key: value for key, value in body.items() if key != 'previous'},
        body['previous'],
    )

    assert rebuilt['log_item_id'] != entries[1]['previous']


def test_recording_writes_the_log_and_leaves_the_manifest_as_it_was(created):
    """An entry is a line in the log; the folders, the models and the manifest
    survive it unchanged."""

    before = project.read_manifest(created)
    project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')

    with zipfile.ZipFile(created) as archive:
        assert archive.namelist() == [
            project.MANIFEST_NAME,
            *project.FOLDERS,
            project.HISTORY_NAME,
        ]
    assert project.read_manifest(created) == before


def test_recording_leaves_no_working_file_behind(created, tmp_path):
    """The archive is rewritten beside the original and moved over it."""

    project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')

    assert [path.name for path in tmp_path.iterdir()] == [created.name]


def test_a_failed_rewrite_leaves_the_project_alone(created, monkeypatch):
    """The move is what makes an interrupted write harmless."""

    before = created.read_bytes()
    monkeypatch.setattr(
        'masafi_simtwin.project.os.replace',
        lambda source, target: (_ for _ in ()).throw(OSError('no')),
    )

    with pytest.raises(project.ProjectError):
        project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')

    assert created.read_bytes() == before


def test_a_history_cannot_be_recorded_into_something_that_is_not_a_project(tmp_path):
    """The same refusal as reading one."""

    path = tmp_path / f'nope{project.PROJECT_SUFFIX}'
    path.write_bytes(b'hello')

    with pytest.raises(project.ProjectError):
        project.record(path, project.EVENT_OPENED, 'jaume', 'install-1')


# ----------------------------------------------------------------------
# Where the history is kept
# ----------------------------------------------------------------------


def rewrite_entry(path: Path, name: str, data: bytes) -> None:
    """Replace one entry of an archive, as a hand or another tool would.

    Parameters
    ----------
    path : pathlib.Path
        The archive.
    name : str
        The entry to replace, which must be there.
    data : bytes
        What to put in it.
    """

    with zipfile.ZipFile(path) as archive:
        entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
    with zipfile.ZipFile(path, 'w') as archive:
        for info, content in entries:
            archive.writestr(info, data if info.filename == name else content)


@pytest.fixture
def legacy(tmp_path):
    """Write a project as version 2 wrote one: the history in its manifest.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The temporary directory pytest made.

    Returns
    -------
    tuple
        The project file and the entries of its history.
    """

    path = tmp_path / f'Old{project.PROJECT_SUFFIX}'
    content = project.manifest('Old', author='jaume')
    content['format_version'] = 2
    first = project.link(
        project.history_entry(project.EVENT_CREATED, content['uuid'], 'jaume', 'install-0'),
        None,
    )
    second = project.link(
        project.history_entry(project.EVENT_OPENED, content['uuid'], 'jaume', 'install-0'),
        first['log_item_id'],
    )
    content['history'] = [first, second]
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(project.MANIFEST_NAME, json.dumps(content, indent=2))
        for folder in project.FOLDERS:
            archive.writestr(folder, b'')
    return path, [first, second]


def test_the_manifest_holds_no_history(created):
    """It says what a project is; what has happened to it is a log."""

    project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')

    assert 'history' not in project.read_manifest(created)


def test_the_history_is_kept_with_the_logs(created):
    """In the folder a project's logs go in."""

    assert project.HISTORY_NAME.startswith('logs/')
    assert 'logs/' in project.FOLDERS


def test_the_log_is_one_canonical_line_per_entry(created):
    """Each line is the JSON its identifier is computed over, with the
    identifier added, so an entry can be read and checked on its own."""

    project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')
    with zipfile.ZipFile(created) as archive:
        lines = archive.read(project.HISTORY_NAME).decode('utf-8').splitlines()
    entries = project.read_history(created)

    assert len(lines) == len(entries) == 2
    assert lines == [
        json.dumps(entry, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        for entry in entries
    ]


def test_a_new_entry_is_a_line_added_at_the_end(created):
    """Nothing before it is touched."""

    with zipfile.ZipFile(created) as archive:
        before = archive.read(project.HISTORY_NAME)
    project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')
    with zipfile.ZipFile(created) as archive:
        after = archive.read(project.HISTORY_NAME)

    assert after.startswith(before)
    assert after.count(b'\n') == before.count(b'\n') + 1


def test_the_format_version_says_the_history_has_moved():
    """Version 3 is the one that keeps it in the log."""

    assert project.FORMAT_VERSION == 3


def test_an_old_history_is_still_read_from_the_manifest(legacy):
    """Until the project is next written, that is where it is."""

    path, entries = legacy

    assert project.read_history(path) == entries


def test_an_old_history_is_moved_into_the_log_when_the_project_is_written(legacy):
    """Untouched, and out of the manifest, which is marked with the new version."""

    path, entries = legacy
    project.record(path, project.EVENT_CLOSED, 'jaume', 'install-0', 30)

    found = project.read_manifest(path)
    assert 'history' not in found
    assert found['format_version'] == project.FORMAT_VERSION
    with zipfile.ZipFile(path) as archive:
        assert project.HISTORY_NAME in archive.namelist()
    assert project.read_history(path)[:2] == entries


def test_the_chain_holds_across_the_move(legacy):
    """The first entry written to the log follows the last one of the manifest."""

    path, entries = legacy
    entry = project.record(path, project.EVENT_CLOSED, 'jaume', 'install-0', 30)

    assert entry['previous'] == entries[-1]['log_item_id']


def test_a_model_change_moves_an_old_history_too(legacy):
    """Every write leaves a project in the current format."""

    path, entries = legacy
    project.add_model(path, 'Line', project.ModelKind.PETRI_NET, {'time': 's'}, document=empty_net)

    assert 'history' not in project.read_manifest(path)
    history = project.read_history(path)
    assert history[:2] == entries
    assert history[-1]['event'] == project.EVENT_MODEL_ADDED


def test_a_later_format_is_not_marked_as_an_earlier_one(created):
    """A project from a newer version of the application keeps its number."""

    newer = dict(project.read_manifest(created), format_version=99)
    rewrite_entry(created, project.MANIFEST_NAME, json.dumps(newer).encode('utf-8'))

    project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')

    assert project.read_manifest(created)['format_version'] == 99


def log_of(path: Path) -> bytes:
    """Read a project's history log as it is stored.

    Parameters
    ----------
    path : pathlib.Path
        The project file.

    Returns
    -------
    bytes
        The log.
    """

    with zipfile.ZipFile(path) as archive:
        return archive.read(project.HISTORY_NAME)


def damage(path: Path, extra: bytes) -> bytes:
    """Put damage at the end of a project's history log.

    Parameters
    ----------
    path : pathlib.Path
        The project file.
    extra : bytes
        What to add to the end of the log.

    Returns
    -------
    bytes
        The damaged log, as it is now stored.
    """

    damaged = log_of(path) + extra
    rewrite_entry(path, project.HISTORY_NAME, damaged)
    return damaged


def test_reading_a_damaged_log_gives_the_entries_that_can_be_read(created):
    """What is not an entry is passed over, not reported."""

    damage(created, b'[1, 2]\n{broken\n\xff\xfe\n')

    assert len(project.read_history(created)) == 1


def test_a_damaged_log_does_not_stop_a_project_being_written(created):
    """The history is evidence, and a project is still work to be done."""

    first = project.read_history(created)[0]
    damage(created, b'{not json\n')

    entry = project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')

    assert project.read_history(created) == [first, entry]


def test_a_new_entry_is_chained_to_the_last_entry_that_can_be_read(created):
    """The break stays where the damage is, for the auditor to find."""

    first = project.read_history(created)[0]
    damage(created, b'{not json\n')

    entry = project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')

    assert entry['previous'] == first['log_item_id']


def test_the_damage_is_kept_in_the_log_as_it_was_found(created):
    """Byte for byte: the application verifies nothing, so it repairs nothing."""

    damaged = damage(created, b'{not json\n\xff\xfe not text\n')

    project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')

    assert log_of(created).startswith(damaged)


def test_a_log_cut_off_mid_line_does_not_swallow_the_next_entry(created):
    """The new entry is a line of its own, not the tail of a broken one."""

    damaged = damage(created, b'{"event": "open')

    entry = project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')

    assert log_of(created).startswith(damaged + b'\n')
    assert project.read_history(created)[-1] == entry


def test_a_model_can_be_changed_in_a_project_whose_log_is_damaged(created):
    """Every write goes past the damage, not only a session's."""

    damage(created, b'garbage\n')

    model = project.add_model(created, 'Line', project.ModelKind.PETRI_NET, {'time': 's'}, document=empty_net)

    assert project.read_history(created)[-1]['model'] == model['uuid']
    assert b'garbage\n' in log_of(created)


def test_a_project_whose_log_has_gone_starts_a_new_one(created):
    """Nothing to chain to is not a reason to refuse to write."""

    with zipfile.ZipFile(created) as archive:
        kept = [
            (info, archive.read(info.filename))
            for info in archive.infolist()
            if info.filename != project.HISTORY_NAME
        ]
    with zipfile.ZipFile(created, 'w') as archive:
        for info, data in kept:
            archive.writestr(info, data)

    entry = project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')

    assert entry['previous'] is None
    assert project.read_history(created) == [entry]


def test_blank_lines_in_the_log_are_passed_over(created):
    """A trailing newline, or one a text editor added, is not an entry."""

    with zipfile.ZipFile(created) as archive:
        log = archive.read(project.HISTORY_NAME)
    rewrite_entry(created, project.HISTORY_NAME, log + b'\n\n')

    assert len(project.read_history(created)) == 1


# ----------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ('name', 'expected'),
    [
        ('Bottling Line', 'Bottling_Line.pnml'),
        ('  spaced  ', 'spaced.pnml'),
        ('a/b', 'a_b.pnml'),
        ('???', 'model.pnml'),
    ],
)
def test_a_model_file_is_named_after_the_model(name, expected):
    """Spaces become underscores; so does anything that would escape the folder."""

    assert project.file_name_for(name) == expected
    assert project.file_name_for(name).endswith(project.MODEL_SUFFIX)


def test_a_model_is_written_into_the_models_folder(created):
    """Where an archive tool will show it, under the name it was given."""

    model = project.add_model(
        created, 'Filling Station', project.ModelKind.PETRI_NET, {'time': 's'}, document=empty_net
    )

    assert model['file'] == 'models/Filling_Station.pnml'
    with zipfile.ZipFile(created) as archive:
        assert archive.read(model['file']) == empty_net(model['uuid'])


def test_a_model_is_recorded_in_the_manifest(created):
    """The manifest is what the project pane is built from."""

    model = project.add_model(
        created, 'Filling Station', project.ModelKind.PETRI_NET, {'time': 's'}, document=empty_net
    )
    stored = project.models_of(created)

    assert [entry['uuid'] for entry in stored] == [model['uuid']]
    assert stored[0]['name'] == 'Filling Station'
    assert uuid.UUID(model['uuid'])


def test_two_models_of_one_name_get_files_of_their_own(created):
    """Two models may share a name; two zip entries may not."""

    first = project.add_model(created, 'Line', project.ModelKind.PETRI_NET, {'time': 's'}, document=empty_net)
    second = project.add_model(created, 'Line', project.ModelKind.PETRI_NET, {'time': 's'}, document=empty_net)

    assert first['file'] != second['file']
    assert second['file'] == 'models/Line_2.pnml'


def test_changing_a_model_changes_the_manifest_and_not_its_file(created):
    """A model's name and units are the manifest's; its file holds the model."""

    model = project.add_model(created, 'Line', project.ModelKind.PETRI_NET, {'time': 's'}, document=empty_net)
    project.update_model(created, model['uuid'], name='Filling', units={'time': 'h'})

    stored = project.models_of(created)[0]

    assert stored['name'] == 'Filling'
    assert stored['units'] == {'time': 'h'}
    assert project.read_model(created, model['uuid']) == empty_net(model['uuid'])


def test_a_renamed_model_keeps_its_file_and_its_identity(created):
    """Its UUID is what it is; the file name is only where it lives."""

    model = project.add_model(created, 'Line', project.ModelKind.PETRI_NET, {'time': 's'}, document=empty_net)
    project.update_model(created, model['uuid'], name='Filling')

    assert project.models_of(created)[0]['uuid'] == model['uuid']
    assert project.models_of(created)[0]['file'] == model['file']


def test_removing_a_model_takes_its_file_with_it(created):
    """Otherwise a project would grow files nothing points at."""

    model = project.add_model(created, 'Line', project.ModelKind.PETRI_NET, {'time': 's'}, document=empty_net)
    project.remove_model(created, model['uuid'])

    assert project.models_of(created) == []
    with zipfile.ZipFile(created) as archive:
        assert model['file'] not in archive.namelist()


def test_removing_one_model_leaves_the_others(created):
    """The rewrite carries across everything it was not told to drop."""

    first = project.add_model(created, 'One', project.ModelKind.PETRI_NET, {'time': 's'}, document=empty_net)
    second = project.add_model(created, 'Two', project.ModelKind.PETRI_NET, {'time': 's'}, document=empty_net)
    project.remove_model(created, first['uuid'])

    with zipfile.ZipFile(created) as archive:
        names = archive.namelist()

    assert [model['uuid'] for model in project.models_of(created)] == [second['uuid']]
    assert second['file'] in names
    assert all(folder in names for folder in project.FOLDERS)


@pytest.mark.parametrize(
    ('action', 'event'),
    [
        ('add', project.EVENT_MODEL_ADDED),
        ('update', project.EVENT_MODEL_UPDATED),
        ('remove', project.EVENT_MODEL_REMOVED),
    ],
)
def test_every_change_to_a_model_is_logged(created, action, event):
    """Created, updated or deleted, it goes into the project's history."""

    model = project.add_model(created, 'Line', project.ModelKind.PETRI_NET, {'time': 's'}, document=empty_net)
    if action == 'update':
        project.update_model(created, model['uuid'], name='Filling')
    elif action == 'remove':
        project.remove_model(created, model['uuid'])

    entry = project.read_history(created)[-1]

    assert entry['event'] == event
    assert entry['model'] == model['uuid']
    assert 'model_name' in entry


def test_the_history_stays_chained_across_model_changes(created):
    """A model change is one write of the archive, and one link in the chain."""

    model = project.add_model(created, 'Line', project.ModelKind.PETRI_NET, {'time': 's'}, document=empty_net)
    project.update_model(created, model['uuid'], name='Filling')
    project.remove_model(created, model['uuid'])

    entries = project.read_history(created)

    assert [entry['previous'] for entry in entries[1:]] == [
        entry['log_item_id'] for entry in entries[:-1]
    ]


@pytest.mark.parametrize('operation', ['update', 'remove'])
def test_acting_on_a_model_that_is_not_there_is_refused(created, operation):
    """A stale selection must not quietly do nothing."""

    act = project.update_model if operation == 'update' else project.remove_model
    with pytest.raises(project.ProjectError, match='holds no model'):
        act(created, 'not-a-uuid')


def test_the_project_keeps_a_model_file_without_reading_it(created):
    """Whatever the file holds is its kind's business."""

    model = project.add_model(
        created,
        'Line',
        project.ModelKind.PETRI_NET,
        {'time': 's'},
        document=lambda identifier: b'\x00 not even text \xff',
    )

    assert project.read_model(created, model['uuid']) == b'\x00 not even text \xff'


def test_the_file_of_a_new_model_is_made_from_its_uuid(created):
    """So a file can carry its model's identity, and the right one."""

    given = []
    model = project.add_model(
        created,
        'Line',
        project.ModelKind.PETRI_NET,
        {'time': 's'},
        document=lambda identifier: given.append(identifier) or b'net',
    )

    assert given == [model['uuid']]


def test_reading_a_model_the_project_does_not_hold_is_refused(created):
    """Rather than reading some other file."""

    with pytest.raises(project.ProjectError, match='holds no model'):
        project.read_model(created, 'not-a-uuid')


@pytest.fixture
def two_models(created):
    """Put two models in the project.

    Parameters
    ----------
    created : pathlib.Path
        The project file.

    Returns
    -------
    tuple
        The project file and the two models' entries.
    """

    first = project.add_model(created, 'One', project.ModelKind.PETRI_NET, {'time': 's'}, document=empty_net)
    second = project.add_model(created, 'Two', project.ModelKind.PETRI_NET, {'time': 's'}, document=empty_net)
    return created, first, second


def writes_of(monkeypatch) -> list:
    """Count the times a project archive is written.

    Every write puts a new archive over the old one with ``os.replace``, so that
    is what is counted.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The pytest patcher.

    Returns
    -------
    list
        One entry per write, filled in as they happen.
    """

    written = []
    real = project.os.replace

    def replace(source, target):
        written.append(target)
        real(source, target)

    monkeypatch.setattr(project.os, 'replace', replace)
    return written


def test_saving_writes_every_model_given_in_one_write(two_models, monkeypatch):
    """However many models are open, the project is rewritten once."""

    path, first, second = two_models
    written = writes_of(monkeypatch)

    saved = project.write_models(path, {first['uuid']: b'A', second['uuid']: b'B'})

    assert saved == [first['uuid'], second['uuid']]
    assert len(written) == 1
    assert project.read_model(path, first['uuid']) == b'A'
    assert project.read_model(path, second['uuid']) == b'B'


def test_a_model_whose_file_has_not_changed_is_not_written(two_models, monkeypatch):
    """A save of a project nobody has changed writes nothing at all."""

    path, first, _ = two_models
    before = path.read_bytes()
    written = writes_of(monkeypatch)

    saved = project.write_models(path, {first['uuid']: empty_net(first['uuid'])})

    assert saved == []
    assert written == []
    assert path.read_bytes() == before


def test_only_the_models_that_changed_are_written(two_models):
    """And the rest are carried across as they were."""

    path, first, second = two_models

    saved = project.write_models(
        path, {first['uuid']: empty_net(first['uuid']), second['uuid']: b'changed'}
    )

    assert saved == [second['uuid']]
    assert project.read_model(path, first['uuid']) == empty_net(first['uuid'])


def test_saving_adds_nothing_to_the_history(two_models):
    """The history records sessions and changes to what a project holds, and a
    save is neither."""

    path, first, _ = two_models
    before = project.read_history(path)

    project.write_models(path, {first['uuid']: b'changed'})

    assert project.read_history(path) == before


def test_saving_leaves_the_manifest_as_it_was(two_models):
    """What a project holds has not changed, only what one model is."""

    path, first, _ = two_models
    before = project.read_manifest(path)

    project.write_models(path, {first['uuid']: b'changed'})

    assert project.read_manifest(path) == before


def test_saving_a_model_the_project_does_not_hold_writes_nothing(two_models):
    """Not even the models that are the project's."""

    path, first, _ = two_models
    before = path.read_bytes()

    with pytest.raises(project.ProjectError, match='holds no model'):
        project.write_models(path, {first['uuid']: b'changed', 'not-a-uuid': b'X'})

    assert path.read_bytes() == before


def test_a_graph_has_no_distance_unit():
    """Which kinds are measured in space is the project's business, not the GUI's."""

    assert project.ModelKind.PETRI_NET not in project.KINDS_WITH_DISTANCE
    assert project.ModelKind.PROCESS_FLOW not in project.KINDS_WITH_DISTANCE
    assert project.ModelKind.PROCESS_2D in project.KINDS_WITH_DISTANCE
    assert project.ModelKind.PROCESS_3D in project.KINDS_WITH_DISTANCE


def test_only_the_petri_net_can_be_built_yet():
    """The other three are offered and refused, not hidden."""

    assert project.IMPLEMENTED_KINDS == (project.ModelKind.PETRI_NET,)


# ----------------------------------------------------------------------
# The journal
# ----------------------------------------------------------------------


def test_the_journal_lies_beside_the_project(created):
    """Where the lock is, and for the same reason: a zip cannot be appended to."""

    assert project.journal_path(created).name == 'Bottling Line.mfstz.journal'
    assert project.journal_path(created).parent == created.parent


def test_a_project_that_was_saved_and_closed_has_no_journal(created):
    """Nothing to replay is the ordinary case, not an error."""

    assert not project.journal_path(created).exists()
    assert project.read_journal(created) == []


def test_entries_are_written_and_read_back_in_order(created):
    """One line each, oldest first."""

    project.append_to_journal(created, {'model': 'm', 'change': {'op': 'one'}})
    project.append_to_journal(created, {'model': 'm', 'change': {'op': 'two'}})

    assert project.read_journal(created) == [
        {'model': 'm', 'change': {'op': 'one'}},
        {'model': 'm', 'change': {'op': 'two'}},
    ]


def test_the_project_does_not_read_what_an_entry_means(created):
    """As it does not read what a model's file holds."""

    project.append_to_journal(created, {'anything': [1, 2, {'at': 'all'}]})

    assert project.read_journal(created) == [{'anything': [1, 2, {'at': 'all'}]}]


def test_an_entry_is_a_line_added_at_the_end(created):
    """Which is the whole point: what came before is not rewritten."""

    project.append_to_journal(created, {'first': True})
    before = project.journal_path(created).read_bytes()
    project.append_to_journal(created, {'second': True})

    assert project.journal_path(created).read_bytes().startswith(before)


def test_a_half_written_last_line_ends_the_reading(created):
    """What a crash leaves behind: replaying a change that was never finished
    would be worse than stopping where the record stops."""

    project.append_to_journal(created, {'model': 'm', 'change': {'op': 'one'}})
    with project.journal_path(created).open('a', encoding='utf-8') as journal:
        journal.write('{"model": "m", "chan')

    assert project.read_journal(created) == [{'model': 'm', 'change': {'op': 'one'}}]


def test_a_journal_that_cannot_be_read_at_all_is_reported(created):
    """A broken journal is worth saying, unlike a missing one."""

    project.journal_path(created).write_bytes(b'\xff\xfe not text\n')

    with pytest.raises(project.ProjectError, match='could not be read'):
        project.read_journal(created)


def test_clearing_the_journal_leaves_nothing_behind(created):
    """Which is what a save does: the project now holds what it said."""

    project.append_to_journal(created, {'model': 'm'})

    project.clear_journal(created)

    assert not project.journal_path(created).exists()
    assert project.read_journal(created) == []


def test_clearing_a_journal_that_is_not_there_is_harmless(created):
    """Saving a project nobody has changed."""

    project.clear_journal(created)

    assert project.read_journal(created) == []


# ----------------------------------------------------------------------
# One holder at a time
# ----------------------------------------------------------------------


def test_a_free_project_can_be_taken(created):
    """The lock sits beside the project, not inside it."""

    held = project.acquire(created)

    assert held['pid'] == os.getpid()
    assert project.lock_path(created).exists()
    assert project.lock_path(created).name.endswith('.mfstz.lock')


def test_a_project_cannot_be_taken_twice(created):
    """Two writers of one archive silently lose each other's work."""

    project.acquire(created)

    with pytest.raises(project.ProjectLocked) as raised:
        project.acquire(created)

    assert raised.value.holder['pid'] == os.getpid()


def test_releasing_frees_the_project(created):
    """So the next window can have it."""

    project.acquire(created)
    project.release(created)

    assert project.holder_of(created) is None
    assert project.acquire(created)['pid'] == os.getpid()


def test_a_lock_left_by_a_dead_process_is_taken_over(created):
    """A crash must not make a project unopenable."""

    project.lock_path(created).write_text(
        json.dumps({'pid': 2**22, 'user': 'x', 'host': socket.gethostname()}),
        encoding='utf-8',
    )

    assert project.acquire(created)['pid'] == os.getpid()


def test_a_lock_from_another_machine_is_obeyed(created):
    """Whether that process is alive cannot be told from here."""

    project.lock_path(created).write_text(
        json.dumps({'pid': 1, 'user': 'someone', 'host': 'elsewhere'}), encoding='utf-8'
    )

    with pytest.raises(project.ProjectLocked):
        project.acquire(created)


def test_releasing_a_lock_that_is_not_ours_leaves_it_alone(created):
    """Otherwise one window could free a project another is writing to."""

    project.lock_path(created).write_text(
        json.dumps({'pid': 1, 'user': 'someone', 'host': 'elsewhere'}), encoding='utf-8'
    )
    project.release(created)

    assert project.holder_of(created) is not None


def test_a_project_that_is_locked_is_still_a_project(created):
    """The lock is beside the archive, so it changes nothing about it."""

    project.acquire(created)

    assert project.read_manifest(created)['name'] == 'Bottling Line'
