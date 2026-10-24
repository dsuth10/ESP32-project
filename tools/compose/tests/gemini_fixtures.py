"""Synthetic Interactions REST fixtures, checked against Google's 24 Oct 2026 schema.

These are constructed examples, not captured account responses. The PNG is a
24 × 24 blue square; it carries no teaching content or personal information.
Schema: https://ai.google.dev/static/api/interactions.openapi.json
"""
import copy

PNG_BASE64 = 'iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAIAAABvFaqvAAAALElEQVR4nGNkYPjPQA3ARBVTGEYNIgaMBjZhMBpGhMFoGBEGo2FEGAy+MAIAeawBL/b1uv8AAAAASUVORK5CYII='
IMAGE = {'type': 'image', 'mime_type': 'image/png', 'data': PNG_BASE64}
COMPLETED = {'id': 'synthetic-interaction-1', 'status': 'completed',
             'model': 'gemini-nano-banana-2.1',
             'steps': [{'type': 'thought', 'summary': [IMAGE]},
                       {'type': 'model_output', 'content': [IMAGE]}],
             'usage': {'total_input_tokens': 12, 'total_output_tokens': 34, 'total_tokens': 46}}
TEXT_ONLY = {'id': 'synthetic-refusal', 'status': 'completed', 'model': 'gemini-nano-banana-2.1',
             'steps': [{'type': 'model_output', 'content': [{'type': 'text', 'text': 'Synthetic refusal.'}]}],
             'usage': {'total_output_tokens': 4}}
INCOMPLETE = {'id': 'synthetic-incomplete', 'status': 'incomplete', 'model': 'gemini-nano-banana-2.1',
              'steps': [{'type': 'model_output', 'content': [IMAGE]}]}


def fixture(name='completed'):
    return copy.deepcopy({'completed': COMPLETED, 'text_only': TEXT_ONLY, 'incomplete': INCOMPLETE}[name])
