"""Deterministic synthetic books/reviews for Growth development seed.

실존 센터 추천 목록(2-3 100권, 4-6 17권)은 운영에서 쓸 제목/저자 그대로 둔다.
일반/도전 도서는 가상 제목이다. 아동 개인정보는 넣지 않는다.

이 모듈은 catalog / theme / voice / review 문장만 둔다.
DB query, seed 선택 로직, Growth insight 로직은 두지 않는다.
"""
from __future__ import annotations

import hashlib

AUTHORS = (
    '김하늘', '이서윤', '박도현', '최유진', '정민재',
    '윤가은', '한지우', '오세린', '강민호', '문예진',
)

RECOMMENDED_23 = [
    ('동물농장', '조지 오웰'),
    ('걸리버 여행기', '조너선 스위프트'),
    ('좁은 문', '앙드레 지드'),
    ('돈 키호테', '미겔 데 세르반테스'),
    ('죄와 벌', '표도르 도스토옙스키'),
    ('정글북', '러디어드 키플링'),
    ('지킬박사와 하이드', '로버트 루이스 스티븐슨'),
    ('전쟁과 평화', '레프 톨스토이'),
    ('지구에서 달까지', '쥘 베른'),
    ('허클베리 핀의 모험', '마크 트웨인'),
    ('비밀의 화원', '프랜시스 호지슨 버넷'),
    ('이상한 나라의 엘리스', '루이스 캐럴'),
    ('아큐정전', '루쉰'),
    ('변신', '프란츠 카프카'),
    ('레 미제라블', '빅토르 위고'),
    ('어머니', '막심 고리키'),
    ('오즈의 마법사', 'L. 프랭크 바움'),
    ('허풍선이 남작의 모험', '고트프리트 아우구스트 뷔르거'),
    ('도련님', '나쓰메 소세키'),
    ('제인 에어', '샬럿 브론테'),
    ('올리버 트위스트', '찰스 디킨스'),
    ('피터 팬', '제임스 매슈 배리'),
    ('위대한 개츠비', 'F. 스콧 피츠제럴드'),
    ('닐스의 이상한 모험', '셀마 라게를뢰프'),
    ('오만과 편견', '제인 오스틴'),
    ('로빈슨 크루소', '대니얼 디포'),
    ('홍당무', '쥘 르나르'),
    ('타임머신', '허버트 조지 웰스'),
    ('파우스트', '요한 볼프강 폰 괴테'),
    ('파랑새', '모리스 마테를링크'),
    ('톰 아저씨의 오두막', '해리엇 비처 스토'),
    ('폭풍의 언덕', '에밀리 브론테'),
    ('작은 아씨들', '루이자 메이 올컷'),
    ('알프스 소녀 하이디', '요하나 슈피리'),
    ('크리스마스 캐럴', '찰스 디킨스'),
    ('보물섬', '로버트 루이스 스티븐슨'),
    ('톰 소여의 모험', '마크 트웨인'),
    ('80간의 세계일주', '쥘 베른'),
    ('사람은 무엇으로 사는가', '레프 톨스토이'),
    ('안네의 일기', '안네 프랑크'),
    ('어린 왕자', '앙투안 드 생텍쥐페리'),
    ('꼬마 철학자', '알퐁스 도데'),
    ('장 크리스토프', '로맹 롤랑'),
    ('오페라의 유령', '가스통 르루'),
    ('삼총사', '알렉상드르 뒤마'),
    ('테스', '토머스 하디'),
    ('1984년', '조지 오웰'),
    ('파브르곤충기', '장 앙리 파브르'),
    ('검은고양이', '에드거 앨런 포'),
    ('베니스의 상인', '윌리엄 셰익스피어'),
    ('노트르담의 꼽추', '빅토르 위고'),
    ('삼국유사', '일연'),
    ('바람과 함께 사라지다', '마거릿 미첼'),
    ('열하일기', '박지원'),
    ('키다리 아저씨', '진 웹스터'),
    ('해저 2만리', '쥘 베른'),
    ('별', '알퐁스 도데'),
    ('적과 흑', '스탕달'),
    ('압록강은 흐른다', '이미륵'),
    ('시턴 동물기', '어니스트 톰프슨 시튼'),
    ('도리언 그레이의 초상', '오스카 와일드'),
    ('난중일기', '이순신'),
    ('쿠오바디스', '헨리크 시엔키에비치'),
    ('몬테크리스토 백작', '알렉상드르 뒤마'),
    ('빨간머리 앤', '루시 모드 몽고메리'),
    ('15소년 표류기', '쥘 베른'),
    ('구운몽', '김만중'),
    ('목로주점', '에밀 졸라'),
    ('부활', '레프 톨스토이'),
    ('일리아드 오디세이', '호메로스'),
    ('모비딕', '허먼 멜빌'),
    ('노인과 바다', '어니스트 헤밍웨이'),
    ('왕자와 거지', '마크 트웨인'),
    ('셜록홈스의 모험', '아서 코난 도일'),
    ('대지', '펄 S. 벅'),
    ('젊은 베르테르의 슬픔', '요한 볼프강 폰 괴테'),
    ('카라마조프의 형제들', '표도르 도스토옙스키'),
    ('주홍글씨', '나다니엘 호손'),
    ('마지막 잎새', '오 헨리'),
    ('사랑의 가족', '아그네스 자퍼'),
    ('탈무드', '작자 미상'),
    ('아라비안나이트', '작자 미상'),
    ('데미안', '헤르만 헤세'),
    ('엄마 찾아 삼만리', '에드몬도 데 아미치스'),
    ('괴도 신사 아르센 뤼팽', '모리스 르블랑'),
    ('여자의 일생', '기 드 모파상'),
    ('로미오와 줄리엣', '윌리엄 셰익스피어'),
    ('안나 카레니나', '레프 톨스토이'),
    ('사랑의 요정', '조르주 상드'),
    ('눈의 여왕', '한스 크리스티안 안데르센'),
    ('말괄량이 길들이기', '윌리엄 셰익스피어'),
    ('악동일기', '토머스 베일리 올드리치'),
    ('사랑의 학교', '에드몬도 데 아미치스'),
    ('플랜더스의 개', '위다'),
    ('플루타르크 영웅전', '플루타르코스'),
    ('그리스 로마 신화', '토머스 불핀치'),
    ('인형의 집', '헨리크 입센'),
    (
        '세계 우수 단편 모음',
        '기 드 모파상, 오스카 와일드, 나다니엘 호손, 안톤 파블로비치 체호프, 빅토르 위고',
    ),
    ('수레바퀴 밑에서', '헤르만 헤세'),
    ('위대한 유산', '찰스 디킨스'),
]

