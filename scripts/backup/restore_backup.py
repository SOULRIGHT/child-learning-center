#!/usr/bin/env python3
"""
간단한 백업 복원 스크립트
사용법: python restore_backup.py [백업파일명]
"""

import os
import sys
import shutil
from datetime import datetime

#!/usr/bin/env python3
"""
간단한 백업 복원 스크립트
사용법: python restore_backup.py [백업파일명]
"""

import os
import sys
import shutil
from datetime import datetime

def create_restore_notification(status, message):
    """복원 알림 생성 (Flask 앱과 연동)"""
    try:
        # Flask 앱 임포트
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from app import app, db, create_restore_notification as create_notification
        
        with app.app_context():
            create_notification(status, message)
            print(f"✅ 복원 알림 생성: {status}")
    except Exception as e:
        print(f"⚠️  알림 생성 실패: {e}")

def restore_backup(backup_filename):
    """백업 파일에서 데이터베이스 복원"""
    
    # 현재 디렉토리 확인
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 백업 파일 경로
    backup_path = os.path.join(current_dir, 'backups', 'database', backup_filename)
    
    # 현재 DB 파일 경로
    current_db = os.path.join(current_dir, 'child_center.db')
    
    # 백업 파일 존재 확인
    if not os.path.exists(backup_path):
        error_msg = f"백업 파일을 찾을 수 없습니다: {backup_path}"
        print(f"❌ {error_msg}")
        create_restore_notification('failed', error_msg)
        return False
    
    # 현재 DB 백업 (안전을 위해)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safety_backup = os.path.join(current_dir, f'child_center_safety_backup_{timestamp}.db')
    
    if os.path.exists(current_db):
        shutil.copy2(current_db, safety_backup)
        print(f"✅ 현재 DB를 안전 백업했습니다: {safety_backup}")
    
    # 복원 실행
    try:
        shutil.copy2(backup_path, current_db)
        success_msg = f"복원 완료: {backup_filename}"
        print(f"✅ {success_msg}")
        print(f"📁 복원된 파일: {current_db}")
        create_restore_notification('success', success_msg)
        return True
        
    except Exception as e:
        error_msg = f"복원 실패: {e}"
        print(f"❌ {error_msg}")
        create_restore_notification('failed', error_msg)
        return False

def list_backups():
    """사용 가능한 백업 파일 목록 표시"""
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups', 'database')
    
    if not os.path.exists(backup_dir):
        print("❌ 백업 디렉토리를 찾을 수 없습니다.")
        return
    
    print("\n📋 사용 가능한 백업 파일:")
    print("-" * 50)
    
    files = [f for f in os.listdir(backup_dir) if f.endswith('.db')]
    files.sort(reverse=True)  # 최신 파일부터
    
    for i, filename in enumerate(files, 1):
        file_path = os.path.join(backup_dir, filename)
        size = os.path.getsize(file_path) / 1024  # KB
        modified = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        print(f"{i:2d}. {filename}")
        print(f"    크기: {size:.1f} KB | 수정일: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
        print()

def main():
    if len(sys.argv) < 2:
        print("🔧 백업 복원 도구")
        print("=" * 50)
        print("사용법:")
        print("  python restore_backup.py [백업파일명]")
        print("  python restore_backup.py --list")
        print()
        
        list_backups()
        return
    
    if sys.argv[1] == '--list':
        list_backups()
        return
    
    backup_filename = sys.argv[1]
    
    # 확인 메시지
    print(f"⚠️  백업 파일 '{backup_filename}'에서 복원하시겠습니까?")
    print("   현재 데이터가 백업으로 덮어써집니다!")
    confirm = input("   계속하려면 'yes'를 입력하세요: ")
    
    if confirm.lower() != 'yes':
        print("❌ 복원이 취소되었습니다.")
        return
    
    # 복원 실행
    if restore_backup(backup_filename):
        print("\n🎉 복원이 완료되었습니다!")
        print("💡 서버를 재시작하면 변경사항이 적용됩니다.")
    else:
        print("\n❌ 복원에 실패했습니다.")

if __name__ == "__main__":
    main()
