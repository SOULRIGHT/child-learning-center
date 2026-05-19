#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Firebase Authentication 설정 및 유틸리티
"""

import firebase_admin
from firebase_admin import auth, credentials
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def initialize_firebase():
    """Firebase Admin SDK 초기화 - 환경변수 기반"""
    if not firebase_admin._apps:
        try:
            # 환경변수에서 Firebase 서비스 계정 키 가져오기
            firebase_credentials_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
            
            if firebase_credentials_json:
                print("🔍 환경변수에서 Firebase 서비스 계정 정보 로드 중...")
                print(f"📝 JSON 길이: {len(firebase_credentials_json)} 문자")
                
                # JSON 문자열을 딕셔너리로 변환
                try:
                    cred_dict = json.loads(firebase_credentials_json)
                    print("✅ JSON 파싱 성공")
                    cred = credentials.Certificate(cred_dict)
                except json.JSONDecodeError as e:
                    print(f"❌ JSON 파싱 오류: {e}")
                    print(f"📄 JSON 내용 (처음 100자): {firebase_credentials_json[:100]}...")
                    raise Exception(f"JSON 파싱 실패: {e}")
            else:
                print("⚠️ FIREBASE_CREDENTIALS_JSON 환경변수가 설정되지 않음")
                # 로컬 개발용 서비스 계정 파일 사용 (개발 환경에서만)
                service_account_path = os.path.join(os.path.dirname(__file__), 'firebase-service-account.json')
                if os.path.exists(service_account_path):
                    print("📁 로컬 서비스 계정 파일 사용")
                    cred = credentials.Certificate(service_account_path)
                else:
                    raise Exception("Firebase 서비스 계정 키를 찾을 수 없습니다. 환경변수 FIREBASE_CREDENTIALS_JSON을 설정하세요.")
            
            firebase_admin.initialize_app(cred)
            print("✅ Firebase Admin SDK 초기화 완료")
            return firebase_admin.get_app()
            
        except Exception as e:
            print(f"❌ Firebase 초기화 실패: {e}")
            return None
    
    return firebase_admin.get_app()

def verify_firebase_token(token):
    """Firebase ID 토큰 검증"""
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        print(f"Firebase token verification failed: {e}")
        return None

def get_user_role_from_email(email):
    """이메일을 기반으로 사용자 역할 결정"""
    print(f"🐛 DEBUG: get_user_role_from_email 호출됨!")
    print(f"🐛 DEBUG: 입력 이메일: '{email}'")
    
    if not email:
        print("🐛 DEBUG: 이메일이 없음 → 일반사용자")
        return '일반사용자'
    
    email_lower = email.lower()
    print(f"🐛 DEBUG: 소문자 변환: '{email_lower}'")
    
    # 이메일 패턴 기반 역할 매핑
    if 'viewer' in email_lower or 'studentview' in email_lower or '열람' in email_lower:
        print(f"🐛 DEBUG: VIEWER 매칭! → 학생열람")
        return '학생열람'
    elif 'center' in email_lower or '센터장' in email_lower:
        print(f"🐛 DEBUG: CENTER 매칭! → 센터장")
        return '센터장'
    elif 'teacher' in email_lower or '선생님' in email_lower:
        print(f"🐛 DEBUG: TEACHER 매칭! → 돌봄선생님")
        return '돌봄선생님'
    elif 'sowo' in email_lower or '사회복무' in email_lower:
        print(f"🐛 DEBUG: SOWO 매칭!")
        # 숫자 패턴으로 구분
        if '1' in email_lower:
            print(f"🐛 DEBUG: 숫자 1 발견 → 사회복무요원1")
            return '사회복무요원1'
        elif '2' in email_lower:
            print(f"🐛 DEBUG: 숫자 2 발견 → 사회복무요원2")
            return '사회복무요원2'
        elif '3' in email_lower:
            print(f"🐛 DEBUG: 숫자 3 발견 → 사회복무요원3")
            return '사회복무요원3'
        else:
            print(f"🐛 DEBUG: 기본 사회복무요원")
            return '사회복무요원'
    elif 'dev' in email_lower or '개발자' in email_lower:
        print(f"🐛 DEBUG: DEV 매칭! → 개발자")
        return '개발자'
    else:
        print(f"🐛 DEBUG: 모든 패턴 실패 → 일반사용자")
        print(f"🐛 DEBUG: 체크 결과 - dev in email: {'dev' in email_lower}")
        return '일반사용자'

def create_firebase_user(email, password, display_name=None):
    """Firebase에 새 사용자 생성 (관리자용)"""
    try:
        user = auth.create_user(
            email=email,
            password=password,
            display_name=display_name or email.split('@')[0]
        )
        print(f"✅ Firebase 사용자 생성 완료: {email}")
        return user
    except Exception as e:
        print(f"❌ Firebase 사용자 생성 실패: {e}")
        return None

def delete_firebase_user(uid):
    """Firebase 사용자 삭제 (관리자용)"""
    try:
        auth.delete_user(uid)
        print(f"✅ Firebase 사용자 삭제 완료: {uid}")
        return True
    except Exception as e:
        print(f"❌ Firebase 사용자 삭제 실패: {e}")
        return False

def list_firebase_users():
    """Firebase 사용자 목록 조회 (관리자용)"""
    try:
        users = []
        for user in auth.list_users().iterate():
            users.append({
                'uid': user.uid,
                'email': user.email,
                'display_name': user.display_name,
                'created_at': user.user_metadata.creation_timestamp,
                'last_sign_in': user.user_metadata.last_sign_in_timestamp
            })
        return users
    except Exception as e:
        print(f"❌ Firebase 사용자 목록 조회 실패: {e}")
        return []

# Firebase 설정 정보 (프론트엔드용) - 환경변수 기반
FIREBASE_CONFIG = {
    "apiKey": os.environ.get('FIREBASE_API_KEY', ''),
    "authDomain": os.environ.get('FIREBASE_AUTH_DOMAIN', 'your-project.firebaseapp.com'),
    "projectId": os.environ.get('FIREBASE_PROJECT_ID', 'your-project-id'),
    "storageBucket": os.environ.get('FIREBASE_STORAGE_BUCKET', 'your-project.firebasestorage.app'),
    "messagingSenderId": os.environ.get('FIREBASE_MESSAGING_SENDER_ID', ''),
    "appId": os.environ.get('FIREBASE_APP_ID', ''),
    "measurementId": os.environ.get('FIREBASE_MEASUREMENT_ID', '')  # Analytics용 (선택사항)
}
