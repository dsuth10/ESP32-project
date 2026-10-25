import copy
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_model
from board_model import (BoardModel, BoardValidationError, BoardConflictError,
                         new_lesson, new_page, new_object)


def add(model, obj=None):
    page = model.snapshot()['pages'][0]['id']
    obj = obj or new_object('text', text='Evaporation')
    model.apply([{'op': 'add_object', 'page_id': page, 'object': obj}], expected_revision=model.revision)
    return obj


def test_typed_objects_roundtrip_without_paths_or_remote_operations():
    model = BoardModel(new_lesson('Water cycle'))
    reference = {'asset_id': str(uuid.uuid4()), 'version_id': str(uuid.uuid4()), 'sha256': 'a' * 64}
    for obj in [new_object('text', text='Water cycle'), new_object('image', image_ref=reference),
                new_object('shape'), new_object('arrow'), new_object('ink', points=[[1, 2], [3, 4]])]:
        add(model, obj)
    snapshot = model.snapshot()
    assert BoardModel(json.loads(json.dumps(snapshot))).snapshot() == snapshot
    assert snapshot['pages'][0]['width'] == 1600
    assert snapshot['pages'][0]['height'] == 900
    reference['sha256'] = 'b' * 64
    assert snapshot['pages'][0]['objects'][1]['image_ref']['sha256'] == 'a' * 64


def test_input_and_snapshot_mutation_cannot_change_model():
    document = new_lesson()
    model = BoardModel(document)
    document['title'] = 'External mutation'
    snapshot = model.snapshot()
    snapshot['pages'].clear()
    assert model.snapshot()['title'] == 'Untitled lesson'
    assert len(model.snapshot()['pages']) == 1


def test_batch_is_atomic_and_one_undo_unit():
    model = BoardModel()
    page = model.snapshot()['pages'][0]['id']
    obj = new_object('text', text='Before')
    initial = model.export_state()
    with pytest.raises(BoardValidationError):
        model.apply([{'op': 'add_object', 'page_id': page, 'object': obj},
                     {'op': 'update_object', 'page_id': page, 'object_id': str(uuid.uuid4()),
                      'changes': {'text': 'Unknown'}}], expected_revision=0)
    assert model.export_state() == initial
    model.apply([{'op': 'add_object', 'page_id': page, 'object': obj},
                 {'op': 'update_object', 'page_id': page, 'object_id': obj['id'],
                  'changes': {'text': 'After', 'x': 50}}], expected_revision=0)
    assert model.revision == 1
    assert model.snapshot()['pages'][0]['objects'][0]['text'] == 'After'
    model.undo(expected_revision=1)
    assert model.revision == 2 and model.snapshot()['pages'][0]['objects'] == []
    with pytest.raises(BoardValidationError, match='no edit'):
        model.undo(expected_revision=2)


def test_undo_redo_never_revalidate_stale_agent_revision():
    model = BoardModel()
    add(model)
    model.undo(expected_revision=1)
    with pytest.raises(BoardConflictError):
        model.apply([{'op': 'rename_lesson', 'title': 'Stale'}], expected_revision=0)
    model.redo(expected_revision=2)
    assert model.revision == 3
    model.undo(expected_revision=3)
    model.apply([{'op': 'rename_lesson', 'title': 'New branch'}], expected_revision=4)
    with pytest.raises(BoardValidationError, match='no edit'):
        model.redo(expected_revision=5)


def test_concurrent_expected_revision_accepts_exactly_one_edit():
    model = BoardModel()
    def edit(title):
        try:
            model.apply([{'op': 'rename_lesson', 'title': title}], expected_revision=0)
            return 'applied'
        except BoardConflictError:
            return 'stale'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(edit, ['First', 'Second'])) == ['applied', 'stale']
    assert model.revision == 1


