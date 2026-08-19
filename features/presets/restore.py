"""수동 포인트 프리셋 JSON 복원. 포인트 원장 복원 경로는 변경하지 않는다."""
from __future__ import annotations

from datetime import datetime

from extensions import db
from feature_models import ManualPointPreset


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def restore_presets_from_backup_data(backup_data):
    rows = (backup_data or {}).get('manual_point_presets') or []
    restored = 0
    for item in rows:
        if not isinstance(item, dict):
            continue
        key = (item.get('key') or '').strip()
        label = (item.get('label') or '').strip()
        if not key or not label:
            continue
        preset = None
        if item.get('id'):
            preset = ManualPointPreset.query.get(item.get('id'))
        if preset is None:
            preset = ManualPointPreset.query.filter_by(key=key).first()
        if preset is None:
            preset = ManualPointPreset(id=item.get('id')) if item.get('id') else ManualPointPreset()
            db.session.add(preset)
        preset.key = key
        preset.label = label
        try:
            preset.default_points = int(item.get('default_points'))
        except (TypeError, ValueError):
            continue
        reason = item.get('default_reason')
        preset.default_reason = (str(reason).strip() if reason is not None else None) or None
        if 'is_active' in item:
            preset.is_active = bool(item.get('is_active'))
        if item.get('sort_order') is not None:
            try:
                preset.sort_order = int(item.get('sort_order'))
            except (TypeError, ValueError):
                preset.sort_order = 0
        created_at = _parse_dt(item.get('created_at'))
        updated_at = _parse_dt(item.get('updated_at'))
        if created_at:
            preset.created_at = created_at
        if updated_at:
            preset.updated_at = updated_at
        restored += 1
    db.session.commit()
    return restored
