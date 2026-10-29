from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

COMPOSE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COMPOSE))

from board_resource_policy import (  # noqa: E402
    BoardRequestAcquisition, format_attribution, render_chart, route_resource,
    validate_commons_candidate, validate_dataset,
)
from image_provider_config import image_snapshot  # noqa: E402


def candidate(*, licence='CC BY 4.0', licence_url='https://creativecommons.org/licenses/by/4.0/',
              restrictions='', copyrighted='true', usage=''):
    def value(text):
        return {'value': text}
    return {
        'title': 'File: Rain <b>cycle</b>.jpg',
        'download_url': 'https://upload.wikimedia.org/wikipedia/commons/a/a1/rain.jpg',
        'description_url': 'https://commons.wikimedia.org/wiki/File:Rain_cycle.jpg',
        'rights_metadata': {
            'LicenseShortName': value(licence), 'LicenseUrl': value(licence_url),
            'Artist': value('<a href="https://example.invalid">A. Teacher</a>'),
            'Attribution': value('A. Teacher / Commons'), 'Credit': value('Classroom credit'),
            'ObjectName': value('Rain cycle'), 'Copyrighted': value(copyrighted),
            'Restrictions': value(restrictions), 'UsageTerms': value(usage),
        },
    }


def dataset(*, illustrative=False):
    return {
        'schema': 1, 'title': 'Monthly rainfall',
        'x': {'label': 'Month', 'unit': 'month'},
        'y': {'label': 'Rainfall', 'unit': 'mm'},
        'points': [{'label': 'Jan', 'value': 80}, {'label': 'Feb', 'value': None},
                   {'label': 'Mar', 'value': 120}],
        'provenance': {'kind': 'published', 'publisher': 'Bureau of Example Data',
                       'source_url': 'https://example.org/rainfall', 'date': '2026-10-25',
                       'licence': 'CC BY 4.0', 'coverage': 'Monthly, 2025'},
        'illustrative': illustrative,
    }


def test_saved_library_wins_and_multiple_versions_remain_a_choice():
    assert route_resource('illustration', saved_matches=[{'version_id': 'v1'}]).route == 'saved'
    ambiguous = route_resource('photo', saved_matches=[{'version_id': 'v1'}, {'version_id': 'v2'}])
    assert (ambiguous.route, ambiguous.saved_version_id) == ('choose_saved', None)


@pytest.mark.parametrize(('intent', 'source'), [('photo', 'commons_once'), ('illustration', 'generate_once')])
def test_source_routing_uses_intent_without_sequential_fallback(intent, source):
    assert route_resource(intent).route == source
    assert route_resource(intent, local_only=True).route == 'teacher_choice'


def test_factual_chart_routes_locally_and_never_fabricates_without_permission():
    assert route_resource('chart', dataset_available=True).route == 'local_chart'
    assert route_resource('chart').route == 'teacher_choice'
    assert route_resource('chart', allow_illustrative=True).route == 'illustrative_chart'
    assert route_resource('chart', local_only=True, dataset_available=True).route == 'local_chart'
    assert route_resource('chart', explicit_source='google', dataset_available=True).route == 'teacher_choice'


def test_commons_rights_require_supported_machine_metadata_and_emit_plain_credit():
    rights = validate_commons_candidate(candidate())
    credit = format_attribution(rights, changes='Cropped for the lesson')
    assert rights.licence == 'CC BY 4.0'
    assert '<' not in credit and 'href' not in credit and 'A. Teacher' in credit
    assert 'Classroom credit' in credit and 'Changes: Cropped for the lesson' in credit
    assert rights.metadata()['licence_url'] == 'https://creativecommons.org/licenses/by/4.0/'


