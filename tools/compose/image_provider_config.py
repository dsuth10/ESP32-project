"""Image producer contract and local request snapshots; never contains credentials."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

OPENAI_MODEL = 'gpt-image-2.5-sunburst'
GOOGLE_MODEL = 'gemini-nano-banana-2.1'
PROVIDER_LABELS = {'openai': 'OpenAI', 'gemini': 'Google Gemini'}


@dataclass(frozen=True)
class ImageCapabilities:
    generation: bool
    reference_image: bool
    sizes: tuple[str, ...]
    aspect_ratios: tuple[str, ...]
    adapter_available: bool = True


CAPABILITIES = {
    'openai': ImageCapabilities(True, True, ('1024x1024',), ('1:1',)),
    'gemini': ImageCapabilities(True, True, ('1K', '2K', '4K'), ('1:1', '3:4', '4:3')),
}


class ImageProvider(Protocol):
    def generate(self, prompt: str, *, parent: Path | None = None, options: dict | None = None, on_stage=None) -> dict: ...
    def close(self): ...


def selected_provider(config):
    provider = config.get('IMAGE_PROVIDER') or 'openai'
    if provider not in CAPABILITIES:
        raise ValueError('Choose a supported image producer in Settings.')
    return provider


def selected_model(config, provider):
    model = config.get('GOOGLE_IMAGE_MODEL' if provider == 'gemini' else 'IMAGE_MODEL')
    model = model or (GOOGLE_MODEL if provider == 'gemini' else OPENAI_MODEL)
    # Exact identifiers only; never permit URL paths or query fragments.
    import re
    if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,119}', model):
        raise ValueError('Enter a valid image model identifier.')
    if provider == 'gemini' and model != GOOGLE_MODEL:
        raise ValueError('This preview supports Nano Banana 2.1 for Google images.')
    return model


def validate_options(provider, options=None):
    defaults = ({'size': '1024x1024', 'aspect_ratio': '1:1', 'quality': 'high'} if provider == 'openai'
                else {'size': '1K', 'aspect_ratio': '1:1', 'thinking': 'medium'})
    if options is not None and (not isinstance(options, dict) or set(options) - set(defaults)):
        raise ValueError('Unsupported image output option.')
    result = {**defaults, **(options or {})}
    capabilities = CAPABILITIES[provider]
    if result['size'] not in capabilities.sizes or result['aspect_ratio'] not in capabilities.aspect_ratios:
        raise ValueError('This image producer does not support that size or aspect ratio.')
    if provider == 'openai' and result['quality'] != 'high':
        raise ValueError('This preview preserves high quality for OpenAI images.')
    if provider == 'gemini' and result['thinking'] not in ('minimal', 'medium', 'high'):
        raise ValueError('Unsupported Google thinking level.')
    return result


def image_snapshot(config, options=None):
    provider = selected_provider(config)
    if options is not None and not isinstance(options, dict):
        raise ValueError('Unsupported image output option.')
    if provider == 'gemini':
        configured = {'size': config.get('GOOGLE_IMAGE_SIZE') or '1K',
                      'aspect_ratio': config.get('GOOGLE_IMAGE_ASPECT_RATIO') or '1:1',
                      'thinking': config.get('GOOGLE_IMAGE_THINKING') or 'medium'}
        options = {**configured, **(options or {})}
    output = validate_options(provider, options)
    # Google has one supported exact model; each resolution needs its own
    # deliberate allocation. Never borrow an OpenAI allocation for Google.
    allocation_key = f"GOOGLE_IMAGE_ESTIMATE_{output['size']}_AUD_CENTS" if provider == 'gemini' else 'IMAGE_ESTIMATE_AUD_CENTS'
    try:
        allocation = int(config.get(allocation_key) or 0)
    except (TypeError, ValueError):
        raise ValueError('Configure a conservative AUD allocation in Settings.') from None
    if not 0 <= allocation <= 3000:
        raise ValueError('Set an allocation from 1 to 3000 AUD cents before generation.')
    return {'schema': 1, 'provider': provider, 'model': selected_model(config, provider),
            'options': output, 'allocation_cents': allocation}


def image_readiness(config):
    provider = selected_provider(config)
    selected_model(config, provider)
    key = 'GOOGLE_IMAGE_API_KEY' if provider == 'gemini' else 'OPENAI_API_KEY'
    credentials = 'configured; model access unchecked' if config.get(key) else 'not configured'
    adapter = 'ready' if CAPABILITIES[provider].adapter_available else 'pending implementation; rendering unavailable'
    enabled = str(config.get('IMAGE_GENERATION_ENABLED', '0')).lower() in {'1', 'true', 'yes', 'on'}
    local = str(config.get('LOCAL_ONLY', '0')).lower() in {'1', 'true', 'yes', 'on'}
    return (f'{PROVIDER_LABELS[provider]} credentials: {credentials}. Adapter: {adapter}.\n'
            f'Generation: {"blocked by local-only mode" if local else "enabled" if enabled else "disabled"}. '
            'Budget: not checked here; the authenticated ledger must reserve before dispatch.')


def create_image_provider(snapshot, config, *, session=None) -> ImageProvider:
    provider = snapshot['provider']
    if provider not in CAPABILITIES:
        raise ValueError('Unsupported image producer.')
    validate_options(provider, snapshot['options'])
    if not CAPABILITIES[provider].adapter_available:
        raise ValueError('Google image rendering is pending implementation. No request was sent.')
    if provider == 'gemini':
        from gemini_images import GeminiImageProvider
        return GeminiImageProvider(config.get('GOOGLE_IMAGE_API_KEY', ''), snapshot['model'], session=session)
    from media_providers import OpenAIImageProvider
    return OpenAIImageProvider(config.get('OPENAI_API_KEY', ''), snapshot['model'], session=session)