RECOMMENDED_46 = [
    ('노인과 바다', '어니스트 헤밍웨이'),
    ('작은 아씨들', '루이자 메이 올컷'),
    ('장발장', '빅토르 위고'),
    ('톰 소여의 모험', '마크 트웨인'),
    ('삼국지', '나관중'),
    ('탈무드', '작자 미상'),
    ('해저 2만리', '쥘 베른'),
    ('파브르곤충기', '장 앙리 파브르'),
    ('그리스 로마 신화', '토머스 불핀치'),
    ('로빈슨 크루소', '대니얼 디포'),
    ('80일간의 세계일주', '쥘 베른'),
    (
        '세계 우수 단편 모음',
        '기 드 모파상, 오스카 와일드, 나다니엘 호손, 안톤 파블로비치 체호프, 빅토르 위고',
    ),
    ('걸리버 여행기', '조너선 스위프트'),
    ('어린 왕자', '앙투안 드 생텍쥐페리'),
    ('보물섬', '로버트 루이스 스티븐슨'),
    ('15소년 표류기', '쥘 베른'),
    ('지킬박사와 하이드', '로버트 루이스 스티븐슨'),
]

GENERAL_23 = [
    '우리 반에 로봇이 전학 왔다',
    '고양이 탐정과 사라진 도시락',
    '비 오는 날의 비밀 지도',
    '토끼 우체부의 빨간 자전거',
    '운동장 아래 작은 왕국',
    '구름 빵집의 수상한 손님',
    '별빛 도서관의 하룻밤',
    '공룡이 학교에 온 날',
    '내 짝꿍은 외계인',
    '바다거북의 여름 여행',
    '마법 연필과 거꾸로 숙제',
    '용감한 겁쟁이 강아지',
    '세상에서 제일 느린 달리기',
    '엄마 몰래 키운 작은 용',
    '사라진 운동화의 범인',
    '비밀 상자와 세 개의 열쇠',
    '꼬마 발명가의 엉뚱한 하루',
    '달나라 소풍 가는 날',
    '도깨비와 함께한 방학',
    '작은 여우의 첫 심부름',
    '학교 뒤 숲의 초록 문',
    '시간을 멈춘 알람시계',
    '우리 동네 유령 편의점',
    '별을 주운 아이',
    '무지개 끝의 보물지도',
]

GENERAL_46 = [
    '달빛 우체국의 마지막 편지',
    '시간을 파는 문구점',
    '사라진 별자리 지도',
    '바다 끝의 등대지기',
    '오래된 시계탑의 수수께끼',
    '화성에서 온 첫 번째 편지',
    '유리성의 마지막 왕자',
    '여름이 멈춘 작은 도시',
    '기억을 보관하는 서점',
    '검은 숲의 지도 제작자',
    '마지막 기차는 새벽에 떠난다',
    '사라진 왕국의 열세 번째 문',
    '북쪽 섬의 겨울 편지',
    '아무도 모르는 지하도서관',
    '시간을 잃어버린 아이들',
    '푸른 행성의 마지막 정원',
    '비밀 연구소의 세 번째 실험',
    '도시를 걷는 작은 늑대',
    '유리병 속의 바다',
    '천 개의 계단과 한 개의 문',
    '사라진 역사책의 첫 페이지',
    '별을 읽는 소년과 지도 없는 여행',
    '붉은 모래섬의 약속',
    '어제의 나에게 보내는 편지',
    '아주 길고 조금 이상한 제목의 모험 이야기, 잃어버린 오후와 세 개의 문',
]

CHALLENGE_TITLES = [
    '침묵의 도시와 마지막 기록자',
    '바람의 제국과 무너진 성벽',
    '시간의 끝에서 발견한 일기',
    '북해의 항해자와 검은 등대',
    '천년 도서관의 금지된 연대기',
    '사라진 문명의 마지막 재판',
    '얼어붙은 강 너머의 왕국',
    '별이 사라진 밤의 관측일지',
    '아무도 돌아오지 않은 탐사선',
    '모래시계 왕국의 마지막 기록',
    '네 개의 도시와 한 사람의 선택',
    '기억을 지우는 학교',
    '유리바다를 건너는 아이들',
    '세계의 끝에서 만난 지도',
    '폐허 위의 작은 공화국',
]

OLD_PLACEHOLDER_TITLES = tuple(
    [f'시드일반{index:02d}' for index in range(1, 36)]
    + ['시드추천23', '시드추천46', '시드도전책', '눈 내리는 날의 오래된 극장']
)

