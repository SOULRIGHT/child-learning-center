import os
import json
import shutil
import threading
import schedule
import time
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from sqlalchemy import func # Added for func.date
from sqlalchemy import text

# Firebase Authentication
from firebase_config import (
    initialize_firebase, 
    verify_firebase_token, 
    get_user_role_from_email,
    FIREBASE_CONFIG
)

# 백업 시스템을 위한 import
try:
    import pandas as pd
    import openpyxl
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    BACKUP_EXCEL_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Excel 백업 기능을 위한 패키지가 설치되지 않았습니다: {e}")
    print("   pip install pandas openpyxl 명령어로 설치하세요.")
    BACKUP_EXCEL_AVAILABLE = False

# 환경 변수 로드
load_dotenv()

# Flask 앱 생성
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production-firebase-auth')

# === 🔐 보안 설정 (2025-09-21 추가) ===
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # 30분 세션 타임아웃
app.config['SESSION_COOKIE_HTTPONLY'] = True  # JavaScript로 쿠키 접근 차단
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # 기본 CSRF 공격 방지
app.config['SESSION_COOKIE_SECURE'] = False  # 개발환경: False, 프로덕션: True

# 데이터베이스 설정
if os.environ.get('DATABASE_URL'):
    # Railway 또는 프로덕션 환경
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SESSION_COOKIE_SECURE'] = True  # 프로덕션에서는 HTTPS 강제
else:
    # 개발 환경 - SQLite 사용
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///child_center.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 확장 프로그램 초기화
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = '로그인이 필요합니다.'

# === 🛡️ 고급 보안 헤더 설정 (2025-09-21 확장) ===
@app.after_request
def set_security_headers(response):
    """모든 응답에 강화된 보안 헤더 추가"""
    
    # === 기본 보안 헤더 ===
    response.headers['X-Content-Type-Options'] = 'nosniff'  # MIME 타입 스니핑 방지
    response.headers['X-Frame-Options'] = 'DENY'  # 클릭재킹 방지
    response.headers['X-XSS-Protection'] = '1; mode=block'  # XSS 공격 방지
    
    # === Content Security Policy (CSP) ===
    # 모든 환경에서 동일한 CSP 적용 (로컬=배포 일관성)
    csp_policy = (
        "default-src 'self'; "
        # JavaScript: Firebase SDK + Bootstrap + CDN
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
        "https://www.gstatic.com https://apis.google.com https://www.googleapis.com "
        "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        # 스타일시트: Bootstrap + Google Fonts + Firebase UI + CDN
        "style-src 'self' 'unsafe-inline' "
        "https://cdn.jsdelivr.net https://fonts.googleapis.com https://cdnjs.cloudflare.com "
        "https://www.gstatic.com; "
        # 폰트: Bootstrap Icons + Google Fonts + CDN
        "font-src 'self' data: "
        "https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        # 이미지: 모든 HTTPS 소스 허용
        "img-src 'self' data: https:; "
        # 연결: Firebase 모든 엔드포인트 + CDN
        "connect-src 'self' "
        "https://identitytoolkit.googleapis.com https://securetoken.googleapis.com "
        "https://www.googleapis.com https://firebase.googleapis.com "
        "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        # 보안 정책
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    response.headers['Content-Security-Policy'] = csp_policy
    
    # === HTTP Strict Transport Security (HSTS) ===
    # 프로덕션에서만 HSTS 적용 (HTTPS 필요)
    if os.environ.get('DATABASE_URL'):  # 프로덕션 환경 감지
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
    
    # === Permissions Policy ===
    # 불필요한 브라우저 기능 차단
    permissions_policy = (
        "accelerometer=(), "
        "camera=(), "
        "geolocation=(), "
        "gyroscope=(), "
        "magnetometer=(), "
        "microphone=(), "
        "payment=(), "
        "usb=()"
    )
    response.headers['Permissions-Policy'] = permissions_policy
    
    # === 추가 보안 헤더 ===
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'  # 리퍼러 정책
    response.headers['X-Permitted-Cross-Domain-Policies'] = 'none'  # Flash/PDF 정책 차단
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'  # 팝업 보안
    response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'  # 리소스 공유 제한
    
    return response

# === 수동 포인트 안전 계산 함수 (2024-09-28 추가) ===
def get_manual_points_from_history(record):
    """manual_history에서 안전하게 manual_points 계산 - 데이터 일관성 보장"""
    if not record or not record.manual_history:
        return 0
    
    try:
        history = json.loads(record.manual_history)
        if not isinstance(history, list):
            return 0
        
        total = 0
        for item in history:
            if isinstance(item, dict) and 'points' in item:
                total += item.get('points', 0)
        
        return total
    except Exception as e:
        print(f"❌ manual_history 파싱 오류: {e}")
        return 0

# === ⏰ 세션 영구화 ===
@app.before_request
def make_session_permanent():
    """모든 세션을 영구 세션으로 설정하여 타임아웃 적용"""
    session.permanent = True

# === 🛡️ 브루트포스 공격 방지 시스템 ===
# IP별 로그인 시도 추적 (메모리 기반)
failed_login_attempts = {}
blocked_ips = {}

def get_client_ip():
    """클라이언트 실제 IP 주소 가져오기 (프록시 고려)"""
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
    elif request.environ.get('HTTP_X_REAL_IP'):
        return request.environ['HTTP_X_REAL_IP']
    else:
        return request.remote_addr

def is_ip_blocked(ip_address):
    """IP가 차단되었는지 확인"""
    if ip_address in blocked_ips:
        block_time = blocked_ips[ip_address]
        # 30분(1800초) 후 자동 해제
        if datetime.utcnow() - block_time < timedelta(minutes=30):
            return True
        else:
            # 차단 해제
            del blocked_ips[ip_address]
            if ip_address in failed_login_attempts:
                del failed_login_attempts[ip_address]
    return False

def record_failed_login(ip_address):
    """로그인 실패 기록"""
    current_time = datetime.utcnow()
    
    if ip_address not in failed_login_attempts:
        failed_login_attempts[ip_address] = []
    
    # 최근 1시간 내 실패 기록만 유지
    failed_login_attempts[ip_address] = [
        attempt_time for attempt_time in failed_login_attempts[ip_address]
        if current_time - attempt_time < timedelta(hours=1)
    ]
    
    # 새로운 실패 기록 추가
    failed_login_attempts[ip_address].append(current_time)
    
    # 5회 이상 실패 시 IP 차단
    if len(failed_login_attempts[ip_address]) >= 5:
        blocked_ips[ip_address] = current_time
        print(f"🚨 IP {ip_address} 차단됨 (5회 연속 로그인 실패)")
        return True
    
    return False

def clear_failed_login(ip_address):
    """로그인 성공 시 실패 기록 초기화"""
    if ip_address in failed_login_attempts:
        del failed_login_attempts[ip_address]

# 컨텍스트 프로세서: 모든 템플릿에서 센터 정보 사용 가능
@app.context_processor
def inject_center_info():
    """모든 템플릿에서 센터 정보를 사용할 수 있도록 컨텍스트에 추가"""
    return {
        'center_name': os.environ.get('CENTER_NAME', '지역아동센터'),
        'center_description': os.environ.get('CENTER_DESCRIPTION', '학습관리 시스템'),
        'center_location': os.environ.get('CENTER_LOCATION', '서울시'),
        'theme_color': os.environ.get('THEME_COLOR', '#ff6b35'),
        'branch_indicator_enabled': os.environ.get('BRANCH_INDICATOR_ENABLED', 'true').lower() == 'true'
    }

# 데이터베이스 모델
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=True)  # Firebase 사용 시 nullable
    password_hash = db.Column(db.String(255), nullable=True)  # Firebase 사용 시 nullable
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    login_attempts = db.Column(db.Integer, default=0)
    last_attempt = db.Column(db.DateTime)
    is_locked = db.Column(db.Boolean, default=False)  # 계정 잠금 상태
    locked_until = db.Column(db.DateTime, nullable=True)  # 잠금 해제 시간
    
    # Firebase Auth 전용 필드들
    email = db.Column(db.String(120), unique=True, nullable=True)
    firebase_uid = db.Column(db.String(128), unique=True, nullable=True)
    
    def is_account_locked(self):
        """계정이 잠겨있는지 확인"""
        if not self.is_locked:
            return False
        
        if self.locked_until and datetime.utcnow() > self.locked_until:
            # 잠금 시간이 지났으면 자동 해제
            self.is_locked = False
            self.locked_until = None
            self.login_attempts = 0
            db.session.commit()
            return False
        
        return self.is_locked
    
    def lock_account(self, minutes=30):
        """계정 잠금"""
        self.is_locked = True
        self.locked_until = datetime.utcnow() + timedelta(minutes=minutes)
        self.login_attempts += 1
        db.session.commit()
    
    def unlock_account(self):
        """계정 잠금 해제"""
        self.is_locked = False
        self.locked_until = None
        self.login_attempts = 0
        db.session.commit()