def test_commons_accepts_cc0_and_strict_public_domain_mark():
    cc0 = validate_commons_candidate(candidate(licence='CC0 1.0',
        licence_url='https://creativecommons.org/publicdomain/zero/1.0/', copyrighted='false'))
    assert cc0.licence == 'CC0 1.0'
    pdm = validate_commons_candidate(candidate(licence='Public Domain Mark 1.0',
        licence_url='https://creativecommons.org/publicdomain/mark/1.0/', copyrighted='false',
        usage='Public domain work; source confirms status'))
    assert pdm.licence == 'Public Domain Mark 1.0'


@pytest.mark.parametrize('bad', [
    candidate(licence='CC BY-SA 4.0', licence_url='https://creativecommons.org/licenses/by-sa/4.0/'),
    candidate(licence='CC BY 4.0', licence_url='https://creativecommons.org/licenses/by-nc/4.0/'),
    candidate(licence='CC BY-SA 4.0', licence_url='https://creativecommons.org/licenses/by/4.0/'),
    candidate(licence='CC0 1.0', licence_url=''),
    {**candidate(), 'rights_metadata': {**candidate()['rights_metadata'],
        'UsageTerms': {'value': 'Creative Commons Attribution-NonCommercial 4.0'}}},
    {**candidate(), 'source': {'licence': 'CC BY 4.0', 'licence_url': 'https://creativecommons.org/licenses/by-nc/4.0/',
                               'url': 'https://commons.wikimedia.org/wiki/File:Rain_cycle.jpg'}},
    candidate(restrictions='Noncommercial use only'),
    candidate(restrictions='Personality rights reservation'),
    candidate(licence='Public domain', licence_url='', copyrighted=''),
    {**candidate(), 'download_url': 'http://upload.wikimedia.org/a.png'},
    {**candidate(), 'description_url': 'https://example.org/file'},
])
def test_commons_denies_unknown_conflicting_or_unsafe_rights(bad):
    with pytest.raises(ValueError):
        validate_commons_candidate(bad)


def test_dataset_keeps_missing_values_and_requires_source_units_and_provenance():
    clean = validate_dataset(dataset())
    assert clean['points'][1]['value'] is None
    assert clean['y']['unit'] == 'mm'
    assert clean['provenance']['source_url'] == 'https://example.org/rainfall'
    no_unit = dataset(); no_unit['y']['unit'] = ''
    with pytest.raises(ValueError):
        validate_dataset(no_unit)
    no_source = dataset(); no_source['provenance']['source_url'] = 'http://example.org/rainfall'
    with pytest.raises(ValueError):
        validate_dataset(no_source)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), 1_000_000_001, True])
def test_dataset_rejects_non_finite_boolean_and_unbounded_values(value):
    data = dataset(); data['points'][0]['value'] = value
    with pytest.raises(ValueError):
        validate_dataset(data)


def test_chart_is_deterministic_immutable_and_visibly_marks_illustrative_data():
    source = dataset()
    artifact = render_chart(source, {'kind': 'bar'})
    repeat = render_chart(source, {'kind': 'bar'})
    assert artifact.image_bytes.startswith(b'\x89PNG\r\n\x1a\n')
    assert artifact.image_bytes == repeat.image_bytes
    assert len(artifact.dataset_sha256) == len(artifact.spec_sha256) == 64
    assert artifact.dataset['points'][1]['value'] is None
    assert artifact.dataset['provenance']['publisher'] in artifact.provenance_label
    view = artifact.dataset
    view['points'][0]['value'] = 9999
    assert artifact.dataset['points'][0]['value'] == 80
    illustrative = dataset(illustrative=True)
    with pytest.raises(ValueError):
        render_chart(illustrative, {'kind': 'bar'})
    marked = render_chart(illustrative, {'kind': 'bar'}, allow_illustrative=True)
    assert marked.image_bytes != artifact.image_bytes
    dense = dataset()
    dense['points'] = [{'label': f'Month {i}', 'value': i} for i in range(13)]
    with pytest.raises(ValueError, match='at most 12 readable bars'):
        render_chart(dense, {'kind': 'bar'})
    dense['points'] = [{'label': f'Month {i}', 'value': i} for i in range(12)]
    dense_artifact = render_chart(dense, {'kind': 'bar'})
    assert dense_artifact.spec['width'] == 1440
    assert dense_artifact.spec['height'] == 720
    assert dense_artifact.dataset['points'][0]['label'] == 'Month 0'
    dense['points'][0]['label'] = 'x' * 80
    with pytest.raises(ValueError, match='does not fit'):
        render_chart(dense, {'kind': 'bar'})


