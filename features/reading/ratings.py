"""ChildReading 체감 난이도·재미. Book AI 난이도와 별개이며 보상에 쓰지 않는다."""

RATING_MIN = 1
RATING_MAX = 5


def parse_optional_rating(raw):
    """빈 값은 None. 그 외는 정수 1~5만 허용. 실패 시 ValueError('invalid_rating')."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        raise ValueError('invalid_rating')
    if isinstance(raw, int):
        if RATING_MIN <= raw <= RATING_MAX:
            return raw
        raise ValueError('invalid_rating')
    if isinstance(raw, float):
        raise ValueError('invalid_rating')
    text = str(raw).strip()
    if text == '':
        return None
    if text[0] == '-' or not text.isdigit():
        raise ValueError('invalid_rating')
    value = int(text)
    if value < RATING_MIN or value > RATING_MAX:
        raise ValueError('invalid_rating')
    return value