class Child(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 누적 포인트 (전체 과목 합계)
    cumulative_points = db.Column(db.Integer, default=0)
    
    # 관계 설정
    learning_records = db.relationship('LearningRecord', backref='child', lazy=True, cascade='all, delete-orphan')
    notes = db.relationship('ChildNote', backref='child', lazy=True, cascade='all, delete-orphan')
    daily_points = db.relationship('DailyPoints', backref='child_ref', lazy=True, cascade='all, delete-orphan')
    include_in_stats = db.Column(db.Boolean, default=True) # 통계에 포함할지 여부

class LearningRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    
    # 국어
    korean_problems_solved = db.Column(db.Integer, default=0)
    korean_problems_correct = db.Column(db.Integer, default=0)
    korean_score = db.Column(db.Float, default=0)
    korean_last_page = db.Column(db.Integer, default=0)
    
    # 쎈 수학
    math_problems_solved = db.Column(db.Integer, default=0)
    math_problems_correct = db.Column(db.Integer, default=0)
    math_score = db.Column(db.Float, default=0)
    math_last_page = db.Column(db.Integer, default=0)
    
    # 독서
    reading_completed = db.Column(db.Boolean, default=False)
    reading_score = db.Column(db.Float, default=0)
    
    # 총점
    total_score = db.Column(db.Float, default=0)
    
    # 메타데이터
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ChildNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계 설정
    creator = db.relationship('User', backref='notes', lazy=True)

# 새로운 포인트 시스템을 위한 테이블
class DailyPoints(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    
    # 각 과목별 포인트 (200 또는 100)
    korean_points = db.Column(db.Integer, default=0)
    math_points = db.Column(db.Integer, default=0)
    ssen_points = db.Column(db.Integer, default=0)
    reading_points = db.Column(db.Integer, default=0)
    
    # 새 과목들 (2025-09-17 추가)
    piano_points = db.Column(db.Integer, default=0)        # 피아노
    english_points = db.Column(db.Integer, default=0)      # 영어
    advanced_math_points = db.Column(db.Integer, default=0) # 고학년수학
    writing_points = db.Column(db.Integer, default=0)      # 쓰기
    
    # 수동 포인트 관리
    manual_points = db.Column(db.Integer, default=0)       # 수동 추가/차감 합계
    manual_history = db.Column(db.Text, default='[]')     # JSON 형태 히스토리
    
    # 총 포인트
    total_points = db.Column(db.Integer, default=0)
    
    # 메타데이터
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계 설정
    child = db.relationship('Child', lazy=True)
    creator = db.relationship('User', backref='points_records', lazy=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 점수 계산 함수
def calculate_score(correct, total):
    if total == 0:
        return 0
    return (correct / total) * 100

# 권한 확인 함수
def check_permission(required_roles=None, excluded_roles=None):
    """권한 확인 함수"""
    if not current_user.is_authenticated:
        return False
    
    # 제외된 역할 확인
    if excluded_roles and current_user.role in excluded_roles:
        return False
    
    # 필요한 역할 확인
    if required_roles and current_user.role not in required_roles:
        return False
    
    return True

# 사용 예시:
# @app.route('/admin')
# @login_required
# def admin_page():
#     if not check_permission(required_roles=['센터장', '개발자']):
#         abort(403)
#     return render_template('admin.html')

# 데이터베이스 초기화 함수
def init_db():
    """⚠️ 주의: 이 함수는 개발/테스트 환경에서만 사용하세요!"""
    print("경고: init_db() 함수가 호출되었습니다!")
    print("현재 데이터베이스의 모든 데이터가 삭제됩니다!")
    
    # 사용자 확인 (안전장치)
    confirm = input("정말로 모든 데이터를 삭제하시겠습니까? (yes/no): ")
    if confirm.lower() != 'yes':
        print("데이터 삭제가 취소되었습니다.")
        return
    
    with app.app_context():
        # 기존 테이블 삭제 후 재생성 (스키마 변경 반영)
        db.drop_all()
        db.create_all()
        
        # 기본 사용자 계정 생성 (환경변수에서 읽어옴)
        import os
        from dotenv import load_dotenv
        
        # 환경변수 로드
        load_dotenv()
        
        # 환경변수에서 사용자 정보 읽기
        usernames = os.environ.get('DEFAULT_USERS', 'developer,center_head,care_teacher').split(',')
        passwords = os.environ.get('DEFAULT_PASSWORDS', 'dev123,center123!,care123!').split(',')
        roles = os.environ.get('DEFAULT_USER_ROLES', '개발자,센터장,돌봄선생님').split(',')
        
        # 사용자 데이터 생성
        default_users = []
        for i, username in enumerate(usernames):
            if i < len(passwords) and i < len(roles):
                default_users.append({
                    'username': username.strip(),
                    'name': roles[i].strip(),
                    'role': roles[i].strip(),
                    'password': passwords[i].strip()
                })
        
        # 환경변수에서 읽을 수 없는 경우 기본값 사용
        if not default_users:
            print("⚠️ 환경변수에서 사용자 데이터를 읽을 수 없습니다. 기본 데이터를 사용합니다.")
        default_users = [
            {'username': 'developer', 'name': '개발자', 'role': '개발자', 'password': 'dev123'},
            {'username': 'center_head', 'name': '센터장', 'role': '센터장', 'password': 'center123!'},
                {'username': 'care_teacher', 'name': '돌봄선생님', 'role': '돌봄선생님', 'password': 'care123!'}
        ]
        
        for user_data in default_users:
                password_hash = generate_password_hash(user_data['password'])
                user = User(
                    username=user_data['username'],
                    password_hash=password_hash,
                    name=user_data['name'],
                    role=user_data['role']
                )
                db.session.add(user)
        
        # 테스트용 아동 데이터 추가 (환경변수에서 읽어옴)
        test_children_data = []
        
        # 환경변수에서 테스트 아동 데이터 읽기
        test_children_count = int(os.environ.get('TEST_CHILDREN_COUNT', 4))
        
        # 1학년부터 시작해서 테스트 아동 생성
        for i in range(test_children_count):
            grade = (i % 4) + 1  # 1-4학년 순환
            env_key = f'CHILDREN_GRADE{grade}'
            children_names = os.environ.get(env_key, '').split(',')
            
            if children_names and len(children_names) > 0:
                name = children_names[0].strip()  # 첫 번째 아동 사용
                include_in_stats = (i < test_children_count - 1)  # 마지막 아동만 통계 제외
                
                test_children_data.append(Child(
                    name=name,
                    grade=grade,
                    include_in_stats=include_in_stats
                ))
        
        # 환경변수에서 읽을 수 없는 경우 기본값 사용
        if not test_children_data:
            print("⚠️ 환경변수에서 테스트 아동 데이터를 읽을 수 없습니다. 기본 데이터를 사용합니다.")
            test_children_data = [
            Child(name='김철수', grade=3, include_in_stats=True),
            Child(name='박영희', grade=3, include_in_stats=True),
            Child(name='이민수', grade=4, include_in_stats=True),
            Child(name='최지영', grade=4, include_in_stats=False),  # 통계 제외 예시
        ]
        
        test_children = test_children_data
        
        for child in test_children:
            db.session.add(child)
        
        db.session.commit()  # 아동 먼저 저장
        
        # 테스트용 점수 데이터 추가
        from datetime import date, timedelta
        today = date.today()
        
        test_records = [
            # 김철수 (3학년) - 최근 3일 기록
            LearningRecord(
                child_id=1, date=today,
                korean_problems_solved=20, korean_problems_correct=18, korean_last_page=15,
                math_problems_solved=15, math_problems_correct=12, math_last_page=22,
                reading_completed=True, reading_score=200,
                korean_score=90, math_score=80, total_score=370, created_by=1
            ),
            LearningRecord(
                child_id=1, date=today - timedelta(days=1),
                korean_problems_solved=18, korean_problems_correct=15, korean_last_page=14,
                math_problems_solved=12, math_problems_correct=10, math_last_page=21,
                reading_completed=True, reading_score=100,
                korean_score=83.3, math_score=83.3, total_score=266.6, created_by=1
            ),
            
            # 박영희 (3학년) - 같은 페이지 비교용
            LearningRecord(
                child_id=2, date=today,
                korean_problems_solved=20, korean_problems_correct=19, korean_last_page=15,
                math_problems_solved=15, math_problems_correct=14, math_last_page=22,
                reading_completed=True, reading_score=200,
                korean_score=95, math_score=93.3, total_score=388.3, created_by=1
            ),
            LearningRecord(
                child_id=2, date=today - timedelta(days=2),
                korean_problems_solved=16, korean_problems_correct=14, korean_last_page=13,
                math_problems_solved=10, math_problems_correct=9, math_last_page=20,
                reading_completed=False, reading_score=100,
                korean_score=87.5, math_score=90, total_score=277.5, created_by=1
            ),
            
            # 이민수 (4학년) - 다른 학년
            LearningRecord(
                child_id=3, date=today,
                korean_problems_solved=25, korean_problems_correct=20, korean_last_page=18,
                math_problems_solved=20, math_problems_correct=16, math_last_page=25,
                reading_completed=True, reading_score=200,
                korean_score=80, math_score=80, total_score=360, created_by=1
            ),
        ]
        
        for record in test_records:
            db.session.add(record)
        
        # DailyPoints 테스트 데이터 추가 (시각화용)
        from datetime import date, timedelta
        today = date.today()
        
        # 최근 28일간의 포인트 데이터 생성
        for i in range(28):
            current_date = today - timedelta(days=i)
            
            # 각 아동별로 랜덤한 포인트 생성
            for child_id in [1, 2, 3]:  # 김철수, 박영희, 이민수
                # 랜덤한 포인트 생성 (200, 100, 0 중에서)
                import random
                korean_points = random.choice([0, 100, 200])
                math_points = random.choice([0, 100, 200])
                ssen_points = random.choice([0, 100, 200])
                reading_points = random.choice([0, 100, 200])
                total_points = korean_points + math_points + ssen_points + reading_points + piano_points + english_points + advanced_math_points + writing_points + manual_points
                
                # 일부 날짜는 기록 없음 (더 현실적인 데이터)
                if random.random() > 0.3:  # 70% 확률로 기록 생성
                    daily_point = DailyPoints(
                        child_id=child_id,
                        date=current_date,
                        korean_points=korean_points,
                        math_points=math_points,
                        ssen_points=ssen_points,
                        reading_points=reading_points,
                piano_points=piano_points,
                english_points=english_points,
                advanced_math_points=advanced_math_points,
                writing_points=writing_points,
                manual_points=manual_points,
                        total_points=total_points,
                        created_by=1
                    )
                    db.session.add(daily_point)
        
        db.session.commit()
        print("데이터베이스가 초기화되었습니다. (테스트 데이터 + 점수 기록 포함)")

# 라우트
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# === 완전 Firebase Auth 시스템 ===
@app.route('/login', methods=['GET', 'POST'])
def login():
    """완전 Firebase Auth 기반 로그인"""
    if request.method == 'POST':
        # === 🛡️ 브루트포스 공격 방지 체크 ===
        client_ip = get_client_ip()
        
        if is_ip_blocked(client_ip):
            flash('⚠️ 보안상 로그인이 일시적으로 제한되었습니다. 30분 후 다시 시도해주세요.', 'error')
            return render_template('login.html', firebase_config=FIREBASE_CONFIG)
        
        # Firebase 토큰 검증
        token = request.json.get('token') if request.is_json else request.form.get('token')
        
        if not token:
            flash('로그인 토큰이 없습니다.', 'error')
            return render_template('login.html', firebase_config=FIREBASE_CONFIG)
        
        # Firebase 토큰 검증
        decoded_token = verify_firebase_token(token)
        
        if decoded_token:
            # 사용자 정보 추출
            firebase_uid = decoded_token['uid']
            email = decoded_token['email']
            name = decoded_token.get('name', email.split('@')[0])
            
            # Firebase 사용자로 로그인 처리 (firebase_uid 또는 email로 찾기)
            user = User.query.filter(
                (User.firebase_uid == firebase_uid) | (User.email == email)
            ).first()
            
            if not user:
                # 새 Firebase 사용자 생성
                user = User(
                    firebase_uid=firebase_uid,
                    email=email,
                    name=name,
                    role=get_user_role_from_email(email),
                    username=email.split('@')[0],  # 호환성을 위해
                    password_hash=''  # Firebase 사용자는 비밀번호 없음
                )
                db.session.add(user)
                db.session.commit()
                print(f"✅ 새 Firebase 사용자 생성: {email}")
            elif not user.firebase_uid:
                # 기존 사용자에 firebase_uid 추가
                user.firebase_uid = firebase_uid
                db.session.commit()
                print(f"✅ 기존 사용자 Firebase UID 업데이트: {email}")
            
            # Firebase 사용자로 로그인
                login_user(user)
            
            # === 🛡️ 로그인 성공 시 실패 기록 초기화 ===
            clear_failed_login(client_ip)
            
            flash(f'{user.name}님, Firebase 인증으로 로그인되었습니다!', 'success')
            
            if request.is_json:
                return jsonify({'success': True, 'redirect': url_for('dashboard')})
            else:
                return redirect(url_for('dashboard'))
        else:
            # === 🛡️ 로그인 실패 시 실패 기록 ===
            is_now_blocked = record_failed_login(client_ip)
            if is_now_blocked:
                flash('⚠️ 연속된 로그인 실패로 인해 30분간 로그인이 제한됩니다.', 'error')
            else:
                flash('Firebase 인증에 실패했습니다.', 'error')
            
            if request.is_json:
                return jsonify({'success': False, 'error': 'Invalid Firebase token'})
    
    # Firebase 설정 정보를 템플릿에 전달
    return render_template('login.html', firebase_config=FIREBASE_CONFIG)

@app.route('/firebase-login', methods=['POST'])
def firebase_login():
    """Firebase Auth API 엔드포인트"""
    try:
        # === 🛡️ 브루트포스 공격 방지 체크 ===
        client_ip = get_client_ip()
        
        if is_ip_blocked(client_ip):
            return jsonify({'success': False, 'error': '보안상 로그인이 일시적으로 제한되었습니다. 30분 후 다시 시도해주세요.'})
        
        data = request.get_json()
        token = data.get('token')
        
        if not token:
            return jsonify({'success': False, 'error': 'Token is required'})
        
        # Firebase 토큰 검증
        decoded_token = verify_firebase_token(token)
        
        if decoded_token:
            # 사용자 정보 추출
            firebase_uid = decoded_token['uid']
            email = decoded_token['email']
            name = decoded_token.get('name', email.split('@')[0])
            
            # Firebase 사용자로 로그인 처리 (firebase_uid 또는 email로 찾기)
            user = User.query.filter(
                (User.firebase_uid == firebase_uid) | (User.email == email)
            ).first()
            
            if not user:
                # 새 Firebase 사용자 생성
                user = User(
                    firebase_uid=firebase_uid,
                    email=email,
                    name=name,
                    role=get_user_role_from_email(email),
                    username=email.split('@')[0],  # 호환성을 위해
                    password_hash=''  # Firebase 사용자는 비밀번호 없음
                )
                db.session.add(user)
                db.session.commit()
                print(f"✅ 새 Firebase 사용자 생성: {email}")
            elif not user.firebase_uid:
                # 기존 사용자에 firebase_uid 추가
                user.firebase_uid = firebase_uid
                db.session.commit()
                print(f"✅ 기존 사용자 Firebase UID 업데이트: {email}")
            
            # Firebase 사용자로 로그인
            login_user(user)
            
            # === 🛡️ 로그인 성공 시 실패 기록 초기화 ===
            clear_failed_login(client_ip)
            
            return jsonify({
                'success': True, 
                'redirect': url_for('dashboard'),
                'user': {
                    'id': user.id,
                    'name': user.name,
                    'email': user.email,
                    'role': user.role,
                    'firebase_uid': user.firebase_uid
                }
            })
        else:
            # === 🛡️ 로그인 실패 시 실패 기록 ===
            record_failed_login(client_ip)
            return jsonify({'success': False, 'error': 'Invalid Firebase token'})
    
    except Exception as e:
        print(f"Firebase login error: {e}")
        # === 🛡️ 오류 시에도 실패 기록 ===
        client_ip = get_client_ip()
        record_failed_login(client_ip)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    today = datetime.now(timezone.utc).date()
    
    # ====== [포인트 시스템 통계 계산] ======
    # 오늘 포인트를 입력한 아동 수
    today_points_children = db.session.query(DailyPoints.child_id).filter_by(date=today).distinct().count()
    
    # 전체 등록 아동 수
    total_children = Child.query.count()
    
    # 이번 주 평균 포인트 계산
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    weekly_points = DailyPoints.query.filter(
        DailyPoints.date >= week_start,
        DailyPoints.date <= week_end
    ).all()
    
    if weekly_points:
        total_weekly_points = sum(record.total_points for record in weekly_points)
        weekly_avg_points = int(round(total_weekly_points / len(weekly_points), 0))
        weekly_points_count = len(weekly_points)
    else:
        weekly_avg_points = 0
        total_weekly_points = 0
        weekly_points_count = 0
    
    # 이번 주 포인트 참여율 계산
    weekly_participants = db.session.query(DailyPoints.child_id).filter(
        DailyPoints.date >= week_start,
        DailyPoints.date <= week_end
    ).distinct().count()
    
    if total_children > 0:
        participation_rate = int(round((weekly_participants / total_children) * 100, 0))
    else:
        participation_rate = 0
    
    # 최근 포인트 기록 (최근 10개)
    recent_records = db.session.query(DailyPoints, Child).join(Child).order_by(DailyPoints.created_at.desc()).limit(10).all()
    
    # ====== [과목별 주간 평균 포인트 계산] ======
    weekly_korean_avg = 0
    weekly_math_avg = 0
    weekly_ssen_avg = 0
    weekly_reading_avg = 0
    weekly_total_points = 0
    
    if weekly_points:
        # 과목별 평균 계산
        korean_points = [record.korean_points for record in weekly_points if record.korean_points > 0]
        math_points = [record.math_points for record in weekly_points if record.math_points > 0]
        ssen_points = [record.ssen_points for record in weekly_points if record.ssen_points > 0]
        reading_points = [record.reading_points for record in weekly_points if record.reading_points > 0]
        
        weekly_korean_avg = round(sum(korean_points) / len(korean_points), 0) if korean_points else 0
        weekly_math_avg = round(sum(math_points) / len(math_points), 0) if math_points else 0
        weekly_ssen_avg = round(sum(ssen_points) / len(ssen_points), 0) if ssen_points else 0
        weekly_reading_avg = round(sum(reading_points) / len(reading_points), 0) if reading_points else 0
        
        # 주간 총 포인트
        weekly_total_points = sum(record.total_points for record in weekly_points)
    
    # ====== [알림 시스템 활성화] ======
    notifications = get_user_notifications(current_user.id, limit=5)
    
    return render_template('dashboard.html', 
                         today_points_children=today_points_children,
                         total_children=total_children,
                         weekly_avg_points=weekly_avg_points,
                         participation_rate=participation_rate,
                         recent_records=recent_records,
                         notifications=notifications,
                         weekly_korean_avg=weekly_korean_avg,
                         weekly_math_avg=weekly_math_avg,
                         weekly_ssen_avg=weekly_ssen_avg,
                         weekly_reading_avg=weekly_reading_avg,
                         weekly_total_points=weekly_total_points,
                         weekly_points_count=weekly_points_count)

# 아동 관리 라우트
@app.route('/children')
@login_required
def children_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    grade_filter = request.args.get('grade', '', type=str)
    
    query = Child.query
    
    # 검색 필터
    if search:
        query = query.filter(Child.name.contains(search))
    
    # 학년 필터
    if grade_filter:
        query = query.filter(Child.grade == int(grade_filter))
    
    # 페이지네이션
    children = query.order_by(Child.name).paginate(
        page=page, per_page=10, error_out=False
    )
    
    # 학년 목록 (필터용)
    grades = db.session.query(Child.grade).distinct().order_by(Child.grade).all()
    grade_list = [g[0] for g in grades]
    
    return render_template('children/list.html', 
                         children=children, 
                         search=search,
                         grade_filter=grade_filter,
                         grade_list=grade_list)

@app.route('/children/add', methods=['GET', 'POST'])
@login_required
def add_child():
    if request.method == 'POST':
        name = request.form['name'].strip()
        grade = request.form['grade']
        
        # 유효성 검사
        if not name:
            flash('이름을 입력해주세요.', 'error')
            return render_template('children/form.html')
        
        if not grade or int(grade) < 1 or int(grade) > 6:
            flash('학년을 올바르게 선택해주세요. (1-6학년)', 'error')
            return render_template('children/form.html')
        
        # 중복 이름 확인
        existing_child = Child.query.filter_by(name=name).first()
        if existing_child:
            flash('이미 등록된 이름입니다. 다른 이름을 사용해주세요.', 'error')
            return render_template('children/form.html')
        
        # 아동 등록
        child = Child(name=name, grade=int(grade))
        db.session.add(child)
        db.session.commit()
        
        flash(f'{name} 아동이 성공적으로 등록되었습니다.', 'success')
        return redirect(url_for('children_list'))
    
    return render_template('children/form.html')

@app.route('/children/<int:child_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_child(child_id):
    child = Child.query.get_or_404(child_id)
    
    if request.method == 'POST':
        name = request.form['name'].strip()
        grade = request.form['grade']
        
        # 유효성 검사
        if not name:
            flash('이름을 입력해주세요.', 'error')
            return render_template('children/form.html', child=child)
        
        if not grade or int(grade) < 1 or int(grade) > 6:
            flash('학년을 올바르게 선택해주세요. (1-6학년)', 'error')
            return render_template('children/form.html', child=child)
        
        # 중복 이름 확인 (자기 자신 제외)
        existing_child = Child.query.filter(Child.name == name, Child.id != child_id).first()
        if existing_child:
            flash('이미 등록된 이름입니다. 다른 이름을 사용해주세요.', 'error')
            return render_template('children/form.html', child=child)
        
        # 아동 정보 업데이트
        child.name = name
        child.grade = int(grade)
        db.session.commit()
        
        flash(f'{name} 아동 정보가 성공적으로 수정되었습니다.', 'success')
        return redirect(url_for('children_list'))
    
    return render_template('children/form.html', child=child)

@app.route('/children/<int:child_id>/delete', methods=['POST'])
@login_required
def delete_child(child_id):
    child = Child.query.get_or_404(child_id)
    child_name = child.name
    
    # 권한 확인 (센터장과 돌봄선생님만 삭제 가능)
    if current_user.role not in ['개발자']:
        flash('아동 삭제 권한이 없습니다.', 'error')
        return redirect(url_for('children_list'))
    
    try:
        # 관련 기록들도 함께 삭제됨 (cascade 설정)
        db.session.delete(child)
        db.session.commit()
        
        flash(f'{child_name} 아동과 관련 기록이 모두 삭제되었습니다.', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"🐛 DEBUG: 아동 삭제 오류 - {str(e)}")
        print(f"🐛 DEBUG: child_id: {child_id}, child_name: {child_name}")
        flash(f'삭제 중 오류가 발생했습니다: {str(e)}', 'error')
    
    return redirect(url_for('children_list'))

@app.route('/children/<int:child_id>')
@login_required
def child_detail(child_id):
    child = Child.query.get_or_404(child_id)
    
    # 페이지네이션 파라미터
    page = request.args.get('page', 1, type=int)
    per_page = 20  # 한 페이지당 20개 기록
    
    # 새로운 포인트 시스템 기록들 (중복 제거) - 페이지네이션 적용
    from sqlalchemy import text
    
    # 전체 기록 수 계산
    count_result = db.session.execute(text("""
        SELECT COUNT(DISTINCT date) as total_count
        FROM daily_points 
        WHERE child_id = :child_id
    """), {"child_id": child_id})
    total_records = count_result.fetchone()[0]
    
    # 페이지네이션 계산
    offset = (page - 1) * per_page
    total_pages = (total_records + per_page - 1) // per_page
    
    # 페이지별 기록 조회
    result = db.session.execute(text("""
        SELECT id, date, korean_points, math_points, ssen_points, reading_points, total_points, created_at
        FROM daily_points 
        WHERE child_id = :child_id 
        AND id IN (
            SELECT MAX(id) 
            FROM daily_points 
            WHERE child_id = :child_id 
            GROUP BY date
        )
        ORDER BY date DESC
        LIMIT :per_page OFFSET :offset
    """), {"child_id": child_id, "per_page": per_page, "offset": offset})
    
    # DailyPoints 객체로 변환
    recent_records = []
    for row in result:
        # 날짜 타입 변환
        date_value = row[1]
        if isinstance(date_value, str):
            from datetime import datetime
            date_value = datetime.strptime(date_value, '%Y-%m-%d').date()
        
        created_at_value = row[7]
        if isinstance(created_at_value, str):
            from datetime import datetime
            created_at_value = datetime.strptime(created_at_value, '%Y-%m-%d %H:%M:%S.%f')
        
        point_record = DailyPoints(
            id=row[0],
            date=date_value,
            korean_points=row[2],
            math_points=row[3],
            ssen_points=row[4],
            reading_points=row[5],
            total_points=row[6]
        )
        # created_at을 별도로 설정 (템플릿에서 사용할 수 있도록)
        point_record.created_at = created_at_value
        recent_records.append(point_record)
    
    # 최근 특이사항들
    recent_notes = ChildNote.query.filter_by(child_id=child_id)\
                                  .order_by(ChildNote.created_at.desc())\
                                  .limit(5).all()
    
    # 통계 계산 (새로운 포인트 시스템 기반)
    if recent_records:
        # 최근 5개 기록의 평균
        recent_avg = sum(record.total_points for record in recent_records[:5]) / min(len(recent_records), 5)
        
        # 가장 최근 기록
        latest_record = recent_records[0] if recent_records else None
    else:
        recent_avg = 0
        latest_record = None
    
    # 총 누적 포인트 (실제 전체 누적)
    total_points = child.cumulative_points
    
    return render_template('children/detail.html', 
                         child=child,
                         recent_records=recent_records,
                         recent_notes=recent_notes,
                         recent_avg=recent_avg,
                         latest_record=latest_record,
                         total_points=total_points,
                         # 페이지네이션 정보
                         current_page=page,
                         total_pages=total_pages,
                         total_records=total_records,
                         per_page=per_page)

# ===== 특이사항 관리 라우트 =====

@app.route('/children/<int:child_id>/notes', methods=['POST'])
@login_required
def add_child_note(child_id):
    """아동 특이사항 추가"""
    child = Child.query.get_or_404(child_id)
    
    note_text = request.form.get('note', '').strip()
    if not note_text:
        flash('특이사항을 입력해주세요.', 'error')
        return redirect(url_for('child_detail', child_id=child_id))
    
    try:
        new_note = ChildNote(
            child_id=child_id,
            note=note_text,
            created_by=current_user.id
        )
        
        db.session.add(new_note)
        db.session.commit()
        
        flash(f'✅ {child.name} 아동의 특이사항이 추가되었습니다.', 'success')
        
        # 특이사항 추가 알림 생성
        print(f"DEBUG: 특이사항 추가 알림 생성 시도 - {child.name}")
        notification = create_notification(
            title=f'📝 {child.name} 특이사항 추가',
            message=f'{current_user.name}님이 {child.name} 아동의 특이사항을 추가했습니다.',
            notification_type='warning',
            child_id=child.id,
            target_role=None,  # 모든 사용자에게 표시
            priority=2,
            auto_expire=True,
            expire_days=3
        )
        print(f"DEBUG: 알림 생성 결과 - {notification}")
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ 특이사항 추가 중 오류가 발생했습니다: {str(e)}', 'error')
    
    return redirect(url_for('child_detail', child_id=child_id))

@app.route('/children/<int:child_id>/notes/<int:note_id>/edit', methods=['POST'])
@login_required  
def edit_child_note(child_id, note_id):
    """아동 특이사항 수정"""
    child = Child.query.get_or_404(child_id)
    note = ChildNote.query.get_or_404(note_id)
    
    # 권한 확인 (작성자 또는 개발자만 수정 가능)
    # 권한 체크 제거 - 모든 사용자가 수정 가능
    
    note_text = request.form.get('note', '').strip()
    if not note_text:
        flash('특이사항을 입력해주세요.', 'error')
        return redirect(url_for('child_detail', child_id=child_id))
    
    try:
        old_note = note.note
        note.note = note_text
        note.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash(f'✅ {child.name} 아동의 특이사항이 수정되었습니다.', 'success')
        
        # 특이사항 수정 알림 생성
        print(f"DEBUG: 특이사항 수정 알림 생성 시도 - {child.name}")
        notification = create_notification(
                title=f'📝 {child.name} 특이사항 수정',
                message=f'{current_user.name}님이 {child.name} 아동의 특이사항을 수정했습니다.',
            notification_type='warning',
                child_id=child.id,
            target_role=None,  # 모든 사용자에게 표시
            priority=2,
            auto_expire=True,
            expire_days=3
        )
        print(f"DEBUG: 수정 알림 생성 결과 - {notification}")
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ 특이사항 수정 중 오류가 발생했습니다: {str(e)}', 'error')
    
    return redirect(url_for('child_detail', child_id=child_id))

@app.route('/children/<int:child_id>/notes/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_child_note(child_id, note_id):
    """아동 특이사항 삭제"""
    child = Child.query.get_or_404(child_id)
    note = ChildNote.query.get_or_404(note_id)
    
    # 권한 확인 (작성자 또는 개발자만 삭제 가능)
    # 권한 체크 제거 - 모든 사용자가 삭제 가능
    
    try:
        db.session.delete(note)
        db.session.commit()
        
        flash(f'✅ {child.name} 아동의 특이사항이 삭제되었습니다.', 'success')
        
        # 특이사항 삭제 알림 생성
        create_notification(
            title=f'🗑️ {child.name} 특이사항 삭제',
            message=f'{current_user.name}님이 {child.name} 아동의 특이사항을 삭제했습니다.',
            notification_type='warning',
            child_id=child.id,
            target_role=None,  # 모든 사용자에게 표시
            priority=2,
            auto_expire=True,
            expire_days=3
        )
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ 특이사항 삭제 중 오류가 발생했습니다: {str(e)}', 'error')
    
    return redirect(url_for('child_detail', child_id=child_id))

@app.route('/children/<int:child_id>/notes/all')
@login_required
def view_all_child_notes(child_id):
    """아동 특이사항 전체 보기"""
    child = Child.query.get_or_404(child_id)
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    notes = ChildNote.query.filter_by(child_id=child_id)\
                          .order_by(ChildNote.created_at.desc())\
                          .paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('children/notes.html', child=child, notes=notes)

# 점수 입력 라우트
@app.route('/scores')
@login_required
def scores_list():
    # 최근 입력된 점수들
    recent_records = db.session.query(LearningRecord, Child)\
                              .join(Child)\
                              .order_by(LearningRecord.date.desc())\
                              .limit(20).all()
    
    return render_template('scores/list.html', recent_records=recent_records)

@app.route('/scores/add', methods=['GET', 'POST'])
@login_required
def add_score():
    # URL 파라미터에서 child_id 가져오기
    preselected_child_id = request.args.get('child_id', type=int)
    
    if request.method == 'POST':
        try:
            # 폼 데이터 받기
            child_id = request.form['child_id']
            date_str = request.form['date']
            
            # 국어 데이터
            korean_problems_solved = int(request.form.get('korean_problems_solved', 0))
            korean_problems_correct = int(request.form.get('korean_problems_correct', 0))
            korean_last_page = int(request.form.get('korean_last_page', 0))
            
            # 수학 데이터  
            math_problems_solved = int(request.form.get('math_problems_correct', 0))
            math_problems_correct = int(request.form.get('math_problems_correct', 0))
            math_last_page = int(request.form.get('math_last_page', 0))
            
            # 독서 데이터
            reading_completed = 'reading_completed' in request.form
            reading_score = float(request.form.get('reading_score', 0))
            
            # 유효성 검사
            if not child_id:
                flash('아동을 선택해주세요.', 'error')
                return render_template('scores/form.html', children=Child.query.all())
            
            if not date_str:
                flash('날짜를 입력해주세요.', 'error')
                return render_template('scores/form.html', children=Child.query.all())
            
            # 날짜 변환
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # 이미 해당 날짜에 기록이 있는지 확인
            existing_record = LearningRecord.query.filter_by(
                child_id=child_id, 
                date=date
            ).first()
            
            if existing_record:
                flash('해당 날짜에 이미 기록이 있습니다. 수정하시겠습니까?', 'error')
                return redirect(url_for('edit_score', record_id=existing_record.id))
            
            # 점수 계산
            korean_score = calculate_score(korean_problems_correct, korean_problems_solved) if korean_problems_solved > 0 else 0
            math_score = calculate_score(math_problems_correct, math_problems_solved) if math_problems_solved > 0 else 0
            
            # 총점 계산 (국어 + 수학 + 독서)
            total_score = korean_score + math_score + reading_score
            
            # 새 기록 생성
            new_record = LearningRecord(
                child_id=child_id,
                date=date,
                korean_problems_solved=korean_problems_solved,
                korean_problems_correct=korean_problems_correct,
                korean_score=korean_score,
                korean_last_page=korean_last_page,
                math_problems_solved=math_problems_solved,
                math_problems_correct=math_problems_correct,
                math_score=math_score,
                math_last_page=math_last_page,
                reading_completed=reading_completed,
                reading_score=reading_score,
                total_score=total_score,
                created_by=current_user.id
            )
            
            db.session.add(new_record)
            db.session.commit()
            
            child = Child.query.get(child_id)
            flash(f'{child.name} 아동의 {date_str} 학습 기록이 저장되었습니다.', 'success')
            return redirect(url_for('child_detail', child_id=child_id))
            
        except ValueError as e:
            flash('입력값을 다시 확인해주세요.', 'error')
            return render_template('scores/form.html', children=Child.query.all())
        except Exception as e:
            db.session.rollback()
            flash('저장 중 오류가 발생했습니다. 다시 시도해주세요.', 'error')
            return render_template('scores/form.html', children=Child.query.all())
    
    # GET 요청 시 폼 표시
    children = Child.query.order_by(Child.name).all()
    return render_template('scores/form.html', children=children, preselected_child_id=preselected_child_id)

@app.route('/scores/<int:record_id>/edit', methods=['GET', 'POST'])
@login_required  
def edit_score(record_id):
    record = LearningRecord.query.get_or_404(record_id)
    
    if request.method == 'POST':
        try:
            # 폼 데이터 받기
            date_str = request.form['date']
            
            # 국어 데이터
            korean_problems_solved = int(request.form.get('korean_problems_correct', 0))
            korean_problems_correct = int(request.form.get('korean_problems_correct', 0))
            korean_last_page = int(request.form.get('korean_last_page', 0))
            
            # 수학 데이터
            math_problems_solved = int(request.form.get('math_problems_correct', 0))
            math_problems_correct = int(request.form.get('math_problems_correct', 0))
            math_last_page = int(request.form.get('math_last_page', 0))
            
            # 독서 데이터
            reading_completed = 'reading_completed' in request.form
            reading_score = float(request.form.get('reading_score', 0))
            
            # 날짜 변환
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # 점수 계산
            korean_score = calculate_score(korean_problems_correct, korean_problems_solved) if korean_problems_solved > 0 else 0
            math_score = calculate_score(math_problems_correct, math_problems_solved) if math_problems_solved > 0 else 0
            
            # 총점 계산
            total_score = korean_score + math_score + reading_score
            
            # 기록 업데이트
            record.date = date
            record.korean_problems_solved = korean_problems_solved
            record.korean_problems_correct = korean_problems_correct
            record.korean_score = korean_score
            record.korean_last_page = korean_last_page
            record.math_problems_solved = math_problems_solved
            record.math_problems_correct = math_problems_correct
            record.math_score = math_score
            record.math_last_page = math_last_page
            record.reading_completed = reading_completed
            record.reading_score = reading_score
            record.total_score = total_score
            record.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash(f'{record.child.name} 아동의 학습 기록이 수정되었습니다.', 'success')
            return redirect(url_for('child_detail', child_id=record.child_id))
            
        except ValueError:
            flash('입력값을 다시 확인해주세요.', 'error')
        except Exception as e:
            db.session.rollback()
            flash('수정 중 오류가 발생했습니다. 다시 시도해주세요.', 'error')
    
    return render_template('scores/form.html', record=record, children=Child.query.all())

@app.route('/scores/<int:record_id>/delete', methods=['POST'])
@login_required
def delete_score(record_id):
    record = LearningRecord.query.get_or_404(record_id)
    child_name = record.child.name
    child_id = record.child_id
    
    # 권한 확인 (센터장과 돌봄선생님만 삭제 가능)
    if current_user.role not in ['개발자']:
        flash('점수 기록 삭제 권한이 없습니다.', 'error')
        return redirect(url_for('child_detail', child_id=child_id))
    
    try:
        db.session.delete(record)
        db.session.commit()
        flash(f'{child_name} 아동의 {record.date.strftime("%Y-%m-%d")} 학습 기록이 삭제되었습니다.', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"🐛 DEBUG: 학습 기록 삭제 오류 - {str(e)}")
        print(f"🐛 DEBUG: record_id: {record_id}, child_id: {child_id}")
        flash(f'삭제 중 오류가 발생했습니다: {str(e)}', 'error')
    
    return redirect(url_for('child_detail', child_id=child_id))

# 통계 포함/제외 토글
@app.route('/children/<int:child_id>/toggle_stats', methods=['POST'])
@login_required
def toggle_child_stats(child_id):
    child = Child.query.get_or_404(child_id)
    print(f"DEBUG: {child.name} - 이전 상태: {child.include_in_stats}")
    
    # 명확한 토글 로직
    if child.include_in_stats:
        child.include_in_stats = False
    else:
        child.include_in_stats = True
    
    print(f"DEBUG: {child.name} - 변경 후 상태: {child.include_in_stats}")
    db.session.commit()
    
    status = "포함" if child.include_in_stats else "제외"
    flash(f'{child.name} 아이가 통계에서 {status}되었습니다.', 'success')
    return redirect(url_for('children_list'))

# 독서 기록 라우트
@app.route('/reading')
@login_required
def reading_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    grade_filter = request.args.get('grade', '', type=str)
    
    # 독서 기록 조회 (reading_score가 있는 기록만)
    query = db.session.query(LearningRecord, Child).join(Child).filter(LearningRecord.reading_score.isnot(None))
    
    # 검색 필터
    if search:
        query = query.filter(Child.name.contains(search))
    
    # 학년 필터
    if grade_filter:
        query = query.filter(Child.grade == int(grade_filter))
    
    # 최신순 정렬
    query = query.order_by(LearningRecord.date.desc(), LearningRecord.created_at.desc())
    
    # 페이지네이션
    records = query.paginate(
        page=page, per_page=15, error_out=False
    )
    
    # 학년 목록 (필터용)
    grades = db.session.query(Child.grade).distinct().order_by(Child.grade).all()
    grade_list = [g[0] for g in grades]
    
    return render_template('reading/list.html', 
                         records=records, 
                         search=search,
                         grade_filter=grade_filter,
                         grade_list=grade_list)

# 과목별 비교 통계 페이지
@app.route('/statistics')
@login_required
def statistics_overview():
    # 학년별 현재 진도 현황
    grade_progress = {}
    
    for grade in range(1, 7):
        children = Child.query.filter_by(grade=grade, include_in_stats=True).all()
        if not children:
            continue
            
        # 각 과목별 최신 페이지 조회
        grade_progress[grade] = {
            'total_children': len(children),
            'korean_pages': {},
            'math_pages': {},
        }
        
        for child in children:
            latest_record = LearningRecord.query.filter_by(child_id=child.id).order_by(LearningRecord.date.desc()).first()
            if latest_record:
                # 국어 페이지별 아이들 그룹화
                if latest_record.korean_last_page:
                    page = latest_record.korean_last_page
                    if page not in grade_progress[grade]['korean_pages']:
                        grade_progress[grade]['korean_pages'][page] = []
                    grade_progress[grade]['korean_pages'][page].append(child)
                
                # 수학 페이지별 아이들 그룹화  
                if latest_record.math_last_page:
                    page = latest_record.math_last_page
                    if page not in grade_progress[grade]['math_pages']:
                        grade_progress[grade]['math_pages'][page] = []
                    grade_progress[grade]['math_pages'][page].append(child)
    
    return render_template('statistics/overview.html', grade_progress=grade_progress)

# 특정 페이지별 상세 통계
@app.route('/statistics/<int:grade>/<subject>/<int:page>')
@login_required
def page_statistics(grade, subject, page):
    # 해당 학년, 과목, 페이지의 모든 기록 조회
    children_in_grade = Child.query.filter_by(grade=grade, include_in_stats=True).all()
    child_ids = [child.id for child in children_in_grade]
    
    if subject == 'korean':
        records = LearningRecord.query.filter(
            LearningRecord.child_id.in_(child_ids),
            LearningRecord.korean_last_page == page
        ).order_by(LearningRecord.date.desc()).all()
        
        # 국어 점수 기준으로 정렬
        records_with_scores = []
        for record in records:
            score = calculate_score(record.korean_problems_correct, record.korean_problems_solved)
            records_with_scores.append({
                'record': record,
                'score': score,
                'child_name': record.child.name
            })
        records_with_scores.sort(key=lambda x: x['score'], reverse=True)
        
    elif subject == 'math':
        records = LearningRecord.query.filter(
            LearningRecord.child_id.in_(child_ids),
            LearningRecord.math_last_page == page
        ).order_by(LearningRecord.date.desc()).all()
        
        # 수학 점수 기준으로 정렬
        records_with_scores = []
        for record in records:
            score = calculate_score(record.math_problems_correct, record.math_problems_solved)
            records_with_scores.append({
                'record': record,
                'score': score,
                'child_name': record.child.name
            })
        records_with_scores.sort(key=lambda x: x['score'], reverse=True)
    
    # 아직 해당 페이지를 풀지 않은 아이들
    completed_child_ids = [r['record'].child_id for r in records_with_scores]
    pending_children = [child for child in children_in_grade if child.id not in completed_child_ids]
    
    return render_template('statistics/page_detail.html', 
                         grade=grade, 
                         subject=subject, 
                         page=page,
                         records_with_scores=records_with_scores,
                         pending_children=pending_children,
                         total_children=len(children_in_grade))

# 시각화 통계 페이지 (진도 및 성적 비교)
@app.route('/statistics/charts')
@login_required
def statistics_charts():
    # 오늘 날짜
    today = datetime.utcnow().date()
    
    # 오늘 학습 기록 가져오기
    today_records = LearningRecord.query.filter(
        func.date(LearningRecord.created_at) == today
    ).order_by(LearningRecord.created_at.desc()).all()
    
    # 학년별로 아이들 그룹화
    grade_progress_data = {}
    page_comparison_data = {}
    grade_average_progress = {}
    
    for grade in range(1, 7):
        children = Child.query.filter_by(grade=grade, include_in_stats=True).all()
        if not children:
            continue
        
        # 각 아이의 최신 진도 정보 가져오기
        grade_students = []
        for child in children:
            # 최신 기록 가져오기
            latest_record = LearningRecord.query.filter_by(
                child_id=child.id
            ).order_by(LearningRecord.date.desc()).first()
            
            korean_page = latest_record.korean_last_page if latest_record else 0
            math_page = latest_record.math_last_page if latest_record else 0

            grade_students.append({
                'name': child.name,
                'korean_page': korean_page,
                'math_page': math_page,
                'total_pages': korean_page + math_page
            })
        
        # 총 진도순으로 정렬
        grade_students.sort(key=lambda x: x['total_pages'], reverse=True)
        grade_progress_data[str(grade)] = grade_students
        
        # 같은 페이지 성적 비교 데이터
        page_comparison_data[str(grade)] = {'korean': {}, 'math': {}}
        
        # 국어 페이지별 비교
        korean_pages = {}
        for child in children:
            records = LearningRecord.query.filter_by(child_id=child.id).all()
            for record in records:
                if record.korean_last_page:
                    page = record.korean_last_page
                    if page not in korean_pages:
                        korean_pages[page] = []
                    korean_pages[page].append({
                        'name': child.name,
                        'score': record.korean_score,
                        'correct': record.korean_problems_correct,
                        'solved': record.korean_problems_solved
                    })
        
        # 2명 이상인 페이지만 필터링하고 점수순 정렬
        for page, students in korean_pages.items():
            if len(students) >= 2:
                students.sort(key=lambda x: x['score'], reverse=True)
                page_comparison_data[str(grade)]['korean'][page] = students

        # 수학 페이지별 비교
        math_pages = {}
        for child in children:
            records = LearningRecord.query.filter_by(child_id=child.id).all()
            for record in records:
                if record.math_last_page:
                    page = record.math_last_page
                    if page not in math_pages:
                        math_pages[page] = []
                    math_pages[page].append({
                        'name': child.name,
                        'score': record.math_score,
                        'correct': record.math_problems_correct,
                        'solved': record.math_problems_solved
                    })
        
        # 2명 이상인 페이지만 필터링하고 점수순 정렬
        for page, students in math_pages.items():
            if len(students) >= 2:
                students.sort(key=lambda x: x['score'], reverse=True)
                page_comparison_data[str(grade)]['math'][page] = students

        # 학년별 평균 진도 계산
        if grade_students:
            korean_avg_page = sum(s['korean_page'] for s in grade_students) / len(grade_students)
            math_avg_page = sum(s['math_page'] for s in grade_students) / len(grade_students)
            
            # 평균 점수 계산
            korean_scores = []
            math_scores = []
            reading_scores = []
            
            for child in children:
                records = LearningRecord.query.filter_by(child_id=child.id).all()
                for record in records:
                    if record.korean_score > 0:
                        korean_scores.append(record.korean_score)
                    if record.math_score > 0:
                        math_scores.append(record.math_score)
                    if record.reading_score > 0:
                        reading_scores.append(record.reading_score)
            
            grade_average_progress[str(grade)] = {
                'korean_avg_page': round(korean_avg_page, 1),
                'math_avg_page': round(math_avg_page, 1),
                'korean_avg_score': round(sum(korean_scores) / len(korean_scores), 1) if korean_scores else 0,
                'math_avg_score': round(sum(math_scores) / len(math_scores), 1) if math_scores else 0,
                'reading_avg_score': round(sum(reading_scores) / len(reading_scores), 1) if reading_scores else 0
            }
    
    # 전체 진도 리더보드 (상위 10명)
    all_children = Child.query.filter_by(include_in_stats=True).all()
    all_students = []
    
    for child in all_children:
        latest_record = LearningRecord.query.filter_by(
            child_id=child.id
        ).order_by(LearningRecord.date.desc()).first()
        
        korean_page = latest_record.korean_last_page if latest_record else 0
        math_page = latest_record.math_last_page if latest_record else 0
        
        # 평균 점수 계산
        all_records = LearningRecord.query.filter_by(child_id=child.id).all()
        total_score = 0
        record_count = 0
        for record in all_records:
            if record.total_score > 0:
                total_score += record.total_score
                record_count += 1
        avg_score = round(total_score / record_count, 1) if record_count > 0 else 0
        
        # 최근 학습일
        last_study = latest_record.date.strftime('%m/%d') if latest_record else '-'

        all_students.append({
            'name': child.name,
            'grade': child.grade,
            'korean_page': korean_page,
            'math_page': math_page,
            'total_pages': korean_page + math_page,
            'avg_score': avg_score,
            'last_study': last_study
        })
    
    # 총 진도순으로 정렬하고 상위 10명만
    all_students.sort(key=lambda x: x['total_pages'], reverse=True)
    progress_leaderboard = all_students[:10]

    return render_template('statistics/charts.html',
                         grade_progress_data=json.dumps(grade_progress_data),
                         page_comparison_data=json.dumps(page_comparison_data),
                         grade_average_progress=json.dumps(grade_average_progress),
                         progress_leaderboard=progress_leaderboard,
                         today_records=today_records)

# 리포트 라우트들
@app.route('/reports')
@login_required
def reports_overview():
    """리포트 메인 페이지"""
    # 테스트사용자는 접근 불가
    if current_user.role == '테스트사용자':
        flash('리포트 페이지에 접근할 권한이 없습니다.', 'error')
        return redirect(url_for('dashboard'))
    from datetime import datetime, timedelta
    today = datetime.utcnow().date()
    return render_template('reports/overview.html', today=today, timedelta=timedelta)

@app.route('/reports/child/<int:child_id>')
@login_required
def child_report(child_id):
    """개별 아동 리포트"""
    child = Child.query.get_or_404(child_id)
    
    # 최근 30일간의 학습 기록
    thirty_days_ago = datetime.utcnow().date() - timedelta(days=30)
    recent_records = LearningRecord.query.filter_by(child_id=child_id).filter(
        LearningRecord.date >= thirty_days_ago
    ).order_by(LearningRecord.date.desc()).all()
    
    # 통계 계산
    total_records = len(recent_records)
    korean_records = [r for r in recent_records if r.korean_score > 0]
    math_records = [r for r in recent_records if r.math_score > 0]
    reading_records = [r for r in recent_records if r.reading_score > 0]
    
    # 평균 점수
    avg_korean = sum(r.korean_score for r in korean_records) / len(korean_records) if korean_records else 0
    avg_math = sum(r.math_score for r in math_records) / len(math_records) if math_records else 0
    avg_reading = sum(r.reading_score for r in reading_records) / len(reading_records) if reading_records else 0
    
    # 최신 진도
    latest_record = recent_records[0] if recent_records else None
    current_korean_page = latest_record.korean_last_page if latest_record else 0
    current_math_page = latest_record.math_last_page if latest_record else 0
    
    # 월별 학습 일수
    monthly_activity = {}
    for record in recent_records:
        month_key = record.date.strftime('%Y-%m')
        if month_key not in monthly_activity:
            monthly_activity[month_key] = 0
        monthly_activity[month_key] += 1
    
    return render_template('reports/child_report.html',
                         child=child,
                         recent_records=recent_records,
                         total_records=total_records,
                         avg_korean=round(avg_korean, 1),
                         avg_math=round(avg_math, 1),
                         avg_reading=round(avg_reading, 1),
                         current_korean_page=current_korean_page,
                         current_math_page=current_math_page,
                         monthly_activity=monthly_activity)

@app.route('/reports/grade/<int:grade>')
@login_required
def grade_report(grade):
    """학년별 리포트"""
    children = Child.query.filter_by(grade=grade, include_in_stats=True).all()
    
    if not children:
        flash(f'{grade}학년에 등록된 아동이 없습니다.', 'warning')
        return redirect(url_for('reports_overview'))
    
    # 학년 통계 계산
    grade_stats = {
        'total_children': len(children),
        'avg_korean_page': 0,
        'avg_math_page': 0,
        'avg_korean_score': 0,
        'avg_math_score': 0,
        'avg_reading_score': 0,
        'children_data': []
    }
    
    korean_pages = []
    math_pages = []
    korean_scores = []
    math_scores = []
    reading_scores = []
    
    for child in children:
        latest_record = LearningRecord.query.filter_by(child_id=child.id).order_by(LearningRecord.date.desc()).first()
        
        if latest_record:
            korean_pages.append(latest_record.korean_last_page)
            math_pages.append(latest_record.math_last_page)
            
            if latest_record.korean_score > 0:
                korean_scores.append(latest_record.korean_score)
            if latest_record.math_score > 0:
                math_scores.append(latest_record.math_score)
            if latest_record.reading_score > 0:
                reading_scores.append(latest_record.reading_score)
        
        # 아동별 데이터
        child_data = {
            'id': child.id,
            'name': child.name,
            'korean_page': latest_record.korean_last_page if latest_record else 0,
            'math_page': latest_record.math_last_page if latest_record else 0,
            'korean_score': latest_record.korean_score if latest_record else 0,
            'math_score': latest_record.math_score if latest_record else 0,
            'reading_score': latest_record.reading_score if latest_record else 0,
            'last_study': latest_record.date.strftime('%m/%d') if latest_record else '-'
        }
        grade_stats['children_data'].append(child_data)
    
    # 평균 계산
    if korean_pages:
        grade_stats['avg_korean_page'] = round(sum(korean_pages) / len(korean_pages), 1)
    if math_pages:
        grade_stats['avg_math_page'] = round(sum(math_pages) / len(math_pages), 1)
    if korean_scores:
        grade_stats['avg_korean_score'] = round(sum(korean_scores) / len(korean_scores), 1)
    if math_scores:
        grade_stats['avg_math_score'] = round(sum(math_scores) / len(math_scores), 1)
    if reading_scores:
        grade_stats['avg_reading_score'] = round(sum(reading_scores) / len(reading_scores), 1)
    
    return render_template('reports/grade_report.html',
                         grade=grade,
                         grade_stats=grade_stats)

@app.route('/reports/period')
@login_required
def period_report():
    """기간별 리포트"""
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    if not start_date or not end_date:
        # 기본값: 이번 달
        today = datetime.utcnow().date()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    # 날짜 변환
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # 기간 내 모든 기록 조회
    records = LearningRecord.query.filter(
        LearningRecord.date >= start,
        LearningRecord.date <= end
    ).order_by(LearningRecord.date.desc()).all()
    
    # 통계 계산
    total_records = len(records)
    total_children = Child.query.filter_by(include_in_stats=True).count()
    
    # 과목별 통계
    korean_records = [r for r in records if r.korean_score > 0]
    math_records = [r for r in records if r.math_score > 0]
    reading_records = [r for r in records if r.reading_score > 0]
    
    # 독서 참여 아동 수 (중복 제거)
    reading_children = len(set(r.child_id for r in reading_records))
    
    # 디버깅용 로그
    print(f"DEBUG: total_children = {total_children}")
    print(f"DEBUG: reading_children = {reading_children}")
    print(f"DEBUG: reading_records count = {len(reading_records)}")
    print(f"DEBUG: all_children = {Child.query.count()}")
    print(f"DEBUG: include_in_stats_children = {Child.query.filter_by(include_in_stats=True).count()}")
    
    period_stats = {
        'total_records': total_records,
        'total_children': total_children,
        'korean_count': len(korean_records),
        'math_count': len(math_records),
        'reading_count': reading_children,  # 독서 참여 아동 수로 변경
        'avg_korean_score': round(sum(r.korean_score for r in korean_records) / len(korean_records), 1) if korean_records else 0,
        'avg_math_score': round(sum(r.math_score for r in math_records) / len(math_records), 1) if math_records else 0,
        'avg_reading_score': round(sum(r.reading_score for r in reading_records) / len(reading_records), 1) if reading_records else 0
    }
    
    return render_template('reports/period_report.html',
                         start_date=start_date,
                         end_date=end_date,
                         period_stats=period_stats,
                         records=records)


# 새로운 포인트 시스템 라우트들
@app.route('/points')
@login_required
def points_list():
    """포인트 기록 목록"""
    # 최근 입력된 포인트들 (입력 시간 기준으로 정렬)
    points_records = DailyPoints.query.order_by(DailyPoints.created_at.desc()).limit(20).all()
    return render_template('points/list.html', points_records=points_records)

@app.route('/points/input/select')
@login_required
def points_input_select():
    """포인트 입력할 아동 선택 페이지"""
    return render_template('points/select.html')

@app.route('/points/input/<int:child_id>', methods=['GET', 'POST'])
@login_required
def points_input(child_id):
    """포인트 입력 페이지"""
    child = Child.query.get_or_404(child_id)
    
    if request.method == 'POST':
        # 오늘 날짜
        today = datetime.utcnow().date()
        
        # 기존 기록이 있는지 확인
        existing_record = DailyPoints.query.filter_by(
            child_id=child_id, 
            date=today
        ).first()
        
        try:
            # 포인트 값 가져오기 및 검증
            korean_points = int(request.form.get('korean_points', 0))
            math_points = int(request.form.get('math_points', 0))
            ssen_points = int(request.form.get('ssen_points', 0))
            reading_points = int(request.form.get('reading_points', 0))
        
            # 새 과목들 (2025-09-17 추가)
            piano_points = int(request.form.get('piano_points', 0))
            english_points = int(request.form.get('english_points', 0))
            advanced_math_points = int(request.form.get('advanced_math_points', 0))
            writing_points = int(request.form.get('writing_points', 0))

            # 수동 포인트 (manual_history에서 실시간 계산)
            manual_points = get_manual_points_from_history(existing_record)
        
            # 값 검증: 음수 방지만 방지
            if any(points < 0 for points in [korean_points, math_points, ssen_points, reading_points, piano_points, english_points, advanced_math_points, writing_points]):
                flash('❌ 포인트는 음수일 수 없습니다. 0 이상의 값을 입력해주세요.', 'error')
                return redirect(url_for('points_input', child_id=child_id))
            
            # 총 포인트 계산 (검증된 값으로)
            total_points = korean_points + math_points + ssen_points + reading_points + piano_points + english_points + advanced_math_points + writing_points + manual_points
            
            # 계산 결과 검증
            expected_total = sum([korean_points, math_points, ssen_points, reading_points, piano_points, english_points, advanced_math_points, writing_points, manual_points])
            if total_points != expected_total:
                flash(f'❌ 포인트 계산 오류가 발생했습니다. 예상: {expected_total}, 계산: {total_points}', 'error')
                return redirect(url_for('points_input', child_id=child_id))
            
            if existing_record:
                # 기존 기록 업데이트 (변경 이력 기록)
                old_total = existing_record.total_points
                old_korean = existing_record.korean_points
                old_math = existing_record.math_points
                old_ssen = existing_record.ssen_points
                old_reading = existing_record.reading_points
                old_piano = existing_record.piano_points
                old_english = existing_record.english_points
                old_advanced_math = existing_record.advanced_math_points
                old_writing = existing_record.writing_points
                old_manual = existing_record.manual_points
                
                # 기존 기록 업데이트
                existing_record.korean_points = korean_points
                existing_record.math_points = math_points
                existing_record.ssen_points = ssen_points
                existing_record.reading_points = reading_points
                existing_record.piano_points = piano_points
                existing_record.english_points = english_points
                existing_record.advanced_math_points = advanced_math_points
                existing_record.writing_points = writing_points
                # existing_record.manual_points = manual_points  # 제거: manual_history에서 실시간 계산
                existing_record.total_points = total_points
                existing_record.updated_at = datetime.utcnow()
                
                # 변경 이력 기록 (PointsHistory 테이블) - 변경사항이 있을 때만
                if (old_korean != korean_points or old_math != math_points or 
                    old_ssen != ssen_points or old_reading != reading_points or old_piano != piano_points or old_english != english_points or old_advanced_math != advanced_math_points or old_writing != writing_points or old_manual != manual_points):
                    
                    history_record = PointsHistory(
                        child_id=child_id,
                        date=today,
                        old_korean_points=old_korean,
                        old_math_points=old_math,
                        old_ssen_points=old_ssen,
                        old_reading_points=old_reading,
                        old_total_points=old_total,
                        new_korean_points=korean_points,
                        new_math_points=math_points,
                        new_ssen_points=ssen_points,
                        new_reading_points=reading_points,
                        new_total_points=total_points,
                        change_type='update',
                        changed_by=current_user.id,
                        change_reason='웹 UI를 통한 포인트 수정'
                    )
                    db.session.add(history_record)
                    
                    # 변경 이력 기록 (간단한 로그)
                    print(f"📝 포인트 변경 이력 - {child.name}({child.grade}학년) - {today}")
                    print(f"  국어: {old_korean} → {korean_points}")
                    print(f"  수학: {old_math} → {math_points}")
                    print(f"  쎈수학: {old_ssen} → {ssen_points}")
                    print(f"  독서: {old_reading} → {reading_points}")
                    print(f"  총점: {old_total} → {total_points}")
                    print(f"  변경자: {current_user.username}")
                
                # 누적 포인트 자동 업데이트 (커밋 없이)
                update_cumulative_points(child_id, commit=False)
                
                # 모든 변경사항을 한 번에 커밋
                db.session.commit()
                
                # 실시간 백업 호출 (백업 실패가 포인트 입력에 영향 주지 않도록)
                try:
                    realtime_backup(child_id, "update")
                except Exception as backup_error:
                    print(f"백업 실패: {backup_error}")
                    # 백업 실패는 포인트 입력 성공에 영향을 주지 않음
                
                flash(f'✅ {child.name} 아이의 포인트가 수정되었습니다. (총점: {total_points}점)', 'success')
                return redirect(url_for('points_list'))
            else:
                # 새 기록 생성 (생성 이력 기록)
                history_record = PointsHistory(
                    child_id=child_id,
                    date=today,
                    old_korean_points=0,
                    old_math_points=0,
                    old_ssen_points=0,
                    old_reading_points=0,
                    old_total_points=0,
                    new_korean_points=korean_points,
                    new_math_points=math_points,
                    new_ssen_points=ssen_points,
                    new_reading_points=reading_points,
                    new_total_points=total_points,
                    change_type='create',
                    changed_by=current_user.id,
                    change_reason='웹 UI를 통한 포인트 신규 입력'
                )
                db.session.add(history_record)
                
                # 새 기록 생성
                new_record = DailyPoints(
                    child_id=child_id,
                    date=today,
                    korean_points=korean_points,
                    math_points=math_points,
                    ssen_points=ssen_points,
                    reading_points=reading_points,
                piano_points=piano_points,
                english_points=english_points,
                advanced_math_points=advanced_math_points,
                writing_points=writing_points,
                    total_points=total_points,
                    created_by=current_user.id
                )
                db.session.add(new_record)
                
                # 누적 포인트 자동 업데이트 (커밋 없이)
                update_cumulative_points(child_id, commit=False)
                
                # 모든 변경사항을 한 번에 커밋
                db.session.commit()
                
                # 실시간 백업 호출 (백업 실패가 포인트 입력에 영향 주지 않도록)
                try:
                    realtime_backup(child_id, "create")
                except Exception as backup_error:
                    print(f"백업 실패: {backup_error}")
                    # 백업 실패는 포인트 입력 성공에 영향을 주지 않음
                
                flash(f'✅ {child.name} 아이의 포인트가 저장되었습니다. (총점: {total_points}점)', 'success')
                return redirect(url_for('points_list'))
            
        except ValueError as e:
            flash('❌ 잘못된 포인트 값이 입력되었습니다. 숫자만 입력해주세요.', 'error')
            return redirect(url_for('points_input', child_id=child_id))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ 포인트 저장 중 오류가 발생했습니다: {str(e)}', 'error')
            return redirect(url_for('points_input', child_id=child_id))
    
    # 오늘 기록 가져오기
    today = datetime.utcnow().date()
    today_record = DailyPoints.query.filter_by(
        child_id=child_id, 
        date=today
    ).first()
    
    # 오늘 날짜 문자열 계산
    today_date = datetime.utcnow().strftime('%Y년 %m월 %d일')
    
    return render_template('points/input.html', child=child, today_record=today_record, today_date=today_date)

def update_cumulative_points(child_id, commit=True):
    """아동의 누적 포인트를 자동으로 업데이트"""
    try:
        # 해당 아동의 모든 일일 포인트 합계 계산
        total_cumulative = db.session.query(
            db.func.sum(DailyPoints.total_points)
        ).filter_by(child_id=child_id).scalar() or 0
        
        # Child 모델의 cumulative_points 업데이트
        child = Child.query.get(child_id)
        if child:
            child.cumulative_points = total_cumulative
            if commit:
                db.session.commit()
            print(f"📊 {child.name}의 누적 포인트 업데이트: {total_cumulative}점")
            return total_cumulative
            
    except Exception as e:
        print(f"❌ 누적 포인트 업데이트 오류: {e}")
        if commit:
            db.session.rollback()
        raise e

@app.route('/points/statistics')
@login_required
def points_statistics():
    """포인트 통계 페이지"""
    # 오늘 날짜
    today = datetime.utcnow().date()
    
    # 학년별 포인트 통계
    grade_stats = {}
    for grade in range(1, 7):  # 1학년~6학년
        children = Child.query.filter_by(grade=grade, include_in_stats=True).all()
        if not children:
            continue
            
        grade_points = []
        for child in children:
            # 오늘 포인트 기록
            today_points = DailyPoints.query.filter_by(
                child_id=child.id, 
                date=today
            ).first()
            
            if today_points:
                grade_points.append(today_points.total_points)
        
        if grade_points:
            grade_stats[grade] = {
                'avg_points': round(sum(grade_points) / len(grade_points), 1),
                'max_points': max(grade_points),
                'min_points': min(grade_points),
                'total_children': len(children),
                'participated_children': len(grade_points)
            }
    
    return render_template('points/statistics.html', grade_stats=grade_stats, today=today)

@app.route('/points/analysis')
@login_required
def points_analysis():
    """포인트 분석 페이지 - 아동별 상세 분석"""
    # 아동 선택 파라미터
    child_id = request.args.get('child_id', type=int)
    
    if child_id:
        # 특정 아동 분석
        child = Child.query.get_or_404(child_id)
        
        # 해당 아동의 전체 포인트 기록 (중복 제거 후)
        # 날짜별로 하나의 기록만 가져오기
        result = db.session.execute(text("""
            SELECT id, date, korean_points, math_points, ssen_points, reading_points, total_points
            FROM daily_points 
            WHERE child_id = :child_id 
            AND id IN (
                SELECT MAX(id) 
                FROM daily_points 
                WHERE child_id = :child_id 
                GROUP BY date 
            )
            ORDER BY date DESC
        """), {"child_id": child_id})
        
        # 실제 DailyPoints 객체로 변환
        child_points = []
        for row in result:
            # 날짜 타입 변환 (문자열일 경우 datetime.date로 변환)
            date_value = row[1]
            if isinstance(date_value, str):
                from datetime import datetime
                date_value = datetime.strptime(date_value, '%Y-%m-%d').date()
            
            # DailyPoints 객체 생성
            point_record = DailyPoints(
                id=row[0],
                date=date_value,
                korean_points=row[2],
                math_points=row[3],
                ssen_points=row[4],
                reading_points=row[5],
                total_points=row[6]
            )
            child_points.append(point_record)
        
        # 총 포인트 계산 (중복 제거된 데이터로)
        total_points = sum(record.total_points for record in child_points)
        
        # 디버깅: 실제 데이터 확인
        print(f"=== {child.name} 포인트 분석 ===")
        print(f"아동 ID: {child_id}")
        print(f"아동 이름: {child.name}")
        print(f"총 기록 수: {len(child_points)}")
        print(f"계산된 총 포인트: {total_points}")
        print(f"Child.cumulative_points: {child.cumulative_points}")
        print("================================")
        
        # 같은 학년 아동들의 포인트 비교 (중복 제거 후)
        same_grade_children = Child.query.filter_by(grade=child.grade, include_in_stats=True).all()
        grade_comparison = []
        
        for grade_child in same_grade_children:
            if grade_child.id != child_id:  # 자기 자신 제외
                # 중복 제거된 포인트 계산
                result = db.session.execute(text("""
                    SELECT SUM(total_points) as total, COUNT(*) as count
                    FROM daily_points 
                    WHERE child_id = :child_id 
                    AND id IN (
                        SELECT MAX(id) 
                        FROM daily_points 
                        WHERE child_id = :child_id 
                        GROUP BY date
                    )
                """), {"child_id": grade_child.id})
                
                row = result.fetchone()
                grade_child_total = row[0] or 0
                record_count = row[1] or 0
                
                grade_comparison.append({
                    'id': grade_child.id,
                    'name': grade_child.name,
                    'total_points': grade_child_total,
                    'record_count': record_count
                })
        
        # 학년 내 순위 계산
        grade_comparison.append({
            'id': child.id,
            'name': child.name,
            'total_points': total_points,
            'record_count': len(child_points)
        })
        grade_comparison.sort(key=lambda x: x['total_points'], reverse=True)
        
        # 전체 학년 순위 (중복 제거 후)
        all_children = Child.query.filter_by(include_in_stats=True).all()
        overall_ranking = []
        
        for all_child in all_children:
            # 중복 제거된 포인트 계산
            result = db.session.execute(text("""
                SELECT SUM(total_points) as total, COUNT(*) as count
                FROM daily_points 
                WHERE child_id = :child_id 
                AND id IN (
                    SELECT MAX(id) 
                    FROM daily_points 
                    WHERE child_id = :child_id 
                    GROUP BY date
                )
            """), {"child_id": all_child.id})
            
            row = result.fetchone()
            all_child_total = row[0] or 0
            record_count = row[1] or 0
            
            overall_ranking.append({
                'id': all_child.id,
                'name': all_child.name,
                'grade': all_child.grade,
                'total_points': all_child_total,
                'record_count': record_count
            })
        
        overall_ranking.sort(key=lambda x: x['total_points'], reverse=True)
        
        return render_template('points/analysis.html', 
                             child=child,
                             child_points=child_points,
                             total_points=total_points,
                             grade_comparison=grade_comparison,
                             overall_ranking=overall_ranking)
    else:
        # 아동 목록 표시
        children = Child.query.filter_by(include_in_stats=True).order_by(Child.grade, Child.name).all()
        return render_template('points/analysis.html', children=children)

@app.route('/points/visualization')
@login_required
def points_visualization():
    """포인트 시각화 페이지"""
    from datetime import datetime, timedelta
    import calendar
    
    today = datetime.utcnow().date()
    
    # 1. 주간 트렌드 (최근 4주) - 배치 쿼리로 최적화
    date_range = [today - timedelta(days=i) for i in range(28, -1, -1)]
    weekly_points = DailyPoints.query.filter(
        DailyPoints.date.in_(date_range)
    ).all()
    
    weekly_data = []
    for date in date_range:
        day_points = [p for p in weekly_points if p.date == date]
        total_points = sum(record.total_points for record in day_points)
        weekly_data.append({
            'date': date.strftime('%m/%d'),
            'points': total_points
        })
    
    # 2. 월별 합계 (올해 전체) - 배치 쿼리로 최적화
    year_start = datetime(today.year, 1, 1).date()
    year_end = datetime(today.year, 12, 31).date()
    all_year_points = DailyPoints.query.filter(
        DailyPoints.date >= year_start,
        DailyPoints.date <= year_end
    ).all()
    
    monthly_data = []
    for month in range(1, 13):
        month_start = datetime(today.year, month, 1).date()
        if month == 12:
            month_end = datetime(today.year + 1, 1, 1).date() - timedelta(days=1)
        else:
            month_end = datetime(today.year, month + 1, 1).date() - timedelta(days=1)
        
        month_points = [p for p in all_year_points 
                       if month_start <= p.date <= month_end]
        total_month_points = sum(record.total_points for record in month_points)
        
        monthly_data.append({
            'month': f'{month}월',
            'points': total_month_points
        })
    
    # 3. 과목별 분포 (전체 기간) - 기존 all_points 재사용
    subject_totals = {
        '국어': sum(record.korean_points for record in all_year_points),
        '수학': sum(record.math_points for record in all_year_points),
        '쎈수학': sum(record.ssen_points for record in all_year_points),
        '독서': sum(record.reading_points for record in all_year_points)
    }
    
    # 4. 학년별 평균 - 배치 쿼리로 최적화
    all_children = Child.query.filter_by(include_in_stats=True).all()
    child_ids = [child.id for child in all_children]
    all_children_points = DailyPoints.query.filter(
        DailyPoints.child_id.in_(child_ids)
    ).all() if child_ids else []
    
    grade_averages = {}
    for grade_num in [1, 2, 3, 4, 5, 6]:
        grade_str = f'{grade_num}학년'
        grade_children = [child for child in all_children if child.grade == grade_num]
        
        if grade_children:
            grade_child_ids = [child.id for child in grade_children]
            grade_points = [p for p in all_children_points if p.child_id in grade_child_ids]
            
            grade_total_points = sum(record.total_points for record in grade_points)
            grade_total_records = len(grade_points)
            
            if grade_total_records > 0:
                # 평균 = 총 포인트 / 총 기록 수 (각 기록당 평균 포인트)
                grade_averages[grade_str] = round(grade_total_points / grade_total_records, 1)
                print(f"DEBUG: {grade_str} - 총 포인트: {grade_total_points}, 총 기록: {grade_total_records}, 평균: {grade_averages[grade_str]}")
            else:
                grade_averages[grade_str] = 0
                print(f"DEBUG: {grade_str} - 기록 없음")
        else:
            grade_averages[grade_str] = 0
            print(f"DEBUG: {grade_str} - 아동 없음")
    
    return render_template('points/visualization.html', 
                         weekly_data=weekly_data,
                         monthly_data=monthly_data,
                         subject_totals=subject_totals,
                         grade_averages=grade_averages,
                         today=today,
                         # JSON 형태로 미리 변환
                         weekly_labels=[item['date'] for item in weekly_data],
                         weekly_points=[item['points'] for item in weekly_data],
                         monthly_labels=[item['month'] for item in monthly_data],
                         monthly_points=[item['points'] for item in monthly_data],
                         subject_labels=list(subject_totals.keys()),
                         subject_values=list(subject_totals.values()),
                         grade_labels=list(grade_averages.keys()),
                         grade_values=list(grade_averages.values()))

@app.route('/points/child/<int:child_id>')
@login_required
def child_point_analysis(child_id):
    """개별 아동 포인트 분석 페이지"""
    from datetime import datetime, timedelta
    import calendar
    
    child = Child.query.get_or_404(child_id)
    today = datetime.utcnow().date()
    
    # 1. 주간 포인트 트렌드 (최근 8주)
    weekly_data = []
    for i in range(56, -1, -1):  # 최근 8주 (56일)
        date = today - timedelta(days=i)
        daily_record = DailyPoints.query.filter_by(child_id=child_id, date=date).first()
        points = daily_record.total_points if daily_record else 0
        weekly_data.append({
            'date': date.strftime('%m/%d'),
            'points': points
        })
    
    # 2. 월간 포인트 합계 (최근 6개월)
    monthly_data = []
    for i in range(6):
        month_date = today - timedelta(days=30*i)
        month_start = month_date.replace(day=1)
        if month_date.month == 12:
            month_end = month_date.replace(year=month_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_date.replace(month=month_date.month + 1, day=1) - timedelta(days=1)
        
        month_points = DailyPoints.query.filter(
            DailyPoints.child_id == child_id,
            DailyPoints.date >= month_start,
            DailyPoints.date <= month_end
        ).all()
        total_month_points = sum(record.total_points for record in month_points)
        
        monthly_data.append({
            'month': month_date.strftime('%Y년 %m월'),
            'points': total_month_points
        })
    
    # 3. 증감률 계산
    # 이번 주 vs 지난 주
    this_week_start = today - timedelta(days=today.weekday())
    last_week_start = this_week_start - timedelta(days=7)
    
    this_week_points = DailyPoints.query.filter(
        DailyPoints.child_id == child_id,
        DailyPoints.date >= this_week_start,
        DailyPoints.date <= today
    ).all()
    this_week_total = sum(record.total_points for record in this_week_points)
    
    last_week_points = DailyPoints.query.filter(
        DailyPoints.child_id == child_id,
        DailyPoints.date >= last_week_start,
        DailyPoints.date < this_week_start
    ).all()
    last_week_total = sum(record.total_points for record in last_week_points)
    
    weekly_change = 0
    if last_week_total > 0:
        weekly_change = round(((this_week_total - last_week_total) / last_week_total) * 100, 1)
    
    # 이번 달 vs 지난 달
    this_month_start = today.replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    
    this_month_points = DailyPoints.query.filter(
        DailyPoints.child_id == child_id,
        DailyPoints.date >= this_month_start,
        DailyPoints.date <= today
    ).all()
    this_month_total = sum(record.total_points for record in this_month_points)
    
    last_month_points = DailyPoints.query.filter(
        DailyPoints.child_id == child_id,
        DailyPoints.date >= last_month_start,
        DailyPoints.date < this_month_start
    ).all()
    last_month_total = sum(record.total_points for record in last_month_points)
    
    monthly_change = 0
    if last_month_total > 0:
        monthly_change = round(((this_month_total - last_month_total) / last_month_total) * 100, 1)
    
    # 4. 같은 학년 비교
    grade_children = Child.query.filter_by(grade=child.grade, include_in_stats=True).all()
    grade_comparison = []
    
    for grade_child in grade_children:
        child_total_points = DailyPoints.query.filter_by(child_id=grade_child.id).all()
        total_points = sum(record.total_points for record in child_total_points)
        record_count = len(child_total_points)
        
        grade_comparison.append({
            'id': grade_child.id,
            'name': grade_child.name,
            'total_points': total_points,
            'record_count': record_count,
            'avg_points': round(total_points / record_count, 0) if record_count > 0 else 0
        })
    
    # 포인트 순으로 정렬
    grade_comparison.sort(key=lambda x: x['total_points'], reverse=True)
    
    # 현재 아동의 순위 찾기
    current_rank = 1
    for i, comp_child in enumerate(grade_comparison):
        if comp_child['id'] == child_id:
            current_rank = i + 1
            break
    
    return render_template('points/child_analysis.html',
                         child=child,
                         weekly_data=weekly_data,
                         monthly_data=monthly_data,
                         weekly_change=weekly_change,
                         monthly_change=monthly_change,
                         this_week_total=this_week_total,
                         last_week_total=last_week_total,
                         this_month_total=this_month_total,
                         last_month_total=last_month_total,
                         grade_comparison=grade_comparison,
                         current_rank=current_rank,
                         total_children_in_grade=len(grade_comparison))

@app.route('/points/grade-comparison/<int:grade>')
@login_required
def grade_point_comparison(grade):
    """학년별 포인트 비교 시각화"""
    from datetime import datetime, timedelta
    
    today = datetime.utcnow().date()
    
    # 해당 학년의 모든 아동 조회
    grade_children = Child.query.filter_by(grade=grade, include_in_stats=True).all()
    
    if not grade_children:
        flash(f'{grade}학년에 아동이 없습니다.', 'warning')
        return redirect(url_for('points_visualization'))
    
    # 각 아동의 포인트 데이터 수집
    children_data = []
    for child in grade_children:
        # 전체 포인트
        all_points = DailyPoints.query.filter_by(child_id=child.id).all()
        total_points = sum(record.total_points for record in all_points)
        
        # 이번 주 포인트
        this_week_start = today - timedelta(days=today.weekday())
        this_week_points = DailyPoints.query.filter(
            DailyPoints.child_id == child.id,
            DailyPoints.date >= this_week_start,
            DailyPoints.date <= today
        ).all()
        this_week_total = sum(record.total_points for record in this_week_points)
        
        # 이번 달 포인트
        this_month_start = today.replace(day=1)
        this_month_points = DailyPoints.query.filter(
            DailyPoints.child_id == child.id,
            DailyPoints.date >= this_month_start,
            DailyPoints.date <= today
        ).all()
        this_month_total = sum(record.total_points for record in this_month_points)
        
        # 평균 포인트
        avg_points = round(total_points / len(all_points), 1) if all_points else 0
        
        children_data.append({
            'id': child.id,
            'name': child.name,
            'total_points': total_points,
            'this_week': this_week_total,
            'this_month': this_month_total,
            'avg_points': avg_points,
            'record_count': len(all_points)
        })
    
    # 총 포인트 순으로 정렬
    children_data.sort(key=lambda x: x['total_points'], reverse=True)
    
    # 차트 데이터 준비
    chart_labels = [child['name'] for child in children_data]
    chart_total_points = [child['total_points'] for child in children_data]
    chart_weekly_points = [child['this_week'] for child in children_data]
    chart_monthly_points = [child['this_month'] for child in children_data]
    chart_avg_points = [child['avg_points'] for child in children_data]
    
    return render_template('points/grade_comparison.html',
                         grade=grade,
                         children_data=children_data,
                         chart_labels=chart_labels,
                         chart_total_points=chart_total_points,
                         chart_weekly_points=chart_weekly_points,
                         chart_monthly_points=chart_monthly_points,
                         chart_avg_points=chart_avg_points)

# 설정 라우트들
@app.route('/settings')
@login_required
def settings():
    """설정 메인 페이지"""
    # 테스트사용자는 접근 불가
    if current_user.role == '테스트사용자':
        flash('설정 페이지에 접근할 권한이 없습니다.', 'error')
        return redirect(url_for('dashboard'))
    return render_template('settings/index.html')

@app.route('/settings/users', methods=['GET', 'POST'])
@login_required
def settings_users():
    """사용자 관리 페이지"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_info':
            # 사용자 정보 업데이트
            new_username = request.form.get('username')
            new_name = request.form.get('name')
            
            # 중복 확인
            existing_user = User.query.filter_by(username=new_username).first()
            if existing_user and existing_user.id != current_user.id:
                flash('이미 사용 중인 아이디입니다.', 'error')
                return redirect(url_for('settings_users'))
            
            current_user.username = new_username
            current_user.name = new_name
            db.session.commit()
            flash('사용자 정보가 업데이트되었습니다.', 'success')
            
        elif action == 'change_password':
            # 비밀번호 변경
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if not check_password_hash(current_user.password_hash, current_password):
                flash('현재 비밀번호가 올바르지 않습니다.', 'error')
                return redirect(url_for('settings_users'))
            
            if new_password != confirm_password:
                flash('새 비밀번호가 일치하지 않습니다.', 'error')
                return redirect(url_for('settings_users'))
            
            current_user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('비밀번호가 변경되었습니다.', 'success')
            
        elif action == 'add_user':
            # 새 사용자 추가 (개발자만 가능)
            if current_user.role != '개발자':
                flash('새 사용자 추가 권한이 없습니다.', 'error')
                return redirect(url_for('settings_users'))
            
            new_username = request.form.get('new_username')
            new_name = request.form.get('new_name')
            new_role = request.form.get('new_role')
            new_password = request.form.get('new_password')
            
            # 중복 확인
            if User.query.filter_by(username=new_username).first():
                flash('이미 사용 중인 아이디입니다.', 'error')
                return redirect(url_for('settings_users'))
            
            new_user = User(
                username=new_username,
                name=new_name,
                role=new_role,
                password_hash=generate_password_hash(new_password)
            )
            db.session.add(new_user)
            db.session.commit()
            flash(f'{new_name} 사용자가 추가되었습니다.', 'success')
    
    return render_template('settings/users.html')

@app.route('/settings/points')
@login_required
def settings_points():
    """수동 포인트 관리 페이지"""
    children = Child.query.filter_by(include_in_stats=True).order_by(Child.grade, Child.name).all()
    return render_template('settings/points.html', children=children)

@app.route('/api/children/by-grade')
@login_required
def get_children_by_grade():
    """학년별 아동 목록 조회 API"""
    try:
        grade = request.args.get('grade', type=int)
        
        # 통계에 포함된 아동들만 조회
        query = Child.query.filter_by(include_in_stats=True)
        
        # 학년 필터 적용 (선택사항)
        if grade:
            query = query.filter_by(grade=grade)
        
        # 학년, 이름 순으로 정렬
        children = query.order_by(Child.grade, Child.name).all()
        
        # JSON 형태로 반환
        children_data = []
        for child in children:
            children_data.append({
                'id': child.id,
                'name': child.name,
                'grade': child.grade,
                'display_name': f"{child.name} ({child.grade}학년)"
            })
        
        return jsonify({
            'success': True,
            'children': children_data,
            'total': len(children_data)
        })
        
    except Exception as e:
        print(f"❌ 아동 목록 조회 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'children': []
        })

# 수동 포인트 관리 API
@app.route('/api/manual-points', methods=['POST'])
@login_required
def add_manual_points():
    """수동 포인트 추가 API"""
    try:
        data = request.get_json()
        child_id = data.get('child_id')
        subject = data.get('subject')
        points = data.get('points')
        reason = data.get('reason')
        
        # 입력 검증
        if not all([child_id, subject, points is not None, reason]):
            return jsonify({'success': False, 'error': '모든 필드를 입력해주세요.'})
        
        # 아동 확인
        child = Child.query.get(child_id)
        if not child:
            return jsonify({'success': False, 'error': '아동을 찾을 수 없습니다.'})
        
        # 오늘 날짜의 기록 찾기 또는 생성
        today = datetime.now().date()
        daily_record = DailyPoints.query.filter_by(child_id=child_id, date=today).first()
        
        if not daily_record:
            # 새 기록 생성
            daily_record = DailyPoints(
                child_id=child_id,
                date=today,
                korean_points=0,
                math_points=0,
                ssen_points=0,
                reading_points=0,
                piano_points=0,
                english_points=0,
                advanced_math_points=0,
                writing_points=0,
                manual_points=0,
                manual_history='[]',
                total_points=0,
                created_by=current_user.id
            )
            db.session.add(daily_record)
        
        # 수동 히스토리 업데이트
        import json
        try:
            history = json.loads(daily_record.manual_history) if daily_record.manual_history else []
        except:
            history = []
        
        # 새 히스토리 항목 추가
        new_history_item = {
            'id': len(history) + 1,
            'subject': subject,
            'points': points,
            'reason': reason,
            'created_by': current_user.name or current_user.username,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        history.append(new_history_item)
        
        # 수동 포인트 총합 계산
        manual_total = sum(item['points'] for item in history)
        
        # 기록 업데이트
        daily_record.manual_history = json.dumps(history, ensure_ascii=False)
        daily_record.manual_points = manual_total
        
        # 총 포인트 재계산 (manual_history에서 실시간 계산)
        manual_points_calculated = get_manual_points_from_history(daily_record)
        daily_record.total_points = (
            daily_record.korean_points + daily_record.math_points + 
            daily_record.ssen_points + daily_record.reading_points +
            daily_record.piano_points + daily_record.english_points +
            daily_record.advanced_math_points + daily_record.writing_points +
            manual_points_calculated
        )
        
        # 포인트 히스토리에도 기록 (변경 이력 페이지용)
        change_type = '추가' if points > 0 else '차감'
        points_history = PointsHistory(
            child_id=child_id,
            date=today,
            old_korean_points=0, old_math_points=0, old_ssen_points=0, old_reading_points=0, old_total_points=daily_record.total_points - points,
            new_korean_points=0, new_math_points=0, new_ssen_points=0, new_reading_points=0, new_total_points=daily_record.total_points,
            change_type=change_type,
            changed_by=current_user.id,
            change_reason=f'수동 {change_type}: {subject} ({reason})'
        )
        db.session.add(points_history)
        
        # 누적 포인트 자동 업데이트
        update_cumulative_points(child_id, commit=False)
        
        db.session.commit()
        
        # 실시간 백업 호출
        try:
            realtime_backup(child_id, "manual_update")
        except Exception as backup_error:
            print(f"백업 실패: {backup_error}")
        
        return jsonify({'success': True, 'message': f'수동 포인트가 {change_type}되었습니다.'})
        
    except Exception as e:
        db.session.rollback()
        print(f"수동 포인트 추가 오류: {str(e)}")
        return jsonify({'success': False, 'error': f'처리 중 오류가 발생했습니다: {str(e)}'})

@app.route('/api/manual-points/recent')
@login_required
def get_recent_manual_points():
    """최근 수동 포인트 내역 조회 API"""
    try:
        import json
        
        # 최근 20개 기록 조회
        recent_records = DailyPoints.query.filter(
            DailyPoints.manual_history != '[]',
            DailyPoints.manual_history.isnot(None)
        ).order_by(DailyPoints.date.desc()).limit(20).all()
        
        history_items = []
        
        for record in recent_records:
            try:
                history = json.loads(record.manual_history) if record.manual_history else []
                child = Child.query.get(record.child_id)
                
                for item in reversed(history):  # 최신순으로
                    history_items.append({
                        'id': f"{record.id}_{item['id']}",  # 고유 ID
                        'child_name': child.name if child else '알 수 없음',
                        'subject': item['subject'],
                        'points': item['points'],
                        'reason': item['reason'],
                        'created_by': item['created_by'],
                        'created_at': item['created_at']
                    })
            except:
                continue
        
        # 날짜순으로 정렬 후 20개만
        history_items.sort(key=lambda x: x['created_at'], reverse=True)
        history_items = history_items[:20]
        
        return jsonify({'success': True, 'history': history_items})
        
    except Exception as e:
        print(f"수동 포인트 조회 오류: {str(e)}")
        return jsonify({'success': False, 'error': f'조회 중 오류가 발생했습니다: {str(e)}'})

@app.route('/api/manual-points/<item_id>', methods=['DELETE'])
@login_required
def delete_manual_point(item_id):
    """수동 포인트 삭제 API"""
    try:
        # item_id는 "record_id_history_id" 형태
        record_id, history_id = item_id.split('_')
        record_id = int(record_id)
        history_id = int(history_id)
        
        daily_record = DailyPoints.query.get(record_id)
        if not daily_record:
            return jsonify({'success': False, 'error': '기록을 찾을 수 없습니다.'})
        
        import json
        try:
            history = json.loads(daily_record.manual_history) if daily_record.manual_history else []
        except:
            return jsonify({'success': False, 'error': '히스토리 데이터 오류'})
        
        # 해당 항목 삭제
        history = [item for item in history if item['id'] != history_id]
        
        # 수동 포인트 총합 재계산
        manual_total = sum(item['points'] for item in history)
        
        # 기록 업데이트
        daily_record.manual_history = json.dumps(history, ensure_ascii=False)
        daily_record.manual_points = manual_total
        
        # 총 포인트 재계산 (manual_history에서 실시간 계산)
        manual_points_calculated = get_manual_points_from_history(daily_record)
        daily_record.total_points = (
            daily_record.korean_points + daily_record.math_points + 
            daily_record.ssen_points + daily_record.reading_points +
            daily_record.piano_points + daily_record.english_points +
            daily_record.advanced_math_points + daily_record.writing_points +
            manual_points_calculated
        )
        
        # 누적 포인트 자동 업데이트
        update_cumulative_points(daily_record.child_id, commit=False)
        
        db.session.commit()
        
        # 실시간 백업 호출
        try:
            realtime_backup(daily_record.child_id, "manual_delete")
        except Exception as backup_error:
            print(f"백업 실패: {backup_error}")
        
        return jsonify({'success': True, 'message': '수동 포인트가 삭제되었습니다.'})
        
    except Exception as e:
        db.session.rollback()
        print(f"수동 포인트 삭제 오류: {str(e)}")
        return jsonify({'success': False, 'error': f'삭제 중 오류가 발생했습니다: {str(e)}'})

@app.route('/settings/data')
@login_required
def settings_data():
    """데이터 관리 페이지"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'seed_data':
            # 시드 데이터 실행
            try:
                from scripts.seed_data import main as seed_main
                seed_main()
                flash('기본 시드 데이터가 성공적으로 실행되었습니다.', 'success')
            except Exception as e:
                flash(f'시드 데이터 실행 중 오류가 발생했습니다: {e}', 'error')
        
        elif action == 'reset_data':
            # 데이터 초기화 (개발자만)
            if current_user.role != '개발자':
                flash('데이터 초기화 권한이 없습니다.', 'error')
                return redirect(url_for('settings_data'))
            
            try:
                # 모든 데이터 삭제
                DailyPoints.query.delete()
                LearningRecord.query.delete()
                Child.query.delete()
                User.query.delete()
                db.session.commit()
                flash('모든 데이터가 초기화되었습니다.', 'success')
            except Exception as e:
                flash(f'데이터 초기화 중 오류가 발생했습니다: {e}', 'error')
        
        elif action == 'export_data':
            # 데이터 내보내기 (개발자만)
            if current_user.role != '개발자':
                flash('데이터 내보내기 권한이 없습니다.', 'error')
                return redirect(url_for('settings_data'))
            
            try:
                # 간단한 데이터 요약 내보내기
                children_count = Child.query.count()
                users_count = User.query.count()
                records_count = LearningRecord.query.count()
                points_count = DailyPoints.query.count()
                
                export_data = {
                    'children_count': children_count,
                    'users_count': users_count,
                    'records_count': records_count,
                    'points_count': points_count,
                    'export_date': datetime.now().isoformat()
                }
                
                # JSON 파일로 다운로드
                response = jsonify(export_data)
                response.headers['Content-Disposition'] = 'attachment; filename=data_export.json'
                return response
                
            except Exception as e:
                flash(f'데이터 내보내기 중 오류가 발생했습니다: {e}', 'error')
    
    # 현재 데이터베이스 현황
    children_count = Child.query.count()
    users_count = User.query.count()
    records_count = LearningRecord.query.count()
    points_count = DailyPoints.query.count()
    
    return render_template('settings/data.html', 
                         children_count=children_count,
                         users_count=users_count,
                         records_count=records_count,
                         points_count=points_count)

@app.route('/settings/ui')
@login_required
def settings_ui():
    """UI/UX 설정 페이지"""
    return render_template('settings/ui.html')

@app.route('/profile')
@login_required
def profile():
    """프로필 페이지"""
    # 테스트사용자는 접근 불가
    if current_user.role == '테스트사용자':
        flash('프로필 페이지에 접근할 권한이 없습니다.', 'error')
        return redirect(url_for('dashboard'))
    return render_template('profile.html')

@app.route('/privacy-policy')
def privacy_policy():
    """개인정보보호 및 시스템 보안 정책 페이지"""
    return render_template('privacy_policy.html')

@app.route('/settings/system')
@login_required
def settings_system():
    """시스템 정보 페이지"""
    return render_template('settings/system.html')

@app.route('/settings/security')
@login_required
def settings_security():
    """보안 설정 진단 페이지 (개발자 전용)"""
    if current_user.role != '개발자':
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('settings'))
    
    # 현재 보안 설정 상태 체크
    security_status = {
        'session_timeout': app.config.get('PERMANENT_SESSION_LIFETIME'),
        'secure_cookies': {
            'httponly': app.config.get('SESSION_COOKIE_HTTPONLY'),
            'samesite': app.config.get('SESSION_COOKIE_SAMESITE'),
            'secure': app.config.get('SESSION_COOKIE_SECURE')
        },
        'brute_force_protection': {
            'ip_tracking': len(failed_login_attempts),
            'blocked_ips': len(blocked_ips),
            'protection_enabled': True
        },
        'security_headers': {
            'csp_enabled': True,
            'hsts_enabled': bool(os.environ.get('DATABASE_URL')),
            'permissions_policy': True,
            'xss_protection': True
        },
        'environment': 'Production' if os.environ.get('DATABASE_URL') else 'Development'
    }
    
    return render_template('settings/security.html', security_status=security_status)

@app.route('/api/security/test-headers')
@login_required
def test_security_headers():
    """보안 헤더 테스트 API (개발자 전용)"""
    if current_user.role != '개발자':
        return jsonify({'error': '권한이 없습니다.'}), 403
    
    # 현재 응답에 적용된 헤더들 반환
    test_response = {
        'timestamp': datetime.utcnow().isoformat(),
        'security_headers_test': 'OK',
        'csp_policy': 'Active',
        'hsts_status': 'Active' if os.environ.get('DATABASE_URL') else 'Development Mode',
        'brute_force_stats': {
            'failed_attempts_tracked': len(failed_login_attempts),
            'currently_blocked_ips': len(blocked_ips)
        }
    }
    
    return jsonify(test_response)

@app.route('/cumulative-points')
@login_required
def cumulative_points():
    """누적 포인트 입력 및 관리 페이지"""
    children = Child.query.order_by(Child.grade, Child.name).all()
    return render_template('cumulative_points.html', children=children)

@app.route('/cumulative-points/input', methods=['POST'])
@login_required
def input_cumulative_points():
    """누적 포인트 입력 처리"""
    try:
        data = request.get_json()
        child_id = data.get('child_id')
        cumulative_points = data.get('cumulative_points')
        
        if not child_id or cumulative_points is None:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'}), 400
        
        # 포인트 값 검증
        try:
            cumulative_points = int(cumulative_points)
            if cumulative_points < 0:
                return jsonify({'success': False, 'message': '포인트는 0 이상이어야 합니다.'}), 400
        except ValueError:
            return jsonify({'success': False, 'message': '올바른 숫자를 입력해주세요.'}), 400
        
        # 아동 정보 업데이트
        child = Child.query.get(child_id)
        if not child:
            return jsonify({'success': False, 'message': '아동을 찾을 수 없습니다.'}), 404
        
        child.cumulative_points = cumulative_points
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'{child.name}의 누적 포인트가 {cumulative_points}점으로 설정되었습니다.',
            'child_name': child.name,
            'cumulative_points': cumulative_points
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'오류가 발생했습니다: {str(e)}'}), 500

@app.route('/cumulative-points/bulk-input', methods=['POST'])
@login_required
def bulk_input_cumulative_points():
    """일괄 누적 포인트 입력 처리"""
    try:
        data = request.get_json()
        points_data = data.get('points_data', [])
        
        if not points_data:
            return jsonify({'success': False, 'message': '입력할 데이터가 없습니다.'}), 400
        
        updated_count = 0
        errors = []
        
        for item in points_data:
            child_id = item.get('child_id')
            cumulative_points = item.get('cumulative_points')
            
            if not child_id or cumulative_points is None:
                errors.append(f'아동 ID {child_id}: 포인트 정보 누락')
                continue
            
            try:
                cumulative_points = int(cumulative_points)
                if cumulative_points < 0:
                    errors.append(f'아동 ID {child_id}: 포인트는 0 이상이어야 합니다.')
                    continue
            except ValueError:
                errors.append(f'아동 ID {child_id}: 올바른 숫자가 아닙니다.')
                continue
            
            child = Child.query.get(child_id)
            if not child:
                errors.append(f'아동 ID {child_id}: 아동을 찾을 수 없습니다.')
                continue
            
            child.cumulative_points = cumulative_points
            updated_count += 1
        
        if errors:
            db.session.rollback()
            return jsonify({
                'success': False, 
                'message': f'{len(errors)}건의 오류가 발생했습니다.',
                'errors': errors
            }), 400
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{updated_count}명의 아동 누적 포인트가 성공적으로 업데이트되었습니다.',
            'updated_count': updated_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'오류가 발생했습니다: {str(e)}'}), 500

# 포인트 변경 이력 테이블
class PointsHistory(db.Model):
    """포인트 변경 이력 기록"""
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    
    # 변경 전 포인트
    old_korean_points = db.Column(db.Integer, default=0)
    old_math_points = db.Column(db.Integer, default=0)
    old_ssen_points = db.Column(db.Integer, default=0)
    old_reading_points = db.Column(db.Integer, default=0)
    old_total_points = db.Column(db.Integer, default=0)
    
    old_piano_points = db.Column(db.Integer, default=0)
    old_english_points = db.Column(db.Integer, default=0) 
    old_advanced_math_points = db.Column(db.Integer, default=0)
    old_writing_points = db.Column(db.Integer, default=0)
    old_total_points = db.Column(db.Integer, default=0)
    
    # 변경 후 포인트
    new_korean_points = db.Column(db.Integer, default=0)
    new_math_points = db.Column(db.Integer, default=0)
    new_ssen_points = db.Column(db.Integer, default=0)
    new_reading_points = db.Column(db.Integer, default=0)
    new_total_points = db.Column(db.Integer, default=0)

    new_piano_points = db.Column(db.Integer, default=0)
    new_english_points = db.Column(db.Integer, default=0)
    new_advanced_math_points = db.Column(db.Integer, default=0)
    new_writing_points = db.Column(db.Integer, default=0)
    new_total_points = db.Column(db.Integer, default=0)
    
    # 변경 정보
    change_type = db.Column(db.String(20), default='update')  # 'create', 'update', 'delete'
    changed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    change_reason = db.Column(db.String(200))  # 변경 사유 (선택사항)
    
    # 관계 설정
    child = db.relationship('Child', backref='points_history', lazy=True)
    user = db.relationship('User', backref='points_changes', lazy=True)
    
    def __repr__(self):
        return f'<PointsHistory {self.child.name} {self.date} {self.change_type}>'

class Notification(db.Model):
    """알림 시스템"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    # 알림 타입 및 우선순위
    type = db.Column(db.String(30), default='info')  # 'info', 'success', 'warning', 'danger'
    priority = db.Column(db.Integer, default=1)  # 1=낮음, 2=보통, 3=높음, 4=긴급
    
    # 대상 및 조건
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # null이면 전체 공지
    target_role = db.Column(db.String(30), nullable=True)  # 특정 역할에만 표시
    child_id = db.Column(db.Integer, db.ForeignKey('child.id'), nullable=True)  # 특정 아동 관련 알림
    
    # 상태 관리
    is_read = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    # is_deleted = db.Column(db.Boolean, default=False)  # 소프트 삭제 플래그
    auto_expire = db.Column(db.Boolean, default=False)  # 자동 만료 여부
    expire_date = db.Column(db.DateTime, nullable=True)  # 만료 일시
    
    # 메타데이터
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # 관계 설정
    target_user = db.relationship('User', foreign_keys=[target_user_id], backref='received_notifications', lazy=True)
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_notifications', lazy=True)
    child = db.relationship('Child', backref='notifications', lazy=True)
    
    def __repr__(self):
        return f'<Notification {self.title} ({self.type})>'
    
    @property
    def icon(self):
        """알림 타입에 따른 아이콘 반환"""
        icons = {
            'info': 'info-circle',
            'success': 'check-circle',
            'warning': 'exclamation-triangle',
            'danger': 'x-circle',
            'reminder': 'clock',
            'system': 'gear',
            'backup_success': 'cloud-check',
            'backup_failed': 'cloud-x',
            'restore_success': 'arrow-clockwise',
            'restore_failed': 'exclamation-triangle'
        }
        return icons.get(self.type, 'bell')
    
    @property
    def color(self):
        """알림 타입에 따른 색상 반환"""
        colors = {
            'info': 'primary',
            'success': 'success',
            'warning': 'warning',
            'danger': 'danger',
            'reminder': 'info',
            'system': 'secondary',
            'backup_success': 'success',
            'backup_failed': 'danger',
            'restore_success': 'success',
            'restore_failed': 'danger'
        }
        return colors.get(self.type, 'primary')

def create_backup_notification(backup_type, status, message, target_role='개발자'):
    """백업 관련 알림 생성"""
    try:
        if status == 'success':
            notification_type = 'backup_success'
            title = f"{backup_type} 백업 완료"
            priority = 2  # 보통 우선순위
        else:
            notification_type = 'backup_failed'
            title = f"{backup_type} 백업 실패"
            priority = 4  # 긴급 우선순위
        
        notification = Notification(
            title=title,
            message=message,
            type=notification_type,
            target_role=target_role,
            priority=priority,
            auto_expire=True,
            expire_date=datetime.utcnow() + timedelta(days=7),  # 7일 후 자동 만료
            created_by=1  # 시스템 생성
        )
        
        db.session.add(notification)
        db.session.commit()
        print(f"✅ 백업 알림 생성: {title}")
        return notification
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ 백업 알림 생성 실패: {e}")
        return None

def create_restore_notification(status, message, target_role='개발자'):
    """복원 관련 알림 생성"""
    try:
        if status == 'success':
            notification_type = 'restore_success'
            title = "데이터베이스 복원 완료"
            priority = 3  # 높은 우선순위
        else:
            notification_type = 'restore_failed'
            title = "데이터베이스 복원 실패"
            priority = 4  # 긴급 우선순위
        
        notification = Notification(
            title=title,
            message=message,
            type=notification_type,
            target_role=target_role,
            priority=priority,
            auto_expire=True,
            expire_date=datetime.utcnow() + timedelta(days=7),  # 7일 후 자동 만료
            created_by=1  # 시스템 생성
        )
        
        db.session.add(notification)
        db.session.commit()
        print(f"✅ 복원 알림 생성: {title}")
        return notification
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ 복원 알림 생성 실패: {e}")
        return None

# ===== 알림 시스템 헬퍼 함수들 =====

def create_notification(title, message, notification_type='info', target_user_id=None, target_role=None, 
                       child_id=None, priority=1, auto_expire=False, expire_days=None):
    """새 알림 생성"""
    try:
        print(f"DEBUG: create_notification 호출됨 - {title}")
        print(f"DEBUG: current_user.is_authenticated = {current_user.is_authenticated}")
        print(f"DEBUG: current_user.id = {current_user.id if current_user.is_authenticated else 'None'}")
        
        expire_date = None
        if auto_expire and expire_days:
            expire_date = datetime.utcnow() + timedelta(days=expire_days)
        
        notification = Notification(
            title=title,
            message=message,
            type=notification_type,
            target_user_id=target_user_id,
            target_role=target_role,
            child_id=child_id,
            priority=priority,
            auto_expire=auto_expire,
            expire_date=expire_date,
            created_by=current_user.id if current_user.is_authenticated else 1
        )
        
        print(f"DEBUG: Notification 객체 생성 완료")
        db.session.add(notification)
        print(f"DEBUG: DB에 추가 완료")
        db.session.commit()
        print(f"DEBUG: DB 커밋 완료 - 알림 ID: {notification.id}")
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"알림 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_user_notifications(user_id, limit=10, unread_only=False):
    """사용자별 알림 조회"""
    user = User.query.get(user_id)
    if not user:
        return []
    
    # 조건들을 리스트로 구성
    conditions = []
    
    # 1. 개인 알림 (target_user_id가 현재 사용자)
    conditions.append(Notification.target_user_id == user_id)
    
    # 2. 전체 공지 (target_user_id=None, target_role=None)
    conditions.append(
        db.and_(
            Notification.target_user_id.is_(None),
            Notification.target_role.is_(None)
        )
    )
    
    # 3. 역할별 공지 (target_user_id=None, target_role=사용자 역할)
    conditions.append(
        db.and_(
            Notification.target_user_id.is_(None),
            Notification.target_role == user.role
        )
    )
    
    # 4. 아동 관련 알림 (child_id가 있는 알림 - 모든 사용자에게 표시)
    conditions.append(Notification.child_id.isnot(None))
    
    # 기본 쿼리: 위의 조건들 중 하나라도 만족하는 알림
    query = Notification.query.filter(db.or_(*conditions))
    
    # 만료 조건 적용
    query = query.filter(
        db.or_(
            Notification.expire_date.is_(None),
            Notification.expire_date > datetime.utcnow()
        )
    )
    
    # 읽지 않은 알림만 필터링 (필요시)
    if unread_only:
        query = query.filter(Notification.is_read == False)
    
    # 정렬
    query = query.order_by(Notification.priority.desc(), Notification.created_at.desc())
    
    # limit 적용
    if limit is not None:
        query = query.limit(limit)
    
    return query.all()

def mark_notification_read(notification_id, user_id):
    """알림을 읽음으로 표시"""
    notification = Notification.query.filter_by(id=notification_id).first()
    if notification and (notification.target_user_id == user_id or notification.target_user_id is None):
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.session.commit()
        return True
    return False

def delete_notification(notification_id, user_id):
    """알림 소프트 삭제 (개발자만 가능)"""
    try:
        # 사용자 권한 확인
        user = User.query.get(user_id)
        if not user or user.role != '개발자':
            return False, "개발자 권한이 필요합니다."
        
        # 알림 조회
        notification = Notification.query.filter_by(id=notification_id).first()
        if not notification:
            return False, "알림을 찾을 수 없습니다."
        
        # 소프트 삭제 처리
        db.session.delete(notification)
        db.session.commit()
        
        return True, "알림이 삭제되었습니다."
        
    except Exception as e:
        db.session.rollback()
        return False, f"삭제 중 오류가 발생했습니다: {str(e)}"

def delete_multiple_notifications(notification_ids, user_id):
    """여러 알림 일괄 삭제 (개발자만 가능)"""
    try:
        # 사용자 권한 확인
        user = User.query.get(user_id)
        if not user or user.role != '개발자':
            return False, "개발자 권한이 필요합니다."
        
        # 알림들 조회 및 삭제
        notifications = Notification.query.filter(
            Notification.id.in_(notification_ids)
        ).all()
        
        if not notifications:
            return False, "삭제할 알림을 찾을 수 없습니다."
        
        # 소프트 삭제 처리
        for notification in notifications:
            db.session.delete(notification)
        
        db.session.commit()
        
        return True, f"{len(notifications)}개의 알림이 삭제되었습니다."
        
    except Exception as e:
        db.session.rollback()
        return False, f"삭제 중 오류가 발생했습니다: {str(e)}"

def create_system_notification(title, message, target_role=None, priority=1):
    """시스템 알림 생성"""
    return create_notification(
        title=title,
        message=message,
        notification_type='system',
        target_role=target_role,
        priority=priority
    )

@app.route('/notifications')
@login_required
def notifications():
    """알림 목록 페이지"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # 모든 알림 조회
    all_notifications = get_user_notifications(current_user.id, limit=None)
    
    # 페이지네이션
    total = len(all_notifications)
    start = (page - 1) * per_page
    end = start + per_page
    notifications_page = all_notifications[start:end]
    
    # 읽지 않은 알림 수
    unread_count = len([n for n in all_notifications if not n.is_read])
    
    return render_template('notifications/list.html',
                         notifications=notifications_page,
                         page=page,
                         per_page=per_page,
                         total=total,
                         unread_count=unread_count)

@app.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_as_read(notification_id):
    """알림 읽음 처리"""
    success = mark_notification_read(notification_id, current_user.id)
    if success:
        return jsonify({'success': True})
    return jsonify({'success': False}), 400

@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """모든 알림 읽음 처리"""
    notifications = get_user_notifications(current_user.id, limit=None, unread_only=True)
    
    for notification in notifications:
        mark_notification_read(notification.id, current_user.id)
    
    return jsonify({'success': True, 'count': len(notifications)})

@app.route('/notifications/<int:notification_id>/delete', methods=['POST'])
@login_required
def delete_single_notification(notification_id):
    """개별 알림 삭제"""
    success, message = delete_notification(notification_id, current_user.id)
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'message': message}), 400

