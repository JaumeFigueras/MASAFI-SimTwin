"""Tests for the project file."""

from __future__ import annotations

import json
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


def test_a_new_project_is_a_zip_holding_its_manifest(created):
    """The container is an ordinary archive, openable with any zip tool."""

    assert zipfile.is_zipfile(created)
    with zipfile.ZipFile(created) as archive:
        assert archive.namelist() == [project.MANIFEST_NAME]


def test_the_manifest_says_what_the_file_is(created):
    """A zip that merely holds a ``manifest.json`` is not a project."""

    with zipfile.ZipFile(created) as archive:
        found = json.loads(archive.read(project.MANIFEST_NAME))

    assert found['format'] == project.FORMAT_NAME
    assert found['format_version'] == project.FORMAT_VERSION
    assert found['name'] == 'Bottling Line'
    assert found['created_by'] == __version__
    assert found['created']


def test_the_format_is_versioned_from_the_first_file(created):
    """Nothing else about the contents is settled, so this one thing must be."""

    assert project.read_manifest(created)['format_version'] == 1


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
