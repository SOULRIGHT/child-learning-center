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
    
    # 2. daily_backup 함수의 with 블록 내부
    {
        'pattern': r'^        # 백업 디렉토리 생성$',
        'context_before': r'with app\.app_context\(\):',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - 백업 디렉토리 생성',
        'max_matches': 1,
    },
    {
        'pattern': r'^        backup_dir = create_backup_directory\(\)$',
        'context_before': r'# 백업 디렉토리 생성',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - backup_dir 생성',
        'max_matches': 1,
    },
    {
        'pattern': r'^        # 백업 데이터 수집$',
        'context_before': r'backup_dir = create_backup_directory\(\)',
        'indent_change': +4,
        'description': 'daily_backup with 블록 - 백업 데이터 수집 주석',
        'max_matches': 1,
    },
    {
        'pattern': r'^        backup_data, error = get_backup_data\(\)$',
        'context_before': r'# 백업 데이터 수집',
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
    
    # 3. JSON/Excel/DB 백업 생성 블록들
    {
        'pattern': r'^        # JSON 백업 생성$',
        'context_before': r'return False',
        'context_after': r'json_path, error = create_json_backup',
        'indent_change': +4,
        'description': 'JSON 백업 생성 주석',
        'max_matches': 2,  # daily_backup과 monthly_backup 둘 다
    },
    {
        'pattern': r'^        json_path, error = create_json_backup\(backup_data, backup_dir, \'(daily|monthly)\'\)$',
        'context_before': r'# JSON 백업 생성',
        'indent_change': +4,
        'description': 'JSON 백업 생성 함수 호출',
        'max_matches': 2,
    },
    {
        'pattern': r'^        if error:$',
        'context_before': r'json_path, error = create_json_backup',
        'context_after': r'error_msg = f"(일일|월간) JSON 백업 생성 실패',
        'indent_change': +4,
        'description': 'JSON 백업 에러 체크',
        'max_matches': 2,
    },
    {
        'pattern': r'^        # Excel 백업 생성$',
        'context_after': r'excel_path, error = create_excel_backup',
        'indent_change': +4,
        'description': 'Excel 백업 생성 주석',
        'max_matches': 2,
    },
    {
        'pattern': r'^        excel_path, error = create_excel_backup\(backup_data, backup_dir, \'(daily|monthly)\'\)$',
        'context_before': r'# Excel 백업 생성',
        'indent_change': +4,
        'description': 'Excel 백업 생성 함수 호출',
        'max_matches': 2,
    },
    {
        'pattern': r'^        if error:$',
        'context_before': r'excel_path, error = create_excel_backup',
        'context_after': r'error_msg = f"(일일|월간) Excel 백업 생성 실패',
        'indent_change': +4,
        'description': 'Excel 백업 에러 체크',
        'max_matches': 2,
    },
    {
        'pattern': r'^        # 데이터베이스 백업 생성$',
        'context_after': r'db_path, error = create_database_backup',
        'indent_change': +4,
        'description': 'DB 백업 생성 주석',
        'max_matches': 2,
    },
    {
        'pattern': r'^        db_path, error = create_database_backup\(backup_dir, \'(daily|monthly)\'\)$',
        'context_before': r'# 데이터베이스 백업 생성',
        'indent_change': +4,
        'description': 'DB 백업 생성 함수 호출',
        'max_matches': 2,
    },
    {
        'pattern': r'^        if error:$',
        'context_before': r'db_path, error = create_database_backup',
        'context_after': r'error_msg = f"(일일|월간) 데이터베이스 백업 생성 실패',
        'indent_change': +4,
        'description': 'DB 백업 에러 체크',
        'max_matches': 2,
    },
    {
        'pattern': r'^        success_msg = f"(일일|월간) 백업 완료:',
        'context_before': r'return False',
        'indent_change': +4,
        'description': '백업 성공 메시지',
        'max_matches': 2,
    },
    {
        'pattern': r'^        return True$',
        'context_before': r'create_backup_notification',
        'indent_change': +4,
        'description': '백업 함수 return True',
        'max_matches': 2,
    },
    
    # 4. monthly_backup 함수의 with 블록
    {
        'pattern': r'^        # 백업 디렉토리 생성$',
        'context_before': r'월간 백업 시작',
        'indent_change': +4,
        'description': 'monthly_backup with 블록 - 백업 디렉토리 생성',
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