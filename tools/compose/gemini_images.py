"""Stateless Gemini Interactions image requests. No retries, fallback or URL downloads."""
from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path

import requests

from image_provider_config import GOOGLE_MODEL, validate_options
from media_providers import ProviderFailure, safe_identifier, safe_usage
from media_store import MediaStore

ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/interactions'
MAX_RESPONSE_BYTES = 30 * 1024 * 1024
MAX_IMAGE_BYTES = 20 * 1024 * 1024
_RPC_STATUSES = {'CANCELLED', 'UNKNOWN', 'INVALID_ARGUMENT', 'DEADLINE_EXCEEDED', 'NOT_FOUND',
                 'ALREADY_EXISTS', 'PERMISSION_DENIED', 'UNAUTHENTICATED', 'RESOURCE_EXHAUSTED',
                 'FAILED_PRECONDITION', 'ABORTED', 'OUT_OF_RANGE', 'UNIMPLEMENTED', 'INTERNAL',
                 'UNAVAILABLE', 'DATA_LOSS'}
_REQUEST_FIELDS = {'body', 'request', 'model', 'input', 'type', 'text', 'mime_type', 'data',
                   'store', 'stream', 'background', 'generation_config', 'thinking_level',
                   'thinking_summaries', 'response_format', 'delivery', 'image_size', 'aspect_ratio'}


def error_diagnostics(response, *, excluded=()):
    """Read bounded error metadata and a redacted summary, never raw response bodies."""
    try:
        body = bytearray()
        for chunk in response.iter_content(4096):
            if len(body) + len(chunk) > 64 * 1024:
                return {}
            body.extend(chunk)
        value = json.loads(body)
        error = value.get('error') if isinstance(value, dict) else None
        if not isinstance(error, dict):return {}
        result = {}
        if error.get('status') in _RPC_STATUSES:
            result['provider_error_status'] = error['status']
        code = error.get('code')
        if type(code) is int and 400 <= code <= 599:
            result['provider_error_code'] = code
        fields = set()
        def add_field(field):
            if not isinstance(field, str) or len(field) > 160 or field in excluded:return
            parts = re.sub(r'\[\d+\]', '', field).split('.')
            if parts and all(part in _REQUEST_FIELDS for part in parts):fields.add(field)
        details = error.get('details')
        for detail in details[:32] if isinstance(details, list) else []:
            if not isinstance(detail, dict):continue
            if detail.get('@type') == 'type.googleapis.com/google.rpc.BadRequest':
                violations = detail.get('fieldViolations')
                for violation in violations[:32] if isinstance(violations, list) else []:
                    if isinstance(violation, dict):add_field(violation.get('field'))
            elif detail.get('@type') == 'type.googleapis.com/google.rpc.ErrorInfo':
                reason = detail.get('reason')
                if (isinstance(reason, str) and reason not in excluded
                        and re.fullmatch(r'[A-Z][A-Z_0-9]{0,79}', reason)):
                    result['provider_error_reason'] = reason
        message = error.get('message')
        if isinstance(message, str):
            # Some Google validation errors identify the rejected name only in
            # prose. Retain known request-field names, never that prose itself.
            for field in re.findall(r'Unknown name ["\']([A-Za-z_][A-Za-z_0-9]*)["\']', message[:8192]):
                add_field(field)
            summary = message
            for secret in sorted((value for value in excluded if value), key=len, reverse=True):
                summary = summary.replace(secret, '<REDACTED>')
            summary = re.sub(r'https?://[^\s<>"\']+', '<REDACTED>', summary)
            summary = re.sub(r'\b[A-Za-z]:[\\/][^\s<>"\']+', '<REDACTED>', summary)
            summary = re.sub(r'(?<!\w)/(?:[\w.-]+/)+[\w.-]*', '<REDACTED>', summary)
            summary = re.sub(r'AIza[A-Za-z_0-9-]{20,}|[A-Za-z_0-9+/=-]{80,}', '<REDACTED>', summary)
            summary = re.sub(r'(?i)\bbearer\s+\S+', 'Bearer <REDACTED>', summary)
            result['provider_error_summary'] = ' '.join(summary.split())[:500]
        if fields:result['provider_error_fields'] = sorted(fields)
        return result
    except Exception:
        return {}