def test_chart_rejects_unsupported_spec_and_unlabelled_dataset_shape():
    with pytest.raises(ValueError):
        render_chart(dataset(), {'kind': 'line'})
    data = dataset(); del data['illustrative']
    with pytest.raises(ValueError):
        validate_dataset(data)


class FakeMediaStore:
    def __init__(self, job):
        self.job = job

    def get_job(self, job_id):
        return copy.deepcopy(self.job) if self.job['job_id'] == job_id else None


def media_service(job, *, failure=None):
    service = Mock()
    service.store = FakeMediaStore(job)
    snapshot = job.get('image_provider') or {}
    provider = snapshot.get('provider', 'gemini')
    size = (snapshot.get('options') or {}).get('size', '1K')
    config = {'IMAGE_PROVIDER': provider, 'IMAGE_GENERATION_ENABLED': '1', 'LOCAL_ONLY': '0',
              'GOOGLE_IMAGE_MODEL': snapshot.get('model', 'gemini-nano-banana-2.1'),
              'GOOGLE_IMAGE_SIZE': size,
              'GOOGLE_IMAGE_ASPECT_RATIO': (snapshot.get('options') or {}).get('aspect_ratio', '1:1'),
              'GOOGLE_IMAGE_THINKING': 'medium',
              f'GOOGLE_IMAGE_ESTIMATE_{size}_AUD_CENTS': snapshot.get('allocation_cents', 50)}
    service.config = config
    if provider == 'openai':
        config.update(IMAGE_MODEL=snapshot.get('model', 'gpt-image-2.5-sunburst'),
                      IMAGE_ESTIMATE_AUD_CENTS=snapshot.get('allocation_cents', 50))
    try:
        job['image_settings'] = image_snapshot(config)
    except ValueError:
        job['image_settings'] = {}
    if failure:
        service.generate.side_effect = failure
    else:
        service.generate.return_value = {'version_id': 'saved-version'}
    return service


def fresh_job(job_id='job-1', *, provider='gemini', model='gemini-nano-banana-2.1', size='1K', estimate=50):
    options = ({'size': '1024x1024', 'aspect_ratio': '1:1', 'quality': 'high'} if provider == 'openai'
               else {'size': size, 'aspect_ratio': '1:1', 'thinking': 'medium'})
    return {'job_id': job_id, 'kind': 'generate', 'phase': 'awaiting_user',
            'image_provider': {'schema': 1, 'provider': provider, 'model': model, 'options': options,
                               'allocation_cents': estimate}}


def test_durable_guard_calls_shared_media_service_once_and_rejects_restart_retry(tmp_path):
    state = tmp_path / 'board-request.json'
    service = media_service(fresh_job())
    guard = BoardRequestAcquisition(state, 'board-request-17')
    assert guard.generate_once(service, 'job-1', estimate_cents=50) == {'version_id': 'saved-version'}
    service.generate.assert_called_once_with('job-1', on_stage=None)
    record = json.loads(state.read_text(encoding='utf-8'))
    assert record == {'schema': 1, 'request_id': 'board-request-17', 'job_id': 'job-1', 'status': 'completed'}
    with pytest.raises(ValueError, match='already attempted'):
        BoardRequestAcquisition(state, 'board-request-17').generate_once(service, 'job-1', estimate_cents=50)
    service.generate.assert_called_once()


