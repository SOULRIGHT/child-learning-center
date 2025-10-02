#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
들여쓰기 자동 수정 스크립트 (패턴 매칭 기반)

줄 번호 대신 실제 코드 패턴을 찾아서 수정하므로,
코드가 추가/삭제되어도 안전하게 작동합니다.
"""

import os
import re
import sys

# ==============================================================================
# 수정 목록 정의 (패턴 기반)
# 각 항목: {
#   'pattern': 찾을 코드 패턴 (정규식 가능),
#   'context': 주변 컨텍스트 (더 정확한 매칭을 위해),
#   'indent_change': 들여쓰기 변화량,
#   'description': 설명
# }
# ==============================================================================

MODIFICATIONS = [
    # 1. Firebase 로그인 else 블록 들여쓰기 감소
    {
        'pattern': r'^            else:$',  # 12칸 들여쓰기된 else
        'context_before': r'return redirect\(url_for\(\'dashboard\'\)\)',
        'indent_change': -4,
        'description': 'Firebase 로그인 else 블록 들여쓰기 감소',
        'max_matches': 1,
    },
    
    # 2. 실시간 백업 함수의 with 블록 내부 (realtime_backup)
    {
        'pattern': r'^        # 백업 디렉토리 생성$',
        'context_before': r'def realtime_backup\(child_id, action\):',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - 백업 디렉토리 생성',
        'max_matches': 1,
    },
    {
        'pattern': r'^        backup_dir = create_backup_directory\(\)$',
        'context_before': r'# 백업 디렉토리 생성',
        'context_after': r'# 백업 데이터 수집',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - backup_dir 생성',
        'max_matches': 1,
    },
    {
        'pattern': r'^        # 백업 데이터 수집$',
        'context_before': r'backup_dir = create_backup_directory\(\)',
        'context_after': r'backup_data, error = get_backup_data\(\)',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - 백업 데이터 수집 주석',
        'max_matches': 1,
    },
    {
        'pattern': r'^        backup_data, error = get_backup_data\(\)$',
        'context_before': r'# 백업 데이터 수집',
        'context_after': r'if error:',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - get_backup_data 호출',
        'max_matches': 1,
    },
    {
        'pattern': r'^        if error:$',
        'context_before': r'backup_data, error = get_backup_data\(\)',
        'context_after': r'error_msg = f"실시간 백업 데이터 수집 실패',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - error 체크',
        'max_matches': 1,
    },
    {
        'pattern': r'^            error_msg = f"실시간 백업 데이터 수집 실패: \{error\}"$',
        'context_before': r'if error:',
        'context_after': r'print\(f"❌ \{error_msg\}"\)',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - error_msg 설정',
        'max_matches': 1,
    },
    {
        'pattern': r'^            print\(f"❌ \{error_msg\}"\)$',
        'context_before': r'error_msg = f"실시간 백업 데이터 수집 실패',
        'context_after': r'create_backup_notification',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - print 에러',
        'max_matches': 1,
    },
    {
        'pattern': r'^            create_backup_notification\(\'실시간\', \'failed\', error_msg\)$',
        'context_before': r'print\(f"❌ \{error_msg\}"\)',
        'context_after': r'return False',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - create_backup_notification',
        'max_matches': 1,
    },
    {
        'pattern': r'^            return False$',
        'context_before': r'create_backup_notification\(\'실시간\', \'failed\', error_msg\)',
        'context_after': r'# JSON 백업 생성',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - return False',
        'max_matches': 1,
    },
    {
        'pattern': r'^        # JSON 백업 생성$',
        'context_before': r'return False',
        'context_after': r'json_path, error = create_json_backup',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - JSON 백업 생성 주석',
        'max_matches': 1,
    },
    {
        'pattern': r'^        json_path, error = create_json_backup\(backup_data, backup_dir, \'realtime\'\)$',
        'context_before': r'# JSON 백업 생성',
        'context_after': r'if error:',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - JSON 백업 생성 함수 호출',
        'max_matches': 1,
    },
    {
        'pattern': r'^        if error:$',
        'context_before': r'json_path, error = create_json_backup\(backup_data, backup_dir, \'realtime\'\)',
        'context_after': r'error_msg = f"실시간 JSON 백업 생성 실패',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - JSON 백업 에러 체크',
        'max_matches': 1,
    },
    {
        'pattern': r'^            error_msg = f"실시간 JSON 백업 생성 실패: \{error\}"$',
        'context_before': r'if error:',
        'context_after': r'print\(f"❌ \{error_msg\}"\)',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - JSON 백업 error_msg',
        'max_matches': 1,
    },
    {
        'pattern': r'^            print\(f"❌ \{error_msg\}"\)$',
        'context_before': r'error_msg = f"실시간 JSON 백업 생성 실패',
        'context_after': r'create_backup_notification',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - JSON 백업 print 에러',
        'max_matches': 1,
    },
    {
        'pattern': r'^            create_backup_notification\(\'실시간\', \'failed\', error_msg\)$',
        'context_before': r'print\(f"❌ \{error_msg\}"\)',
        'context_after': r'return False',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - JSON 백업 create_backup_notification',
        'max_matches': 1,
    },
    {
        'pattern': r'^            return False$',
        'context_before': r'create_backup_notification\(\'실시간\', \'failed\', error_msg\)',
        'context_after': r'# Excel 백업 생성',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - JSON 백업 return False',
        'max_matches': 1,
    },
    {
        'pattern': r'^        # Excel 백업 생성$',
        'context_before': r'return False',
        'context_after': r'excel_path, error = create_excel_backup',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - Excel 백업 생성 주석',
        'max_matches': 1,
    },
    {
        'pattern': r'^        excel_path, error = create_excel_backup\(backup_data, backup_dir, \'realtime\'\)$',
        'context_before': r'# Excel 백업 생성',
        'context_after': r'if error:',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - Excel 백업 생성 함수 호출',
        'max_matches': 1,
    },
    {
        'pattern': r'^        if error:$',
        'context_before': r'excel_path, error = create_excel_backup\(backup_data, backup_dir, \'realtime\'\)',
        'context_after': r'error_msg = f"실시간 Excel 백업 생성 실패',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - Excel 백업 에러 체크',
        'max_matches': 1,
    },
    {
        'pattern': r'^            error_msg = f"실시간 Excel 백업 생성 실패: \{error\}"$',
        'context_before': r'if error:',
        'context_after': r'print\(f"❌ \{error_msg\}"\)',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - Excel 백업 error_msg',
        'max_matches': 1,
    },
    {
        'pattern': r'^            print\(f"❌ \{error_msg\}"\)$',
        'context_before': r'error_msg = f"실시간 Excel 백업 생성 실패',
        'context_after': r'create_backup_notification',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - Excel 백업 print 에러',
        'max_matches': 1,
    },
    {
        'pattern': r'^            create_backup_notification\(\'실시간\', \'failed\', error_msg\)$',
        'context_before': r'print\(f"❌ \{error_msg\}"\)',
        'context_after': r'return False',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - Excel 백업 create_backup_notification',
        'max_matches': 1,
    },
    {
        'pattern': r'^            return False$',
        'context_before': r'create_backup_notification\(\'실시간\', \'failed\', error_msg\)',
        'context_after': r'# 데이터베이스 백업 생성',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - Excel 백업 return False',
        'max_matches': 1,
    },
    {
        'pattern': r'^        # 데이터베이스 백업 생성$',
        'context_before': r'return False',
        'context_after': r'db_path, error = create_database_backup',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - DB 백업 생성 주석',
        'max_matches': 1,
    },
    {
        'pattern': r'^        db_path, error = create_database_backup\(backup_dir, \'realtime\'\)$',
        'context_before': r'# 데이터베이스 백업 생성',
        'context_after': r'if error:',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - DB 백업 생성 함수 호출',
        'max_matches': 1,
    },
    {
        'pattern': r'^        if error:$',
        'context_before': r'db_path, error = create_database_backup\(backup_dir, \'realtime\'\)',
        'context_after': r'error_msg = f"실시간 데이터베이스 백업 생성 실패',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - DB 백업 에러 체크',
        'max_matches': 1,
    },
    {
        'pattern': r'^            error_msg = f"실시간 데이터베이스 백업 생성 실패: \{error\}"$',
        'context_before': r'if error:',
        'context_after': r'print\(f"❌ \{error_msg\}"\)',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - DB 백업 error_msg',
        'max_matches': 1,
    },
    {
        'pattern': r'^            print\(f"❌ \{error_msg\}"\)$',
        'context_before': r'error_msg = f"실시간 데이터베이스 백업 생성 실패',
        'context_after': r'create_backup_notification',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - DB 백업 print 에러',
        'max_matches': 1,
    },
    {
        'pattern': r'^            create_backup_notification\(\'실시간\', \'failed\', error_msg\)$',
        'context_before': r'print\(f"❌ \{error_msg\}"\)',
        'context_after': r'return False',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - DB 백업 create_backup_notification',
        'max_matches': 1,
    },
    {
        'pattern': r'^            return False$',
        'context_before': r'create_backup_notification\(\'실시간\', \'failed\', error_msg\)',
        'context_after': r'success_msg = f"실시간 백업 완료',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - DB 백업 return False',
        'max_matches': 1,
    },
    {
        'pattern': r'^        success_msg = f"실시간 백업 완료:',
        'context_before': r'return False',
        'context_after': r'print\(f"✅ \{success_msg\}"\)',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - success_msg',
        'max_matches': 1,
    },
    {
        'pattern': r'^        print\(f"✅ \{success_msg\}"\)$',
        'context_before': r'success_msg = f"실시간 백업 완료',
        'context_after': r'create_backup_notification',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - print 성공',
        'max_matches': 1,
    },
    {
        'pattern': r'^        create_backup_notification\(\'실시간\', \'success\', success_msg\)$',
        'context_before': r'print\(f"✅ \{success_msg\}"\)',
        'context_after': r'return True',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - create_backup_notification 성공',
        'max_matches': 1,
    },
    {
        'pattern': r'^        return True$',
        'context_before': r'create_backup_notification\(\'실시간\', \'success\', success_msg\)',
        'indent_change': +4,
        'description': 'realtime_backup with 블록 - return True',
        'max_matches': 1,
    },
    
    # 3. daily_backup 함수의 with 블록 내부
    {
        'pattern': r'^        # 백업 디렉토리 생성$',
        'context_before': r'def daily_backup\(\):',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - 백업 디렉토리 생성',
        'max_matches': 1,
    },
    {
        'pattern': r'^        backup_dir = create_backup_directory\(\)$',
        'context_before': r'# 백업 디렉토리 생성',
        'context_after': r'# 백업 데이터 수집',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - backup_dir 생성',
        'max_matches': 1,
    },
    {
        'pattern': r'^        # 백업 데이터 수집$',
        'context_before': r'backup_dir = create_backup_directory\(\)',
        'context_after': r'backup_data, error = get_backup_data\(\)',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - 백업 데이터 수집 주석',
        'max_matches': 1,
    },
    {
        'pattern': r'^        backup_data, error = get_backup_data\(\)$',
        'context_before': r'# 백업 데이터 수집',
        'context_after': r'if error:',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - get_backup_data 호출',
        'max_matches': 1,
    },
    {
        'pattern': r'^        if error:$',
        'context_before': r'backup_data, error = get_backup_data\(\)',
        'context_after': r'error_msg = f"일일 백업 데이터 수집 실패',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - error 체크',
        'max_matches': 1,
    },
    
    # 4. JSON/Excel/DB 백업 생성 블록들 (daily_backup)
    {
        'pattern': r'^        # JSON 백업 생성$',
        'context_before': r'return False',
        'context_after': r'json_path, error = create_json_backup',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - JSON 백업 생성 주석',
        'max_matches': 1,
    },
    {
        'pattern': r'^        json_path, error = create_json_backup\(backup_data, backup_dir, \'daily\'\)$',
        'context_before': r'# JSON 백업 생성',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - JSON 백업 생성 함수 호출',
        'max_matches': 1,
    },
    {
        'pattern': r'^        if error:$',
        'context_before': r'json_path, error = create_json_backup\(backup_data, backup_dir, \'daily\'\)',
        'context_after': r'error_msg = f"일일 JSON 백업 생성 실패',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - JSON 백업 에러 체크',
        'max_matches': 1,
    },
    {
        'pattern': r'^        # Excel 백업 생성$',
        'context_after': r'excel_path, error = create_excel_backup',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - Excel 백업 생성 주석',
        'max_matches': 1,
    },
    {
        'pattern': r'^        excel_path, error = create_excel_backup\(backup_data, backup_dir, \'daily\'\)$',
        'context_before': r'# Excel 백업 생성',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - Excel 백업 생성 함수 호출',
        'max_matches': 1,
    },
    {
        'pattern': r'^        if error:$',
        'context_before': r'excel_path, error = create_excel_backup\(backup_data, backup_dir, \'daily\'\)',
        'context_after': r'error_msg = f"일일 Excel 백업 생성 실패',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - Excel 백업 에러 체크',
        'max_matches': 1,
    },
    {
        'pattern': r'^        # 데이터베이스 백업 생성$',
        'context_after': r'db_path, error = create_database_backup',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - DB 백업 생성 주석',
        'max_matches': 1,
    },
    {
        'pattern': r'^        db_path, error = create_database_backup\(backup_dir, \'daily\'\)$',
        'context_before': r'# 데이터베이스 백업 생성',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - DB 백업 생성 함수 호출',
        'max_matches': 1,
    },
    {
        'pattern': r'^        if error:$',
        'context_before': r'db_path, error = create_database_backup\(backup_dir, \'daily\'\)',
        'context_after': r'error_msg = f"일일 데이터베이스 백업 생성 실패',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - DB 백업 에러 체크',
        'max_matches': 1,
    },
    {
        'pattern': r'^        success_msg = f"일일 백업 완료:',
        'context_before': r'return False',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - success_msg',
        'max_matches': 1,
    },
    {
        'pattern': r'^        return True$',
        'context_before': r'create_backup_notification',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - return True',
        'max_matches': 1,
    },
    
    # 5. monthly_backup 함수의 with 블록
    {
        'pattern': r'^        # 백업 디렉토리 생성$',
        'context_before': r'월간 백업 시작',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - 백업 디렉토리 생성',
        'max_matches': 1,
    },
    {
        'pattern': r'^        backup_dir = create_backup_directory\(\)$',
        'context_before': r'# 백업 디렉토리 생성',
        'context_after': r'# 백업 데이터 수집',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - backup_dir 생성',
        'max_matches': 1,
    },
    {
        'pattern': r'^        # 백업 데이터 수집$',
        'context_before': r'backup_dir = create_backup_directory\(\)',
        'context_after': r'backup_data, error = get_backup_data\(\)',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - 백업 데이터 수집 주석',
        'max_matches': 1,
    },
    {
        'pattern': r'^        backup_data, error = get_backup_data\(\)$',
        'context_before': r'# 백업 데이터 수집',
        'context_after': r'if error:',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - get_backup_data 호출',
        'max_matches': 1,
    },
    {
        'pattern': r'^        if error:$',
        'context_before': r'backup_data, error = get_backup_data\(\)',
        'context_after': r'error_msg = f"월간 백업 데이터 수집 실패',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - error 체크',
        'max_matches': 1,
    },
    {
        'pattern': r'^        # JSON 백업 생성$',
        'context_before': r'return False',
        'context_after': r'json_path, error = create_json_backup',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - JSON 백업 생성 주석',
        'max_matches': 1,
    },
    {
        'pattern': r'^        json_path, error = create_json_backup\(backup_data, backup_dir, \'monthly\'\)$',
        'context_before': r'# JSON 백업 생성',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - JSON 백업 생성 함수 호출',
        'max_matches': 1,
    },
    {
        'pattern': r'^        if error:$',
        'context_before': r'json_path, error = create_json_backup\(backup_data, backup_dir, \'monthly\'\)',
        'context_after': r'error_msg = f"월간 JSON 백업 생성 실패',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - JSON 백업 에러 체크',
        'max_matches': 1,
    },
    {
        'pattern': r'^        # Excel 백업 생성$',
        'context_after': r'excel_path, error = create_excel_backup',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - Excel 백업 생성 주석',
        'max_matches': 1,
    },
    {
        'pattern': r'^        excel_path, error = create_excel_backup\(backup_data, backup_dir, \'monthly\'\)$',
        'context_before': r'# Excel 백업 생성',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - Excel 백업 생성 함수 호출',
        'max_matches': 1,
    },
    {
        'pattern': r'^        if error:$',
        'context_before': r'excel_path, error = create_excel_backup\(backup_data, backup_dir, \'monthly\'\)',
        'context_after': r'error_msg = f"월간 Excel 백업 생성 실패',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - Excel 백업 에러 체크',
        'max_matches': 1,
    },
    {
        'pattern': r'^        # 데이터베이스 백업 생성$',
        'context_after': r'db_path, error = create_database_backup',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - DB 백업 생성 주석',
        'max_matches': 1,
    },
    {
        'pattern': r'^        db_path, error = create_database_backup\(backup_dir, \'monthly\'\)$',
        'context_before': r'# 데이터베이스 백업 생성',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - DB 백업 생성 함수 호출',
        'max_matches': 1,
    },
    {
        'pattern': r'^        if error:$',
        'context_before': r'db_path, error = create_database_backup\(backup_dir, \'monthly\'\)',
        'context_after': r'error_msg = f"월간 데이터베이스 백업 생성 실패',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - DB 백업 에러 체크',
        'max_matches': 1,
    },
    {
        'pattern': r'^        success_msg = f"월간 백업 완료:',
        'context_before': r'return False',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - success_msg',
        'max_matches': 1,
    },
    {
        'pattern': r'^        return True$',
        'context_before': r'create_backup_notification',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - return True',
        'max_matches': 1,
    },
]


def find_line_with_context(lines, pattern, context_before=None, context_after=None, start_from=0):
    """컨텍스트를 고려하여 패턴이 일치하는 줄 찾기"""
    pattern_re = re.compile(pattern)
    context_before_re = re.compile(context_before) if context_before else None
    context_after_re = re.compile(context_after) if context_after else None
    
    for i in range(start_from, len(lines)):
        if pattern_re.match(lines[i]):
            # context_before 체크
            if context_before_re:
                found_before = False
                for j in range(max(0, i-10), i):  # 이전 10줄 이내 검색
                    if context_before_re.search(lines[j]):
                        found_before = True
                        break
                if not found_before:
                    continue
            
            # context_after 체크
            if context_after_re:
                found_after = False
                for j in range(i+1, min(len(lines), i+11)):  # 이후 10줄 이내 검색
                    if context_after_re.search(lines[j]):
                        found_after = True
                        break
                if not found_after:
                    continue
            
            return i
    
    return -1


def fix_indentation(file_path):
    """들여쓰기 자동 수정 함수"""
    
    INDENT_SIZE = 4
    INDENT_STR = ' ' * INDENT_SIZE

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f'❌ 파일 읽기 실패: {file_path}를 찾을 수 없습니다.')
        return False
    except Exception as e:
        print(f'❌ 파일 읽기 중 오류 발생: {e}')
        return False

    original_content = content
    lines = content.split('\n')
    
    modified_line_count = 0
    modification_details = []

    # 정의된 수정 목록 적용
    for mod in MODIFICATIONS:
        pattern = mod['pattern']
        context_before = mod.get('context_before')
        context_after = mod.get('context_after')
        indent_change = mod['indent_change']
        description = mod.get('description', 'N/A')
        max_matches = mod.get('max_matches', 1)
        
        matches_found = 0
        search_start = 0
        
        while matches_found < max_matches:
            line_index = find_line_with_context(
                lines, pattern, context_before, context_after, search_start
            )
            
            if line_index == -1:
                break
            
            line = lines[line_index]
            
            # 빈 줄은 수정하지 않음
            if not line.strip():
                search_start = line_index + 1
                continue
            
            new_line = line
            
            # 들여쓰기 증가
            if indent_change > 0:
                indent_count = indent_change // INDENT_SIZE
                new_line = INDENT_STR * indent_count + line
            
            # 들여쓰기 감소
            elif indent_change < 0:
                indent_count = (-indent_change) // INDENT_SIZE
                expected_indent = INDENT_STR * indent_count
                
                if line.startswith(expected_indent):
                    new_line = line[len(expected_indent):]
                else:
                    current_indent = len(line) - len(line.lstrip(' '))
                    if current_indent > 0:
                        remove_count = min(current_indent, -indent_change)
                        new_line = line[remove_count:]
            
            if new_line != line:
                lines[line_index] = new_line
                modified_line_count += 1
                modification_details.append(
                    f'  ✓ {line_index + 1}번 줄: {description} ({indent_change:+d}칸)'
                )
                matches_found += 1
            
            search_start = line_index + 1
        
        if matches_found == 0:
            print(f'⚠️  패턴 미발견: {description}')
    
    # 수정된 내용 합치기
    content = '\n'.join(lines)
    
    # === 🔧 추가 수정: 중복된 else 블록 제거 ===
    lines = content.split('\n')
    modified = False
    
    # Firebase 로그인의 중복된 else 블록 찾기 및 제거
    for i in range(len(lines)):
        if i > 0 and lines[i].strip() == 'else:':
            # 이전 줄에 else가 있는지 확인
            for j in range(max(0, i-5), i):
                if lines[j].strip() == 'else:':
                    # 중복된 else 발견
                    # 다음 줄의 들여쓰기가 잘못된 경우 수정
                    if i + 1 < len(lines) and lines[i+1].strip():
                        # flash 문장이 있는 경우 들여쓰기 수정
                        if 'flash' in lines[i+1]:
                            # 현재 들여쓰기 확인
                            current_indent = len(lines[i+1]) - len(lines[i+1].lstrip(' '))
                            # 12칸으로 수정
                            lines[i+1] = '            ' + lines[i+1].strip()
                    # 중복된 else 라인 제거
                    lines.pop(i)
                    modified = True
                    modified_line_count += 1
                    modification_details.append(
                        f'  ✓ {i + 1}번 줄: 중복된 else 블록 제거'
                    )
                    break
    
    if modified:
        content = '\n'.join(lines)
    
    # === 🔧 추가 수정: realtime_backup 함수의 과도한 들여쓰기 수정 ===
    lines = content.split('\n')
    in_realtime_backup = False
    in_try_block = False
    modified = False
    
    for i in range(len(lines)):
        line = lines[i]
        
        # realtime_backup 함수 시작 감지
        if 'def realtime_backup(' in line:
            in_realtime_backup = True
            in_try_block = False
            continue
        
        # 다음 함수 시작 시 종료
        if in_realtime_backup and line.strip().startswith('def ') and 'realtime_backup' not in line:
            in_realtime_backup = False
            in_try_block = False
            continue
        
        # try 블록 시작
        if in_realtime_backup and line.strip() == 'try:':
            in_try_block = True
            continue
        
        # except 블록 시작 시 try 블록 종료
        if in_realtime_backup and in_try_block and line.strip().startswith('except '):
            in_try_block = False
            continue
        
        # try 블록 내부에서 12칸 들여쓰기를 8칸으로 수정
        if in_realtime_backup and in_try_block:
            if line.startswith('            ') and not line.startswith('                '):  # 정확히 12칸
                # 8칸으로 변경
                lines[i] = '        ' + line[12:]
                modified = True
                modified_line_count += 1
                modification_details.append(
                    f'  ✓ {i + 1}번 줄: realtime_backup try 블록 들여쓰기 수정 (12칸 -> 8칸)'
                )
    
    if modified:
        content = '\n'.join(lines)
    
    # 변경사항이 있는지 확인
    if content != original_content:
        # 백업 생성
        backup_path = file_path + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        print(f'📁 백업 생성: {backup_path}')
        
        # 수정된 내용 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f'✅ 들여쓰기 수정 완료: {file_path}')
        print(f'📊 수정된 줄 수: {modified_line_count}개\n')
        
        # 상세 수정 내역 출력
        if modification_details:
            print(f'📝 수정 내역:')
            for detail in modification_details:
                print(detail)
        
        return True
    else:
        print(f'ℹ️  수정할 내용 없음: {file_path}')
        return False


def main():
    """메인 함수"""
    print('='*70)
    print('들여쓰기 자동 수정 스크립트 (패턴 매칭 기반 - 안전 모드)')
    print('='*70)
    print('✨ 줄 번호가 아닌 코드 패턴으로 찾아서 수정합니다.')
    print('✨ 코드가 추가/삭제되어도 안전하게 작동합니다.\n')
    
    # 수정할 파일 목록
    files_to_fix = ['app.py']
    
    for file_path in files_to_fix:
        print(f'🔧 처리 중: {file_path}\n')
        fix_indentation(file_path)
    
    print('\n' + '='*70)
    print('완료!')
    print('='*70)
    print('\n💡 권장: 수정 후 Python 문법을 검사하세요:')
    print('   python -m py_compile app.py')


if __name__ == '__main__':
    main()