CLASSIC_THEMES = {
    '로빈슨 크루소': 'robinson',
    '어린 왕자': 'little_prince',
    '보물섬': 'treasure',
    '톰 소여의 모험': 'tom',
    '15소년 표류기': 'boys',
    '노인과 바다': 'oldman',
    '파브르곤충기': 'insects',
    '해저 2만리': 'nmo',
    '그리스 로마 신화': 'myth',
    '지킬박사와 하이드': 'hyde',
    '걸리버 여행기': 'gulliver',
    '작은 아씨들': 'women',
    '장발장': 'valjean',
    '삼국지': 'three',
    '탈무드': 'talmud',
    '80일간의 세계일주': 'eighty',
    '80간의 세계일주': 'eighty',
    '세계 우수 단편 모음': 'stories',
    '동물농장': 'farm',
    '피터 팬': 'peter',
    '오즈의 마법사': 'oz',
    '알프스 소녀 하이디': 'heidi',
    '빨간머리 앤': 'anne',
    '눈의 여왕': 'snow',
    '이상한 나라의 엘리스': 'alice',
}

GENERIC_THEMES = (
    'school', 'adventure', 'letter', 'forest', 'library',
    'sea', 'friend', 'mystery', 'animal', 'time',
)

VOICE_KEYS = (
    'VOICE_A', 'VOICE_B', 'VOICE_C', 'VOICE_D', 'VOICE_E',
    'VOICE_TERSE', 'VOICE_VERBOSE', 'VOICE_RARE',
)

# Child-level habit. 감상 길이는 entry 추첨이 아니라 이 습관으로 간다.
# CAREFUL≈10%, NORMAL≈60%, TERSE≈30% 는 CHILD_PROFILES voice 매핑으로 맞춘다.
# mid_mod: (day_index + salt) % mid_mod == 0 이면 중간 감상.
# typo: 0 never, 1 rare, 2 often
VOICES = {
    'VOICE_A': {'habit': 'NORMAL', 'style': 'short', 'mid_mod': 4, 'complete': True, 'typo': 2, 'join': False},
    'VOICE_B': {'habit': 'NORMAL', 'style': 'feeling', 'mid_mod': 3, 'complete': True, 'typo': 2, 'join': False},
    'VOICE_C': {'habit': 'NORMAL', 'style': 'plot', 'mid_mod': 3, 'complete': True, 'typo': 1, 'join': True},
    'VOICE_D': {'habit': 'NORMAL', 'style': 'think', 'mid_mod': 3, 'complete': True, 'typo': 1, 'join': True},
    'VOICE_E': {'habit': 'NORMAL', 'style': 'think', 'mid_mod': 3, 'complete': True, 'typo': 1, 'join': True},
    'VOICE_TERSE': {'habit': 'TERSE', 'style': 'terse', 'mid_mod': 8, 'complete': True, 'typo': 2, 'join': False},
    'VOICE_VERBOSE': {'habit': 'CAREFUL', 'style': 'verbose', 'mid_mod': 2, 'complete': True, 'typo': 1, 'join': True},
    'VOICE_RARE': {'habit': 'TERSE', 'style': 'rare', 'mid_mod': 99, 'complete': 'sometimes', 'typo': 2, 'join': False},
}

CAREFUL_TAILS = (
    '읽으면서 주인공 입장이 되면 나도 똑같이 할 수 있을지 모르겟다.',
    '중간에 조금 어려웠는데 뒤에는 더 잘 읽혔다.',
    '친구한테도 이 책 이야기 해보고 싶다.',
    '결말이 조금 아쉽기도 하고 좋기도 햇다.',
    '다음에 비슷한 책을 또 읽어보고 싶다.',
    '그래서 조금 더 생각하게 된거 같다.',
)

