"""Tests for the project file."""

from __future__ import annotations

import hashlib
import json
import uuid
import zipfile
from pathlib import Path

import pytest

from masafi_simtwin import __version__, project


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


def test_a_new_project_is_a_zip_holding_its_manifest_and_its_folders(created):
    """The container is an ordinary archive, openable with any zip tool."""

    assert zipfile.is_zipfile(created)
    with zipfile.ZipFile(created) as archive:
        assert archive.namelist() == [project.MANIFEST_NAME, *project.FOLDERS]


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

    return project.read_manifest(path)['history']


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


def test_only_the_manifest_is_replaced_when_recording(created):
    """The folders, and later the models, survive a history entry."""

    project.record(created, project.EVENT_OPENED, 'jaume', 'install-1')

    with zipfile.ZipFile(created) as archive:
        assert archive.namelist() == [project.MANIFEST_NAME, *project.FOLDERS]


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
# Models
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ('name', 'expected'),
    [
        ('Bottling Line', 'Bottling_Line.mfst'),
        ('  spaced  ', 'spaced.mfst'),
        ('a/b', 'a_b.mfst'),
        ('???', 'model.mfst'),
    ],
)
def test_a_model_file_is_named_after_the_model(name, expected):
    """Spaces become underscores; so does anything that would escape the folder."""

    assert project.file_name_for(name) == expected
    assert project.file_name_for(name).endswith(project.MODEL_SUFFIX)


def test_a_model_is_written_into_the_models_folder(created):
    """Where an archive tool will show it, under the name it was given."""

    model = project.add_model(
        created, 'Filling Station', project.ModelKind.PETRI_NET, {'time': 's'}
    )

    assert model['file'] == 'models/Filling_Station.mfst'
    with zipfile.ZipFile(created) as archive:
        document = json.loads(archive.read(model['file']))

    assert document['format'] == project.MODEL_FORMAT_NAME
    assert document['kind'] == 'petri-net'
    assert document['units'] == {'time': 's'}
    assert document['content'] == {}


def test_a_model_is_recorded_in_the_manifest(created):
    """The manifest is what the project pane is built from."""

    model = project.add_model(
        created, 'Filling Station', project.ModelKind.PETRI_NET, {'time': 's'}
    )
    stored = project.models_of(created)

    assert [entry['uuid'] for entry in stored] == [model['uuid']]
    assert stored[0]['name'] == 'Filling Station'
    assert uuid.UUID(model['uuid'])


def test_two_models_of_one_name_get_files_of_their_own(created):
    """Two models may share a name; two zip entries may not."""

    first = project.add_model(created, 'Line', project.ModelKind.PETRI_NET, {'time': 's'})
    second = project.add_model(created, 'Line', project.ModelKind.PETRI_NET, {'time': 's'})

    assert first['file'] != second['file']
    assert second['file'] == 'models/Line_2.mfst'


def test_changing_a_model_changes_its_document_too(created):
    """The manifest and the file must not drift apart."""

    model = project.add_model(created, 'Line', project.ModelKind.PETRI_NET, {'time': 's'})
    project.update_model(created, model['uuid'], name='Filling', units={'time': 'h'})

    stored = project.models_of(created)[0]
    with zipfile.ZipFile(created) as archive:
        document = json.loads(archive.read(model['file']))

    assert stored['name'] == 'Filling'
    assert stored['units'] == {'time': 'h'}
    assert document['name'] == 'Filling'
    assert document['units'] == {'time': 'h'}


def test_a_renamed_model_keeps_its_file_and_its_identity(created):
    """Its UUID is what it is; the file name is only where it lives."""

    model = project.add_model(created, 'Line', project.ModelKind.PETRI_NET, {'time': 's'})
    project.update_model(created, model['uuid'], name='Filling')

    assert project.models_of(created)[0]['uuid'] == model['uuid']
    assert project.models_of(created)[0]['file'] == model['file']


def test_removing_a_model_takes_its_file_with_it(created):
    """Otherwise a project would grow files nothing points at."""

    model = project.add_model(created, 'Line', project.ModelKind.PETRI_NET, {'time': 's'})
    project.remove_model(created, model['uuid'])

    assert project.models_of(created) == []
    with zipfile.ZipFile(created) as archive:
        assert model['file'] not in archive.namelist()


def test_removing_one_model_leaves_the_others(created):
    """The rewrite carries across everything it was not told to drop."""

    first = project.add_model(created, 'One', project.ModelKind.PETRI_NET, {'time': 's'})
    second = project.add_model(created, 'Two', project.ModelKind.PETRI_NET, {'time': 's'})
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

    model = project.add_model(created, 'Line', project.ModelKind.PETRI_NET, {'time': 's'})
    if action == 'update':
        project.update_model(created, model['uuid'], name='Filling')
    elif action == 'remove':
        project.remove_model(created, model['uuid'])

    entry = project.read_manifest(created)['history'][-1]

    assert entry['event'] == event
    assert entry['model'] == model['uuid']
    assert 'model_name' in entry


def test_the_history_stays_chained_across_model_changes(created):
    """A model change is one write of the archive, and one link in the chain."""

    model = project.add_model(created, 'Line', project.ModelKind.PETRI_NET, {'time': 's'})
    project.update_model(created, model['uuid'], name='Filling')
    project.remove_model(created, model['uuid'])

    entries = project.read_manifest(created)['history']

    assert [entry['previous'] for entry in entries[1:]] == [
        entry['log_item_id'] for entry in entries[:-1]
    ]


@pytest.mark.parametrize('operation', ['update', 'remove'])
def test_acting_on_a_model_that_is_not_there_is_refused(created, operation):
    """A stale selection must not quietly do nothing."""

    act = project.update_model if operation == 'update' else project.remove_model
    with pytest.raises(project.ProjectError, match='holds no model'):
        act(created, 'not-a-uuid')


def test_a_graph_has_no_distance_unit():
    """Which kinds are measured in space is the project's business, not the GUI's."""

    assert project.ModelKind.PETRI_NET not in project.KINDS_WITH_DISTANCE
    assert project.ModelKind.PROCESS_FLOW not in project.KINDS_WITH_DISTANCE
    assert project.ModelKind.PROCESS_2D in project.KINDS_WITH_DISTANCE
    assert project.ModelKind.PROCESS_3D in project.KINDS_WITH_DISTANCE


def test_only_the_petri_net_can_be_built_yet():
    """The other three are offered and refused, not hidden."""

    assert project.IMPLEMENTED_KINDS == (project.ModelKind.PETRI_NET,)
