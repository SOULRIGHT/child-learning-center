[1mdiff --git a/app.py b/app.py[m
[1mindex 0da1bac..6d91da2 100644[m
[1m--- a/app.py[m
[1m+++ b/app.py[m
[36m@@ -52,6 +52,19 @@[m [mif os.environ.get('DATABASE_URL'):[m
     # Railway 또는 프로덕션 환경[m
     app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')[m
     app.config['SESSION_COOKIE_SECURE'] = True  # 프로덕션에서는 HTTPS 강제[m
[32m+[m[41m    [m
[32m+[m[32m    # 🔧 연결 풀 설정 (간헐적 연결 오류 해결)[m
[32m+[m[32m    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {[m
[32m+[m[32m        'pool_size': 10,           # 기본 연결 풀 크기[m
[32m+[m[32m        'max_overflow': 20,        # 추가 연결 허용[m
[32m+[m[32m        'pool_timeout': 30,        # 연결 대기 시간 (초)[m
[32m+[m[32m        'pool_recycle': 3600,      # 연결 재사용 시간 (1시간)[m
[32m+[m[32m        'pool_pre_ping': True,     # 연결 유효성 사전 검사[m
[32m+[m[32m        'connect_args': {[m
[32m+[m[32m            'connect_timeout': 10,  # 연결 타임아웃[m
[32m+[m[32m            'application_name': 'child-learning-center'[m
[32m+[m[32m        }[m
[32m+[m[32m    }[m
 else:[m
     # 개발 환경 - SQLite 사용[m
     app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///child_center.db'[m
[36m@@ -656,7 +669,7 @@[m [mdef login():[m
                 return jsonify({'success': True, 'redirect': url_for('dashboard')})[m
             else:[m
                 return redirect(url_for('dashboard'))[m
[31m-        else:[m
[32m+[m[32m            else:[m
             # === 🛡️ 로그인 실패 시 실패 기록 ===[m
             is_now_blocked = record_failed_login(client_ip)[m
             if is_now_blocked:[m
[36m@@ -4093,45 +4106,45 @@[m [mdef daily_backup():[m
         [m
         # Flask 앱 컨텍스트 내에서 실행[m
         with app.app_context():[m
[31m-            # 백업 디렉토리 생성[m
[31m-            backup_dir = create_backup_directory()[m
[32m+[m[32m        # 백업 디렉토리 생성[m
[32m+[m[32m        backup_dir = create_backup_directory()[m
         [m
[31m-            # 백업 데이터 수집[m
[31m-            backup_data, error = get_backup_data()[m
[31m-            if error:[m
[32m+[m[32m        # 백업 데이터 수집[m
[32m+[m[32m        backup_data, error = get_backup_data()[m
[32m+[m[32m        if error:[m
                 error_msg = f"일일 백업 데이터 수집 실패: {error}"[m
                 print(f"❌ {error_msg}")[m
                 create_backup_notification('일일', 'failed', error_msg)[m
[31m-                return False[m
[32m+[m[32m            return False[m
         [m
[31m-            # JSON 백업 생성[m
[31m-            json_path, error = create_json_backup(backup_data, backup_dir, 'daily')[m
[31m-            if error:[m
[32m+[m[32m        # JSON 백업 생성[m
[32m+[m[32m        json_path, error = create_json_backup(backup_data, backup_dir, 'daily')[m
[32m+[m[32m        if error:[m
                 error_msg = f"일일 JSON 백업 생성 실패: {error}"[m
                 print(f"❌ {error_msg}")[m
                 create_backup_notification('일일', 'failed', error_msg)[m
[31m-                return False[m
[32m+[m[32m            return False[m
         [m
[31m-            # Excel 백업 생성[m
[31m-            excel_path, error = create_excel_backup(backup_data, backup_dir, 'daily')[m
[31m-            if error:[m
[32m+[m[32m        # Excel 백업 생성[m
[32m+[m[32m        excel_path, error = create_excel_backup(backup_data, backup_dir, 'daily')[m
[32m+[m[32m        if error:[m
                 error_msg = f"일일 Excel 백업 생성 실패: {error}"[m
                 print(f"❌ {error_msg}")[m
                 create_backup_notification('일일', 'failed', error_msg)[m
[31m-                return False[m
[32m+[m[32m            return False[m
         [m
[31m-            # 데이터베이스 백업 생성[m
[31m-            db_path, error = create_database_backup(backup_dir, 'daily')[m
[31m-            if error:[m
[32m+[m[32m        # 데이터베이스 백업 생성[m
[32m+[m[32m        db_path, error = create_database_backup(backup_dir, 'daily')[m
[32m+[m[32m        if error:[m
                 error_msg = f"일일 데이터베이스 백업 생성 실패: {error}"[m
                 print(f"❌ {error_msg}")[m
                 create_backup_notification('일일', 'failed', error_msg)[m
[31m-                return False[m
[32m+[m[32m            return False[m
         [m
             success_msg = f"일일 백업 완료: {os.path.basename(json_path)}, {os.path.basename(excel_path)}, {os.path.basename(db_path)}"[m
             print(f"✅ {success_msg}")[m
             create_backup_notification('일일', 'success', success_msg)[m
[31m-            return True[m
[32m+[m[32m        return True[m
         [m
     except Exception as e:[m
         error_msg = f"일일 백업 실행 중 오류: {str(e)}"[m
[36m@@ -4146,45 +4159,45 @@[m [mdef monthly_backup():[m
         [m
         # Flask 앱 컨텍스트 내에서 실행[m
         with app.app_context():[m
[31m-            # 백업 디렉토리 생성[m
[31m-            backup_dir = create_backup_directory()[m
[32m+[m[32m        # 백업 디렉토리 생성[m
[32m+[m[32m        backup_dir = create_backup_directory()[m
         [m
[31m-            # 백업 데이터 수집[m
[31m-            backup_data, error = get_backup_data()[m
[31m-            if error:[m
[32m+[m[32m        # 백업 데이터 수집[m
[32m+[m[32m        backup_data, error = get_backup_data()[m
[32m+[m[32m        if error:[m
                 error_msg = f"월간 백업 데이터 수집 실패: {error}"[m
                 print(f"❌ {error_msg}")[m
                 create_backup_notification('월간', 'failed', error_msg)[m
             return False[m
         [m
[31m-            # JSON 백업 생성[m
[31m-            json_path, error = create_json_backup(backup_data, backup_dir, 'monthly')[m
[31m-            if error:[m
[32m+[m[32m        # JSON 백업 생성[m
[32m+[m[32m        json_path, error = create_json_backup(backup_data, backup_dir, 'monthly')[m
[32m+[m[32m        if error:[m
                 error_msg = f"월간 JSON 백업 생성 실패: {error}"[m
                 print(f"❌ {error_msg}")[m
                 create_backup_notification('월간', 'failed', error_msg)[m
[31m-                return False[m
[32m+[m[32m            return False[m
         [m
[31m-            # Excel 백업 생성[m
[31m-            excel_path, error = create_excel_backup(backup_data, backup_dir, 'monthly')[m
[31m-            if error:[m
[32m+[m[32m        # Excel 백업 생성[m
[32m+[m[32m        excel_path, error = create_excel_backup(backup_data, backup_dir, 'monthly')[m
[32m+[m[32m        if error:[m
                 error_msg = f"월간 Excel 백업 생성 실패: {error}"[m
                 print(f"❌ {error_msg}")[m
                 create_backup_notification('월간', 'failed', error_msg)[m
[31m-                return False[m
[32m+[m[32m            return False[m
         [m
[31m-            # 데이터베이스 백업 생성[m
[31m-            db_path, error = create_database_backup(backup_dir, 'monthly')[m
[31m-            if error:[m
[32m+[m[32m        # 데이터베이스 백업 생성[m
[32m+[m[32m        db_path, error = create_database_backup(backup_dir, 'monthly')[m
[32m+[m[32m        if error:[m
                 error_msg = f"월간 데이터베이스 백업 생성 실패: {error}"[m
                 print(f"❌ {error_msg}")[m
                 create_backup_notification('월간', 'failed', error_msg)[m
[31m-                return False[m
[32m+[m[32m            return False[m
         [m
             success_msg = f"월간 백업 완료: {os.path.basename(json_path)}, {os.path.basename(excel_path)}, {os.path.basename(db_path)}"