THEME_LINES = {
    'robinson': {
        'first': (
            '{title}는 무인도에서 혼자 남는 이야기다.',
            '섬에 혼자 남아서 조금 걱정됐다.',
            '배를 타고 가다가 사고가 나서 놀랐다.',
        ),
        'mid': (
            '혼자 집을 만들고 사냥하는게 힘들어 보였다.',
            '포기 안 하고 버틸려고 해서 멋찐거 같다.',
            '금요일과 같이 지내서 덜 외로워 보였다.',
        ),
        'done': (
            '로빈슨 크루소가 혼자서도 포기안해서 나도 크루소처럼 멋찐 사람이 되고싶었다.',
            '무인도에서 끝까지 살아남은게 기억에 남았다. 나라면 무서웠을거 같다.',
            '혼자여도 매일 할 일을 정하는 모습이 인상 깊었다.',
        ),
    },
    'little_prince': {
        'first': (
            '{title}는 별에서 온 아이 이야기다.',
            '어린왕자가 작아서 신기했다.',
            '사막에 떨어진 비행기가 궁금했다.',
        ),
        'mid': (
            '장미 때문에 고민하는게 이해가 됐다.',
            '별을 많이 돌아다녀서 재미있었다.',
            '여우랑 친구가 되는 장면이 좋앗다.',
        ),
        'done': (
            '어린왕자는 왜 많은 별을 우주선도없이 돌아다니난지 신기했다.',
            '장미한테 다시 돌아가려고 한게 기억에 남았다. 나도 친구를 잘 챙겨야겠다.',
            '중요한 것은 눈에 보이지 않는다는 말이 오래 남았다.',
        ),
    },
    'treasure': {
        'first': (
            '{title}는 보물을 찾는 모험이다.',
            '지도가 나와서 설렜다.',
            '배가 떠나기 전부터 긴장이 됐다.',
        ),
        'mid': (
            '해적들이 나와서 무서울거 같았다.',
            '섬에 도착해서 보물을 찾는게 재미있었다.',
            '누가 적인지 헷갈렸다.',
        ),
        'done': (
            '나는 보물섬에 진짜 가면 무서울거 같은데 한번은 가보고싶다.',
            '보물보다 친구를 믿는 일이 더 어려워 보였다.',
            '항해가 위험했지만 끝까지 가서 후련했다.',
        ),
    },
    'tom': {
        'first': (
            '{title}는 장난이 많은 이야기다.',
            '톰이 학교를 빼먹는게 웃겼다.',
            '강가에서 노는 장면이 재미있었다.',
        ),
        'mid': (
            '페인트 칠을 친구한테 시키는게 약았다.',
            '톰소여가 장난을 많이 치는데 그래도 친구랑 같이 다녀서 재밋었다.',
            '동굴에 들어가는 장면은 좀 무서웠다.',
        ),
        'done': (
            '장난만 하는 줄 알았는데 친구를 지키려는 마음이 있었다.',
            '모험이 많아서 재밋었다. 나도 친구랑 그렇게 다녀보고 싶다.',
            '마지막에 다시 만나서 좋앗다. 처음에는 좀 슬펏다.',
        ),
    },
    'boys': {
        'first': (
            '{title}는 아이들끼리 섬에 남는 이야기다.',
            '배가 난파돼서 긴장됐다.',
            '어른이 없어서 어떻게 살지 궁금했다.',
        ),
        'mid': (
            '역할을 나눠서 일하는 장면이 좋았다.',
            '다투다가도 다시 협력하는게 인상 깊었다.',
            '섬에서 집을 만드는게 신기했다.',
        ),
        'done': (
            '아이들끼리도 서로 도우면 버틸 수 있다는 이야기가 남았다.',
            '15명이 협력하는 장면이 제일 기억에 남는다.',
            '혼자였으면 못 했을 일을 같이 해서 다행이라고 생각했다.',
        ),
    },
    'oldman': {
        'first': (
            '{title}는 바다에서 고기를 잡는 이야기다.',
            '노인이 배를 타고 나가서 외로워 보였다.',
            '큰 물고기를 만나서 긴장됐다.',
        ),
        'mid': (
            '고기가 너무 커서 놓치기 싫다고 했다.',
            '팔이 아픈데도 줄을 놓지 않았다.',
            '바다와 오래 싸우는 장면이 길었다.',
        ),
        'done': (
            '포기하지 않는 노인이 멋있었다. 결과가 아쉽기도 했다.',
            '큰 물고기를 잡고도 상어에게 뺏기는게 슬펐다.',
            '이겨도 남는 게 없을 수 있다는 결말이 무거웠다.',
        ),
    },
    'insects': {
        'first': (
            '{title}는 곤충을 자세히 보는 책이다.',
            '벌레가 많아서 처음엔 별로였다.',
            '관찰하는 장면이 차분했다.',
        ),
        'mid': (
            '곤충이 이렇게 종류가 많은지 몰랏다.',
            '집을 짓는 벌레가 신기했다.',
            '싸움하는 장면은 의외로 재미있었다.',
        ),
        'done': (
            '가까이 보면 별거 아닌 벌레도 사는 방식이 달랐다.',
            '관찰을 오래 하는 사람이 대단하다고 생각했다.',
            '이제는 길에서 벌레를 보면 조금 다르게 보게 될 거 같다.',
        ),
    },
    'nmo': {
        'first': (
            '{title}는 잠수함을 타고 바닷속을 가는 이야기다.',
            '네모 선장이 수수께끼 같아서 궁금했다.',
            '바닷속 생물이 신기했다.',
        ),
        'mid': (
            '창문 밖으로 해파리가 지나가는 장면이 예뻤다.',
            '갇혀 있는 기분이 들어서 답답했다.',
            '바다가 넓어서 길을 잃을 거 같았다.',
        ),
        'done': (
            '바닷속이 무섭기도 하고 아름답기도 했다.',
            '잠수함을 타고 세계를 도는 상상을 했다.',
            '자유롭지만 갇혀 있는 선장이 복잡하게 느껴졌다.',
        ),
    },
    'myth': {
        'first': (
            '{title}는 신들이 나오는 이야기다.',
            '이름이 많아서 헷갈렸다.',
            '영웅이 모험을 시작해서 재미있었다.',
        ),
        'mid': (
            '신들이 싸우는 이유가 사람 같아서 이상했다.',
            '영웅이 실수를 해서 큰일이 났다.',
            '괴물을 만나는 장면이 긴장됐다.',
        ),
        'done': (
            '신 이야긴데도 질투나 용기가 사람 이야기 같았다.',
            '여러 영웅 중에 누가 제일 용감한지 고르기 어려웠다.',
            '이야기가 많아서 다 외우진 못 했지만 재미있었다.',
        ),
    },
    'hyde': {
        'first': (
            '{title}는 한 사람이 달라지는 이야기다.',
            '처음부터 분위기가 좀 무서웠다.',
            '의사가 약을 먹는 장면이 이상했다.',
        ),
        'mid': (
            '하이드가 나와서 무서웠다.',
            '같은 사람인데 행동이 너무 달랐다.',
            '비밀을 숨기려는 장면이 답답했다.',
        ),
        'done': (
            '한 사람 안에 다른 모습이 있다는 게 소름 돋았다.',
            '착한 척만 하면 안 된다는 생각이 들었다.',
            '무서웠지만 왜 그런 선택을 했는지 조금은 알 거 같다.',
        ),
    },
    'gulliver': {
        'first': (
            '{title}는 이상한 나라에 가는 이야기다.',
            '작은 사람들 나라에 가서 웃겼다.',
            '배가 난파돼서 모험이 시작됐다.',
        ),
        'mid': (
            '거인 나라에 가니까 반대로 작아져서 신기했다.',
            '나라마다 규칙이 달라서 헷갈렸다.',
            '말을 하는 말들이 나와서 이상했다.',
        ),
        'done': (
            '다른 나라 눈으로 보면 우리 일도 이상하게 보일 수 있겠다고 생각했다.',
            '여행이 길어서 힘들었지만 볼거리가 많았다.',
            '마지막에 집에 돌아와서 다행이라고 느꼈다.',
        ),
    },
    'women': {
        'first': (
            '{title}는 자매들이 나오는 이야기다.',
            '네 명의 성격이 달라서 재미있었다.',
            '집이 가난해도 사이가 좋아 보였다.',
        ),
        'mid': (
            '조가 글을 쓰는 장면이 좋았다.',
            '서로 싸우고 화해하는게 우리 집 같았다.',
            '크리스마스 장면이 따뜻했다.',
        ),
        'done': (
            '자매가 각자 다른 길을 가는 게 자연스러워 보였다.',
            '특별한 사건보다 일상이 오래 남았다.',
            '가족을 챙기는 마음이 이야기의 중심 같았다.',
        ),
    },
    'valjean': {
        'first': (
            '{title}는 죄를 짓고 다시 살려고 하는 이야기다.',
            '빵을 훔친 이유부터 슬펐다.',
            '주교가 촛대를 주는 장면이 인상 깊었다.',
        ),
        'mid': (
            '자베르가 쫓아와서 긴장됐다.',
            '코제트를 돌보는 장면이 따뜻했다.',
            '도망 다니는 삶이 힘들어 보였다.',
        ),
        'done': (
            '잘못을 만회하려는 시간이 아주 길었다.',
            '사람이 바뀔 수 있는지 계속 생각하게 됐다.',
            '마지막이 슬펐지만 허무하진 않았다.',
        ),
    },
    'three': {
        'first': (
            '{title}는 전쟁과 의리 이야기다.',
            '이름이 많아서 처음엔 헷갈렸다.',
            '도원결의 장면이 멋있었다.',
        ),
        'mid': (
            '싸움이 많아서 누가 이겼는지 놓쳤다.',
            '친구를 지키려는 마음이 강했다.',
            '계략이 나와서 조금 어려웠다.',
        ),
        'done': (
            '의리가 중요하다고 하면서도 배신이 많아서 복잡했다.',
            '영웅들이 결국 지치는 느낌이 있었다.',
            '긴 이야기라 다 기억은 못 했지만 인상 깊었다.',
        ),
    },
    'talmud': {
        'first': (
            '{title}는 짧은 이야기와 가르침이 많다.',
            '질문이 많아서 신기했다.',
            '한 편 한 편이 짧아서 읽기 편했다.',
        ),
        'mid': (
            '정답이 바로 안 나오고 생각하라는 느낌이 있었다.',
            '사람 사이의 약속을 중요하게 말했다.',
            '어떤 이야기는 이해가 안 됐다.',
        ),
        'done': (
            '큰 모험은 없지만 생각이 남는 책이었다.',
            '작은 선택이 중요하다는 말이 기억에 남는다.',
            '다 외우진 못 해도 몇 가지 이야기는 남을 거 같다.',
        ),
    },
    'eighty': {
        'first': (
            '{title}는 세계 여러 곳을 빨리 도는 이야기다.',
            '내기를 해서 출발하는게 재미있었다.',
            '기차와 배를 갈아타는 장면이 신기했다.',
        ),
        'mid': (
            '시간이 부족해서 초조했다.',
            '길을 잘못 드는 장면이 긴장됐다.',
            '새로운 도시가 나올 때마다 구경하는 기분이다.',
        ),
        'done': (
            '서두르면 놓치는 것도 있겠다고 생각했다.',
            '세계가 넓다는 게 숫자로 느껴졌다.',
            '도착하는 순간이 시원했다.',
        ),
    },
    'stories': {
        'first': (
            '{title}는 짧은 이야기가 여러 개다.',
            '작가가 여러 명이라 분위기가 달랐다.',
            '한 편씩 끊어서 읽기 좋았다.',
        ),
        'mid': (
            '어떤 편은 슬프고 어떤 편은 반전이 있었다.',
            '결말이 허무한 이야기도 있었다.',
            '인물이 많아서 이름이 섞였다.',
        ),
        'done': (
            '한 권 안에서 여러 감정을 본 느낌이다.',
            '제일 기억에 남는 한 편만 골라도 충분할 거 같다.',
            '짧은 글도 여운이 남을 수 있다는 걸 알았다.',
        ),
    },
    'farm': {
        'first': (
            '{title}는 동물들이 농장을 차지하는 이야기다.',
            '동물들이 말을 해서 처음엔 웃겼다.',
            '농장 주인이 미워서 동물 편이 됐다.',
        ),
        'mid': (
            '규칙이 슬쩍 바뀌는게 찝찝했다.',
            '돼지들이 다른 동물을 부리는게 이상했다.',
            '평등하다고 했는데 아닌 거 같았다.',
        ),
        'done': (
            '처음과 끝이 너무 달라서 씁쓸했다.',
            '구호만 외치면 안 된다는 생각이 들었다.',
            '동물 이야긴데 사람 사회 같아서 오래 남았다.',
        ),
    },
    'peter': {
        'first': (
            '{title}는 영원히 어린 아이 이야기다.',
            '하늘을 나는 장면이 좋았다.',
            '네버랜드가 신기했다.',
        ),
        'mid': (
            '후크 선장이 나와서 긴장됐다.',
            '친구들이랑 모험하는게 재밋었다.',
            '집에 가고 싶어하는 마음이 이해됐다.',
        ),
        'done': (
            '영원히 아이로 남는 게 꼭 좋지만은 않아 보였다.',
            '모험은 재미있지만 돌아갈 곳도 필요해 보였다.',
            '마지막에 생각이 복잡해졌다.',
        ),
    },
    'oz': {
        'first': (
            '{title}는 이상한 나라로 가는 이야기다.',
            '회오리바람에 집이 날아가서 놀랐다.',
            '노란 길이 궁금했다.',
        ),
        'mid': (
            '허수아비 사자 양철나무꾼이 같이 가서 좋았다.',
            '마법사가 가짜일 수도 있겠다고 생각했다.',
            '마녀가 무서웠다.',
        ),
        'done': (
            '이미 가지고 있는 걸 찾으러 떠난 이야기 같았다.',
            '친구들과 같이 가서 용기가 생긴 거 같다.',
            '집으로 돌아가는 결말이 안심됐다.',
        ),
    },
    'heidi': {
        'first': (
            '{title}는 산에서 사는 이야기다.',
            '할아버지랑 사는게 처음엔 어색해 보였다.',
            '산 공기 묘사가 좋았다.',
        ),
        'mid': (
            '염소를 치는 장면이 평화로웠다.',
            '도시로 가서 아파하는게 슬펐다.',
            '다시 산을 그리워했다.',
        ),
        'done': (
            '자신이 편한 곳이 따로 있다는 생각이 들었다.',
            '사람을 돌보는 마음이 따뜻했다.',
            '결말이 포근해서 좋았다.',
        ),
    },
    'anne': {
        'first': (
            '{title}는 빨간 머리 소녀 이야기다.',
            '앤이 말이 많아서 웃겼다.',
            '새로 온 집이 궁금했다.',
        ),
        'mid': (
            '상상하는 장면이 재미있었다.',
            '실수를 하고 사과하는게 사람 같았다.',
            '친구를 사귀는 과정이 길었다.',
        ),
        'done': (
            '서툰 말도 진심이면 전해진다는 느낌이 있었다.',
            '앤처럼 말도 많고 씩씩하게 사는 게 부러웠다.',
            '마지막에 성장한 느낌이 났다.',
        ),
    },
    'snow': {
        'first': (
            '{title}는 차가운 여왕이 나오는 이야기다.',
            '거울 조각이 눈에 들어가서 이상해졌다.',
            '눈 내리는 장면이 예뻤다.',
        ),
        'mid': (
            '친구를 찾아 떠나는 길이 길었다.',
            '도와 주는 사람들이 많아서 덜 외로웠다.',
            '얼음 궁전이 무서웠다.',
        ),
        'done': (
            '따뜻한 마음이 얼음을 녹인다는 결말이 남았다.',
            '친구를 끝까지 찾아간 게 멋있었다.',
            '조금 동화 같았지만 끝까지 읽게 됐다.',
        ),
    },
    'alice': {
        'first': (
            '{title}는 토끼를 따라가는 이야기다.',
            '구멍이 나와서 이상했다.',
            '크기가 커졌다 작아져서 웃겼다.',
        ),
        'mid': (
            '규칙이 없는 나라 같아서 헷갈렸다.',
            '카드 병정들이 나와서 소란스러웠다.',
            '차를 마시는 장면이 이상하고 재미있었다.',
        ),
        'done': (
            '꿈인지 실제인지 헷갈리는 결말이었다.',
            '말도 안 되는 일이 연속돼서 어지러웠다.',
            '이상한 나라라도 자기 생각을 말하는 장면이 좋았다.',
        ),
    },
    'school': {
        'first': ('학교에서 이상한 일이 시작됐다.', '전학 온 친구가 궁금했다.', '수업 시간에 사건이 났다.'),
        'mid': ('오해가 생겨서 속상했다.', '같이 숨어서 단서를 찾았다.', '선생님이 아직 모른다.'),
        'done': ('결국 친구가 되어서 기뻤다.', '작은 용기가 필요했던 이야기였다.', '우리 반에서도 볼 법한 일이었다.'),
    },
    'adventure': {
        'first': ('모험이 시작돼서 설렜다.', '지도를 보고 출발했다.', '위험한 길이 나왔다.'),
        'mid': ('길이 막혀서 다른 곳으로 갔다.', '친구가 도와줘서 넘어갔다.', '보물인지 함정인지 헷갈렸다.'),
        'done': ('집에 돌아와서 안심됐다.', '용기와 무모함이 비슷해 보였다.', '멀리 갔다 온 이유가 분명해졌다.'),
    },
    'letter': {
        'first': ('편지 이야길 읽기 시작했다.', '누가 보냈는지 궁금했다.', '우체통이 중요한 거 같다.'),
        'mid': ('편지에 거짓말이 있는 거 같았다.', '기다림이 길어서 답답했다.', '답을 쓸지 말지 고민했다.'),
        'done': ('마지막 편지를 보내고 나서 안심이 됐다.', '하지 못한 말이 더 커 보였다.', '작은 편지가 사람을 바꿨다.'),
    },
    'forest': {
        'first': ('숲이 비밀이 많아서 궁금했다.', '초록 문이 나와서 들어갔다.', '길이 두 개라 고민했다.'),
        'mid': ('약속을 지키기 어려워 보였다.', '누가 먼저 말했는지 기억이 안 난다.', '밤에 숲이 무서웠다.'),
        'done': ('같이 가서 다행이었다.', '쉬운 약속일수록 깨지기 쉬웠다.', '숲을 나와도 여운이 남았다.'),
    },
    'library': {
        'first': ('도서관이 배경이라 조용했다.', '잃어버린 책을 찾는 이야기다.', '고양이가 나와서 귀여웠다.'),
        'mid': ('숨겨진 방이 있을 거 같았다.', '책을 순서대로 찾아갔다.', '관리하는 사람이 힘들어 보였다.'),
        'done': ('책을 지키는 마음이 따뜻했다.', '공간이 사람을 바꾸는 느낌이었다.', '다 읽고 나니 도서관이 다르게 보였다.'),
    },
    'sea': {
        'first': ('바다 이야기가 시작됐다.', '파도가 세서 긴장됐다.', '배를 타고 떠났다.'),
        'mid': ('길을 잃을 뻔했다.', '등대가 보여서 안심했다.', '비가 와서 계획이 바뀌었다.'),
        'done': ('바다를 건너고 나니 후련했다.', '풍경보다 사람이 남았다.', '다시 가고 싶기도 하고 무섭기도 하다.'),
    },
    'friend': {
        'first': ('친구 이야길 읽기 시작했다.', '처음엔 사이가 별로였다.', '오해가 있을 거 같았다.'),
        'mid': ('싸우고 나서 어색했다.', '작은 일로 화해했다.', '같이 심부름을 갔다.'),
        'done': ('친구가 생겨서 좋았다.', '말보다 행동이 중요했다.', '나도 그렇게 대해야겠다고 생각했다.'),
    },
    'mystery': {
        'first': ('범인이 누구인지 궁금했다.', '단서가 하나 나왔다.', '사라진 물건이 핵심이다.'),
        'mid': ('용의자가 여러 명이라 헷갈렸다.', '거짓말이 하나 있었다.', '밤에 단서를 찾았다.'),
        'done': ('범인이 의외라서 놀랐다.', '끝까지 읽길 잘했다.', '작은 단서를 놓치면 안 되겠다고 생각했다.'),
    },
    'animal': {
        'first': ('동물이 주인공이라 귀여웠다.', '말을 해서 신기했다.', '사람이랑 같이 모험했다.'),
        'mid': ('위험에 빠졌다.', '사람이 도와주는 장면이 좋았다.', '집을 찾아가는 길이 길었다.'),
        'done': ('끝까지 포기하지 않아서 좋았다.', '동물이 사람보다 솔직해 보였다.', '다시 읽고 싶은 책이다.'),
    },
    'time': {
        'first': ('시간이 이상하게 흐른다.', '시계가 멈춰서 걱정됐다.', '과거로 가는 줄 알았다.'),
        'mid': ('하루를 반복하는 기분이었다.', '선택을 바꾸면 결과가 달라졌다.', '서두르다 중요한 걸 놓쳤다.'),
        'done': ('빠른 길이 좋은 길은 아닌 거 같다.', '시간을 고친다는 말이 사람을 고친다는 말 같았다.', '천천히 가는 결말이 마음에 들었다.'),
    },
    'classic': {
        'first': ('{title}를 읽기 시작했다.', '처음엔 조금 어려웠다.', '인물 이름이 낯설었다.'),
        'mid': ('사건이 커져서 집중됐다.', '주인공 선택이 이해 안 갔다.', '책이 좀 어려웠는데 뒤에는 재밌어졋다.'),
        'done': ('끝까지 읽으니까 조금 알 거 같았다.', '주인공이 왜 그런 선택을 했는지는 아직 잘 모르겠다 근데 나라면 무서웠을거 같다.', '여운이 남아서 표지를 다시 봤다.'),
    },
    'long': {
        'first': ('제목이 길어서 웃겼다.', '문이 세 개라서 고르기 어려웠다.', '오후를 잃어버린다는 말이 이상했다.'),
        'mid': ('문을 열 때마다 오후가 달라졌다.', '제목만 길 줄 알았는데 내용도 복잡했다.', '어느 문이 맞는지 모르겠다.'),
        'done': (
            '잃어버린 오후를 되찾는 대신 그 오후에 한 일을 인정하는 결말이 오래 남았다.',
            '길이 많아서 오히려 더 천천히 읽게 됐다.',
            '제목이 장난 같아도 선택은 진지했다.',
        ),
    },
    'challenge': {
        'first': ('문장이 길어서 천천히 읽었다.', '세계가 어두워서 분위기가 무거웠다.', '기록이 중요한 이야기 같다.'),
        'mid': ('누가 진실을 말하는지 모르겠다.', '도시가 무너지는 장면이 길었다.', '지도가 틀렸을 수도 있다.'),
        'done': (
            '끝까지 읽기 힘들었지만 포기는 안 했다.',
            '승리가 아니라 무엇을 남길지 묻는 이야기 같았다.',
            '여운이 길어서 바로 다른 책을 못 고르겠다.',
        ),
    },
}

