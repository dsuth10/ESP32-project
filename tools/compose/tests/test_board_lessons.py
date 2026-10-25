"""Synthetic independent lesson-copy checks; no participant data is opened."""
import hashlib
from io import BytesIO
import os
import json
from pathlib import Path
import subprocess
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_lessons
from board_lessons import copy_saved_lesson, local_image_resolver
from board_model import BoardModel, BoardConflictError, new_lesson, new_object
from board_session import BoardSession
from board_store import BoardStore
from media_store import MediaStore


@pytest.fixture
def saved(tmp_path, monkeypatch):
    root = tmp_path / 'candidate'
    root.mkdir()
    monkeypatch.setattr(board_lessons, 'CANDIDATE_ROOT', root)
    source = root / 'original'
    media = MediaStore(source / 'media')
    stream = BytesIO()
    Image.new('RGB', (12, 8), '#0088cc').save(stream, format='PNG')
    record = media.import_bytes(stream.getvalue(), 'Water', tags=['science'],
                               source={'creator': 'Synthetic author', 'licence': 'CC0'},
                               prompt='private prompt not to copy')
    media.import_bytes(stream.getvalue(), 'Unused unrelated image')
    reference = {field: record[field] for field in ('asset_id', 'version_id', 'sha256')}
    lesson = new_lesson('Original')
    page = lesson['pages'][0]
    image = new_object('image', image_ref=reference)
    text = new_object('text', text='Before')
    page['objects'] = [image, text]
    model = BoardModel(lesson)
    model.apply([dict(op='update_object', page_id=page['id'], object_id=text['id'],
                      changes={'text': 'After'})], expected_revision=model.revision)
    # Retain an image only in undo history, proving copies are self-contained
    # after an undo as well as in the initially visible current document.
    model.apply([dict(op='remove_object', page_id=page['id'], object_id=image['id'])],
                expected_revision=model.revision)
    model.undo(expected_revision=model.revision)
    store = BoardStore(source)
    session = BoardSession(model, store=store, image_resolver=local_image_resolver(media))
    session.save(expected_token=session.teacher_view()['token'])
    (source / 'evidence').mkdir()
    (source / 'evidence' / 'crash.txt').write_text('private evidence')
    (source / 'application.stderr.log').write_text('private log')
    yield source, session, store, reference
    session.close()


