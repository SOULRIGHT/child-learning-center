"""신규 도메인 모델. 기존 app.py 모델은 이동하지 않는다."""
from __future__ import annotations

import re
import unicodedata

from datetime import datetime

from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text

from extensions import db


_PUNCT_AND_SPACE_RE = re.compile(
    r'[\s\-–—_·•.,!?;:\'"“”‘’()\[\]{}/\\~*`]+'
)


def normalize_book_title(title):
    """제목 표기 차이를 완화한 검색 키를 만든다.

    규칙:
    - NFKC 정규화 (전각/호환 문자를 호환 형태로)
    - casefold (영문 대소문자)
    - 공백, 하이픈, 흔한 문장부호 제거
    - 한글/숫자/영문 본문은 유지
    - 저자는 포함하지 않음
    """
    if title is None:
        return ''
    text = unicodedata.normalize('NFKC', str(title)).strip()
    if not text:
        return ''
    text = text.casefold()
    text = _PUNCT_AND_SPACE_RE.sub('', text)
    return text


def clean_book_title(title):
    text = '' if title is None else str(title).strip()
    return text


def clean_book_author(author):
    if author is None:
        return None
    text = str(author).strip()
    return text or None


class Book(db.Model):
    __tablename__ = 'book'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=True)
    normalized_key = db.Column(db.String(255), nullable=False, index=True)
    is_recommended = db.Column(db.Boolean, nullable=False, default=False)
    grade_band = db.Column(db.String(16), nullable=True)
    is_challenge_eligible = db.Column(db.Boolean, nullable=False, default=False)
    ai_difficulty_low = db.Column(db.Integer, nullable=True)
    ai_difficulty_high = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_public_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'is_recommended': bool(self.is_recommended),
            'is_challenge_eligible': bool(self.is_challenge_eligible),
            'grade_band': self.grade_band,
            'is_active': bool(self.is_active),
        }

    def __repr__(self):
        return f'<Book {self.id} {self.title}>'


STATUS_IN_PROGRESS = 'in_progress'
STATUS_COMPLETED = 'completed'
STATUS_ABANDONED = 'abandoned'
PROGRAM_TYPE_GENERAL = 'general'
PROGRAM_TYPE_RECOMMENDED = 'recommended'
PROGRAM_TYPE_CHALLENGE = 'challenge'
POLICY_VERSION_GENERAL_V2 = 'general_v2'
POLICY_VERSION_RECOMMENDED_V1 = 'recommended_v1'
POLICY_VERSION_CHALLENGE_V1 = 'challenge_v1'
GRADE_BAND_2_3 = '2-3'
GRADE_BAND_4_6 = '4-6'
EVENT_RECOMMENDED_START = 'recommended_start'
EVENT_RECOMMENDED_COMPLETE = 'recommended_complete'
EVENT_CHALLENGE_START = 'challenge_start'
EVENT_CHALLENGE_COMPLETE = 'challenge_complete'
ACTOR_CHILD = 'child'
ACTOR_TEACHER = 'teacher'
REWARD_MODE_POINTS = 'points'
REWARD_MODE_EXEMPTION = 'exemption'
TICKET_STATUS_ACTIVE = 'active'
TICKET_STATUS_USED = 'used'
TICKET_STATUS_EXPIRED = 'expired'
TICKET_STATUS_REVOKED = 'revoked'

# 일일 학습 세션. reading/session.py 의 viewer 본인확인(verified)과 다른 축이다.
STUDY_STATUS_STUDIED = 'studied'
STUDY_STATUS_EXPLICIT_NOT_STUDIED = 'explicit_not_studied'
STUDY_STATUS_UNKNOWN = 'unknown'
RECORD_VERIFICATION_OBSERVED = 'observed'
RECORD_VERIFICATION_VERIFIED = 'verified'
STUDY_CHANGE_CREATED = 'created'
STUDY_CHANGE_UPDATED = 'updated'
STUDY_CHANGE_DELETED = 'deleted'
NON_STUDY_SOURCE_CENTER = 'center'
NON_STUDY_SOURCE_SYSTEM_HOLIDAY = 'system_holiday'