TYPO_SWAPS = (
    ('재미있었다', '재밋었다'),
    ('몰랐다', '몰랏다'),
    ('좋았다', '좋앗다'),
    ('했다', '햇다'),
    ('멋진', '멋찐'),
    ('것 같다', '거 같다'),
    ('되었다', '됬다'),
    ('슬펐다', '슬펏다'),
)

INTENTIONAL_TYPOS = ('재밋었다', '멋찐', '좋앗다', '몰랏다', '햇다', '거 같다', '재밌어졋다', '슬펏다')


def _digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def stable_int(text, modulo=10 ** 9):
    return int(_digest(text)[:12], 16) % modulo


def theme_for_title(title, *, challenge=False):
    if title in CLASSIC_THEMES:
        return CLASSIC_THEMES[title]
    if '이상한 제목' in title:
        return 'long'
    if challenge:
        return 'challenge'
    return GENERIC_THEMES[stable_int(title, len(GENERIC_THEMES))]


def _apply_typos(text, voice_key, salt):
    if not text:
        return text
    level = VOICES[voice_key]['typo']
    if level <= 0:
        return text
    step = 2 if level == 1 else 1
    out = text
    for index, (src, dst) in enumerate(TYPO_SWAPS):
        if (salt + index) % (step + 1) != 0:
            continue
        if src in out:
            out = out.replace(src, dst, 1)
    if ' ' in out and (salt % 5 == 0) and level == 2:
        parts = out.split(' ', 1)
        out = parts[0] + parts[1]
    return out


