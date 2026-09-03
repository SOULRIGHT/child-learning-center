# 분석용 PointEvent projection. 원장 쓰기가 아니다.
from features.points.events import PointEvent
from features.points.project import accounting_parts, project_point_events


def project_current_center_events(records):
    """현재 센터 classifier를 주입한다. projector/composition core가 mapping을 모른다."""
    from features.points.mapping.current import classify_manual
    return project_point_events(records, classify_manual=classify_manual)


__all__ = (
    'PointEvent',
    'accounting_parts',
    'project_current_center_events',
    'project_point_events',
)