class GeminiImageProvider:
    def __init__(self, api_key, model=GOOGLE_MODEL, *, session=None):
        if not api_key or model != GOOGLE_MODEL:
            raise ValueError('Configure the Google image API key and supported model in Settings.')
        self.key, self.model = api_key, model
        self.session = session or requests.Session()
        self.session.trust_env = False
        if session is None:
            self.session.mount('https://', requests.adapters.HTTPAdapter(max_retries=0))

    def generate(self, prompt, *, parent: Path | None = None, options=None, on_stage=None):
        output = validate_options('gemini', options)
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 8000:
            raise ValueError('Describe the image in 1–8000 characters.')
        content = [{'type': 'text', 'text': prompt}]
        if parent is not None:
            # Validate the one deliberate reference before any network dispatch.
            with Path(parent).open('rb') as stream:
                data = stream.read(MAX_IMAGE_BYTES + 1)
            mime, _, _ = MediaStore._inspect(data)
            content.append({'type': 'image', 'mime_type': mime,
                            'data': base64.b64encode(data).decode('ascii')})
        payload = {'model': self.model, 'input': content, 'store': False,
                   'stream': False, 'background': False,
                   'generation_config': {'thinking_level': output['thinking'], 'thinking_summaries': 'none'},
                   # The live API rejects explicit delivery='inline' although
                   # its OpenAPI schema lists it. Use the documented default;
                   # parsing still requires inline bytes and never fetches URIs.
                   'response_format': {'type': 'image', 'mime_type': 'image/jpeg',
                                       'image_size': output['size'], 'aspect_ratio': output['aspect_ratio']}}
        receipt = {'provider': 'gemini', 'requested_model': self.model, 'outcome': 'uncertain'}
        started = time.perf_counter()
        try:
            if on_stage:
                on_stage('Requesting image')
            with self.session.post(ENDPOINT, headers={'x-goog-api-key': self.key,
                    'Content-Type': 'application/json'}, json=payload,
                    timeout=(10, 240), allow_redirects=False, stream=True) as response:
                receipt['http_status'] = response.status_code
                receipt['request_id'] = safe_identifier(response.headers.get('x-request-id') or response.headers.get('x-goog-request-id', ''))
                if not 200 <= response.status_code < 300:
                    receipt['outcome'] = {401: 'authentication', 403: 'access_denied', 429: 'quota'}.get(
                        response.status_code, 'http_error')
                    receipt.update(error_diagnostics(response, excluded=(self.key, prompt)))
                    raise ValueError('No confirmed image')
                if on_stage:
                    on_stage('Receiving image')
                body = bytearray()
                for chunk in response.iter_content(64 * 1024):
                    if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                        receipt['outcome'] = 'oversized_response'
                        raise ValueError('Response exceeds limit')
                    body.extend(chunk)
                receipt['round_trip_seconds'] = round(time.perf_counter() - started, 3)
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError('Malformed response')
            receipt['interaction_id'] = safe_identifier(result.get('id'))
            receipt['usage'] = safe_usage(result.get('usage'))
            receipt['returned_model'] = safe_identifier(result.get('model'))
            status = result.get('status')
            receipt['status'] = status if status in {'completed', 'failed', 'cancelled', 'incomplete',
                                                       'in_progress', 'requires_action'} else 'unknown'
            if status != 'completed':
                receipt['outcome'] = 'incomplete_response'
                raise ValueError('Interaction is not complete')
            steps = result.get('steps')
            if not isinstance(steps, list) or not receipt['returned_model']:
                raise ValueError('Missing result provenance')
            finals = [step for step in steps if isinstance(step, dict) and step.get('type') == 'model_output']
            if not finals or not isinstance(finals[-1].get('content'), list):
                receipt['outcome'] = 'no_final_image'
                raise ValueError('No final output')
            images = [block for block in finals[-1]['content']
                      if isinstance(block, dict) and block.get('type') == 'image']
            image_count = sum(1 for step in finals for block in (step.get('content') or [])
                              if isinstance(block, dict) and block.get('type') == 'image')
            if len(images) != 1 or image_count != 1:
                receipt['outcome'] = 'no_final_image' if not images else 'multiple_final_images'
                raise ValueError('Expected one final image')
            image = images[0]
            encoded = image.get('data')
            if not isinstance(encoded, str) or len(encoded) > 28_000_000:
                raise ValueError('Invalid image data')
            data = base64.b64decode(encoded, validate=True)
            mime, width, height = MediaStore._inspect(data)
            if image.get('mime_type') != mime:
                raise ValueError('Image MIME mismatch')
            receipt.update(outcome='image_received', mime=mime, width=width, height=height)
            return {'data': data, 'mime': mime, 'source': {'provider': 'gemini', 'model': receipt['returned_model']},
                    'request_id': receipt['request_id'], 'usage': receipt['usage'], 'receipt': receipt}
        except Exception:
            receipt.setdefault('round_trip_seconds', round(time.perf_counter() - started, 3))
            if receipt['outcome'] == 'uncertain' and receipt.get('status') == 'completed':
                receipt['outcome'] = 'invalid_image_response'
            # No raw provider text, prompt, key, response bytes or local paths in errors.
            raise ProviderFailure('Google did not confirm a usable final image. Review this attempt; '
                                  'its allocation remains held and it will not retry automatically.', receipt=receipt) from None

    def close(self):
        self.session.close()


def check_google_model(config, *, session=None):
    """Explicit metadata GET only. Never invoke this during startup/save/setup."""
    if str(config.get('LOCAL_ONLY', '0')).lower() in {'1', 'true', 'yes', 'on'}:
        raise ValueError('Google connection checking is unavailable in local-only mode.')
    model = config.get('GOOGLE_IMAGE_MODEL') or GOOGLE_MODEL
    key = config.get('GOOGLE_IMAGE_API_KEY')
    if model != GOOGLE_MODEL or not key:
        raise ValueError('Enter the Google image key and supported model first.')
    client = session or requests.Session()
    client.trust_env = False
    try:
        with client.get('https://generativelanguage.googleapis.com/v1beta/models/' + model,
                        headers={'x-goog-api-key': key}, timeout=(5, 15), allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise ValueError('Model metadata could not be accessed')
            body = bytearray()
            for chunk in response.iter_content(8192):
                if len(body) + len(chunk) > 64 * 1024:
                    raise ValueError('Model metadata exceeds limit')
                body.extend(chunk)
            if json.loads(body).get('name') != 'models/' + model:
                raise ValueError('Unexpected model metadata')
        return 'Google model metadata is accessible. Paid rendering and budget availability remain unverified.'
    except Exception:
        raise ValueError('Google model access was not confirmed. Check the key, model access and connection. No image was requested.') from None
    finally:
        if session is None:
            client.close()