def review_habit_for_voice(voice_key):
    return VOICES[voice_key]['habit']


def _raw_line(theme, stage, variant, title):
    pool = THEME_LINES.get(theme) or THEME_LINES['classic']
    lines = pool.get(stage) or THEME_LINES['classic'][stage]
    return lines[variant % len(lines)].replace('{title}', title)


def _first_sentence(text):
    piece = text.split('.')[0].strip()
    if not piece:
        return text.strip()
    return piece + '.'


def _compose_sentences(theme, title, count, salt, *, last):
    """UI가 newline을 collapse하므로 문장 수로 길이를 만든다."""
    stages = ('done', 'mid', 'first') if last else ('first', 'mid', 'done')
    parts = []
    seen = set()
    for step in range(max(1, count) + 3):
        if len(parts) >= count:
            break
        stage = stages[step % len(stages)]
        line = _raw_line(theme, stage, salt + step, title).strip()
        if not line.endswith('.'):
            line = line + '.'
        if line in seen:
            tail = CAREFUL_TAILS[(salt + step) % len(CAREFUL_TAILS)]
            if tail in seen:
                continue
            line = tail
        seen.add(line)
        parts.append(line)
    while len(parts) < count:
        tail = CAREFUL_TAILS[(salt + len(parts)) % len(CAREFUL_TAILS)]
        if tail not in seen:
            seen.add(tail)
            parts.append(tail)
        else:
            break
    return ' '.join(parts)


