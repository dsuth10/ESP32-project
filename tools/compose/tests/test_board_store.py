import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_store
from board_model import BoardModel, BoardConflictError, canonical_json
from board_store import BoardStore, BoardStoreError


def rename(model, title):
    return model.apply([{'op': 'rename_lesson', 'title': title}], expected_revision=model.revision)


def test_save_reopen_preserves_document_and_undo_redo_across_restart(tmp_path):
    store = BoardStore(tmp_path / 'isolated-lesson')
    model = BoardModel()
    rename(model, 'First'); rename(model, 'Second')
    model.undo(expected_revision=2)
    assert store.save(model) == 3
    reopened = BoardStore(store.root).load()
    assert reopened.snapshot() == model.snapshot()
    reopened.redo(expected_revision=3)
    assert reopened.revision == 4 and reopened.snapshot()['title'] == 'Second'
    reopened.undo(expected_revision=4)
    assert reopened.revision == 5 and reopened.snapshot()['title'] == 'First'
    assert not (tmp_path / 'companion.sqlite3').exists()
    assert not (tmp_path / 'media.sqlite3').exists()


@pytest.mark.parametrize('damage', ['corrupt', 'missing', 'oversized'])
def test_current_damage_recovers_previous_without_promoting_orphan_writes(tmp_path, damage):
    store, model = BoardStore(tmp_path), BoardModel()
    store.save(model)
    rename(model, 'Second checkpoint'); store.save(model)
    if damage == 'missing':
        store.current_path.unlink()
    elif damage == 'oversized':
        with store.current_path.open('wb') as stream:
            stream.truncate(board_store.MAX_FILE_BYTES + 1)
    else:
        store.current_path.write_bytes(b'{broken checkpoint')
    (tmp_path / '.board-pending-orphan').write_text('{not committed}', encoding='utf-8')
    recovered_store = BoardStore(tmp_path)
    recovered = recovered_store.load()
    assert recovered_store.recovery_status == 'recovered_previous'
    assert recovered.revision == 0 and recovered.snapshot()['title'] == 'Untitled lesson'
    rename(recovered, 'Recovered edit')
    recovered_store.save(recovered)
    assert BoardStore(tmp_path).load().snapshot()['title'] == 'Recovered edit'
    assert (tmp_path / '.board-pending-orphan').exists()


def test_interrupted_current_replace_leaves_last_saved_checkpoint_reopenable(tmp_path):
    store, model = BoardStore(tmp_path), BoardModel()
    store.save(model)
    rename(model, 'Not committed')
    actual_replace = board_store.os.replace
    def fail_current(source, destination):
        if Path(destination) == store.current_path:
            raise OSError('Synthetic interrupted replacement')
        return actual_replace(source, destination)
    with patch('board_store.os.replace', side_effect=fail_current):
        with pytest.raises(OSError, match='interrupted'):
            store.save(model)
    assert BoardStore(tmp_path).load().revision == 0
    assert model.revision == 1
    assert not list(tmp_path.glob('.board-pending-*'))


def test_no_valid_checkpoint_refuses_load_and_fresh_owner_overwrite(tmp_path):
    (tmp_path / 'lesson.json').write_bytes(b'invalid')
    (tmp_path / 'lesson.previous.json').write_bytes(b'also invalid')
    store = BoardStore(tmp_path)
    with pytest.raises(BoardStoreError, match='No valid'):
        store.load()
    with pytest.raises(BoardConflictError, match='Load the existing'):
        store.save(BoardModel())
    assert (tmp_path / 'lesson.json').read_bytes() == b'invalid'


def test_second_writer_cannot_overwrite_new_saved_or_recovered_state(tmp_path):
    original, model = BoardStore(tmp_path), BoardModel()
    original.save(model)
    first, second = BoardStore(tmp_path), BoardStore(tmp_path)
    a, b = first.load(), second.load()
    rename(a, 'Writer A'); first.save(a)
    rename(b, 'Writer B')
    with pytest.raises(BoardConflictError, match='another writer'):
        second.save(b)
    assert BoardStore(tmp_path).load().snapshot()['title'] == 'Writer A'
    first.current_path.write_bytes(b'corrupt')
    recovery_a, recovery_b = BoardStore(tmp_path), BoardStore(tmp_path)
    a, b = recovery_a.load(), recovery_b.load()
    rename(a, 'Recovery A'); recovery_a.save(a)
    rename(b, 'Recovery B')
    with pytest.raises(BoardConflictError):
        recovery_b.save(b)


def test_same_owner_cannot_roll_back_model_revision(tmp_path):
    store, model = BoardStore(tmp_path), BoardModel()
    old = BoardModel(model.snapshot())
    store.save(model)
    rename(model, 'Newer'); store.save(model)
    with pytest.raises(BoardConflictError, match='newer or different'):
        store.save(old)


def test_save_reports_captured_revision_when_model_changes_during_io(tmp_path):
    store, model = BoardStore(tmp_path), BoardModel()
    actual_write = store._atomic_write
    def edit_during_save(destination, data):
        rename(model, 'New unsaved edit')
        return actual_write(destination, data)
    with patch.object(store, '_atomic_write', side_effect=edit_during_save):
        saved_revision = store.save(model)
    assert saved_revision == 0 and model.revision == 1
    assert BoardStore(tmp_path).load().revision == 0
    assert store.save(model) == 1


def test_checksum_and_invalid_history_cannot_be_loaded(tmp_path):
    store, model = BoardStore(tmp_path), BoardModel()
    rename(model, 'Saved'); store.save(model)
    envelope = json.loads(store.current_path.read_text(encoding='utf-8'))
    envelope['state']['document']['title'] = 'Tampered'
    store.current_path.write_bytes(canonical_json(envelope))
    with pytest.raises(BoardStoreError):
        BoardStore(tmp_path).load()
    envelope['sha256'] = hashlib.sha256(canonical_json(envelope['state'])).hexdigest()
    envelope['state']['undo'][0]['lesson_id'] = 'not-a-uuid'
    envelope['sha256'] = hashlib.sha256(canonical_json(envelope['state'])).hexdigest()
    store.current_path.write_bytes(canonical_json(envelope))
    with pytest.raises(BoardStoreError):
        BoardStore(tmp_path).load()


def test_os_lock_refuses_other_writer_and_releases_on_exit(tmp_path):
    first, second = BoardStore(tmp_path), BoardStore(tmp_path)
    with first._exclusive():
        with pytest.raises(BoardStoreError, match='busy'):
            second.save(BoardModel())
    assert second.save(BoardModel()) == 0