@app.route('/notifications/delete-multiple', methods=['POST'])
@login_required
def delete_multiple_notifications_route():
    """여러 알림 일괄 삭제"""
    try:
        data = request.get_json()
        notification_ids = data.get('notification_ids', [])
        
        if not notification_ids:
            return jsonify({'success': False, 'message': '삭제할 알림을 선택해주세요.'}), 400
        
        success, message = delete_multiple_notifications(notification_ids, current_user.id)
        if success:
            return jsonify({'success': True, 'message': message})
        return jsonify({'success': False, 'message': message}), 400
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'오류가 발생했습니다: {str(e)}'}), 500

@app.route('/notifications/test')
@login_required
def test_notifications():
    """테스트 알림 생성 (개발용)"""
    if not current_user.role == '개발자':
        return redirect(url_for('dashboard'))
    
    # 테스트 알림들 생성
    create_notification(
        title="시스템 업데이트 완료",
        message="포인트 시스템이 성공적으로 업데이트되었습니다.",
        notification_type='success',
        priority=2
    )
    
    create_notification(
        title="주간 보고서 준비",
        message="이번 주 아동들의 학습 성과 보고서를 확인해주세요.",
        notification_type='info',
        target_role='센터장',
        priority=1
    )
    
    create_notification(
        title="데이터 백업 필요",
        message="정기 데이터 백업을 진행해주세요.",
        notification_type='warning',
        priority=3,
        auto_expire=True,
        expire_days=3
    )
    
    return redirect(url_for('notifications'))

