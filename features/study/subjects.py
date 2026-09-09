"""학습 세션/정상학습일이 쓰는 과목 목록. 고정 3-key 목록을 쓰지 않는다."""
from features.progress.service import list_active_subjects


def list_study_subjects():
    """활성 LearningSubject. 과목명/key를 하드코딩하지 않는다."""
    return list_active_subjects()