@pytest.mark.parametrize(('provider', 'size'), [('gemini', '2K'), ('gemini', '4K'), ('openai', '1024x1024')])
def test_all_producers_keep_durable_no_replay_guard_and_frozen_options(tmp_path, provider, size):
    job = fresh_job(provider=provider, model='gemini-nano-banana-2.1' if provider == 'gemini' else 'gpt-image-2.5-sunburst',
                    size=size, estimate=125)
    service = media_service(job)
    guard = BoardRequestAcquisition(tmp_path / 'request.json', 'request')
    guard.generate_once(service, 'job-1', estimate_cents=125)
    with pytest.raises(ValueError, match='already attempted'):
        guard.generate_once(service, 'job-1', estimate_cents=125)
    service.generate.assert_called_once()

    other = media_service(copy.deepcopy(job))
    if provider == 'gemini':
        other.config['GOOGLE_IMAGE_SIZE'] = '1K'
    else:
        other.config['IMAGE_MODEL'] = 'changed-model'
    with pytest.raises(ValueError, match='configured image producer'):
        BoardRequestAcquisition(tmp_path / 'other.json', 'other').generate_once(other, 'job-1', estimate_cents=125)
    other.generate.assert_not_called()


def test_failed_or_uncertain_dispatch_keeps_claim_and_cannot_replace_identity(tmp_path):
    state = tmp_path / 'board-request.json'
    service = media_service(fresh_job(), failure=TimeoutError('uncertain'))
    with pytest.raises(TimeoutError):
        BoardRequestAcquisition(state, 'request-A').generate_once(service, 'job-1', estimate_cents=50)
    assert json.loads(state.read_text())['status'] == 'uncertain'
    replacement = media_service(fresh_job('job-2'))
    with pytest.raises(ValueError, match='different provider job'):
        BoardRequestAcquisition(state, 'request-A').generate_once(replacement, 'job-2', estimate_cents=50)
    service.generate.assert_called_once()
    replacement.generate.assert_not_called()


def test_concurrent_guard_instances_cannot_replace_the_exclusive_request_claim(tmp_path):
    state = tmp_path / 'board-request.json'
    services = [media_service(fresh_job()) for _ in range(2)]
    def attempt(service):
        try:
            return BoardRequestAcquisition(state, 'same-request').generate_once(
                service, 'job-1', estimate_cents=50)
        except ValueError as error:
            return error
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, services))
    assert sum(isinstance(value, dict) for value in outcomes) == 1
    assert sum(service.generate.call_count for service in services) == 1


@pytest.mark.parametrize('kwargs', [
    {'estimate_cents': 0}, {'estimate_cents': 3001}, {'estimate_cents': True},
])
def test_guard_rejects_invalid_or_over_limit_configured_estimate(tmp_path, kwargs):
    service = media_service(fresh_job())
    with pytest.raises(ValueError):
        BoardRequestAcquisition(tmp_path / 'state.json', 'request').generate_once(service, 'job-1', **kwargs)
    service.generate.assert_not_called()


@pytest.mark.parametrize('job', [
    fresh_job(provider='unsupported'), fresh_job(model='invalid/model'), fresh_job(size='invalid'),
    fresh_job(estimate=49), {**fresh_job(), 'kind': 'refine'},
])
def test_guard_rejects_refinement_wrong_model_resolution_and_estimate(tmp_path, job):
    service = media_service(job)
    with pytest.raises(ValueError):
        BoardRequestAcquisition(tmp_path / f'{job["job_id"]}.json', 'request').generate_once(
            service, job['job_id'], estimate_cents=50, action='refine' if job['kind'] == 'refine' else 'generate')
    service.generate.assert_not_called()


def test_guard_rejects_fresh_paid_refinement_even_with_valid_estimate(tmp_path):
    job = fresh_job(); job['kind'] = 'refine'
    service = media_service(job)
    with pytest.raises(ValueError, match='cannot refine'):
        BoardRequestAcquisition(tmp_path / 'state.json', 'request').generate_once(
            service, 'job-1', estimate_cents=50, action='refine')
    service.generate.assert_not_called()