@app.route('/points/history/<int:child_id>')
@login_required
def points_history(child_id):
    """아동별 포인트 변경 이력 조회"""
    child = Child.query.get_or_404(child_id)
    
    # 최근 30일간의 변경 이력 조회
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.utcnow().date() - timedelta(days=30)
    
    history_records = PointsHistory.query.filter(
        PointsHistory.child_id == child_id,
        PointsHistory.changed_at >= thirty_days_ago
    ).order_by(PointsHistory.changed_at.desc()).all()
    
    return render_template('points/history.html', 
                         child=child, 
                         history_records=history_records)

@app.route('/points/history')
@login_required
def all_points_history():
    """전체 포인트 변경 이력 조회 (관리자용)"""
    # 최근 100건의 변경 이력 조회
    history_records = PointsHistory.query.order_by(PointsHistory.changed_at.desc()).limit(100).all()
    
    return render_template('points/all_history.html', history_records=history_records)

def check_duplicate_daily_points():
    """중복 일일 포인트 기록 검사 및 정리"""
    try:
        print("🔍 중복 일일 포인트 기록 검사 시작...")
        from sqlalchemy import text
        
        result = db.session.execute(text("""
            SELECT child_id, date, COUNT(*) as count
            FROM daily_points 
            GROUP BY child_id, date 
            HAVING COUNT(*) > 1
        """))
        duplicates = result.fetchall()
        
        if not duplicates:
            print("✅ 중복된 일일 포인트 기록이 없습니다.")
            return
        
        print(f"⚠️ {len(duplicates)}개의 중복 기록 발견")
        
        for duplicate in duplicates:
            child_id = duplicate[0]
            date = duplicate[1]
            child = Child.query.get(child_id)
            print(f"  {child.name} - {date}: {duplicate[2]}개 기록")
            
            # 해당 날짜의 모든 기록을 ID 순으로 정렬하여 첫 번째만 남기고 나머지 삭제
            records = DailyPoints.query.filter_by(
                child_id=child_id, 
                date=date
            ).order_by(DailyPoints.id.asc()).all()
            
            for record in records[1:]:  # 첫 번째 제외하고 모두 삭제
                print(f"    삭제: ID {record.id} (총점: {record.total_points})")
                db.session.delete(record)
            
            # 누적 포인트 재계산
            update_cumulative_points(child_id)
        
        db.session.commit()
        print("✅ 중복 기록 정리 완료")
        
    except Exception as e:
        print(f"❌ 중복 기록 검사 오류: {e}")
        db.session.rollback()

