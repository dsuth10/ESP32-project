"""Bounded, local-first resource policy and deterministic factual charts for Board.

This module contains no network clients. Provider reservations remain owned by
MediaService and its shared ledger; the Board wrapper durably claims a single
job before calling that service.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from datetime import date
from typing import Any, Callable
from urllib.parse import urlparse

MAX_GOOGLE_ESTIMATE_CENTS = 50
MAX_CHART_POINTS = 50
MAX_RENDER_CHART_POINTS = 12
MAX_CHART_VALUE = 1_000_000_000
CHART_WIDTH, CHART_HEIGHT = 960, 720


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reason: str
    saved_version_id: str | None = None


def route_resource(intent: str, *, saved_matches=(), explicit_source: str | None = None,
                   local_only: bool = False, allow_illustrative: bool = False,
                   dataset_available: bool = False) -> RouteDecision:
    """Choose a route after deterministic local catalogue matching.

    ``saved_matches`` must already be relevance-filtered exact-version records.
    Multiple records are deliberately returned to a chooser rather than guessed.
    """
    matches = tuple(saved_matches or ())
    if matches:
        if len(matches) == 1:
            version = matches[0].get('version_id') if isinstance(matches[0], dict) else None
            if not isinstance(version, str) or not version:
                raise ValueError('A saved match must identify its immutable version.')
            return RouteDecision('saved', 'single suitable saved version', version)
        return RouteDecision('choose_saved', 'several suitable saved versions')
    if explicit_source not in (None, 'library', 'commons', 'google', 'chart'):
        raise ValueError('Choose a supported Board resource source.')
    if explicit_source == 'library':
        return RouteDecision('teacher_choice', 'no suitable saved version; select or import one')
    if intent not in {'photo', 'factual_image', 'illustration', 'chart', 'dataset'}:
        raise ValueError('The Board resource intent is unsupported.')
    if intent in {'chart', 'dataset'} or explicit_source == 'chart':
        if explicit_source in {'commons', 'google'}:
            return RouteDecision('teacher_choice', 'external pictures cannot supply factual chart measurements')
        if dataset_available:
            return RouteDecision('local_chart', 'validated teacher-supplied or saved dataset')
        if allow_illustrative:
            return RouteDecision('illustrative_chart', 'illustrative values explicitly permitted')
        return RouteDecision('teacher_choice', 'factual data is required for this chart')
    if local_only:
        return RouteDecision('teacher_choice', 'local-only mode blocks external acquisition')
    if explicit_source == 'google':
        if intent in {'photo', 'factual_image'}:
            return RouteDecision('teacher_choice', 'Google generation cannot substitute for factual photographic evidence')
        return RouteDecision('google_once', 'explicit illustration source')
    if explicit_source == 'commons' or intent in {'photo', 'factual_image'}:
        return RouteDecision('commons_once', 'bounded Commons retrieval for a real subject')
    return RouteDecision('google_once', 'original illustration')


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {'script', 'style'}:
            self._suppressed += 1

    def handle_endtag(self, tag):
        if tag.lower() in {'script', 'style'} and self._suppressed:
            self._suppressed -= 1

    def handle_data(self, data):
        if not self._suppressed:
            self.parts.append(data)


def _plain(value: Any, limit=1000) -> str:
    if isinstance(value, dict):
        value = value.get('value', '')
    if not isinstance(value, str):
        return ''
    parser = _PlainText()
    try:
        parser.feed(value)
        parser.close()
        value = ' '.join(' '.join(parser.parts).split())
    except Exception:
        return ''
    value = ''.join(ch for ch in value if ch >= ' ' and ch != '\x7f')
    return value[:limit].strip()


def _https_url(value: Any, *, host: str | None = None) -> str:
    if not isinstance(value, str) or len(value) > 2000:
        return ''
    parsed = urlparse(value)
    try:
        port = parsed.port
    except ValueError:
        return ''
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or port not in (None, 443) or parsed.fragment):
        return ''
    if host and parsed.hostname.lower() != host:
        return ''
    return value


def _machine_value(meta: dict, name: str) -> str:
    return _plain(meta.get(name, ''), 2000)


@dataclass(frozen=True)
class SanitisedRights:
    title: str
    creator: str
    licence: str
    licence_url: str
    source_url: str
    attribution: str
    credit: str = ''
    changes: str = ''

    def metadata(self) -> dict[str, str]:
        return {'title': self.title, 'creator': self.creator, 'licence': self.licence,
                'licence_url': self.licence_url, 'url': self.source_url,
                'attribution': self.attribution, 'credit': self.credit}


def validate_commons_candidate(candidate: dict) -> SanitisedRights:
    """Validate supported machine metadata; display strings alone never pass."""
    if not isinstance(candidate, dict):
        raise ValueError('Commons rights metadata is unavailable.')
    source = candidate.get('source') if isinstance(candidate.get('source'), dict) else {}
    meta = candidate.get('rights_metadata')
    if not isinstance(meta, dict):
        meta = candidate.get('extmetadata')
    if not isinstance(meta, dict):
        meta = candidate.get('metadata') if isinstance(candidate.get('metadata'), dict) else {}
    # The MediaWiki API exposes machine metadata under extmetadata. Flat
    # ``source`` fields are accepted for the already-normalised provider shape,
    # but only when an explicit canonical licence URL is also present.
    title = _plain(_machine_value(meta, 'ObjectName') or candidate.get('title') or source.get('title'), 300)
    creator = _plain(_machine_value(meta, 'Artist') or source.get('creator'), 500)
    attribution = _plain(_machine_value(meta, 'Attribution') or source.get('attribution'), 1000)
    credit = _plain(_machine_value(meta, 'Credit') or source.get('credit'), 1000)
    short = _plain(_machine_value(meta, 'LicenseShortName') or source.get('licence') or source.get('license'), 200).casefold()
    licence_url = _https_url(_machine_value(meta, 'LicenseUrl') or source.get('licence_url') or source.get('license_url'))
    source_url = _https_url(candidate.get('description_url') or candidate.get('source_url') or source.get('url'),
                            host='commons.wikimedia.org')
    download_url = _https_url(candidate.get('download_url'), host='upload.wikimedia.org')
    if not title or not source_url or not download_url:
        raise ValueError('Commons title and allowlisted source and file URLs are required.')

    copyrighted = _machine_value(meta, 'Copyrighted').strip().casefold()
    restrictions = _machine_value(meta, 'Restrictions').strip().casefold()
    usage_terms = _plain(_machine_value(meta, 'UsageTerms'), 1000).casefold()
    permission = _plain(_machine_value(meta, 'Permission'), 1000).casefold()
    attribution_required = _machine_value(meta, 'AttributionRequired').strip().casefold()
    if restrictions not in {'', 'none', 'none known', 'no restrictions', 'not applicable', 'attribution required'}:
        raise ValueError('Commons metadata reports unsupported or conflicting reuse restrictions.')
    unsupported_terms = ('by-sa', 'by-nc', 'by-nd', 'noncommercial', 'no derivatives', 'share-alike',
                         'share alike', 'all rights reserved', 'personality rights', 'privacy rights')
    if any(term in permission or term in usage_terms for term in unsupported_terms):
        raise ValueError('Commons permission metadata conflicts with the automatic reuse policy.')

    cc0_url = 'https://creativecommons.org/publicdomain/zero/1.0/'
    by_url = 'https://creativecommons.org/licenses/by/4.0/'
    pdm_url = 'https://creativecommons.org/publicdomain/mark/1.0/'
    canonical = licence_url.rstrip('/') + '/' if licence_url else ''
    if short in {'cc0', 'cc0 1.0', 'cc0 1.0 universal', 'creative commons zero 1.0'}:
        if canonical != cc0_url:
            raise ValueError('CC0 reuse needs the exact CC0 1.0 licence URL.')
        licence, licence_url = 'CC0 1.0', cc0_url
    elif short in {'cc by 4.0', 'cc by 4.0 international', 'creative commons attribution 4.0',
                   'creative commons attribution 4.0 international'}:
        if canonical != by_url:
            raise ValueError('CC BY reuse needs the exact CC BY 4.0 licence URL.')
        if not (creator or attribution or credit):
            raise ValueError('CC BY 4.0 needs its exact licence URL and complete attribution metadata.')
        licence, licence_url = 'CC BY 4.0', by_url
    elif short in {'public domain mark 1.0', 'public domain mark', 'cc public domain mark 1.0'}:
        if canonical != pdm_url:
            raise ValueError('Public Domain Mark needs its exact 1.0 designation URL.')
        if copyrighted not in {'false', 'no', '0'}:
            raise ValueError('Public-domain reuse needs a machine-readable uncopyrighted status.')
        if not any(phrase in usage_terms for phrase in ('public domain', 'public-domain')):
            raise ValueError('Public-domain reuse needs supporting machine-readable source terms.')
        licence, licence_url = 'Public Domain Mark 1.0', pdm_url
    else:
        raise ValueError('This Commons licence is outside the automatic reuse policy.')

    if licence == 'CC BY 4.0' and not (creator or attribution or credit):
        raise ValueError('CC BY 4.0 requires readable creator attribution.')
    if attribution_required in {'true', 'yes', '1'} and not (creator or attribution or credit):
        raise ValueError('Commons metadata requires attribution but provides no readable credit.')
    source_licence = _plain(source.get('licence') or source.get('license'), 200).casefold()
    source_licence_url = _https_url(source.get('licence_url') or source.get('license_url'))
    if source_licence_url and source_licence_url.rstrip('/') + '/' != licence_url:
        raise ValueError('Commons file and source-page licence URLs conflict.')
    if source_licence:
        accepted_labels = {
            'CC0 1.0': {'cc0', 'cc0 1.0', 'cc0 1.0 universal', 'creative commons zero 1.0'},
            'CC BY 4.0': {'cc by 4.0', 'cc by 4.0 international', 'creative commons attribution 4.0',
                          'creative commons attribution 4.0 international'},
            'Public Domain Mark 1.0': {'public domain mark', 'public domain mark 1.0'},
        }[licence]
        if source_licence not in accepted_labels:
            raise ValueError('Commons file and source-page licence metadata conflict.')
    return SanitisedRights(title, creator, licence, licence_url, source_url, attribution, credit)


def format_attribution(rights: SanitisedRights, *, changes: str = '') -> str:
    if not isinstance(rights, SanitisedRights):
        raise ValueError('Validate Commons rights before formatting attribution.')
    clean_changes = _plain(changes, 300)
    pieces = [rights.title]
    if rights.creator:
        pieces.append(f'by {rights.creator}')
    if rights.attribution:
        pieces.append(rights.attribution)
    if rights.credit and rights.credit != rights.attribution:
        pieces.append(rights.credit)
    pieces.extend((rights.source_url, f'{rights.licence} ({rights.licence_url})'))
    if clean_changes:
        pieces.append(f'Changes: {clean_changes}')
    return ' — '.join(pieces)


def _atomic_json(path: Path, value: dict) -> None:
    path = Path(path)
    if path.is_symlink() or path.is_junction():
        raise ValueError('Board acquisition state must not use a link or junction.')
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.board-acquisition-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, sort_keys=True, separators=(',', ':'), allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _create_claim(path: Path, value: dict) -> None:
    """Create the first request claim exclusively; never race via replace."""
    path = Path(path)
    if path.is_symlink() or path.is_junction():
        raise ValueError('Board acquisition state must not use a link or junction.')
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, 'O_BINARY'):
        flags |= os.O_BINARY
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


class BoardRequestAcquisition:
    """Durable one-attempt guard tied to a MediaService job identity.

    Use one state file per durable Board request (normally below the private
    application data directory). It calls ``MediaService.generate`` once, so
    the existing service continues to own reservation and outcome accounting.
    """
    def __init__(self, state_path: str | Path, request_id: str):
        if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,200}', request_id):
            raise ValueError('Board request identity is invalid.')
        self.path = Path(state_path)
        self.request_id = request_id

    def _read(self) -> dict | None:
        if not self.path.exists():
            return None
        if self.path.is_symlink() or self.path.is_junction() or self.path.stat().st_size > 4096:
            raise ValueError('Board acquisition state is unsafe or oversized.')
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError, UnicodeError):
            raise ValueError('Board acquisition state needs recovery; no retry is allowed.') from None
        if (not isinstance(value, dict) or value.get('schema') != 1
                or value.get('request_id') != self.request_id
                or value.get('status') not in {'claimed', 'completed', 'uncertain', 'reconciled'}):
            raise ValueError('Board acquisition identity or state is invalid; no retry is allowed.')
        return value

    @staticmethod
    def unresolved(state_root: str | Path, *, maximum=200) -> list[dict[str, str]]:
        """Return bounded unresolved paid-operation identities without prompts."""
        root = Path(state_root)
        if root.is_symlink() or root.is_junction():
            raise ValueError('Board acquisition state must not use a link or junction.')
        if not root.exists():
            return []
        if not root.is_dir() or type(maximum) is not int or not 1 <= maximum <= 1000:
            raise ValueError('Board acquisition state directory or scan limit is invalid.')
        files = sorted(root.glob('*.json'))
        if len(files) > maximum:
            raise ValueError('Too many Board acquisition records need review before another Google attempt.')
        pending = []
        for path in files:
            if path.is_symlink() or path.is_junction() or path.stat().st_size > 4096:
                raise ValueError('A Board acquisition record is unsafe or oversized.')
            try:
                value = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError, UnicodeError):
                raise ValueError('A Board acquisition record needs recovery; no new Google attempt is allowed.') from None
            if not isinstance(value, dict):
                raise ValueError('A Board acquisition record is invalid; no new Google attempt is allowed.')
            request_id, job_id, status = value.get('request_id'), value.get('job_id'), value.get('status')
            if (value.get('schema') != 1
                    or not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,200}', request_id)
                    or path.name != request_id + '.json'
                    or not isinstance(job_id, str) or not job_id
                    or status not in {'claimed', 'completed', 'uncertain', 'reconciled'}):
                raise ValueError('A Board acquisition record is invalid; no new Google attempt is allowed.')
            if status in {'claimed', 'uncertain'}:
                pending.append({'request_id': request_id, 'job_id': job_id, 'status': status})
        return pending

    def reconcile(self, media_service, job_id: str, *, outcome: str):
        """Clear an unresolved barrier only after an explicit existing-job review."""
        if outcome not in {'saved_result_reviewed', 'provider_account_reviewed', 'pre_dispatch_failure_reviewed'}:
            raise ValueError('Choose an explicit completed provider, saved-result or pre-dispatch review.')
        state = self._read()
        if not state or state.get('job_id') != job_id or state.get('status') not in {'claimed', 'uncertain'}:
            raise ValueError('Select the unresolved job bound to this Board request.')
        job = media_service.store.get_job(job_id)
        if not job or job.get('job_id') != job_id:
            raise ValueError('The existing media job is unavailable; retain its allocation for recovery.')
        phase = job.get('phase')
        if outcome == 'saved_result_reviewed' and (phase != 'preview_ready' or not job.get('version_id')):
            raise ValueError('The selected media job has no saved image to review.')
        if outcome == 'provider_account_reviewed' and phase != 'needs_recovery':
            raise ValueError('The selected media job is not awaiting provider reconciliation.')
        if outcome == 'pre_dispatch_failure_reviewed' and (phase != 'failed' or job.get('provider_dispatched')):
            raise ValueError('The selected media job may have dispatched and cannot be cleared as a pre-dispatch failure.')
        state.update(status='reconciled', reconciliation=outcome)
        _atomic_json(self.path, state)
        return state

    def generate_once(self, media_service, job_id: str, *, estimate_cents: int,
                      action: str = 'generate', on_stage=None):
        if action != 'generate':
            raise ValueError('Automatic Board acquisition cannot refine or create a second candidate.')
        if type(estimate_cents) is not int or not 1 <= estimate_cents <= MAX_GOOGLE_ESTIMATE_CENTS:
            raise ValueError('The configured Google estimate must be positive and no more than A$0.50 per request.')
        job = media_service.store.get_job(job_id)
        if not job or job.get('kind') != 'generate' or job.get('phase') != 'awaiting_user':
            raise ValueError('Select a fresh Board generation job before acquisition.')
        snapshot = job.get('image_provider') or {}
        options = snapshot.get('options') or {}
        config = getattr(media_service, 'config', {})
        if str(config.get('LOCAL_ONLY', '0')).lower() in {'1', 'true', 'yes', 'on'}:
            raise ValueError('Cloud image generation is unavailable in local-only mode.')
        if str(config.get('IMAGE_GENERATION_ENABLED', '0')).lower() not in {'1', 'true', 'yes', 'on'}:
            raise ValueError('Image generation is disabled in the current settings.')
        try:
            from image_provider_config import image_snapshot
            current_snapshot = image_snapshot(config, options)
            current_settings = image_snapshot(config)
        except (TypeError, ValueError):
            raise ValueError('The configured Google estimate and output settings are invalid.') from None
        if (snapshot.get('provider') != 'gemini' or snapshot.get('model') != 'gemini-nano-banana-2.1'
                or options.get('size') != '1K' or type(snapshot.get('allocation_cents')) is not int
                or snapshot.get('allocation_cents') != estimate_cents
                or snapshot != current_snapshot or job.get('image_settings', snapshot) != current_settings):
            raise ValueError('Board acquisition requires the configured Google Nano Banana 2.1 estimate and 1K output.')
        previous = self._read()
        if previous:
            if previous.get('job_id') != job_id:
                raise ValueError('This Board request already claimed a different provider job; no replacement identity is allowed.')
            raise ValueError('This Board request already attempted Google. Reconcile the same job; do not retry automatically.')
        claim = {'schema': 1, 'request_id': self.request_id, 'job_id': job_id, 'status': 'claimed'}
        try:
            _create_claim(self.path, claim)
        except FileExistsError:
            raise ValueError('This Board request was already claimed concurrently; do not retry automatically.') from None
        try:
            result = media_service.generate(job_id, on_stage=on_stage)
        except Exception:
            claim['status'] = 'uncertain'
            _atomic_json(self.path, claim)
            raise
        claim['status'] = 'completed'
        _atomic_json(self.path, claim)
        return result


def _text_field(value: Any, maximum: int, label: str, *, required=False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f'{label} must be readable text within {maximum} characters.')
    if any(ord(ch) < 32 and ch not in '\t\n\r' for ch in value):
        raise ValueError(f'{label} contains unsupported control characters.')
    return value.strip()


def _date_field(value: Any, label: str) -> str:
    value = _text_field(value, 10, label, required=True)
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError()
    except ValueError:
        raise ValueError(f'{label} must be an exact YYYY-MM-DD date.') from None
    return value


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                          allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ValueError('Chart data must be finite, valid UTF-8 JSON.') from None


def validate_dataset(dataset: dict) -> dict:
    """Validate bounded structured data and retain all missing values as null."""
    if not isinstance(dataset, dict) or set(dataset) != {'schema', 'title', 'x', 'y', 'points', 'provenance', 'illustrative'}:
        raise ValueError('Dataset fields are incomplete or unsupported.')
    if dataset['schema'] != 1 or type(dataset['illustrative']) is not bool:
        raise ValueError('Unsupported dataset schema or illustrative flag.')
    title = _text_field(dataset['title'], 160, 'Dataset title', required=True)
    axes = {}
    for key in ('x', 'y'):
        axis = dataset[key]
        if not isinstance(axis, dict) or set(axis) != {'label', 'unit'}:
            raise ValueError('Each chart axis needs an explicit label and unit.')
        axes[key] = {'label': _text_field(axis['label'], 100, 'Axis label', required=True),
                     'unit': _text_field(axis['unit'], 50, 'Axis unit', required=True)}
    points = dataset['points']
    if not isinstance(points, list) or not 1 <= len(points) <= MAX_CHART_POINTS:
        raise ValueError(f'Dataset must contain 1–{MAX_CHART_POINTS} points.')
    clean_points = []
    for point in points:
        if not isinstance(point, dict) or set(point) != {'label', 'value'}:
            raise ValueError('Each dataset point needs a label and a value.')
        label = _text_field(point['label'], 80, 'Data label', required=True)
        value = point['value']
        if value is not None:
            if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > MAX_CHART_VALUE:
                raise ValueError('Chart values must be finite numbers within the supported range, or null.')
            value = int(value) if type(value) is int else float(value)
        clean_points.append({'label': label, 'value': value})
    provenance = dataset['provenance']
    if not isinstance(provenance, dict) or provenance.get('kind') not in {'teacher_supplied', 'saved', 'published'}:
        raise ValueError('Dataset provenance must identify a teacher, saved or published source.')
    kind = provenance['kind']
    if kind == 'teacher_supplied':
        source = {'kind': kind, 'publisher': _text_field(provenance.get('publisher', 'Teacher supplied'), 160, 'Publisher', required=True),
                  'source_url': _https_url(provenance.get('source_url')),
                  'date': _date_field(provenance.get('date', ''), 'Date'),
                  'coverage': _text_field(provenance.get('coverage', ''), 200, 'Data coverage', required=True)}
    elif kind == 'saved':
        if not re.fullmatch(r'[0-9a-f]{64}', str(provenance.get('sha256', ''))):
            raise ValueError('A saved dataset needs its immutable SHA-256 reference.')
        version_id = _text_field(provenance.get('version_id', ''), 200, 'Saved dataset version', required=True)
        source = {'kind': kind, 'publisher': _text_field(provenance.get('publisher', ''), 160, 'Publisher', required=True),
                  'source_url': _https_url(provenance.get('source_url')),
                  'date': _date_field(provenance.get('date', ''), 'Date'),
                  'coverage': _text_field(provenance.get('coverage', ''), 200, 'Data coverage', required=True),
                  'sha256': provenance['sha256'], 'version_id': version_id}
        if not source['source_url']:
            raise ValueError('A saved dataset needs its source URL.')
    else:
        source_url = _https_url(provenance.get('source_url'))
        published_date = _date_field(provenance.get('date', ''), 'Publication or retrieval date')
        licence = _text_field(provenance.get('licence', ''), 200, 'Dataset licence', required=True)
        if not source_url or not _text_field(provenance.get('publisher', ''), 160, 'Publisher', required=True):
            raise ValueError('Published data needs a publisher and HTTPS source URL.')
        source = {'kind': kind, 'publisher': provenance['publisher'].strip(), 'source_url': source_url,
                  'date': published_date, 'licence': licence,
                  'coverage': _text_field(provenance.get('coverage', ''), 200, 'Data coverage', required=True)}
    result = {'schema': 1, 'title': title, 'x': axes['x'], 'y': axes['y'],
              'points': clean_points, 'provenance': source, 'illustrative': dataset['illustrative']}
    _canonical(result)
    return result


@dataclass(frozen=True)
class ChartArtifact:
    image_bytes: bytes
    mime: str
    dataset_sha256: str
    spec_sha256: str
    _dataset_json: bytes
    _spec_json: bytes
    provenance_label: str

    @property
    def dataset(self) -> dict:
        """Return a fresh view; the catalogue snapshot itself is immutable bytes."""
        return json.loads(self._dataset_json.decode('utf-8'))

    @property
    def spec(self) -> dict:
        return json.loads(self._spec_json.decode('utf-8'))


def render_chart(dataset: dict, spec: dict, *, allow_illustrative: bool = False) -> ChartArtifact:
    """Render a readable deterministic bar chart from a bounded dataset."""
    clean = validate_dataset(dataset)
    if clean['illustrative'] and not allow_illustrative:
        raise ValueError('Illustrative data is not permitted for this request.')
    if not isinstance(spec, dict) or set(spec) - {'kind', 'title', 'colour'}:
        raise ValueError('Unsupported chart specification.')
    kind = spec.get('kind', 'bar')
    if kind != 'bar':
        raise ValueError('Only deterministic bar charts are currently supported.')
    if len(clean['points']) > MAX_RENDER_CHART_POINTS:
        raise ValueError(f'A single Board chart supports at most {MAX_RENDER_CHART_POINTS} readable bars; reduce or split the dataset.')
    title = _text_field(spec.get('title', clean['title']), 160, 'Chart title', required=True)
    colour = spec.get('colour', '#2878B5')
    if not isinstance(colour, str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}', colour):
        raise ValueError('Chart colour must use #RRGGBB.')
    chart_width = max(CHART_WIDTH, min(1440, len(clean['points']) * 110 + 120))
    chart_height = 720
    clean_spec = {'kind': 'bar', 'title': title, 'colour': colour.upper(),
                  'width': chart_width, 'height': chart_height}

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise ValueError('Pillow is required for local chart rendering.') from None
    image = Image.new('RGB', (chart_width, chart_height), 'white')
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=28)
    except TypeError:
        raise ValueError('Pillow with scalable fonts is required for a readable chart.') from None
    left, right, top, bottom = 230, 30, 150, 290
    plot_left, plot_right = left, chart_width - right
    plot_top, plot_bottom = top, chart_height - bottom
    def wrap(text, max_width, max_lines, label, *, split_words=False):
        lines, line = [], ''
        for word in text.split():
            if draw.textbbox((0, 0), word, font=font)[2] > max_width:
                if not split_words:
                    raise ValueError(f'{label} contains a word too wide for the supported chart layout.')
                segments, segment = [], ''
                for character in word:
                    candidate = segment + character
                    if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                        segment = candidate
                    else:
                        if not segment:
                            raise ValueError(f'{label} contains a character too wide for the supported chart layout.')
                        segments.append(segment); segment = character
                if segment:
                    segments.append(segment)
                if line:
                    lines.append(line); line = ''
                lines.extend(segments[:-1])
                word = segments[-1]
            candidate = word if not line else line + ' ' + word
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                line = candidate
            else:
                lines.append(line); line = word
        if line:
            lines.append(line)
        if not lines or len(lines) > max_lines:
            raise ValueError(f'{label} does not fit the supported chart layout without truncation.')
        return lines

    visible_title = 'ILLUSTRATIVE DATA — ' + title if clean['illustrative'] else title
    if clean['illustrative']:
        draw.rectangle((0, 0, chart_width, 112), fill='#FFF1CC')
    title_lines = wrap(visible_title, chart_width - 60, 2, 'Chart title')
    for line_number, line in enumerate(title_lines):
        draw.text((30, 18 + line_number * 34), line,
                  fill='#7A4200' if clean['illustrative'] else '#17324D', font=font)
    source = clean['provenance']
    source_label = f"Source: {source['publisher']}"
    if source.get('date'):
        source_label += f" · {source['date']}"
    source_lines = wrap(source_label, chart_width - 60, 2, 'Chart source and date')
    values = [p['value'] for p in clean['points'] if p['value'] is not None]
    if not values:
        raise ValueError('A factual chart needs at least one measured value.')
    low, high = min(0, min(values)), max(0, max(values))
    if low == high:
        low, high = -1, 1
    def value_y(value):
        return plot_top + (high - value) / (high - low) * (plot_bottom - plot_top)
    tick_values = sorted(set((low, 0, high)))
    for tick in tick_values:
        y = round(value_y(tick))
        draw.line((plot_left, y, plot_right, y), fill='#CBD5DF' if tick else '#506070', width=2 if not tick else 1)
        draw.text((12, max(0, y - 17)), f'{tick:g}', fill='#17324D', font=font)
    baseline = value_y(0)
    slot = (plot_right - plot_left) / len(clean['points'])
    for index, point in enumerate(clean['points']):
        slot_left = plot_left + index * slot
        x0 = slot_left + slot * 0.22
        x1 = plot_left + (index + 1) * slot - slot * 0.22
        value = point['value']
        if value is not None:
            y0, y1 = sorted((value_y(value), baseline))
            draw.rectangle((round(x0), round(y0), round(x1), round(y1)), fill=clean_spec['colour'])
        label = point['label'] if value is not None else point['label'] + ' (no data)'
        lines = wrap(label, slot - 14, 3, 'Chart category label', split_words=True)
        for line_number, line in enumerate(lines):
            draw.text((round(slot_left + 7), plot_bottom + 8 + line_number * 34), line, fill='#17324D', font=font)
    axis_text = (f"X axis: {clean['x']['label']} ({clean['x']['unit']}) · "
                 f"Y axis: {clean['y']['label']} ({clean['y']['unit']})")
    axis_lines = wrap(axis_text, chart_width - 60, 2, 'Chart axis labels and units')
    for line_number, line in enumerate(axis_lines):
        draw.text((30, 550 + line_number * 34), line, fill='#34495E', font=font)
    for line_number, line in enumerate(source_lines):
        draw.text((30, 630 + line_number * 34), line, fill='#34495E', font=font)
    from io import BytesIO
    stream = BytesIO()
    image.save(stream, format='PNG', optimize=False, compress_level=9)
    data_bytes = stream.getvalue()
    provenance_label = source_label + (f" · {clean['y']['unit']}" if clean['y']['unit'] else '')
    dataset_json, spec_json = _canonical(clean), _canonical(clean_spec)
    return ChartArtifact(data_bytes, 'image/png', hashlib.sha256(dataset_json).hexdigest(),
                         hashlib.sha256(spec_json).hexdigest(), dataset_json, spec_json, provenance_label)
