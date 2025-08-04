import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from sqlalchemy import func # Added for func.date

# 환경 변수 로드
load_dotenv()

# Flask 앱 생성
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# 데이터베이스 설정
if os.environ.get('DATABASE_URL'):
    # Railway 또는 프로덕션 환경
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
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

# 데이터베이스 모델
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    login_attempts = db.Column(db.Integer, default=0)
    last_attempt = db.Column(db.DateTime)

class Child(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 관계 설정
    learning_records = db.relationship('LearningRecord', backref='child', lazy=True, cascade='all, delete-orphan')
    notes = db.relationship('ChildNote', backref='child', lazy=True, cascade='all, delete-orphan')
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
    
    # 총 포인트
    total_points = db.Column(db.Integer, default=0)
    
    # 메타데이터
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계 설정
    child = db.relationship('Child', backref='daily_points', lazy=True)
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

# 데이터베이스 초기화 함수
def init_db():
    with app.app_context():
        # 기존 테이블 삭제 후 재생성 (스키마 변경 반영)
        db.drop_all()
        db.create_all()
        
        # 기본 사용자 계정 생성
        default_users = [
            {'username': 'developer', 'name': '개발자', 'role': '개발자', 'password': 'dev123'},
            {'username': 'center_head', 'name': '센터장', 'role': '센터장', 'password': 'center123!'},
            {'username': 'care_teacher', 'name': '돌봄선생님', 'role': '돌봄선생님', 'password': 'care123!'},
            {'username': 'social_worker1', 'name': '사회복무요원1', 'role': '사회복무요원', 'password': 'social123!'},
            {'username': 'social_worker2', 'name': '사회복무요원2', 'role': '사회복무요원', 'password': 'social456!'},
            {'username': 'assistant', 'name': '보조교사', 'role': '보조교사', 'password': 'assist123!'},
            {'username': 'test_user', 'name': '테스트사용자', 'role': '테스트사용자', 'password': 'test_kohi'}
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
        
        # 테스트용 아동 데이터 추가
        test_children = [
            Child(name='김철수', grade=3, include_in_stats=True),
            Child(name='박영희', grade=3, include_in_stats=True),
            Child(name='이민수', grade=4, include_in_stats=True),
            Child(name='최지영', grade=4, include_in_stats=False),  # 통계 제외 예시
        ]
        
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
                total_points = korean_points + math_points + ssen_points + reading_points
                
                # 일부 날짜는 기록 없음 (더 현실적인 데이터)
                if random.random() > 0.3:  # 70% 확률로 기록 생성
                    daily_point = DailyPoints(
                        child_id=child_id,
                        date=current_date,
                        korean_points=korean_points,
                        math_points=math_points,
                        ssen_points=ssen_points,
                        reading_points=reading_points,
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user:
            # 로그인 시도 횟수 확인
            if user.login_attempts >= 5:
                if user.last_attempt and (datetime.utcnow() - user.last_attempt).seconds < 900:  # 15분 잠금
                    flash('로그인 시도 횟수를 초과했습니다. 15분 후 다시 시도해주세요.', 'error')
                    return render_template('login.html')
                else:
                    # 잠금 시간 해제
                    user.login_attempts = 0
                    db.session.commit()
            
            if check_password_hash(user.password_hash, password):
                # 로그인 성공
                user.login_attempts = 0
                user.last_attempt = None
                db.session.commit()
                login_user(user)
                flash(f'{user.name}님, 환영합니다!', 'success')
                return redirect(url_for('dashboard'))
            else:
                # 로그인 실패
                user.login_attempts += 1
                user.last_attempt = datetime.utcnow()
                db.session.commit()
                flash('아이디 또는 비밀번호가 잘못되었습니다.', 'error')
        else:
            flash('아이디 또는 비밀번호가 잘못되었습니다.', 'error')
    
    return render_template('login.html')

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
        weekly_avg_points = round(total_weekly_points / len(weekly_points), 1)
    else:
        weekly_avg_points = 0
    
    # 이번 주 포인트 참여율 계산
    weekly_participants = db.session.query(DailyPoints.child_id).filter(
        DailyPoints.date >= week_start,
        DailyPoints.date <= week_end
    ).distinct().count()
    
    if total_children > 0:
        participation_rate = round((weekly_participants / total_children) * 100, 1)
    else:
        participation_rate = 0
    
    # 최근 포인트 기록 (최근 10개)
    recent_records = db.session.query(DailyPoints, Child).join(Child).order_by(DailyPoints.created_at.desc()).limit(10).all()
    
    # ====== [과목별 주간 평균 포인트 계산] ======
    weekly_korean_avg = 0
    weekly_math_avg = 0
    weekly_reading_avg = 0
    weekly_total_points = 0
    
    if weekly_points:
        # 과목별 평균 계산
        korean_points = [record.korean_points for record in weekly_points if record.korean_points > 0]
        math_points = [record.math_points for record in weekly_points if record.math_points > 0]
        reading_points = [record.reading_points for record in weekly_points if record.reading_points > 0]
        
        weekly_korean_avg = round(sum(korean_points) / len(korean_points), 1) if korean_points else 0
        weekly_math_avg = round(sum(math_points) / len(math_points), 1) if math_points else 0
        weekly_reading_avg = round(sum(reading_points) / len(reading_points), 1) if reading_points else 0
        
        # 주간 총 포인트
        weekly_total_points = sum(record.total_points for record in weekly_points)
    
    # ====== [알림 시스템 임시 비활성화] ======
    notifications = []
    # TODO: 나중에 알림 로직 재구현
    # 현재는 빈 리스트 반환
    
    return render_template('dashboard.html', 
                         today_points_children=today_points_children,
                         total_children=total_children,
                         weekly_avg_points=weekly_avg_points,
                         participation_rate=participation_rate,
                         recent_records=recent_records,
                         notifications=notifications,
                         weekly_korean_avg=weekly_korean_avg,
                         weekly_math_avg=weekly_math_avg,
                         weekly_reading_avg=weekly_reading_avg,
                         weekly_total_points=weekly_total_points)

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
    if current_user.role not in ['센터장', '돌봄선생님']:
        flash('아동 삭제 권한이 없습니다.', 'error')
        return redirect(url_for('children_list'))
    
    try:
        # 관련 기록들도 함께 삭제됨 (cascade 설정)
        db.session.delete(child)
        db.session.commit()
        
        flash(f'{child_name} 아동과 관련 기록이 모두 삭제되었습니다.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('삭제 중 오류가 발생했습니다. 다시 시도해주세요.', 'error')
    
    return redirect(url_for('children_list'))

@app.route('/children/<int:child_id>')
@login_required
def child_detail(child_id):
    child = Child.query.get_or_404(child_id)
    
    # 최근 학습 기록들
    recent_records = LearningRecord.query.filter_by(child_id=child_id)\
                                         .order_by(LearningRecord.date.desc())\
                                         .limit(10).all()
    
    # 최근 특이사항들
    recent_notes = ChildNote.query.filter_by(child_id=child_id)\
                                  .order_by(ChildNote.created_at.desc())\
                                  .limit(5).all()
    
    # 통계 계산
    if recent_records:
        # 최근 5개 기록의 평균
        recent_avg = sum(record.total_score for record in recent_records[:5]) / min(len(recent_records), 5)
        
        # 가장 최근 기록
        latest_record = recent_records[0] if recent_records else None
    else:
        recent_avg = 0
        latest_record = None
    
    return render_template('children/detail.html', 
                         child=child,
                         recent_records=recent_records,
                         recent_notes=recent_notes,
                         recent_avg=recent_avg,
                         latest_record=latest_record)

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
            math_problems_solved = int(request.form.get('math_problems_solved', 0))
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
    if current_user.role not in ['센터장', '돌봄선생님']:
        flash('점수 기록 삭제 권한이 없습니다.', 'error')
        return redirect(url_for('child_detail', child_id=child_id))
    
    try:
        db.session.delete(record)
        db.session.commit()
        flash(f'{child_name} 아동의 {record.date.strftime("%Y-%m-%d")} 학습 기록이 삭제되었습니다.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('삭제 중 오류가 발생했습니다. 다시 시도해주세요.', 'error')
    
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
    # 최근 입력된 포인트들
    points_records = DailyPoints.query.order_by(DailyPoints.date.desc()).limit(20).all()
    return render_template('points/list.html', points_records=points_records)

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
        
        # 포인트 값 가져오기
        korean_points = int(request.form.get('korean_points', 0))
        math_points = int(request.form.get('math_points', 0))
        ssen_points = int(request.form.get('ssen_points', 0))
        reading_points = int(request.form.get('reading_points', 0))
        
        # 총 포인트 계산
        total_points = korean_points + math_points + ssen_points + reading_points
        
        if existing_record:
            # 기존 기록 업데이트
            existing_record.korean_points = korean_points
            existing_record.math_points = math_points
            existing_record.ssen_points = ssen_points
            existing_record.reading_points = reading_points
            existing_record.total_points = total_points
            existing_record.updated_at = datetime.utcnow()
        else:
            # 새 기록 생성
            new_record = DailyPoints(
                child_id=child_id,
                date=today,
                korean_points=korean_points,
                math_points=math_points,
                ssen_points=ssen_points,
                reading_points=reading_points,
                total_points=total_points,
                created_by=current_user.id
            )
            db.session.add(new_record)
        
        db.session.commit()
        flash(f'{child.name} 아이의 포인트가 저장되었습니다.', 'success')
        return redirect(url_for('points_list'))
    
    # 오늘 기록 가져오기
    today = datetime.utcnow().date()
    today_record = DailyPoints.query.filter_by(
        child_id=child_id, 
        date=today
    ).first()
    
    # 오늘 날짜 문자열 계산
    today_date = datetime.utcnow().strftime('%Y년 %m월 %d일')
    
    return render_template('points/input.html', child=child, today_record=today_record, today_date=today_date)

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
    
    # 디버깅: 함수 호출 확인
    print(f"=== points_analysis 함수 호출됨 ===")
    print(f"child_id: {child_id}")
    print(f"request.args: {request.args}")
    print("==================================")
    
    # 데이터베이스 직접 확인
    from sqlalchemy import text
    result = db.session.execute(text("SELECT COUNT(*) as count FROM daily_points WHERE child_id = :child_id"), {"child_id": child_id})
    total_count = result.fetchone()[0]
    print(f"데이터베이스에서 직접 확인한 기록 수: {total_count}")
    
    # 중복 날짜 확인
    result = db.session.execute(text("""
        SELECT date, COUNT(*) as count 
        FROM daily_points 
        WHERE child_id = :child_id 
        GROUP BY date 
        HAVING COUNT(*) > 1
    """), {"child_id": child_id})
    duplicates = result.fetchall()
    if duplicates:
        print("=== 중복된 날짜 발견 ===")
        for date, count in duplicates:
            print(f"날짜: {date}, 중복 횟수: {count}")
        print("========================")
    
    if child_id:
        # 특정 아동 분석
        child = Child.query.get_or_404(child_id)
        
        # 해당 아동의 전체 포인트 기록
        child_points = DailyPoints.query.filter_by(child_id=child_id).order_by(DailyPoints.date.desc()).all()
        
        # 총 포인트 계산
        total_points = sum(record.total_points for record in child_points)
        
        # 디버깅: 실제 데이터 확인
        print(f"=== 김철수 포인트 디버깅 ===")
        print(f"아동 ID: {child_id}")
        print(f"아동 이름: {child.name}")
        print(f"총 기록 수: {len(child_points)}")
        
        # 모든 기록 출력
        for i, record in enumerate(child_points):
            print(f"기록 {i+1}: {record.date} - 총점: {record.total_points} (국어:{record.korean_points}, 수학:{record.math_points}, 쎈:{record.ssen_points}, 독서:{record.reading_points})")
        
        print(f"계산된 총 포인트: {total_points}")
        print("================================")
        
        # 같은 학년 아동들의 포인트 비교
        same_grade_children = Child.query.filter_by(grade=child.grade, include_in_stats=True).all()
        grade_comparison = []
        
        for grade_child in same_grade_children:
            if grade_child.id != child_id:  # 자기 자신 제외
                grade_child_points = DailyPoints.query.filter_by(child_id=grade_child.id).all()
                grade_child_total = sum(record.total_points for record in grade_child_points)
                grade_comparison.append({
                    'id': grade_child.id,
                    'name': grade_child.name,
                    'total_points': grade_child_total,
                    'record_count': len(grade_child_points)
                })
        
        # 학년 내 순위 계산
        grade_comparison.append({
            'id': child.id,
            'name': child.name,
            'total_points': total_points,
            'record_count': len(child_points)
        })
        grade_comparison.sort(key=lambda x: x['total_points'], reverse=True)
        
        # 전체 학년 순위
        all_children = Child.query.filter_by(include_in_stats=True).all()
        overall_ranking = []
        
        for all_child in all_children:
            all_child_points = DailyPoints.query.filter_by(child_id=all_child.id).all()
            all_child_total = sum(record.total_points for record in all_child_points)
            overall_ranking.append({
                'id': all_child.id,
                'name': all_child.name,
                'grade': all_child.grade,
                'total_points': all_child_total,
                'record_count': len(all_child_points)
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
    
    # 1. 주간 트렌드 (최근 4주)
    weekly_data = []
    for i in range(28, -1, -1):  # 최근 28일
        date = today - timedelta(days=i)
        daily_points = DailyPoints.query.filter_by(date=date).all()
        total_points = sum(record.total_points for record in daily_points)
        weekly_data.append({
            'date': date.strftime('%m/%d'),
            'points': total_points
        })
    
    # 2. 월별 합계 (올해 전체)
    monthly_data = []
    for month in range(1, 13):
        month_start = datetime(today.year, month, 1).date()
        if month == 12:
            month_end = datetime(today.year + 1, 1, 1).date() - timedelta(days=1)
        else:
            month_end = datetime(today.year, month + 1, 1).date() - timedelta(days=1)
        
        month_points = DailyPoints.query.filter(
            DailyPoints.date >= month_start,
            DailyPoints.date <= month_end
        ).all()
        total_month_points = sum(record.total_points for record in month_points)
        
        monthly_data.append({
            'month': f'{month}월',
            'points': total_month_points
        })
    
    # 3. 과목별 분포 (전체 기간)
    all_points = DailyPoints.query.all()
    subject_totals = {
        '국어': sum(record.korean_points for record in all_points),
        '수학': sum(record.math_points for record in all_points),
        '쎈수학': sum(record.ssen_points for record in all_points),
        '독서': sum(record.reading_points for record in all_points)
    }
    
    # 4. 학년별 평균
    grade_averages = {}
    for grade_num in [1, 2, 3, 4, 5, 6]:
        grade_str = f'{grade_num}학년'
        grade_children = Child.query.filter_by(grade=grade_num, include_in_stats=True).all()
        if grade_children:
            grade_total_points = 0
            grade_total_records = 0
            
            for child in grade_children:
                child_points = DailyPoints.query.filter_by(child_id=child.id).all()
                grade_total_points += sum(record.total_points for record in child_points)
                grade_total_records += len(child_points)
            
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
            'avg_points': round(total_points / record_count, 1) if record_count > 0 else 0
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
    """포인트 시스템 설정 페이지"""
    return render_template('settings/points.html')

@app.route('/settings/data')
@login_required
def settings_data():
    """데이터 관리 페이지"""
    return render_template('settings/data.html')

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

@app.route('/settings/system')
@login_required
def settings_system():
    """시스템 정보 페이지"""
    return render_template('settings/system.html')


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
else:
    # 배포된 환경에서도 데이터베이스 초기화
    with app.app_context():
        db.create_all()
        # 기본 사용자가 없으면 생성
        if not User.query.filter_by(username='center_head').first():
            init_db()