class ChildReading(db.Model):
    """한 아동이 한 권을 읽은 전체 기간."""
    __tablename__ = 'child_reading'
    __table_args__ = (
        Index(
            'uq_child_reading_one_in_progress',
            'child_id',
            unique=True,
            sqlite_where=text("status = 'in_progress'"),
            postgresql_where=text("status = 'in_progress'"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False, index=True)

    started_on = db.Column(db.Date, nullable=False)
    completed_on = db.Column(db.Date, nullable=True)
    ended_on = db.Column(db.Date, nullable=True)

    status = db.Column(db.String(32), nullable=False, default=STATUS_IN_PROGRESS, index=True)
    program_type = db.Column(db.String(32), nullable=False, default=PROGRAM_TYPE_GENERAL)
    policy_version = db.Column(db.String(32), nullable=False, default=POLICY_VERSION_GENERAL_V2)
    reward_mode = db.Column(db.String(16), nullable=True)
    difficulty_rating = db.Column(db.Integer, nullable=True)
    fun_rating = db.Column(db.Integer, nullable=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    actor_type = db.Column(db.String(16), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    book = db.relationship('Book')
    days = db.relationship('ReadingDay', back_populates='child_reading', lazy='dynamic')

    def __repr__(self):
        return f'<ChildReading {self.id} child={self.child_id} book={self.book_id} {self.status}>'


class ReadingDay(db.Model):
    """실제로 읽은 날짜의 독서기록장 한 칸."""
    __tablename__ = 'reading_day'
    __table_args__ = (
        UniqueConstraint('child_reading_id', 'date', name='uq_reading_day_reading_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    child_reading_id = db.Column(
        db.Integer,
        db.ForeignKey('child_reading.id'),
        nullable=False,
        index=True,
    )
    date = db.Column(db.Date, nullable=False, index=True)
    review_text = db.Column(db.Text, nullable=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    actor_type = db.Column(db.String(16), nullable=False)
    policy_version = db.Column(db.String(32), nullable=False, default=POLICY_VERSION_GENERAL_V2)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    child_reading = db.relationship('ChildReading', back_populates='days')

    def __repr__(self):
        return f'<ReadingDay {self.id} reading={self.child_reading_id} {self.date}>'


class ReadingRewardEvent(db.Model):
    """추천독서 시작/완독 보상 원장. 중복 지급 방지의 정본."""
    __tablename__ = 'reading_reward_event'
    __table_args__ = (
        UniqueConstraint(
            'child_reading_id',
            'event_type',
            name='uq_reading_reward_event_reading_type',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    child_reading_id = db.Column(
        db.Integer,
        db.ForeignKey('child_reading.id'),
        nullable=False,
        index=True,
    )
    event_type = db.Column(db.String(32), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    awarded_on = db.Column(db.Date, nullable=False, index=True)
    policy_version = db.Column(db.String(32), nullable=False, default=POLICY_VERSION_RECOMMENDED_V1)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    child_reading = db.relationship('ChildReading')

    def __repr__(self):
        return (
            f'<ReadingRewardEvent {self.id} reading={self.child_reading_id} '
            f'{self.event_type} {self.points}P>'
        )


class ManualPointPreset(db.Model):
    """자주 쓰는 수동포인트 버튼 설정. 실제 지급 원장이 아니다."""
    __tablename__ = 'manual_point_preset'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), nullable=False, unique=True)
    label = db.Column(db.String(80), nullable=False)
    default_points = db.Column(db.Integer, nullable=False)
    default_reason = db.Column(db.String(80), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_public_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'label': self.label,
            'default_points': self.default_points,
            'default_reason': self.default_reason or '',
            'is_active': bool(self.is_active),
            'sort_order': self.sort_order,
        }

    def __repr__(self):
        return f'<ManualPointPreset {self.key} {self.default_points}>'


class PointSemanticMapping(db.Model):
    """수동 label → category 의미 mapping. 금액/원장/개인정보가 아니다."""
    __tablename__ = 'point_semantic_mapping'

    id = db.Column(db.Integer, primary_key=True)
    normalized_label = db.Column(db.String(255), nullable=False, unique=True)
    category = db.Column(db.String(64), nullable=False)
    subject_key = db.Column(db.String(64), nullable=True)
    item_key = db.Column(db.String(64), nullable=True)
    source = db.Column(db.String(32), nullable=False, default='semantic_llm')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<PointSemanticMapping {self.normalized_label} {self.category}>'


class LearningSubject(db.Model):
    """학습진도 과목 마스터. DailyPoints 과목 컬럼 및 면제권 과목 목록과 별개다."""
    __tablename__ = 'learning_subject'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), nullable=False, unique=True)
    name = db.Column(db.String(80), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<LearningSubject {self.key}>'


class LearningProgressEntry(db.Model):
    """아동+과목+날짜 단위의 학습진도 스냅샷. 다른 날짜는 append-only."""
    __tablename__ = 'learning_progress_entry'
    __table_args__ = (
        UniqueConstraint(
            'child_id',
            'learning_subject_id',
            'recorded_on',
            name='uq_progress_child_subject_date',
        ),
        Index('ix_progress_child_recorded_on', 'child_id', 'recorded_on'),
    )

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False, index=True)
    learning_subject_id = db.Column(
        db.Integer,
        db.ForeignKey('learning_subject.id'),
        nullable=False,
        index=True,
    )
    recorded_on = db.Column(db.Date, nullable=False, index=True)
    textbook_title = db.Column(db.String(120), nullable=False)
    page = db.Column(db.Integer, nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subject = db.relationship('LearningSubject')

    def __repr__(self):
        return (
            f'<LearningProgressEntry {self.id} child={self.child_id} '
            f'{self.recorded_on} p{self.page}>'
        )


class LearningWorkbookPlan(db.Model):
    """학년+과목+교재 공유 학습 계획. 진도 스냅샷(LearningProgressEntry)과 섞지 않는다.

    start_page~end_page 는 교재 물리 구간이다.
    exclusion_ranges_json 은 교사 계획상 영구 제외 페이지다.
    일시적으로 건너뛴 페이지는 여기에 넣지 않으며, 학습 세션에 없다고 완료로 채우지 않는다.
    """
    __tablename__ = 'learning_workbook_plan'
    __table_args__ = (
        UniqueConstraint(
            'grade',
            'learning_subject_id',
            'textbook_title',
            'start_date',
            name='uq_workbook_plan_grade_subject_title_start',
        ),
        CheckConstraint('start_page <= end_page', name='ck_workbook_plan_page_order'),
        CheckConstraint('start_page >= 1', name='ck_workbook_plan_start_page'),
        CheckConstraint(
            'target_completion_date >= start_date',
            name='ck_workbook_plan_date_order',
        ),
        Index('ix_workbook_plan_grade_subject', 'grade', 'learning_subject_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    grade = db.Column(db.Integer, nullable=False, index=True)
    learning_subject_id = db.Column(
        db.Integer,
        db.ForeignKey('learning_subject.id'),
        nullable=False,
        index=True,
    )
    textbook_title = db.Column(db.String(120), nullable=False)
    start_page = db.Column(db.Integer, nullable=False)
    end_page = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    target_completion_date = db.Column(db.Date, nullable=False)
    exclusion_ranges_text = db.Column(db.Text, nullable=True)
    exclusion_ranges_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subject = db.relationship('LearningSubject')

    def __repr__(self):
        return (
            f'<LearningWorkbookPlan {self.id} g{self.grade} '
            f'{self.textbook_title} {self.start_date}>'
        )


class CenterStudyCalendar(db.Model):
    """센터 기본 예정 학습요일. single-center singleton이다."""
    __tablename__ = 'center_study_calendar'

    id = db.Column(db.Integer, primary_key=True)
    singleton_key = db.Column(db.String(16), nullable=False, unique=True, default='default')
    study_weekdays = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<CenterStudyCalendar {self.singleton_key} {self.study_weekdays}>'


class ChildStudyWeekdays(db.Model):
    """아동별 예정 학습요일 override. row가 없으면 센터 기본값을 쓴다."""
    __tablename__ = 'child_study_weekdays'

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(
        db.Integer,
        db.ForeignKey('child.id'),
        nullable=False,
        unique=True,
        index=True,
    )
    study_weekdays = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ChildStudyWeekdays child={self.child_id} {self.study_weekdays}>'


class CenterSubjectStudyWeekdays(db.Model):
    """과목별 예정 학습요일. row가 없으면 이후 계산이 센터 기본 요일을 fallback한다."""
    __tablename__ = 'center_subject_study_weekdays'

    id = db.Column(db.Integer, primary_key=True)
    learning_subject_id = db.Column(
        db.Integer,
        db.ForeignKey('learning_subject.id'),
        nullable=False,
        unique=True,
        index=True,
    )
    study_weekdays = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subject = db.relationship('LearningSubject')

    def __repr__(self):
        return (
            f'<CenterSubjectStudyWeekdays subject={self.learning_subject_id} '
            f'{self.study_weekdays}>'
        )


class CenterNonStudyDay(db.Model):
    """센터 지정 비학습일 및 향후 시스템 공휴일 seed 자리. 출석/미학습 판정이 아니다."""
    __tablename__ = 'center_non_study_day'
    __table_args__ = (
        UniqueConstraint('day', name='uq_center_non_study_day_day'),
        CheckConstraint(
            "source IN ('center', 'system_holiday')",
            name='ck_center_non_study_day_source',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Date, nullable=False, index=True)
    source = db.Column(
        db.String(32),
        nullable=False,
        default=NON_STUDY_SOURCE_CENTER,
        server_default='center',
    )
    label = db.Column(db.String(80), nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<CenterNonStudyDay {self.day} {self.source}>'


class LearningStudySession(db.Model):
    """아동×과목×날짜 학습 세션. LearningProgressEntry 스냅샷과 별 정본이다.

    study_status 와 record_verification 은 독립이다.
    record_verification 은 교사가 실제 교재를 확인했는지이며,
    공용 태블릿 viewer 본인확인(features.reading.session)이 아니다.
    """
    __tablename__ = 'learning_study_session'
    __table_args__ = (
        CheckConstraint(
            "study_status IN ('studied', 'explicit_not_studied', 'unknown')",
            name='ck_learning_study_session_study_status',
        ),
        CheckConstraint(
            "record_verification IN ('observed', 'verified')",
            name='ck_learning_study_session_record_verification',
        ),
        CheckConstraint(
            "("
            "study_status = 'studied' AND start_page IS NOT NULL AND end_page IS NOT NULL "
            "AND start_page >= 1 AND start_page <= end_page"
            ") OR ("
            "study_status IN ('explicit_not_studied', 'unknown') "
            "AND start_page IS NULL AND end_page IS NULL"
            ")",
            name='ck_learning_study_session_pages_match_status',
        ),
        Index(
            'ix_learning_study_session_child_subject_date',
            'child_id',
            'learning_subject_id',
            'study_date',
        ),
        Index(
            'uq_learning_study_session_non_range_day',
            'child_id',
            'learning_subject_id',
            'study_date',
            unique=True,
            sqlite_where=text(
                "study_status IN ('explicit_not_studied', 'unknown')"
            ),
            postgresql_where=text(
                "study_status IN ('explicit_not_studied', 'unknown')"
            ),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False, index=True)
    learning_subject_id = db.Column(
        db.Integer,
        db.ForeignKey('learning_subject.id'),
        nullable=False,
        index=True,
    )
    study_date = db.Column(db.Date, nullable=False, index=True)
    textbook_title = db.Column(db.String(120), nullable=True)
    study_status = db.Column(db.String(32), nullable=False)
    start_page = db.Column(db.Integer, nullable=True)
    end_page = db.Column(db.Integer, nullable=True)
    record_verification = db.Column(
        db.String(16),
        nullable=False,
        default=RECORD_VERIFICATION_OBSERVED,
        server_default='observed',
    )
    recorded_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    actor_type = db.Column(
        db.String(16),
        nullable=False,
        default=ACTOR_TEACHER,
        server_default='teacher',
    )
    input_channel = db.Column(db.String(32), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subject = db.relationship('LearningSubject')
    changes = db.relationship(
        'LearningStudySessionChange',
        back_populates='session',
        lazy='dynamic',
    )

    def __repr__(self):
        return (
            f'<LearningStudySession {self.id} child={self.child_id} '
            f'{self.study_date} {self.study_status}>'
        )


class LearningStudySessionChange(db.Model):
    """학습 세션 수정/삭제 이력. 삭제는 예외 이벤트다. Growth 리포트 스냅샷이 아니다."""
    __tablename__ = 'learning_study_session_change'
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('created', 'updated', 'deleted')",
            name='ck_learning_study_session_change_event',
        ),
        Index('ix_learning_study_session_change_session_id', 'session_id'),
        Index(
            'ix_learning_study_session_change_child_date',
            'child_id',
            'study_date',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer,
        db.ForeignKey('learning_study_session.id', ondelete='SET NULL'),
        nullable=True,
    )
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False)
    learning_subject_id = db.Column(
        db.Integer,
        db.ForeignKey('learning_subject.id'),
        nullable=False,
    )
    study_date = db.Column(db.Date, nullable=False)
    event_type = db.Column(db.String(16), nullable=False)
    before_payload = db.Column(db.JSON, nullable=True)
    after_payload = db.Column(db.JSON, nullable=True)
    change_reason = db.Column(db.Text, nullable=True)
    changed_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    session = db.relationship('LearningStudySession', back_populates='changes')

    def __repr__(self):
        return (
            f'<LearningStudySessionChange {self.id} {self.event_type} '
            f'session={self.session_id}>'
        )


class ExemptionTicket(db.Model):
    """학습 면제권 장부. 종이 면제권의 발급/보유/만료/취소를 기록한다."""
    __tablename__ = 'exemption_ticket'
    __table_args__ = (
        Index(
            'uq_exemption_ticket_one_active',
            'child_id',
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        Index('ix_exemption_ticket_child_status', 'child_id', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False, index=True)
    issued_on = db.Column(db.Date, nullable=False, index=True)
    expires_on = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(16), nullable=False, default=TICKET_STATUS_ACTIVE, index=True)
    policy_version = db.Column(db.String(32), nullable=False)
    issued_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    sources = db.relationship('ExemptionTicketSource', back_populates='ticket')
    usage = db.relationship('ExemptionUsage', back_populates='ticket', uselist=False)

    def __repr__(self):
        return f'<ExemptionTicket {self.id} child={self.child_id} {self.status}>'


class ExemptionTicketSource(db.Model):
    """면제권 발급에 소비된 추천독서 완독. revoked ticket source는 조회에서 미소비로 본다."""
    __tablename__ = 'exemption_ticket_source'
    __table_args__ = (
        UniqueConstraint(
            'exemption_ticket_id',
            'child_reading_id',
            name='uq_exemption_source_ticket_reading',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    exemption_ticket_id = db.Column(
        db.Integer,
        db.ForeignKey('exemption_ticket.id'),
        nullable=False,
        index=True,
    )
    child_reading_id = db.Column(
        db.Integer,
        db.ForeignKey('child_reading.id'),
        nullable=False,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ticket = db.relationship('ExemptionTicket', back_populates='sources')
    child_reading = db.relationship('ChildReading')

    def __repr__(self):
        return (
            f'<ExemptionTicketSource {self.id} ticket={self.exemption_ticket_id} '
            f'reading={self.child_reading_id}>'
        )


class ExemptionUsage(db.Model):
    """면제권 사용 장부. 한 ticket은 한 과목·한 날짜만 면제한다."""
    __tablename__ = 'exemption_usage'
    __table_args__ = (
        UniqueConstraint('exemption_ticket_id', name='uq_exemption_usage_ticket'),
    )

    id = db.Column(db.Integer, primary_key=True)
    exemption_ticket_id = db.Column(
        db.Integer,
        db.ForeignKey('exemption_ticket.id'),
        nullable=False,
        unique=True,
    )
    subject_key = db.Column(db.String(64), nullable=False, index=True)
    subject_name = db.Column(db.String(80), nullable=False)
    used_on = db.Column(db.Date, nullable=False, index=True)
    recorded_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ticket = db.relationship('ExemptionTicket', back_populates='usage')

    def __repr__(self):
        return (
            f'<ExemptionUsage {self.id} ticket={self.exemption_ticket_id} '
            f'{self.subject_key} {self.used_on}>'
        )


GROWTH_AI_STATUS_PENDING = 'PENDING'
GROWTH_AI_STATUS_SUCCESS = 'SUCCESS'
GROWTH_AI_STATUS_FAILED = 'FAILED'


class GrowthAIGeneration(db.Model):
    """교사 Growth AI 해석 1회 요청. Evidence Packet/prompt/원문 오류는 저장하지 않는다."""
    __tablename__ = 'growth_ai_generation'
    __table_args__ = (
        Index(
            'ix_growth_ai_gen_child_hash_runtime',
            'child_id',
            'packet_hash',
            'runtime_signature',
        ),
        Index('ix_growth_ai_gen_user_created', 'requested_by_user_id', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False, index=True)
    requested_by_user_id = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=False, index=True,
    )
    packet_hash = db.Column(db.String(64), nullable=False, index=True)
    runtime_signature = db.Column(db.String(64), nullable=False)
    as_of = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(16), nullable=False)
    parsed_output = db.Column(db.JSON, nullable=True)
    failure_code = db.Column(db.String(64), nullable=True)
    generator_provider = db.Column(db.String(32), nullable=True)
    model = db.Column(db.String(64), nullable=True)
    prompt_version = db.Column(db.String(64), nullable=True)
    output_schema_version = db.Column(db.String(64), nullable=True)
    factual_validator_version = db.Column(db.String(64), nullable=True)
    safety_provider = db.Column(db.String(64), nullable=True)
    safety_guardrail_version = db.Column(db.String(64), nullable=True)
    attempt_count = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    attempts = db.relationship(
        'GrowthAIAttempt', back_populates='generation', lazy='dynamic',
    )

    def __repr__(self):
        return f'<GrowthAIGeneration {self.id} {self.status}>'


class GrowthAIAttempt(db.Model):
    """generation 내부 1회 attempt 진단 로그. 일반 UI/API에 노출하지 않는다."""
    __tablename__ = 'growth_ai_attempt'
    __table_args__ = (
        Index('ix_growth_ai_attempt_generation_id', 'generation_id'),
        Index('ix_growth_ai_attempt_status', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    generation_id = db.Column(
        db.Integer, db.ForeignKey('growth_ai_generation.id'), nullable=False,
    )
    attempt_number = db.Column(db.Integer, nullable=False)
    started_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    generator_provider = db.Column(db.String(32), nullable=True)
    model = db.Column(db.String(64), nullable=True)
    prompt_version = db.Column(db.String(64), nullable=True)
    output_schema_version = db.Column(db.String(64), nullable=True)
    stage = db.Column(db.String(32), nullable=True)
    status = db.Column(db.String(32), nullable=False)
    generated_output = db.Column(db.JSON, nullable=True)
    generated_text = db.Column(db.Text, nullable=True)
    validator_valid = db.Column(db.Boolean, nullable=True)
    validator_codes = db.Column(db.JSON, nullable=True)
    validator_issues = db.Column(db.JSON, nullable=True)
    safety_action = db.Column(db.String(64), nullable=True)
    safety_reason = db.Column(db.String(255), nullable=True)
    safety_categories = db.Column(db.JSON, nullable=True)
    input_tokens = db.Column(db.Integer, nullable=True)
    output_tokens = db.Column(db.Integer, nullable=True)
    total_tokens = db.Column(db.Integer, nullable=True)
    generator_latency_ms = db.Column(db.Integer, nullable=True)
    validator_latency_ms = db.Column(db.Integer, nullable=True)
    safety_latency_ms = db.Column(db.Integer, nullable=True)
    total_latency_ms = db.Column(db.Integer, nullable=True)
    failure_code = db.Column(db.String(64), nullable=True)

    generation = db.relationship('GrowthAIGeneration', back_populates='attempts')

    def __repr__(self):
        return f'<GrowthAIAttempt {self.id} gen={self.generation_id} {self.status}>'


class GrowthAIFeedback(db.Model):
    """교사 Growth AI 해석 피드백. LLM/AWS로 전달하지 않는다."""
    __tablename__ = 'growth_ai_feedback'
    __table_args__ = (
        UniqueConstraint(
            'generation_id', 'user_id', name='uq_growth_ai_feedback_generation_user',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    generation_id = db.Column(
        db.Integer, db.ForeignKey('growth_ai_generation.id'), nullable=False, index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    helpful = db.Column(db.Boolean, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<GrowthAIFeedback {self.id} gen={self.generation_id}>'