def validate_points_integrity():
    """포인트 데이터 무결성 검증 및 자동 수정"""
    try:
        print("🔍 포인트 데이터 무결성 검증 시작...")
        children = Child.query.all()
        fixed_count = 0
        
        for child in children:
            # 해당 아동의 모든 일일 포인트 합계 계산
            calculated_total = db.session.query(
                db.func.sum(DailyPoints.total_points)
            ).filter_by(child_id=child.id).scalar() or 0
            
            if child.cumulative_points != calculated_total:
                print(f"⚠️ {child.name}의 누적 포인트 불일치 발견")
                print(f"  DB: {child.cumulative_points}, 계산: {calculated_total}")
                child.cumulative_points = calculated_total
                fixed_count += 1
        
        if fixed_count > 0:
            db.session.commit()
            print(f"🔧 총 {fixed_count}명의 누적 포인트가 자동으로 수정되었습니다.")
        else:
            print("✅ 모든 포인트 데이터가 정상입니다.")
            
    except Exception as e:
        print(f"❌ 포인트 무결성 검증 오류: {e}")
        db.session.rollback()

# ==================== 백업 시스템 함수들 ====================

def create_backup_directory():
    """백업 디렉토리 생성"""
    backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # 하위 디렉토리들 생성
    subdirs = ['daily', 'monthly', 'realtime', 'database']
    for subdir in subdirs:
        subdir_path = os.path.join(backup_dir, subdir)
        if not os.path.exists(subdir_path):
            os.makedirs(subdir_path)
    
    return backup_dir

