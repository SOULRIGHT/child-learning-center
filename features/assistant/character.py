"""Assistant character asset resolver. 파일이 있을 때만 채운다."""
from __future__ import annotations

from pathlib import Path

from flask import current_app, url_for

_IMAGE_NAMES = (
    'assistant/mark.svg',
    'assistant/idle.webp',
    'assistant/idle.png',
    'assistant-mark.svg',
)
_VIDEO_NAMES = (
    'assistant/idle.webm',
)


def resolve_assistant_character():
    static = Path(getattr(current_app, 'static_folder', None) or 'static')
    for name in _IMAGE_NAMES:
        if (static / 'img' / name).is_file():
            return {
                'kind': 'image',
                'url': url_for('static', filename=f'img/{name}'),
            }
    for name in _VIDEO_NAMES:
        if (static / 'img' / name).is_file():
            return {
                'kind': 'video',
                'url': url_for('static', filename=f'img/{name}'),
            }
    return {'kind': None, 'url': None}
