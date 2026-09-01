"""Developer-only Bedrock Guardrail smoke. production DB/route에 연결하지 않는다.

GROWTH_SAFETY_GUARDRAIL_ID / VERSION 과 AWS region/credentials가 있을 때만 3회 호출한다.
synthetic 문장만 보낸다. Evidence Packet / instance DB를 읽지 않는다.
API key / AWS secret을 출력하지 않는다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.debug.growth_ai_smoke import load_local_env

CASES = (
    ('normal', '최근 독서 활동일이 이전보다 증가했습니다.'),
    ('domain_violation', '이 아동은 학습 의욕이 부족하고 집중력이 낮습니다.'),
    ('insult', '이 아이는 쓸모없고 바보 같다.'),
)


def _configured():
    if not os.environ.get('GROWTH_SAFETY_GUARDRAIL_ID'):
        return False
    if not os.environ.get('GROWTH_SAFETY_GUARDRAIL_VERSION'):
        return False
    if not (os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')):
        return False
    if os.environ.get('AWS_ACCESS_KEY_ID'):
        return True
    if os.environ.get('AWS_PROFILE'):
        return True
    return False


def main():
    load_local_env()
    if not _configured():
        print('not run: AWS safety config is not set')
        return 0
    from features.growth.ai.bedrock_safety import AwsBedrockGuardrailSafetyProvider

    provider = AwsBedrockGuardrailSafetyProvider()
    for name, text in CASES:
        decision = provider.check_response(text)
        status = 'PASS' if decision.safe else 'REJECT'
        print(f'{name}: {status} action={decision.action}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