def get_backup_data():
    """백업할 데이터 수집"""
    try:
        # 아동 정보
        children = Child.query.all()
        children_data = []
        for child in children:
            child_dict = {
                'id': child.id,
                'name': child.name,
                'grade': child.grade,
                'cumulative_points': child.cumulative_points,
                'created_at': child.created_at.isoformat() if child.created_at else None
            }
            children_data.append(child_dict)
        
        # 일일 포인트 기록
        daily_points = DailyPoints.query.all()
        daily_points_data = []
        for point in daily_points:
            point_dict = {
                'id': point.id,
                'child_id': point.child_id,
                'date': point.date.isoformat() if point.date else None,
                'korean_points': point.korean_points,
                'math_points': point.math_points,
                'ssen_points': point.ssen_points,
                'reading_points': point.reading_points,
                'piano_points': point.piano_points,
                'english_points': point.english_points,
                'advanced_math_points': point.advanced_math_points,
                'writing_points': point.writing_points,
                'manual_points': point.manual_points,
                'manual_history': point.manual_history,
                'total_points': point.total_points,
                'created_by': point.created_by,
                'created_at': point.created_at.isoformat() if point.created_at else None,
                'updated_at': point.updated_at.isoformat() if point.updated_at else None
            }
            daily_points_data.append(point_dict)
        
        # 포인트 히스토리
        points_history = PointsHistory.query.all()
        history_data = []
        for history in points_history:
            history_dict = {
                'id': history.id,
                'child_id': history.child_id,
                'date': history.date.isoformat() if history.date else None,
                'old_korean_points': history.old_korean_points,
                'old_math_points': history.old_math_points,
                'old_ssen_points': history.old_ssen_points,
                'old_reading_points': history.old_reading_points,
                'old_total_points': history.old_total_points,
                'new_korean_points': history.new_korean_points,
                'new_math_points': history.new_math_points,
                'new_ssen_points': history.new_ssen_points,
                'new_reading_points': history.new_reading_points,
                'new_total_points': history.new_total_points,
                'change_type': history.change_type,
                'changed_by': history.changed_by,
                'changed_at': history.changed_at.isoformat() if history.changed_at else None,
                'change_reason': history.change_reason
            }
            history_data.append(history_dict)
        
        # 사용자 정보
        users = User.query.all()
        users_data = []
        for user in users:
            user_dict = {
                'id': user.id,
                'username': user.username,
                'name': user.name,
                'role': user.role,
                'created_at': user.created_at.isoformat() if user.created_at else None
            }
            users_data.append(user_dict)
        
        backup_data = {
            'backup_metadata': {
                'backup_id': datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
                'backup_type': 'manual',
                'timestamp': datetime.now().isoformat(),
                'data_version': '1.0.0',
                'records_count': {
                    'children': len(children_data),
                    'daily_points': len(daily_points_data),
                    'points_history': len(history_data),
                    'users': len(users_data)
                }
            },
            'children': children_data,
            'daily_points': daily_points_data,
            'points_history': history_data,
            'users': users_data
        }
        
        return backup_data, None
        
    except Exception as e:
        return None, str(e)