def test_page_commands_and_object_layer_order_keep_stable_identities():
    model = BoardModel()
    first = model.snapshot()['pages'][0]['id']
    second = new_page('Condensation')
    a, b = new_object('shape'), new_object('text', text='Cloud')
    model.apply([{'op': 'add_page', 'page': second},
                 {'op': 'add_object', 'page_id': second['id'], 'object': a},
                 {'op': 'add_object', 'page_id': second['id'], 'object': b},
                 {'op': 'reorder_object', 'page_id': second['id'], 'object_id': a['id'], 'index': 1},
                 {'op': 'update_page', 'page_id': second['id'], 'changes': {'title': 'Clouds'}},
                 {'op': 'remove_page', 'page_id': first}], expected_revision=0)
    page = model.snapshot()['pages'][0]
    assert page['id'] == second['id'] and page['title'] == 'Clouds'
    assert [obj['id'] for obj in page['objects']] == [b['id'], a['id']]


def test_cannot_remove_only_page_or_duplicate_any_identity():
    model = BoardModel()
    page = model.snapshot()['pages'][0]
    with pytest.raises(BoardValidationError):
        model.apply([{'op': 'remove_page', 'page_id': page['id']}], expected_revision=0)
    with pytest.raises(BoardValidationError, match='unique'):
        model.apply([{'op': 'add_page', 'page': page}], expected_revision=0)
    assert model.revision == 0


def test_image_reference_is_immutable_and_cannot_contain_paths():
    model = BoardModel()
    ref = {'asset_id': str(uuid.uuid4()), 'version_id': str(uuid.uuid4()), 'sha256': 'a' * 64}
    obj = add(model, new_object('image', image_ref=ref))
    with pytest.raises(BoardValidationError, match='immutable'):
        model.apply([{'op': 'update_object', 'page_id': model.snapshot()['pages'][0]['id'],
                      'object_id': obj['id'], 'changes': {'image_ref': {**ref, 'sha256': 'b' * 64}}}],
                    expected_revision=1)
    with pytest.raises(BoardValidationError):
        new_object('image', image_ref={**ref, 'path': 'private.png'})


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), True, 10**1000, '20'])
def test_numeric_inputs_reject_nonfinite_bool_oversize_and_strings(value):
    with pytest.raises(BoardValidationError):
        new_object('shape', x=value)


@pytest.mark.parametrize('kind', [[], {}, None, 'script'])
def test_invalid_object_type_has_consistent_validation_error(kind):
    with pytest.raises(BoardValidationError):
        new_object(kind)


def test_text_ink_revision_and_unknown_fields_are_bounded():
    with pytest.raises(BoardValidationError):
        new_object('text', text='x' * 20001)
    with pytest.raises(BoardValidationError):
        new_object('ink', points=[[0, 0]] * 10001)
    with pytest.raises(BoardValidationError):
        new_object('ink', points=[[101, 0]])
    with pytest.raises(BoardValidationError):
        BoardModel({**new_lesson(), 'revision': True})
    with pytest.raises(BoardValidationError):
        new_object('text', html='<script>run()</script>')


def test_aggregate_command_limit_precedes_candidate_mutation(monkeypatch):
    model = BoardModel()
    initial = model.export_state()
    monkeypatch.setattr(board_model, 'MAX_DOCUMENT_BYTES', 256)
    with pytest.raises(BoardValidationError, match='batch exceeds'):
        model.apply([{'op': 'rename_lesson', 'title': 'x' * 180}] * 3, expected_revision=0)
    assert model.export_state() == initial


def test_persisted_history_rejects_different_lesson_and_future_revisions():
    model = BoardModel()
    add(model)
    state = model.export_state()
    bad = copy.deepcopy(state)
    bad['undo'][0]['lesson_id'] = str(uuid.uuid4())
    with pytest.raises(BoardValidationError, match='History'):
        BoardModel.from_state(bad)
    state['undo'][0]['revision'] = model.revision
    with pytest.raises(BoardValidationError, match='History'):
        BoardModel.from_state(state)
