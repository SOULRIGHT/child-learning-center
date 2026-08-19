"""수동 포인트 프리셋 설정. DailyPoints 지급 경로는 건드리지 않는다."""
from __future__ import annotations

import re

from sqlalchemy.exc import IntegrityError

from extensions import db
from feature_models import ManualPointPreset

KEY_RE = re.compile(r'^[a-z][a-z0-9_]{0,62}$')

DEFAULT_PRESETS = (
    {'key': 'textbook', 'label': '교재', 'default_points': 3000, 'default_reason': '교재 완료', 'sort_order': 10},
    {'key': 'print', 'label': '프린트', 'default_points': -100, 'default_reason': '프린트 사용', 'sort_order': 20},
    {'key': 'pencil', 'label': '연필', 'default_points': -300, 'default_reason': '연필 구매', 'sort_order': 30},
    {'key': 'eraser', 'label': '지우개', 'default_points': -500, 'default_reason': '지우개 구매', 'sort_order': 40},
    {'key': 'pencil_case', 'label': '필통', 'default_points': -1000, 'default_reason': '필통 구매', 'sort_order': 50},
)


class PresetError(Exception):
    def __init__(self, message, code='error'):
        super().__init__(message)
        self.message = message
        self.code = code


def _clean_key(raw):
    key = '' if raw is None else str(raw).strip().lower()
    if not KEY_RE.match(key):
        raise PresetError('key는 영문 소문자로 시작하고 영문/숫자/_ 만 사용할 수 있습니다.', code='invalid_key')
    return key


def _clean_label(raw):
    label = '' if raw is None else str(raw).strip()
    if not label:
        raise PresetError('표시 이름은 필수입니다.', code='label_required')
    return label[:80]


def _clean_reason(raw):
    if raw is None:
        return None
    text = str(raw).strip()
    return text[:80] or None


def _clean_points(raw):
    try:
        points = int(raw)
    except (TypeError, ValueError) as exc:
        raise PresetError('기본 포인트는 정수여야 합니다.', code='invalid_points') from exc
    if points == 0:
        raise PresetError('프리셋 포인트는 0이 될 수 없습니다.', code='zero_points')
    if points < -50000 or points > 50000:
        raise PresetError('프리셋 포인트 범위를 확인해주세요.', code='points_range')
    return points


def _clean_sort_order(raw):
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise PresetError('정렬 순서는 정수여야 합니다.', code='invalid_sort') from exc


def ensure_default_presets():
    """복구/초기화용. 없는 key만 추가하고 기존 값은 덮어쓰지 않는다.

    기본 5개의 정본은 Alembic migration e3a7b16c4d20 이다.
    페이지 GET / list_active_presets 에서는 호출하지 않는다.
    """
    existing = {row.key for row in ManualPointPreset.query.all()}
    created = 0
    for item in DEFAULT_PRESETS:
        if item['key'] in existing:
            continue
        db.session.add(ManualPointPreset(
            key=item['key'],
            label=item['label'],
            default_points=item['default_points'],
            default_reason=item['default_reason'],
            is_active=True,
            sort_order=item['sort_order'],
        ))
        created += 1
    if created:
        db.session.commit()
    return created


def list_presets(include_inactive=True):
    query = ManualPointPreset.query
    if not include_inactive:
        query = query.filter_by(is_active=True)
    return query.order_by(ManualPointPreset.sort_order.asc(), ManualPointPreset.id.asc()).all()


def list_active_presets():
    """활성 프리셋 SELECT만 수행한다. 누락 row를 재생성하지 않는다."""
    return list_presets(include_inactive=False)


def get_preset(preset_id):
    return ManualPointPreset.query.get(preset_id)


def create_preset(key, label, default_points, default_reason=None, is_active=True, sort_order=0):
    preset = ManualPointPreset(
        key=_clean_key(key),
        label=_clean_label(label),
        default_points=_clean_points(default_points),
        default_reason=_clean_reason(default_reason),
        is_active=bool(is_active),
        sort_order=_clean_sort_order(sort_order),
    )
    db.session.add(preset)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise PresetError('이미 사용 중인 key입니다.', code='duplicate_key') from exc
    return preset


def update_preset(preset, *, label=None, default_points=None, default_reason=None, is_active=None, sort_order=None):
    if label is not None:
        preset.label = _clean_label(label)
    if default_points is not None:
        preset.default_points = _clean_points(default_points)
    if default_reason is not None:
        preset.default_reason = _clean_reason(default_reason)
    if is_active is not None:
        preset.is_active = bool(is_active)
    if sort_order is not None:
        preset.sort_order = _clean_sort_order(sort_order)
    db.session.commit()
    return preset


def set_preset_active(preset, is_active):
    preset.is_active = bool(is_active)
    db.session.commit()
    return preset