def create_json_backup(backup_data, backup_dir, backup_type='manual'):
    """JSON 형태로 백업 생성"""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        
        if backup_type == 'daily':
            filename = f"{datetime.now().strftime('%Y-%m-%d')}_{timestamp.split('_')[1]}.json"
            filepath = os.path.join(backup_dir, 'daily', filename)
        elif backup_type == 'monthly':
            filename = f"{datetime.now().strftime('%Y-%m')}_archive.json"
            filepath = os.path.join(backup_dir, 'monthly', filename)
        else:
            filename = f"{timestamp}.json"
            filepath = os.path.join(backup_dir, 'realtime', filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        return filepath, None
        
    except Exception as e:
        return None, str(e)

def create_excel_backup(backup_data, backup_dir, backup_type='manual'):
    """Excel 형태로 백업 생성"""
    if not BACKUP_EXCEL_AVAILABLE:
        print("❌ Excel 백업을 위한 패키지가 설치되지 않았습니다.")
        return None, "pandas 또는 openpyxl 패키지가 설치되지 않았습니다."
    
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        
        if backup_type == 'daily':
            filename = f"{datetime.now().strftime('%Y-%m-%d')}_{timestamp.split('_')[1]}.xlsx"
            filepath = os.path.join(backup_dir, 'daily', filename)
        elif backup_type == 'monthly':
            filename = f"{datetime.now().strftime('%Y-%m')}_archive.xlsx"
            filepath = os.path.join(backup_dir, 'monthly', filename)
        else:
            filename = f"{timestamp}.xlsx"
            filepath = os.path.join(backup_dir, 'realtime', filename)
        
        # Excel 워크북 생성
        wb = Workbook()
        
        # 아동 정보 시트
        ws_children = wb.active
        ws_children.title = "아동정보"
        ws_children.append(['ID', '이름', '학년', '누적포인트', '생성일'])
        
        for child in backup_data['children']:
            ws_children.append([
                child['id'],
                child['name'],
                child['grade'],
                child['cumulative_points'],
                child['created_at']
            ])
        
        # 포인트 기록 시트
        ws_points = wb.create_sheet("포인트기록")
        ws_points.append(['ID', '아동ID', '날짜', '국어', '수학', '쎈수학', '독서', '피아노', '영어', '고학년수학', '쓰기', '수동포인트', '수동히스토리', '총점', '입력자', '생성일'])
        
        for point in backup_data['daily_points']:
            ws_points.append([
                point['id'],
                point['child_id'],
                point['date'],
                point['korean_points'],
                point['math_points'],
                point['ssen_points'],
                point['reading_points'],
                point.get('piano_points', 0),
                point.get('english_points', 0),
                point.get('advanced_math_points', 0),
                point.get('writing_points', 0),
                point.get('manual_points', 0),
                point.get('manual_history', '[]'),
                point['total_points'],
                point['created_by'],
                point['created_at']
            ])
        
        # 포인트 히스토리 시트
        ws_history = wb.create_sheet("포인트변경이력")
        ws_history.append(['ID', '아동ID', '날짜', '변경타입', '변경자', '변경일', '변경사유'])
        
        for history in backup_data['points_history']:
            ws_history.append([
                history['id'],
                history['child_id'],
                history['date'],
                history['change_type'],
                history['changed_by'],
                history['changed_at'],
                history['change_reason']
            ])
        
        # 사용자 정보 시트
        ws_users = wb.create_sheet("사용자정보")
        ws_users.append(['ID', '사용자명', '이름', '권한', '생성일'])
        
        for user in backup_data['users']:
            ws_users.append([
                user['id'],
                user['username'],
                user['name'],
                user['role'],
                user['created_at']
            ])
        
        # 메타데이터 시트
        ws_meta = wb.create_sheet("백업메타데이터")
        meta = backup_data['backup_metadata']
        ws_meta.append(['백업ID', meta['backup_id']])
        ws_meta.append(['백업타입', meta['backup_type']])
        ws_meta.append(['백업시간', meta['timestamp']])
        ws_meta.append(['데이터버전', meta['data_version']])
        ws_meta.append(['아동수', meta['records_count']['children']])
        ws_meta.append(['포인트기록수', meta['records_count']['daily_points']])
        ws_meta.append(['변경이력수', meta['records_count']['points_history']])
        ws_meta.append(['사용자수', meta['records_count']['users']])
        
        # 스타일 적용
        for ws in [ws_children, ws_points, ws_history, ws_users, ws_meta]:
            for row in ws.iter_rows(min_row=1, max_row=1):
                for cell in row:
                    cell.font = Font(bold=True)
                    cell.alignment = Alignment(horizontal='center')
        
        # 파일 저장
        wb.save(filepath)
        
        return filepath, None
        
    except Exception as e:
        return None, str(e)

def realtime_backup(child_id, action_type):
    """실시간 백업 실행 (포인트 입력 시)"""
    try:
        # 백업 디렉토리 생성
        backup_dir = create_backup_directory()
        
        # 백업 데이터 수집
        backup_data, error = get_backup_data()
        if error:
            error_msg = f"실시간 백업 데이터 수집 실패: {error}"
            print(f"❌ {error_msg}")
            create_backup_notification('실시간', 'failed', error_msg)
            return False
        
        # JSON 백업 생성
        json_path, error = create_json_backup(backup_data, backup_dir, 'realtime')
        if error:
            error_msg = f"실시간 JSON 백업 생성 실패: {error}"
            print(f"❌ {error_msg}")
            create_backup_notification('실시간', 'failed', error_msg)
            return False
        
        # Excel 백업 생성
        excel_path, error = create_excel_backup(backup_data, backup_dir, 'realtime')
        if error:
            error_msg = f"실시간 Excel 백업 생성 실패: {error}"
            print(f"❌ {error_msg}")
            create_backup_notification('실시간', 'failed', error_msg)
            return False
        
        success_msg = f"실시간 백업 완료 - {action_type}: {os.path.basename(json_path)}, {os.path.basename(excel_path)}"
        print(f"✅ {success_msg}")
        create_backup_notification('실시간', 'success', success_msg)
        return True
        
    except Exception as e:
        error_msg = f"실시간 백업 실행 중 오류: {str(e)}"
        print(f"❌ {error_msg}")
        create_backup_notification('실시간', 'failed', error_msg)
        return False

def create_database_backup(backup_dir, backup_type='manual'):
    """데이터베이스 파일 백업"""
    try:
        # 현재 DB 파일 경로
        db_path = os.path.join(os.path.dirname(__file__), 'instance', 'child_center.db')
        
        if not os.path.exists(db_path):
            return None, "데이터베이스 파일을 찾을 수 없습니다"
        
        # 백업 파일명
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_filename = f"{datetime.now().strftime('%Y-%m-%d')}_{timestamp.split('_')[1]}_{backup_type}.db"
        backup_path = os.path.join(backup_dir, 'database', backup_filename)
        
        # 파일 복사
        shutil.copy2(db_path, backup_path)
        
        return backup_path, None
        
    except Exception as e:
        return None, str(e)

# 스케줄 백업 시스템
def daily_backup():
    """일일 백업 실행 (매일 22시)"""
    try:
        print("🔄 일일 백업 시작...")
        
        # Flask 앱 컨텍스트 내에서 실행
        with app.app_context():
            # 백업 디렉토리 생성
            backup_dir = create_backup_directory()
        
            # 백업 데이터 수집
            backup_data, error = get_backup_data()
            if error:
                error_msg = f"일일 백업 데이터 수집 실패: {error}"
                print(f"❌ {error_msg}")
                create_backup_notification('일일', 'failed', error_msg)
                return False
        
            # JSON 백업 생성
            json_path, error = create_json_backup(backup_data, backup_dir, 'daily')
            if error:
                error_msg = f"일일 JSON 백업 생성 실패: {error}"
                print(f"❌ {error_msg}")
                create_backup_notification('일일', 'failed', error_msg)
                return False
        
            # Excel 백업 생성
            excel_path, error = create_excel_backup(backup_data, backup_dir, 'daily')
            if error:
                error_msg = f"일일 Excel 백업 생성 실패: {error}"
                print(f"❌ {error_msg}")
                create_backup_notification('일일', 'failed', error_msg)
                return False
        
            # 데이터베이스 백업 생성
            db_path, error = create_database_backup(backup_dir, 'daily')
            if error:
                error_msg = f"일일 데이터베이스 백업 생성 실패: {error}"
                print(f"❌ {error_msg}")
                create_backup_notification('일일', 'failed', error_msg)
                return False
        
            success_msg = f"일일 백업 완료: {os.path.basename(json_path)}, {os.path.basename(excel_path)}, {os.path.basename(db_path)}"
            print(f"✅ {success_msg}")
            create_backup_notification('일일', 'success', success_msg)
            return True
        
    except Exception as e:
        error_msg = f"일일 백업 실행 중 오류: {str(e)}"
        print(f"❌ {error_msg}")
        create_backup_notification('일일', 'failed', error_msg)
        return False

def monthly_backup():
    """월간 백업 실행 (매월 마지막 날 23시)"""
    try:
        print("🔄 월간 백업 시작...")
        
        # Flask 앱 컨텍스트 내에서 실행
        with app.app_context():
            # 백업 디렉토리 생성
            backup_dir = create_backup_directory()
        
            # 백업 데이터 수집
            backup_data, error = get_backup_data()
            if error:
                error_msg = f"월간 백업 데이터 수집 실패: {error}"
                print(f"❌ {error_msg}")
                create_backup_notification('월간', 'failed', error_msg)
            return False
        
            # JSON 백업 생성
            json_path, error = create_json_backup(backup_data, backup_dir, 'monthly')
            if error:
                error_msg = f"월간 JSON 백업 생성 실패: {error}"
                print(f"❌ {error_msg}")
                create_backup_notification('월간', 'failed', error_msg)
                return False
        
            # Excel 백업 생성
            excel_path, error = create_excel_backup(backup_data, backup_dir, 'monthly')
            if error:
                error_msg = f"월간 Excel 백업 생성 실패: {error}"
                print(f"❌ {error_msg}")
                create_backup_notification('월간', 'failed', error_msg)
                return False
        
            # 데이터베이스 백업 생성
            db_path, error = create_database_backup(backup_dir, 'monthly')
            if error:
                error_msg = f"월간 데이터베이스 백업 생성 실패: {error}"
                print(f"❌ {error_msg}")
                create_backup_notification('월간', 'failed', error_msg)
                return False
        
            success_msg = f"월간 백업 완료: {os.path.basename(json_path)}, {os.path.basename(excel_path)}, {os.path.basename(db_path)}"
            print(f"✅ {success_msg}")
            create_backup_notification('월간', 'success', success_msg)
            return True
        
    except Exception as e:
        error_msg = f"월간 백업 실행 중 오류: {str(e)}"
        print(f"❌ {error_msg}")
        create_backup_notification('월간', 'failed', error_msg)
        return False

def run_scheduler():
    """스케줄러 실행 함수"""
    try:
        # 일일 백업 스케줄 (매일 22시)
        schedule.every().day.at("22:00").do(daily_backup)
        
        # 월간 백업 체크 함수 (매일 23시에 월의 마지막 날인지 확인)
        def check_monthly_backup():
            now = datetime.now()
            # 오늘이 월의 마지막 날이고 23시인지 확인
            last_day_of_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            if now.day == last_day_of_month.day and now.hour == 23:
                monthly_backup()
        
        schedule.every().day.at("23:00").do(check_monthly_backup)
        
        print("✅ 스케줄 백업 시스템 시작됨")
        print("   - 일일 백업: 매일 22:00")
        print("   - 월간 백업: 매월 마지막 날 23:00")
        
        # 스케줄러 루프 실행
        while True:
            schedule.run_pending()
            time.sleep(60)  # 1분마다 체크
            
    except Exception as e:
        print(f"❌ 스케줄러 실행 중 오류: {str(e)}")

def start_backup_scheduler():
    """백그라운드에서 스케줄러 시작"""
    try:
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        print("✅ 백업 스케줄러가 백그라운드에서 시작되었습니다.")
    except Exception as e:
        print(f"❌ 백업 스케줄러 시작 실패: {str(e)}")

@app.route('/backup/manual', methods=['POST'])
@login_required
def backup_manual():
    """수동 백업 실행"""
    if current_user.role != '개발자':
        flash('개발자만 백업을 실행할 수 있습니다.', 'error')
        return redirect(url_for('settings_data'))
    
    try:
        # 백업 디렉토리 생성
        backup_dir = create_backup_directory()
        
        # 백업 데이터 수집
        backup_data, error = get_backup_data()
        if error:
            error_msg = f'백업 데이터 수집 실패: {error}'
            flash(error_msg, 'error')
            create_backup_notification('수동', 'failed', error_msg)
            return redirect(url_for('settings_data'))
        
        # JSON 백업 생성
        json_path, error = create_json_backup(backup_data, backup_dir, 'manual')
        if error:
            error_msg = f'JSON 백업 생성 실패: {error}'
            flash(error_msg, 'error')
            create_backup_notification('수동', 'failed', error_msg)
            return redirect(url_for('settings_data'))
        
        # Excel 백업 생성
        excel_path, error = create_excel_backup(backup_data, backup_dir, 'manual')
        if error:
            error_msg = f'Excel 백업 생성 실패: {error}'
            flash(error_msg, 'error')
            create_backup_notification('수동', 'failed', error_msg)
            return redirect(url_for('settings_data'))
        
        # 데이터베이스 백업 생성
        db_path, error = create_database_backup(backup_dir, 'manual')
        if error:
            error_msg = f'데이터베이스 백업 생성 실패: {error}'
            flash(error_msg, 'error')
            create_backup_notification('수동', 'failed', error_msg)
            return redirect(url_for('settings_data'))
        
        success_msg = f'백업이 완료되었습니다. JSON: {os.path.basename(json_path)}, Excel: {os.path.basename(excel_path)}, DB: {os.path.basename(db_path)}'
        flash(success_msg, 'success')
        create_backup_notification('수동', 'success', success_msg)
        return redirect(url_for('settings_data'))
        
    except Exception as e:
        error_msg = f'백업 실행 중 오류 발생: {str(e)}'
        flash(error_msg, 'error')
        create_backup_notification('수동', 'failed', error_msg)
        return redirect(url_for('settings_data'))

@app.route('/backup/list')
@login_required
def backup_list():
    """백업 파일 목록 조회"""
    if current_user.role != '개발자':
        flash('개발자만 백업 목록을 조회할 수 있습니다.', 'error')
        return redirect(url_for('settings_data'))
    
    try:
        backup_dir = create_backup_directory()
        
        # 백업 파일 목록 조회
        backups = []
        if os.path.exists(backup_dir):
            for filename in os.listdir(backup_dir):
                if filename.endswith(('.json', '.xlsx', '.db')):
                    file_path = os.path.join(backup_dir, filename)
                    file_stat = os.stat(file_path)
                    
                    # 파일 타입 추출
                    if 'realtime' in filename:
                        backup_type = 'realtime'
                    elif 'daily' in filename:
                        backup_type = 'daily'
                    elif 'monthly' in filename:
                        backup_type = 'monthly'
                    elif 'manual' in filename:
                        backup_type = 'manual'
                    else:
                        backup_type = 'unknown'
                    
                    # 크기를 MB로 변환
                    size_mb = round(file_stat.st_size / (1024 * 1024), 2)
                    
                    backups.append({
                        'filename': filename,
                        'type': backup_type,
                        'size_mb': size_mb,
                        'created_at': datetime.fromtimestamp(file_stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                        'filepath': file_path,
                        'restore_safe': True  # 기본적으로 복구 가능으로 설정
                    })
        
        # 최신 파일부터 정렬
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        
        return render_template('backup/list.html', backups=backups)
        
    except Exception as e:
        flash(f'백업 목록 조회 실패: {str(e)}', 'error')
        return redirect(url_for('settings_data'))

@app.route('/backup/status')
@login_required
def backup_status():
    """백업 상태 및 목록 조회 (JSON API)"""
    if current_user.role != '개발자':
        return jsonify({'error': '개발자만 접근할 수 있습니다.'}), 403
    
    try:
        backup_dir = create_backup_directory()
        
        # 백업 파일 목록 조회 (모든 하위 디렉토리 포함)
        backups = []
        if os.path.exists(backup_dir):
            # 루트 디렉토리 검색
            for filename in os.listdir(backup_dir):
                if filename.endswith(('.json', '.xlsx', '.db')):
                    file_path = os.path.join(backup_dir, filename)
                    file_stat = os.stat(file_path)
                    
                    # 크기를 MB로 변환
                    size_mb = round(file_stat.st_size / (1024 * 1024), 2)
                    
                    backups.append({
                        'filename': filename,
                        'size_mb': size_mb,
                        'created_at': datetime.fromtimestamp(file_stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
                    })
            
            # 하위 디렉토리들 검색
            subdirs = ['realtime', 'daily', 'monthly', 'database']
            for subdir in subdirs:
                subdir_path = os.path.join(backup_dir, subdir)
                if os.path.exists(subdir_path):
                    for filename in os.listdir(subdir_path):
                        if filename.endswith(('.json', '.xlsx', '.db')):
                            file_path = os.path.join(subdir_path, filename)
                            file_stat = os.stat(file_path)
                            
                            # 크기를 MB로 변환
                            size_mb = round(file_stat.st_size / (1024 * 1024), 2)
                            
                            backups.append({
                                'filename': f"{subdir}/{filename}",
                                'size_mb': size_mb,
                                'created_at': datetime.fromtimestamp(file_stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
                            })
        
        # 최신 파일부터 정렬
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        
        return jsonify({
            'backups': backups,
            'total_count': len(backups),
            'backup_dir': backup_dir
        })
        
    except Exception as e:
        return jsonify({'error': f'백업 상태 조회 실패: {str(e)}'}), 500

if __name__ == '__main__':
    # Firebase 초기화
    initialize_firebase()
    
    # 백업 스케줄러 시작
    start_backup_scheduler()
    
    # init_db() 제거 - 서버 재시작 시 데이터 초기화 방지
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
else:
    # 배포된 환경에서도 데이터베이스 초기화
    with app.app_context():
        # Firebase 초기화
        initialize_firebase()
        
        db.create_all()
        # 기본 사용자가 없으면 생성 (한 번만) - Firebase 사용 시 임시 비활성화
        # if not User.query.filter_by(username='center_head').first():
        #     # init_db() 제거 - 실제 데이터 보호
        #     pass
    
    # 배포 환경에서도 백업 스케줄러 시작
    start_backup_scheduler()