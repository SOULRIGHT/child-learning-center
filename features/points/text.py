"""분류용 문자열 정규화. DB 원문 raw_subject/raw_reason은 바꾸지 않는다."""
from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r'\s+')
# lookup 키용. 문장 전체를 이어붙이지 않도록 공백·괄호만 제거한다.
_COMPACT = re.compile(r'[\s()[\]{}（）【】〔〕]+')


def normalize_lookup(value):
    if value is None:
        return ''
    text = unicodedata.normalize('NFKC', str(value)).strip().casefold()
    return _WHITESPACE.sub(' ', text)


def compact_lookup(value):
    return _COMPACT.sub('', normalize_lookup(value))
