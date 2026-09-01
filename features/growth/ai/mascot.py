"""Growth AI mascot slot. 최종 캐릭터 파일만 교체하면 된다."""
from __future__ import annotations

from pathlib import Path

from flask import current_app, url_for

# 드롭인 파일 이름. PNG/WebP 우선, 이후 webm 등도 같은 slot에 넣는다.
_IMAGE_NAMES = (
    'growth-ai-mascot.webp',
    'growth-ai-mascot.png',
    'growth-ai-mascot.svg',
    'growth-ai/mascot.webp',
    'growth-ai/mascot.png',
)
_VIDEO_NAMES = (
    'growth-ai-mascot.webm',
    'growth-ai/mascot.webm',
)


def resolve_growth_ai_mascot():
    """정적 파일이 있으면 url/kind를 반환한다. 없으면 placeholder SVG를 쓴다."""
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