def compose_review(voice_key, title, *, challenge, index, total, child_key):
    """Child voice habit로 길이를 정한다. entry마다 10/60/30 추첨하지 않는다."""
    if total <= 0:
        return None
    voice = VOICES[voice_key]
    habit = voice['habit']
    last = index == total - 1
    salt = stable_int(f'{child_key}:{title}:{index}:{total}')
    theme = theme_for_title(title, challenge=challenge)
    if voice_key == 'VOICE_RARE':
        if not last:
            return None
        if salt % 3 != 0:
            return None
        text = _first_sentence(_raw_line(theme, 'done', salt, title))
        return _apply_typos(text, voice_key, salt)
    if last:
        if voice['complete'] == 'sometimes' and salt % 2 == 1:
            return None
        if habit == 'CAREFUL':
            count = 4 + (salt % 2)
        elif habit == 'TERSE':
            count = 1 + (salt % 2)
        else:
            count = 2 + (salt % 2)
        text = _compose_sentences(theme, title, count, salt, last=True)
        if habit == 'TERSE':
            text = ' '.join(text.split('. ')[:count])
            if text and not text.endswith('.'):
                text = text + '.'
        elif habit == 'NORMAL' and voice['style'] == 'think' and salt % 2 == 0:
            text = f'{text} 나라면 다르게 했을 수도 있다.'
    elif index == 0:
        if habit == 'TERSE' and salt % 2 == 0:
            return None
        if habit == 'NORMAL' and total >= 4 and salt % 3 == 0:
            return None
        if habit == 'CAREFUL':
            count = 1 + (salt % 2)
        else:
            count = 1
        text = _compose_sentences(theme, title, count, salt, last=False)
        if habit == 'TERSE':
            text = _first_sentence(text)
    else:
        mid_mod = 2 if habit == 'CAREFUL' else voice['mid_mod']
        if (index + salt) % max(1, mid_mod) != 0:
            return None
        count = 2 if habit == 'CAREFUL' and salt % 3 == 0 else 1
        text = _compose_sentences(theme, title, count, salt, last=False)
        if habit == 'TERSE':
            text = _first_sentence(text)
        if habit == 'NORMAL' and voice['join'] and ' ' in text and salt % 4 == 1:
            text = text.replace('. ', ' ')
    return _apply_typos(text, voice_key, salt)


