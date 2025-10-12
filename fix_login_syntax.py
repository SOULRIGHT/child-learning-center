#!/usr/bin/env python3
"""
로그인 함수의 문법 오류 수정
"""

def fix_login_function():
    """로그인 함수의 들여쓰기 및 중복 else 수정"""
    
    with open('app.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 695번 라인의 들여쓰기 수정 (login_user 함수)
    if len(lines) > 694:
        lines[694] = '            login_user(user)\n'  # 12칸 들여쓰기
    
    # 706번 라인의 중복 else 제거
    if len(lines) > 705:
        if lines[705].strip() == 'else:':
            lines[705] = '        else:\n'  # 8칸 들여쓰기로 변경
    
    # 707번 라인 이후 들여쓰기 수정
    if len(lines) > 706:
        lines[706] = '            # === 🛡️ 로그인 실패 시 실패 기록 ===\n'  # 12칸
    if len(lines) > 707:
        lines[707] = '            is_now_blocked = record_failed_login(client_ip)\n'  # 12칸
    if len(lines) > 708:
        lines[708] = '            if is_now_blocked:\n'  # 12칸
    if len(lines) > 709:
        lines[709] = '                flash(\'⚠️ 연속된 로그인 실패로 인해 30분간 로그인이 제한됩니다.\', \'error\')\n'  # 16칸
    if len(lines) > 710:
        lines[710] = '            else:\n'  # 12칸
    if len(lines) > 711:
        lines[711] = '                flash(\'Firebase 인증에 실패했습니다.\', \'error\')\n'  # 16칸
    if len(lines) > 712:
        lines[712] = '            \n'  # 빈 줄
    if len(lines) > 713:
        lines[713] = '            if request.is_json:\n'  # 12칸
    if len(lines) > 714:
        lines[714] = '                return jsonify({\'success\': False, \'error\': \'Invalid Firebase token\'})\n'  # 16칸
    
    with open('app.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("✅ 로그인 함수 문법 오류 수정 완료!")

if __name__ == "__main__":
    fix_login_function()

