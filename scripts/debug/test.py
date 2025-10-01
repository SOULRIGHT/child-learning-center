from firebase_config import initialize_firebase
try:
    initialize_firebase()
    print('✅ Firebase 초기화 성공')
except Exception as e:
    print(f'❌ Firebase 초기화 실패: {e}')