def hashes(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


def test_copy_preserves_source_and_independent_media_history(saved):
    source, original, _, reference = saved
    before = hashes(source)
    view = original.teacher_view()
    copy, store, resolver = copy_saved_lesson(original, source, source.parent / 'copy', 'Named copy')
    try:
        assert hashes(source) == before
        assert original.teacher_view() == view
        assert copy.teacher_view()['document']['lesson_id'] != view['document']['lesson_id']
        assert copy.teacher_view()['document']['title'] == 'Named copy'
        assert not copy.teacher_view()['dirty']
        state = store.load().export_state()
        assert all(document['lesson_id'] == state['document']['lesson_id']
                   and document['title'] == 'Named copy'
                   for document in [state['document'], *state['undo'], *state['redo']])
        media = MediaStore(store.root / 'media')
        assert len(media.list_assets()) == 1
        new_reference = next(obj['image_ref'] for obj in state['document']['pages'][0]['objects']
                             if obj['type'] == 'image')
        version = media.get_version(new_reference['version_id'])
        assert version['source'] == {'creator': 'Synthetic author', 'licence': 'CC0'}
        assert new_reference['sha256'] == reference['sha256']
        assert new_reference['version_id'] != reference['version_id']
        # Original media becoming unavailable cannot break the independent copy.
        original_blob = source / 'media' / 'blobs' / 'sha256' / reference['sha256'][:2] / reference['sha256'][2:]
        original_blob.rename(original_blob.with_name('temporarily-unavailable'))
        assert hashlib.sha256(copy.resolve_image(new_reference)).hexdigest() == reference['sha256']
        for method in (copy.teacher_undo, copy.teacher_redo):
            current = copy.teacher_view()
            method(expected_revision=current['revision'], expected_token=current['token'])
        assert copy.teacher_view()['document']['lesson_id'] == state['document']['lesson_id']
        copy.save(expected_token=copy.teacher_view()['token'])
        reopened = BoardSession.open(BoardStore(store.root), image_resolver=resolver)
        assert reopened.teacher_view()['document'] == copy.teacher_view()['document']
        reopened.close()
        assert not (store.root / 'evidence').exists()
        assert not (store.root / 'application.stderr.log').exists()
        assert (store.root / 'Open Teaching Board Lesson.cmd').is_file()
        assert '--demo' not in (store.root / 'reopen-lesson.ps1').read_text()
        with media._connect() as db:
            assert [row[0] for row in db.execute('SELECT prompt FROM local_prompt')] == ['']
    finally:
        copy.close()


def test_copy_rejects_dirty_and_changed_saved_source(saved):
    source, session, _, _ = saved
    view = session.teacher_view()
    session.teacher_apply([dict(op='rename_lesson', title='Unsaved')],
                          expected_revision=view['revision'], expected_token=view['token'])
    with pytest.raises(BoardConflictError, match='Save'):
        copy_saved_lesson(session, source, source.parent / 'copy', 'Copy')
    assert not (source.parent / 'copy').exists()
    session.save(expected_token=session.teacher_view()['token'])
    other = BoardStore(source)
    model = other.load()
    model.apply([dict(op='rename_lesson', title='Changed elsewhere')], expected_revision=model.revision)
    other.save(model)
    with pytest.raises(BoardConflictError, match='changed'):
        copy_saved_lesson(session, source, source.parent / 'copy', 'Copy')


def test_copy_rejects_existing_outside_nested_and_invalid_title(saved, tmp_path):
    source, session, _, _ = saved
    destination = source.parent / 'existing'
    destination.mkdir()
    sentinel = destination / 'preserve.txt'
    sentinel.write_text('unchanged')
    with pytest.raises(FileExistsError):
        copy_saved_lesson(session, source, destination, 'Copy')
    for target in (source, source / 'nested', tmp_path / 'outside'):
        with pytest.raises(ValueError):
            copy_saved_lesson(session, source, target, 'Copy')
    for title in ('', '  ', 'x' * 201, None):
        with pytest.raises(ValueError):
            copy_saved_lesson(session, source, source.parent / 'copy', title)
    assert sentinel.read_text() == 'unchanged'
    assert not (source.parent / 'copy').exists()


def test_copy_failure_discards_only_staging_and_retains_original(saved, monkeypatch):
    source, session, _, _ = saved
    before = hashes(source)
    def fail(*args, **kwargs):
        raise OSError('synthetic media-write failure')
    monkeypatch.setattr(MediaStore, 'import_bytes', fail)
    with pytest.raises(OSError, match='synthetic'):
        copy_saved_lesson(session, source, source.parent / 'copy', 'Copy')
    assert hashes(source) == before
    assert session.teacher_view()['document']['title'] == 'Original'
    assert not (source.parent / 'copy').exists()
    assert not list(source.parent.glob('.lesson-copy-*'))


def test_destination_appearing_during_copy_is_preserved(saved, monkeypatch):
    source, session, _, _ = saved
    destination = source.parent / 'copy'
    write_launcher = board_lessons._write_launcher
    def collide(staging):
        write_launcher(staging)
        destination.mkdir()
        (destination / 'sentinel').write_text('do not replace')
    monkeypatch.setattr(board_lessons, '_write_launcher', collide)
    with pytest.raises(FileExistsError):
        copy_saved_lesson(session, source, destination, 'Copy')
    assert (destination / 'sentinel').read_text() == 'do not replace'
    assert not (destination / 'lesson.json').exists()
    assert not list(source.parent.glob('.lesson-copy-*'))


def test_copy_rejects_linked_storage(saved, tmp_path):
    source, session, _, _ = saved
    outside = tmp_path / 'outside'
    outside.mkdir()
    link = source / 'linked'
    if os.name == 'nt':
        import _winapi
        try:
            _winapi.CreateJunction(str(outside), str(link))
        except OSError as error:
            pytest.skip(f'Windows junction unavailable: {error}')
    else:
        link.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(ValueError, match='links|junctions'):
            copy_saved_lesson(session, source, source.parent / 'copy', 'Copy')
    finally:
        if os.name == 'nt':
            link.rmdir()
        else:
            link.unlink()
    assert not (source.parent / 'copy').exists()


def test_image_referenced_only_by_undo_history_is_independently_copied(saved):
    source, session, _, reference = saved
    view = session.teacher_view()
    session.teacher_redo(expected_revision=view['revision'], expected_token=view['token'])
    session.save(expected_token=session.teacher_view()['token'])
    assert not any(obj['type'] == 'image' for obj in session.teacher_view()['document']['pages'][0]['objects'])
    copy, store, _ = copy_saved_lesson(session, source, source.parent / 'history-copy', 'History copy')
    try:
        current = copy.teacher_view()
        copy.teacher_undo(expected_revision=current['revision'], expected_token=current['token'])
        image = next(obj for obj in copy.teacher_view()['document']['pages'][0]['objects'] if obj['type'] == 'image')
        assert hashlib.sha256(copy.resolve_image(image['image_ref'])).hexdigest() == reference['sha256']
        assert image['image_ref']['version_id'] != reference['version_id']
    finally:
        copy.close()


def test_missing_media_does_not_publish_an_incomplete_copy(saved):
    source, session, _, reference = saved
    blob = source / 'media' / 'blobs' / 'sha256' / reference['sha256'][:2] / reference['sha256'][2:]
    blob.unlink()
    before = hashes(source)
    with pytest.raises(RuntimeError, match='image'):
        copy_saved_lesson(session, source, source.parent / 'copy', 'Copy')
    assert hashes(source) == before
    assert not (source.parent / 'copy').exists()
    assert not list(source.parent.glob('.lesson-copy-*'))


def test_post_publication_open_failure_identifies_preserved_copy(saved, monkeypatch):
    source, session, _, _ = saved
    destination = source.parent / 'copy'
    before = hashes(source)
    original_open = BoardSession.open
    def fail_final_open(store, **kwargs):
        if store.root == destination:
            raise OSError('synthetic final reopen failure')
        return original_open(store, **kwargs)
    monkeypatch.setattr(BoardSession, 'open', fail_final_open)
    with pytest.raises(RuntimeError, match='copy was saved') as error:
        copy_saved_lesson(session, source, destination, 'Copy')
    assert str(destination) in str(error.value)
    assert 'original lesson remains active' in str(error.value)
    assert (destination / 'lesson.json').exists()
    assert (destination / 'Open Teaching Board Lesson.cmd').exists()
    assert hashes(source) == before
    assert session.teacher_view()['document']['title'] == 'Original'


def test_catalogue_lists_both_titles_and_keeps_source_bytes_unchanged(saved):
    source, session, _, _ = saved
    before = hashes(source)
    destination = board_lessons.new_saved_lesson_directory('A separate named lesson')
    copy, store, _ = copy_saved_lesson(session, source, destination, 'A separate named lesson')
    try:
        result = board_lessons.refresh_saved_lesson_access((source, store.root))
        assert not result['warnings']
        assert {entry['title'] for entry in result['entries']} == {'Original', 'A separate named lesson'}
        assert destination.parent == result['root'] / 'data'
        assert destination.name.startswith('A separate named lesson -- ')
        assert hashes(source) == before
        for entry in result['entries']:
            command = (result['root'] / entry['file']).read_text()
            assert entry['key'] in command
            assert '--demo' not in command
            assert (board_lessons.CANDIDATE_ROOT / entry['path'] / 'lesson.json').is_file()
        script = (result['root'] / '.open-lesson.ps1').read_text(encoding='utf-8-sig')
        assert '--data-root' in script and '--demo' not in script
        assert 'no new lesson was created' in script
    finally:
        copy.close()


def test_catalogue_rename_updates_named_entry_and_preserves_user_files(saved):
    source, session, _, _ = saved
    first = board_lessons.refresh_saved_lesson_access((source,))
    old_file = first['root'] / first['entries'][0]['file']
    unrelated = first['root'] / 'My personal note.cmd'
    unrelated.write_text('Do not overwrite')
    view = session.teacher_view()
    session.teacher_apply([dict(op='rename_lesson', title='Renamed lesson')],
                          expected_revision=view['revision'], expected_token=view['token'])
    session.save(expected_token=session.teacher_view()['token'])
    before = hashes(source)
    second = board_lessons.refresh_saved_lesson_access((source,))
    assert not old_file.exists()
    assert len(second['entries']) == 1 and second['entries'][0]['title'] == 'Renamed lesson'
    assert (second['root'] / second['entries'][0]['file']).is_file()
    assert unrelated.read_text() == 'Do not overwrite'
    assert hashes(source) == before


def test_catalogue_duplicate_titles_remain_distinct_and_skip_test_snapshots(saved):
    source, session, _, _ = saved
    copy, store, _ = copy_saved_lesson(session, source, source.parent / 'lesson-second', 'Original')
    try:
        for name in ('pytest-diagnostic', 'crash-repro-example', 'smoke-example', 'feedback-native-smoke-example'):
            snapshot = BoardStore(source.parent / name)
            snapshot.save(BoardModel(new_lesson('Diagnostic: ' + name)))
        result = board_lessons.refresh_saved_lesson_access((source, store.root))
        assert len(result['entries']) == 2
        assert len({entry['file'] for entry in result['entries']}) == 2
        assert {entry['title'] for entry in result['entries']} == {'Original'}
    finally:
        copy.close()


def test_catalogue_safe_windows_names_and_title_is_never_shell_code(saved):
    source, session, _, _ = saved
    title = 'CON: vapour / rain "test" & $() %PATH%'
    destination = board_lessons.new_saved_lesson_directory(title)
    copy, store, _ = copy_saved_lesson(session, source, destination, title)
    try:
        result = board_lessons.refresh_saved_lesson_access((source, store.root))
        entry = next(item for item in result['entries'] if item['title'] == title)
        assert not any(character in entry['file'] for character in '<>:"/\\|?*')
        assert title not in (result['root'] / entry['file']).read_text()
        assert BoardStore(store.root).load().snapshot()['title'] == title
        assert board_lessons._title_stem('CON') == 'Lesson CON'
        assert board_lessons._title_stem('...') == 'Lesson'
    finally:
        copy.close()


def test_catalogue_corrupt_checkpoint_warns_without_mutating_sources(saved):
    source, session, _, _ = saved
    first = board_lessons.refresh_saved_lesson_access((source,))
    (source / 'lesson.json').write_text('damaged checkpoint')
    before = hashes(source)
    result = board_lessons.refresh_saved_lesson_access((source,))
    assert result['warnings']
    assert result['entries'] == first['entries']
    assert (result['root'] / result['entries'][0]['file']).is_file()
    assert hashes(source) == before


def test_catalogue_never_overwrites_unrelated_file_at_generated_name(saved):
    source, _, _, _ = saved
    root = board_lessons.saved_lessons_root()
    key = board_lessons._catalogue_key(source)
    collision = root / ('Original [' + key + '].cmd')
    collision.write_text('user file')
    before = hashes(source)
    with pytest.raises(FileExistsError, match='unrelated file'):
        board_lessons.refresh_saved_lesson_access((source,))
    assert collision.read_text() == 'user file'
    assert hashes(source) == before


@pytest.mark.skipif(os.name != 'nt', reason='Windows reopen launcher')
def test_catalogue_launcher_resolves_exact_saved_folder_without_recreating_lesson(saved):
    source, _, _, _ = saved
    result = board_lessons.refresh_saved_lesson_access((source,))
    entry = result['entries'][0]
    script = str(result['root'] / '.open-lesson.ps1').replace("'", "''")
    # Execute the actual generated script; intercept only process creation so
    # the test cannot leave a second editor open or edit the saved lesson.
    command = (
        "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding; "
        "function Start-Process { param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle) "
        "@{runtime=$FilePath; arguments=@($ArgumentList); working=$WorkingDirectory} | ConvertTo-Json -Compress }; "
        f"& '{script}' -LessonKey '{entry['key']}'"
    )
    before = hashes(source)
    process = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command],
                             capture_output=True, encoding='utf-8', timeout=20)
    assert process.returncode == 0, process.stderr
    launch = json.loads(process.stdout.lstrip('\ufeff'))
    assert launch['arguments'][-1] == '"' + str(source) + '"'
    assert '--data-root' in launch['arguments'] and '--demo' not in launch['arguments']
    assert Path(launch['runtime']).name == 'pythonw.exe'
    assert hashes(source) == before
