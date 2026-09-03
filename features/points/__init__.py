# 분석용 PointEvent projection. 원장 쓰기가 아니다.
from features.points.events import CATEGORY_UNCLASSIFIED, ManualClassification, PointEvent
from features.points.project import accounting_parts, project_point_events


def project_current_center_events(records):
    """현재 센터 deterministic + stored semantic fallback. projector core는 mapping을 모른다."""
    from features.points.mapping.current import classify_manual
    from features.points.semantic import semantic_classification_for

    def classify(item):
        classified = classify_manual(item)
        if (
            isinstance(classified, ManualClassification)
            and classified.category != CATEGORY_UNCLASSIFIED
        ):
            return classified
        return semantic_classification_for(item)

    return project_point_events(records, classify_manual=classify)


__all__ = (
    'PointEvent',
    'accounting_parts',
    'project_current_center_events',
    'project_point_events',
)