def _author_for(index):
    return AUTHORS[index % len(AUTHORS)]


def all_book_specs():
    specs = []
    for index, (title, author) in enumerate(RECOMMENDED_23, start=1):
        specs.append({
            'key': f'r23-{index:03d}',
            'title': title,
            'author': author,
            'theme': theme_for_title(title),
            'recommended': True,
            'challenge': False,
            'grade_band': '2-3',
        })
    for index, (title, author) in enumerate(RECOMMENDED_46, start=1):
        specs.append({
            'key': f'r46-{index:03d}',
            'title': title,
            'author': author,
            'theme': theme_for_title(title),
            'recommended': True,
            'challenge': False,
            'grade_band': '4-6',
        })
    for index, title in enumerate(GENERAL_23, start=1):
        specs.append({
            'key': f'g23-{index:02d}',
            'title': title,
            'author': _author_for(index),
            'theme': theme_for_title(title),
            'recommended': False,
            'challenge': False,
            'grade_band': '2-3',
        })
    for index, title in enumerate(GENERAL_46, start=1):
        specs.append({
            'key': f'g46-{index:02d}',
            'title': title,
            'author': _author_for(index + 3),
            'theme': theme_for_title(title),
            'recommended': False,
            'challenge': False,
            'grade_band': '4-6',
        })
    for index, title in enumerate(CHALLENGE_TITLES, start=1):
        specs.append({
            'key': f'ch-{index:02d}',
            'title': title,
            'author': _author_for(index + 7),
            'theme': theme_for_title(title, challenge=True),
            'recommended': False,
            'challenge': True,
            'grade_band': '4-6',
        })
    return specs


def book_titles():
    return {spec['title'] for spec in all_book_specs()}


def specs_for_band(grade_band, *, recommended=None, challenge=None):
    out = []
    for spec in all_book_specs():
        if spec['grade_band'] != grade_band:
            continue
        if recommended is not None and spec['recommended'] != recommended:
            continue
        if challenge is not None and spec['challenge'] != challenge:
            continue
        out.append(spec)
    return out
