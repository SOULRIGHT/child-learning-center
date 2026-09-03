# Point / Reward Data Contract

- Last updated: 2026-09-03
- Implementation baseline: PointEvent `e57d4b7`; composition this commit
- Test baseline: 885 tests OK
- Status: **CURRENT**

이 문서는 **현재 코드와 DB 구조**를 설명한다.

`FUTURE` 섹션에 적힌 내용 외에는, 구현되지 않은 설계를 CURRENT처럼 기록하지 않는다.

코드와 이 문서가 다르면 **코드가 정본**이다. 관련 Growth 운영 데이터 정본의 다른 축은 `docs/growth-data-contract.md`다. 본 파일은 Point / Reward 원장, Reading reward mirror, PointEvent projection, 센터 mapping 경계, 합산/디버깅 기준을 잠근다.

PointEvent projection은 `e57d4b7`에 있다.
Point composition metrics는 `features/growth/point_composition.py` → `metrics_bundle['point_composition']`에 있다.
**Evidence Packet / AI prompt / UI에는 아직 연결되지 않았다.**

---

## 문서 목적

1. **데이터 의미 보존** — 각 table/column이 무엇을 뜻하는지 복원 가능하게 한다.
2. **잘못된 합산 방지** — Growth·분석·리팩터링이 같은 금액을 두 번 더하지 않게 한다.
3. **Reading reward double-count 방지** — `ReadingRewardEvent`와 DailyPoints mirror는 한 사건의 두 표현이다.
4. **센터 정책을 product-core에 하드코딩하지 않기** — 200/100/3000, 요일, 품목 단가는 불변식이 아니다.
5. **자유입력 normalization 해석 기준 보존** — alias/keyword/UNCLASSIFIED 규칙을 남긴다.
6. **다기관화 확장 경계 보존** — projector와 current-center classifier가 분리된 이유를 남긴다.
7. **숫자 불일치 디버깅 기준** — 화면/원장/fetch/Growth/PointEvent 중 어디를 먼저 볼지 고정한다.

---

## 용어 사전

코드 의미 기준. 일상어로 바꾸지 말 것.

| 용어 | 실제 의미 |
|---|---|
| **DailyPoints** | `app.py` SQLAlchemy model. 테이블명 `daily_points`. 아동×활동일 포인트 원장. |
| **daily_points** | 위 테이블. Growth·fetch·PointEvent의 canonical 읽기 대상. |
| **manual_history** | `daily_points.manual_history` TEXT. JSON array 문자열. 그날 수동 이벤트 목록. |
| **manual_points** | `daily_points.manual_points` INTEGER. 수동 합계 **컬럼**. JSON이 있으면 fetch가 이 컬럼을 무시한다 (XOR). |
| **total_points** | `daily_points.total_points` INTEGER. **저장된** 일일 총점. fetch/Growth는 이 값을 버리고 재계산한다. |
| **PointsHistory** | `points_history`. DailyPoints 편집 audit. Growth·fetch·PointEvent source 아님. |
| **Child.cumulative_points** | `child.cumulative_points`. 오늘 live cache. Growth evidence 아님 (오늘+원장 공백 fallback만). |
| **ManualPointPreset** | `manual_point_preset`. UI 버튼 기본값. 지급 원장이 아님. 금액 정본이 아님. |
| **ReadingRewardEvent** | `reading_reward_event`. 추천/도전 독서 시작·완독 보상 **사건** 원장. 일일 총점 SOT가 아님. |
| **Reading reward mirror** | 같은 보상 금액을 `DailyPoints.manual_history` JSON에 복사한 항목. 두 번째 지급이 아님. |
| **ExemptionTicket** | `exemption_ticket`. 면제권 발급/보유. 포인트 금액이 아님. |
| **ExemptionUsage** | `exemption_usage`. 면제권 사용 1건 (과목+날짜). PointEvent가 아님. |
| **canonical / SOT** | 해당 질문에 대한 정본 읽기 경로. 포인트 **일일 총액**의 SOT는 `fetch_child_daily_point_records()`가 재계산한 DailyPoints row다. |
| **PointEvent** | DB entity/table이 **아니다**. canonical fetch record를 읽어 분석 시점에 만드는 **immutable runtime projection** (`frozen dataclass`). |
| **projection** | 원장을 복사·이관하지 않고, 읽기 결과를 분석용 객체로 변환하는 것. |
| **normalization** | 수동 텍스트/presetKey → category/item_key/subject_key. 원문 DB 값을 바꾸지 않음. |
| **current-center mapping** | `features/points/mapping/current.py`. 현재 센터 alias. product projector가 import하지 않음. |
| **classifier** | `classify_manual(item) -> ManualClassification`. projector에 주입하는 callable. |
| **source_kind** | PointEvent가 어디서 왔는지. v1: `daily_subject` \| `manual` 만. |
| **provenance** | 더 좁은 출처. `daily_column` \| `manual_json` \| `manual_sum`. |
| **EARN / SPEND** | `amount > 0` / `amount < 0`. 저장 field가 아님. property `PointEvent.direction`. |
| **UNCLASSIFIED** | 의미를 안전하게 확정할 수 없음. 오류가 아니라 정상 fallback. 금액은 그대로 둔다. |
| **Growth metrics** | `features/growth/metrics.py` 등 deterministic 집계. `point_composition`은 내부 payload. Evidence에는 안 실림. |
| **Evidence Packet** | `build_teacher_evidence_packet()` → `growth_teacher_evidence_v1`. PointEvent raw / composition breakdown **미포함**. |
| **activity_date** | 활동이 일어난 달력일. DailyPoints는 `date`. PointEvent는 `activity_date`. |
| **created_at** | row/JSON 기록 시각(UTC). 활동일 아님. Growth window·PointEvent 날짜로 쓰지 않음. |

---

## 전체 구조도 (CURRENT)

PointEvent는 기존 Growth 파이프를 **변경하지 않는다.** 병렬 읽기 레이어다.

```
포인트 입력 UI  (templates/points/input.html, /api/manual-points)
        │
        ▼
DailyPoints / daily_points
        ├─ subject columns  (korean_points … writing_points)
        └─ manual_history JSON + manual_points 컬럼 + stored total_points
        │
        ▼
fetch_child_daily_point_records(child_id)     ← 일일 총액 canonical reader
        │  MAX(id) GROUP BY date
        │  subjects 재구성, manual XOR, total 재계산
        │
        ├──────────────────────────────────────────────┐
        ▼                                              ▼
project_point_events(records, *, classify_manual=…)   Growth (기존, 미변경)
        │                                              │
        ▼                                              ▼
PointEvent[]  (runtime, DB 없음)                      points_metrics / reward_metrics
        │                                              │
        ▼                                              ├─ Evidence Packet (composition 미포함)
point_composition                                      │
  summarize_point_events /                             ▼
  point_composition_from_events                        Luna (버튼 generation만)
        │
        ▼
metrics_bundle['point_composition']   ← 내부 deterministic만. AI 미전달
```

독서 보상 (별도 쓰기 경로, `features/reading/rewards.py`):

```
독서 lifecycle  (ChildReading 시작/완독 승인)
        │
        ▼
ReadingRewardEvent          ← 보상 사건의 domain 정본 (중복 지급 방지)
        │
        ▼
동일 금액 append
        │
        ▼
DailyPoints.manual_history  ← 실제 일일 포인트 총액에 반영하는 mirror
        │                     reading_points 컬럼은 건드리지 않음
        ▼
fetch 재계산 total 에 mirror amount 포함
```

**합산 한 줄:** 일일 총액에는 DailyPoints만 더한다. `ReadingRewardEvent.points`를 fetch/Growth period total/PointEvent 합에 **다시 더하지 않는다.**

---

## 관련 DB model / table inventory

확인 기준: `app.py`, `feature_models.py`, live SQLite `PRAGMA table_info` (`instance/child_center.db`, 컬럼명만).

| model / table | 역할 | child 연결 | activity date | created timestamp | 주요 columns | canonical? | Growth 사용 | 포인트 총액에 직접 포함? | 분류 | 주의 |
|---|---|---|---|---|---|---|---|---|---|---|
| **DailyPoints** / `daily_points` | 일일 포인트 원장 | `child_id` FK | **`date`** | `created_at`, `updated_at` | 8 과목 + `manual_points` + `manual_history` + `total_points` + `created_by` | **일일 총액 SOT** (fetch 재계산) | 예 (fetch 경유) | **예** | 운영 원장 | `(child_id, date)` unique **없음**. 읽기는 `MAX(id)`. |
| **PointsHistory** / `points_history` | DailyPoints 편집 감사 | `child_id` | `date` (대상일) | `changed_at` | old/new 과목·total, `change_type`, `change_reason` | 아님 | 아니오 | 아니오 | audit | `test_points_history_audit_does_not_change_period_points`. model 클래스에 `old_total_points`/`new_total_points` 중복 할당이 있으나 SQLite에는 컬럼 1개씩. |
| **Child.cumulative_points** | live 누적 cache | child row | 없음 | child `created_at`과 무관 | INTEGER | 아님. 오늘+빈 원장 fallback만 | evidence 금지 | 직접 포함 아님 | cache | `update_cumulative_points()`는 저장 `total_points` SUM, `MAX(id)` 미적용. |
| **ManualPointPreset** / `manual_point_preset` | UI 프리셋 | 없음 | 없음 | `created_at`/`updated_at` | `key`, `label`, `default_points`, `default_reason` | 원장 아님 | 아니오 | 아니오 | UI 설정 | 저장된 이벤트 금액을 덮어쓰지 말 것. |
| **ReadingRewardEvent** / `reading_reward_event` | 독서 보상 사건 | `child_reading_id` → ChildReading → child | **`awarded_on`** | `created_at` | `event_type`, `points`, `policy_version`, `revoked_*` | 보상 **사건** SOT. 일일 총액 SOT 아님 | `reward_metrics.reading_reward_points` overlay | **총액에 다시 더하면 안 됨** | 독서 domain | unique `(child_reading_id, event_type)`. |
| **LearningRecord** / `learning_record` | 예전 문제수/점수 | `child_id` | `date` | `created_at` | korean/math 문제·score, reading_score | 포인트 SOT 아님 | 아니오 | 아니오 | **legacy** | 포인트 컬럼 없음. |
| **LearningSubject** / `learning_subject` | 진도 과목 마스터 | 없음 | 없음 | `created_at` | `key`, `name` | 진도 domain | learning metrics | 아니오 | 진도 | DailyPoints 과목 컬럼과 **별개**. |
| **LearningProgressEntry** / `learning_progress_entry` | 진도 페이지 스냅샷 | `child_id` + subject FK | **`recorded_on`** | `created_at` | `textbook_title`, `page` | 진도 SOT | 예 (진도 family) | 아니오 | 진도 | unique `(child_id, learning_subject_id, recorded_on)`. |
| **ExemptionTicket** / `exemption_ticket` | 면제권 장부 | `child_id` | `issued_on` / `expires_on` | `created_at` | `status`, `policy_version`, `revoked_*` | 면제 domain | usage count만 | 아니오 | 면제 | 포인트 컬럼 없음. |
| **ExemptionTicketSource** / `exemption_ticket_source` | 발급에 쓴 완독 | ticket + `child_reading_id` | 없음 | `created_at` | FKs | 면제 | 직접 evidence 아님 | 아니오 | 면제 | |
| **ExemptionUsage** / `exemption_usage` | 사용 1회 | ticket → child | **`used_on`** | `created_at` | `subject_key`, `subject_name` | 면제 사용 SOT | `rewards.exemption.usage` 건수 | 아니오 | 면제 | 포인트 금액 없음. |

---

## DailyPoints column contract

model: `app.py` `class DailyPoints`. live SQLite 컬럼명과 일치.

모델 주석 `각 과목별 포인트 (200 또는 100)` 은 **UI 관례 설명**이다. DB CHECK 제약이 아니다. product invariant가 아니다.

| column | type | 의미 | activity vs metadata | signed | canonical 계산 | stored 신뢰? | fallback/legacy | center vs core |
|---|---|---|---|---|---|---|---|---|
| `id` | INTEGER PK | row id. 같은 날 중복 시 **MAX(id)가 읽기 canonical** | metadata | n/a | 행 선택에만 | 예 | 없음 | core |
| `child_id` | INTEGER FK `child.id` NOT NULL | 아동 | identity | n/a | 필터 | 예 | 없음 | core |
| `date` | DATE NOT NULL | **활동일** | **activity** | n/a | window·PointEvent `activity_date` | 예 | 없음 | core |
| `korean_points` | INTEGER default 0 | 국어 과목 포인트 | activity | 입력 UI는 음수 거부. 원장은 정수 | **더함** | 저장된 정수 그대로 (fetch `normalize_points`) | 없음 | **컬럼 존재는 현재 센터 과목 집합**. 값 의미(200/100)는 센터 policy |
| `math_points` | INTEGER | 수학 | activity | 동일 | 더함 | 그대로 | 없음 | 동일 |
| `ssen_points` | INTEGER | 쎈 | activity | 동일 | 더함 | 그대로 | 없음 | 동일 |
| `reading_points` | INTEGER | **일반 독서 활동 점수** (추천완독 보상 아님) | activity | 동일 | 더함 | 그대로 | 없음 | 동일 |
| `piano_points` | INTEGER | 피아노 | activity | 동일 | 더함 | 그대로 | 없음 | 동일. 요일 하드코딩 없음 |
| `english_points` | INTEGER | 영어 | activity | 동일 | 더함 | 그대로 | 없음 | 동일 |
| `advanced_math_points` | INTEGER | 고학년수학 | activity | 동일 | 더함 | 그대로 | 컬럼은 있음 | 현재 센터 컬럼 |
| `writing_points` | INTEGER | 쓰기 | activity | 동일 | 더함 | 그대로 | 컬럼은 있음 | 현재 센터 컬럼 |
| `manual_points` | INTEGER default 0 | 수동 합 **컬럼** | activity 합 cache | **signed** (차감 음수) | JSON 없을 때만 | JSON 있으면 **무시** | XOR fallback | core (XOR 규칙) |
| `manual_history` | TEXT default `'[]'` | 수동 이벤트 JSON | activity 목록 | 원소 `points` signed | 비어 있지 않으면 **이 합만** | JSON 파싱 가능해야 함 | 파싱 실패 시 빈 list → 컬럼 fallback | core 형식 JSON. 텍스트 의미는 센터 |
| `total_points` | INTEGER default 0 | 저장 총점 | 파생 저장값 | signed 가능 | **fetch가 재계산하므로 기간합에 안 씀** | **권위 없음** | 쓰기 경로가 채워 둘 수 있음 | core: “저장 total은 비권위” |
| `created_by` | INTEGER FK `user.id` NOT NULL | 작성자 | metadata | n/a | fetch SELECT 안 함 | n/a | 없음 | core |
| `created_at` | DATETIME utcnow | 기록 시각 | **metadata** | n/a | cumulative 정렬 tie-break만. 활동일 아님 | n/a | 없음 | core |
| `updated_at` | DATETIME | 수정 시각 | metadata | n/a | fetch가 **SELECT하지 않음** | n/a | 없음 | core |

`(child_id, date)` unique index: **없음** (live `PRAGMA index_list(daily_points)` 빈 목록, 코드 UniqueConstraint 없음).

---

## canonical fetch 상세 계약

함수: `app.fetch_child_daily_point_records(child_id)` (`app.py`).

Growth wrapper: `features.growth.metrics._canonical_daily_point_records` → 위 함수 호출. as_of 필터: `_records_as_of` (`date`가 as_of 이하).

### 읽는 테이블

**`daily_points`만.** `ReadingRewardEvent`, `points_history`, exemption, `Child.cumulative_points`를 읽거나 더하지 않는다.

### SQL

```sql
SELECT id, date,
       korean_points, math_points, ssen_points, reading_points,
       piano_points, english_points, advanced_math_points, writing_points,
       total_points, manual_points, manual_history, created_at
FROM daily_points
WHERE child_id = :child_id
AND id IN (
    SELECT MAX(id)
    FROM daily_points
    WHERE child_id = :child_id
    GROUP BY date
)
ORDER BY date DESC
```

- 같은 `date` 여러 row → **가장 큰 `id` 1행**.
- SELECT의 `total_points`(row[10])는 파싱 후 **버린다.** 반환 dict의 `total_points`는 재계산 값.

### 반환 레코드 (핵심 키)

| key | 내용 |
|---|---|
| `id` | daily_points.id |
| `date` | activity `date` (`datetime.date`) |
| `subjects` | `{korean, math, ssen, reading, piano, english, advanced_math, writing}` 각 `normalize_points` |
| `manual_items` | JSON list (실패/비list면 `[]`) |
| `manual_history_raw` | 원문 TEXT |
| `manual_points` | XOR 결과 정수 (아래) |
| `total_points` | **재계산** T |
| `created_at` | 파싱된 datetime 또는 None |
| `cumulative_total` | 날짜 오름차순 재계산 total 누적 (정렬 후 부여) |

SQL `ORDER BY date DESC`로 가져온 뒤, `cumulative_total`만 `date` 오름차순(+ `created_at`)으로 다시 돌며 채운다. 리스트 자체는 DESC 순서를 유지한다.

### 일일 공식 (구현과 동일)

```
canonical_manual =
    Σ item.points   if parsed manual_items 가 비어 있지 않은 list
    else column manual_points

T_day = korean + math + ssen + reading
      + piano + english + advanced_math + writing
      + canonical_manual
```

`normalize_points`: int 변환 실패 시 0.

**ReadingRewardEvent를 T_day에 더하지 않는다.** mirror +200은 이미 `canonical_manual` 안에 있다.

**PointsHistory / exemption 독립.**

### created_at vs activity date

- window, PointEvent, Growth `date_in_window` → **`date`**
- `created_at`은 기록 시각. 활동일로 쓰지 않음.

---

## manual_history JSON contract

쓰기 정규화: `parse_manual_entries()` (`app.py`).  
독서 미러 append: `features.reading.rewards._append_manual_item()`.  
읽기: fetch `json.loads`.

실제 코드가 읽고/쓰는 키만 적는다. `label`/`memo`는 CSV formatter가 **읽을 수는** 있으나 parse/reward가 쓰지 않는다 → 아래 CSV 절.

| field | 타입 | required | 의미 | 누가 기록 | 분석 | normalization 입력 | provenance | AI raw 금지 |
|---|---|---|---|---|---|---|---|---|
| `id` | int (>0) | parse가 부여 | 그날 JSON 내부 순번. DB PK 아님 | parse / reward append | PointEvent에 **없음** | 아니오 | 아니오 | 해당 없음 |
| `subject` | str ≤30 (parse) | parse: 빈 문자열이면 항목 skip | 표시 라벨 | 교사 UI / reward 라벨 | PointEvent `raw_subject` | **예** | 아니오 | **예** (packet에 넣지 말 것) |
| `points` | int, parse 시 ±50000 clamp | 사실상 금액 | **저장된 지급/차감** | UI / reward `event.points` | PointEvent `amount` | **금액으로 분류 금지** | 회계 | 값은 집계만, 사유 아님 |
| `reason` | str ≤80 | optional (빈 문자열 가능) | 메모 | 교사 / reward 승인 문구 | `raw_reason` | **예** | 아니오 | **예** |
| `created_by` | str | parse가 author로 채움 | 표시 작성자명 | parse / reward `user_name` | PointEvent에 없음 | 아니오 | 아니오 | **예** (이름) |
| `created_at` | `'YYYY-MM-DD HH:MM:SS'` 문자열 | parse/reward가 utcnow | JSON 항목 기록 시각. **활동일 아님** | parse / reward | PointEvent에 없음 | 아니오 | 아니오 | 가능하면 제외 |
| `presetKey` | str or null | optional. `preset_key` alias도 parse가 받음 | 클릭한 프리셋 key | UI | classifier **힌트만**. 금액 결정 금지 | **예** (1순위) | 아니오 | key는 비교적 안전, reason은 금지 |
| `source_type` | str | optional. 키 있을 때만 보존 | 미러 도메인. 현재 `recommended_reading` / `challenge_reading` | reward append | PointEvent `source_type`, `is_reading_reward_mirror` | 아니오 (구조 메타) | **예** | 식별자성 낮음 |
| `source_child_reading_id` | int | optional | `ChildReading.id` | reward append | **PointEvent field 없음.** JSON에는 남음. revoke 매칭에 사용 | 아니오 | 미러 매칭 (rewards 쪽) | **PK → packet 금지** |
| `source_event` | str | optional | `'start'` / `'complete'` 등 | reward append | PointEvent field 없음 | 아니오 | rewards `_remove_manual_item` | 대체로 비PII |
| `source_event_id` | int | optional | `ReadingRewardEvent.id` | reward append | PointEvent `source_event_id`. mirror helper | 아니오 | **예** | **PK → packet 금지** |

`parse_manual_entries`는 `source_*`를 **이미 있는 키만** 복사한다. 일반 수동 입력에는 보통 없다.

---

## CSV 표시 vs DB 저장

**WARNING:** CSV/엑셀에 `|`가 보여도 DB canonical delimiter가 아니다.

저장: JSON array.

표시: `format_manual_items_for_csv()`:

```
{subject} ({points:+}점)[- {reason}]
```

여러 건은 `" | ".join`.

예 (표시):

```
한자 (+100점) | 프린트 (-100점) - 프린트 사용
```

DB `manual_history` 예 (아동 식별 정보 없음):

```json
[
  {
    "id": 1,
    "subject": "한자",
    "points": 100,
    "reason": "",
    "created_by": "교사표시명",
    "created_at": "2026-08-22 03:00:00",
    "presetKey": null
  },
  {
    "id": 2,
    "subject": "프린트",
    "points": -100,
    "reason": "프린트 사용",
    "created_by": "교사표시명",
    "created_at": "2026-08-22 03:01:00",
    "presetKey": "print"
  }
]
```

`"|"` 문자열을 split 해서 원장을 복원하지 말 것.

---

## manual_history / manual_points XOR

**WARNING:** 둘을 동시에 더하면 총점이 커진다.

fetch 구현 (`manual_items`가 truthy한 list이면 JSON 합, 아니면 컬럼):

```
calculated = sum(points of dict items)
manual_points_canonical = calculated if manual_items else column_manual_points
```

| 상황 | canonical manual | 하지 말 것 |
|---|---|---|
| `manual_history = '[{"points": 200}]'` 이고 컬럼 `manual_points = 200` | **200** (JSON만) | 200+200=400 |
| JSON `[]` 또는 파싱 실패 → `manual_items=[]`, 컬럼 500 | **500** | JSON 0을 “있다”고 더하기 |
| JSON 비어 있지 않은데 컬럼이 stale 999 | **JSON 합만** | 컬럼 신뢰 |

테스트:

- `test_manual_history_xor_does_not_add_column_and_history`
- `test_empty_manual_history_uses_manual_points_column`

PointEvent projector도 같은 분기: `manual_items`가 비어 있지 않은 list면 JSON 경로, 아니면 `manual_points` → `provenance=manual_sum`. JSON 경로에서 amount 0 항목은 이벤트 생략 (합 0과 동일).

---

## ReadingRewardEvent contract

model: `feature_models.ReadingRewardEvent`. 테이블 `reading_reward_event`.

파일 주석: *추천독서 시작/완독 보상 원장. 중복 지급 방지의 정본.*  
`features/reading/rewards.py` 모듈 주석: *DailyPoints.reading_points는 건드리지 않는다.*

| column | type | 의미 |
|---|---|---|
| `id` | INTEGER PK | `source_event_id`로 미러 연결 |
| `child_reading_id` | INTEGER FK `child_reading.id` NOT NULL, index | 아동은 ChildReading 경유 |
| `event_type` | String(32) NOT NULL | `recommended_start`, `recommended_complete`, `challenge_start`, `challenge_complete` |
| `points` | INTEGER NOT NULL | **그 사건에 지급된 금액** (정책 테이블이 아니라 저장된 값) |
| `awarded_on` | DATE NOT NULL, index | 보상 활동일. Growth overlay window |
| `policy_version` | String(32) NOT NULL default `recommended_v1` | 정책 버전 기록 |
| `created_by_user_id` | INTEGER FK user NOT NULL | 승인자 |
| `created_at` | DATETIME | 기록 시각 ≠ `awarded_on` |
| `revoked_at` | DATETIME NULL | 있으면 비활성. Growth overlay는 `revoked_at IS NULL`만 |
| `revoked_by_user_id` | INTEGER NULL | |

**Unique:** `uq_reading_reward_event_reading_type` (`child_reading_id`, `event_type`).

현재 센터 정책 금액 (`READING_REWARD_POLICIES`)은 **쓰기 기본값**이다. 원장 `points`를 재계산해 덮어쓰지 말 것. product 불변식 아님.

---

## Reading reward mirror — 이중 표현, 이중 지급 아님

눈에 잘 띄게 고정한다.

### 정의

| 기록 | 역할 |
|---|---|
| **ReadingRewardEvent** | “이 책 lifecycle에서 이 유형의 보상을 지급했다”는 **독서 domain 사건** |
| **DailyPoints.manual_history mirror** | 그 **동일 금액**을 아동 일일 포인트 총액에 넣는 운영 원장 반영 |

같은 +200이 두 번 지급된 것이 아니다. 목적이 다른 두 domain에 한 사건이 표현된 것이다.

### 대표 예 (서로 다른 실제 포인트 + 한 번의 미러)

| 출처 | 필드 | 금액 | 실제 포인트인가 |
|---|---|---|---|
| 일반 독서 활동 | `daily_points.reading_points` | +100 | **예** (수업/활동 점수) |
| 추천도서 완독 보상 사건 | `reading_reward_event.points` | +200 | 사건의 금액. **총액 가산 소스는 아님** |
| 동일 보상의 일일 반영 | `manual_history[].points` + `source_type=recommended_reading` | +200 | **예** (총액의 일부) |

**실제 DailyPoints canonical total:**

```
reading_points +100
+ mirror manual +200
= +300
```

**잘못: ReadingRewardEvent +200을 total에 다시 합산**

```
+100 + +200 + +200 = +500   ← double count
```

**잘못: mirror를 “중복”이라며 DailyPoints에서 제거**

```
reading +100 만 남김 → 완독보상 +200이 총액에서 사라짐
```

일반 독서 +100과 완독보상 +200은 **서로 다른 실제 포인트**다. 합 +300이 맞다. mirror 삭제로 +100만 남기면 안 된다.

쓰기: reward 코드는 `reading_points`를 수정하지 않고 `manual_history`에 append한다 (`_append_manual_item`). 일일 독서과목과 reward는 **다른 필드**.

Growth:

- `points.period` / fetch T: DailyPoints만 (mirror 포함).
- `rewards.reading_event.points`: `ReadingRewardEvent` overlay. period에 더하지 말 것.
- `rewards.manual.points`: `source_type ∈ {recommended_reading, challenge_reading}` **제외** (`reward_metrics._manual_slice`).

PointEvent v1:

- `ReadingRewardEvent`를 **projection하지 않음** (테이블 미읽음).
- mirror manual 이벤트는 **삭제하지 않음**. amount 유지. `is_reading_reward_mirror`로 표시만.

테스트:

- `test_reward_event_without_daily_points_does_not_add_period_points` — 이벤트만 있으면 period 0.
- `test_reward_reflected_in_manual_history_is_counted_once` — korean 100 + mirror 200 = period 300 (400 아님).
- `test_reading_subject_plus_completion_mirror_is_300`
- `test_fetch_reading_plus_mirror_stays_300_even_if_reward_event_exists`

---

## mirror metadata

manual JSON (reward `_append_manual_item`):

| field | 의미 |
|---|---|
| `source_type` | `'recommended_reading'` 또는 `'challenge_reading'` (`READING_REWARD_POLICIES[].source_type`) |
| `source_event_id` | `ReadingRewardEvent.id` |
| `source_child_reading_id` | `event.child_reading_id` |
| `source_event` | append 시 넘긴 `'start'` / `'complete'` |

제거 매칭 (`_remove_manual_item`): `source_event_id == event.id` 우선, 아니면 `(source_type, source_child_reading_id, source_event)`.

### PointEvent.is_reading_reward_mirror (실제 코드)

`features/points/events.py`:

```
source_kind == 'manual'
AND (
  source_type in {'recommended_reading', 'challenge_reading'}
  OR source_event_id is not None
)
```

- `daily_subject`는 항상 False (`reading_points` +100은 미러가 아님).
- **ReadingRewardEvent 테이블을 조회하지 않음.**
- `source_child_reading_id` / `source_event`는 PointEvent에 없어서 이 property에 안 씀.
- `source_event_id is not None`만으로도 True. 현재 쓰기 경로는 독서 미러만 이 키를 넣는다. 다른 domain이 같은 키를 쓰기 시작하면 이 helper를 재검토해야 한다.
- 미러여도 amount를 0으로 만들지 않음.

상수: `READING_REWARD_MIRROR_SOURCE_TYPES` (points)와 `reward_metrics.READING_REWARD_SOURCE_TYPES`가 같은 두 문자열.

---

## Exemption domain

PointEvent에 넣지 않는 이유 (CURRENT):

- `features/exemption/service.py`: *DailyPoints / 누적포인트 / 학습진도와 독립*.
- ticket/source/usage에 **포인트 금액 컬럼이 없다.**
- 사용은 `used_on` + `subject_key` 1회.
- Growth: `rewards.exemption.usage` = **건수** current/previous/delta + peer. 금액 아님.
- 면제권 지급이 포인트를 대체하는 운영(고학년 선택)이 있어도, 그 선택은 ReadingRewardEvent/면제 장부에 있고 DailyPoints 강제 통합이 아니다.

향후에도 “무조건 PointEvent로 합치기”가 정답이 아니다. 별도 domain으로 두는 것이 현재 계약이다.

---

## PointEvent CURRENT implementation (`e57d4b7`)

파일: `features/points/events.py`.

`@dataclass(frozen=True) class PointEvent`.

**DB 테이블이 아니다.** `fetch_child_daily_point_records` 형태 dict를 `project_point_events`가 변환한 런타임 객체다.

생성 안 함: `amount == 0`, activity_date 파싱 실패, record가 dict 아님, JSON 항목이 dict 아님.

| field | 타입 | 필수 | 의미 | source | AI 전달 (현재) | center-specific? |
|---|---|---|---|---|---|---|
| `activity_date` | `datetime.date` | 필수 | 활동일 | fetch `date` (created_at 아님) | 아직 packet 미연결 | core |
| `source_kind` | str | 필수 | `daily_subject` \| `manual` | projector | 미연결 | core |
| `amount` | int | 필수 | **저장된 부호 있는 정수** | 과목 컬럼 또는 item `points` 또는 fallback 컬럼 | 미연결. 나중에도 집계만 | core (값은 원장) |
| `provenance` | str | 필수 | `daily_column` \| `manual_json` \| `manual_sum` | projector 분기 | 미연결 | core |
| `subject_key` | str \| None | optional | 과목 컬럼 key, 또는 교재완료 mapping | subjects key / classifier | 미연결 | key 집합은 현재 센터 컬럼 |
| `category` | str \| None | optional | 수동 의미. **daily_subject는 None** (UNCLASSIFIED 아님) | classifier 또는 fallback UNCLASSIFIED | 미연결 | mapping은 센터 |
| `item_key` | str \| None | optional | print/clay/… | classifier | 미연결 | 센터 mapping |
| `raw_subject` | str \| None | optional | JSON 원문. **수정하지 않음** | `item.subject` | **기본 전달 금지** | 원문 |
| `raw_reason` | str \| None | optional | JSON 원문 | `item.reason` | **기본 전달 금지** | 원문 |
| `source_type` | str \| None | optional | 미러 태그 | JSON | PK 아님. 집계 플래그용 | core 메타 |
| `source_event_id` | int \| None | optional | ReadingRewardEvent.id | JSON | **packet에 PK 금지** | core 메타 |

넣지 않는 것 (의도): `direction` 저장, `child_id`, `created_at`, `presetKey` 원문 field, `source_child_reading_id`, `source_event`, exemption, `reading_reward` source_kind.

`ManualClassification`: `category`, `subject_key=None`, `item_key=None`. classifier 반환형.

---

## direction contract

저장 field 없음. `direction_for(amount)` / `PointEvent.direction`:

| amount | direction | PointEvent |
|---|---|---|
| `> 0` | `EARN` | 생성 |
| `< 0` | `SPEND` | 생성 |
| `== 0` | `None` | **생성하지 않음** |

별도 field를 두지 않는 이유: `amount=+100` 인데 `direction=SPEND` 같은 모순 상태를 원천 차단.

---

## source_kind (v1)

정확히 두 개:

1. `daily_subject` — fetch `subjects`에서 0이 아닌 컬럼.
2. `manual` — JSON 항목 또는 `manual_sum` fallback.

**`ReadingRewardEvent`는 source_kind가 아니다.** `e57d4b7` projector는 그 테이블을 읽지 않는다.

누군가 `source_kind=reading_reward`를 추가하기 전에 이 문서를 검토할 것. 추가하는 순간 period total에 더할 위험이 생긴다. overlay는 기존 `reward_metrics` / `ReadingRewardEvent`가 이미 담당한다.

---

## daily_subject projection

`features/points/project.py` `_subject_events`.

`record['subjects']` dict를 순회. 키가 무엇이든 0이 아니면 이벤트 1개. 하드코딩된 200/100 해석 없음. 요일 없음.

예:

```
korean=200, math=100, reading=100, ssen=0
→
daily_subject korean +200
daily_subject math +100
daily_subject reading +100
```

음수 과목 값도 그대로 보존 (`test_negative_subject_is_preserved`). 입력 UI는 음수를 거부하므로 정상 운영 경로가 아닐 수 있으나 projector가 고치지 않음.

현재 fetch가 넣는 키: `korean, math, ssen, reading, piano, english, advanced_math, writing` (`CURRENT_SUBJECTS`와 대응). projector는 `CURRENT_SUBJECTS`를 import하지 않고 dict에 있는 키를 쓴다.

센터 정책이 아님:

- 다 맞으면 200 / 부분 100 / 안함 0
- 월·수 영어, 목 피아노

실측 저장된 amount만 본다.

---

## manual projection

`_manual_events` / `_manual_json_event`.

| 입력 | 결과 |
|---|---|
| `manual_items` 비어 있지 않은 list | dict 항목마다 amount≠0이면 `manual` 1건, `provenance=manual_json` |
| list 비어 있음 또는 없음, `manual_points` ≠ 0 | `manual` 1건, `provenance=manual_sum`, `category=UNCLASSIFIED`, raw/source 없음 |
| `manual_points` 0 이고 items 없음 | 수동 이벤트 없음 |

JSON 경로에서 보존: `raw_subject`, `raw_reason`, `source_type`, `source_event_id`, classifier의 category/subject_key/item_key.

`manual_sum`에서 세부 이벤트를 추측하지 않는 이유: 원장에 항목이 없고 합만 있다. 칭찬 3건인지 교재 1건인지 알 수 없다.

classifier:

- `None` → 모든 JSON manual `UNCLASSIFIED` (금액은 유지).
- 반환이 `ManualClassification`이 아니면 `UNCLASSIFIED`.

`presetKey`는 classifier가 읽을 수 있음. projector는 금액을 preset 기본값으로 바꾸지 않음.

---

## `accounting_parts()`

```python
def accounting_parts(record, events=None) -> dict
```

`events is None`이면 `project_point_events((record,))` — **classifier 없이** 재투사하므로 이 경로의 category는 UNCLASSIFIED여도 금액 항등식은 성립.

`record['date']`로 같은 날 이벤트만 필터.

반환:

```python
{
  'canonical_total': int,  # record['total_points']  — fetch record면 재계산 T
  'subject_sum': S,        # daily_subject amount 합
  'manual_sum': M,         # manual amount 합 (미러 포함)
  'balanced': T == S + M,
}
```

**ReadingRewardEvent를 더하지 않는다.** mirror +200은 이미 M.

불일치 시 (구현 그대로):

- residual PointEvent 생성 **안 함**
- DB 수정 **안 함**
- production assert로 프로세스 종료 **안 함**
- `balanced=False`로 관찰 (`test_mismatch_does_not_invent_residual`)

`canonical_total`은 **인자 record의 `total_points` 필드**다. fetch 결과를 넣으면 재계산 T. 저장 컬럼을 그대로 넣은 handmade dict면 저장값과 비교하므로 불일치가 날 수 있다. 그게 함수의 관찰 목적이다.

---

## 현재 센터 mapping (`mapping/current.py`)

함수: `classify_manual(item)`. **`item['points']`를 읽지 않는다.**

presetKey (casefold exact):

| presetKey | category | subject_key | item_key |
|---|---|---|---|
| `textbook` | TEXTBOOK_COMPLETE | 텍스트에서 과목 1개만 추출, 충돌 시 UNCLASSIFIED | None |
| `print` | ACTIVITY_MATERIAL | None | `print` |
| `pencil` | STATIONERY | None | `pencil` |
| `eraser` | STATIONERY | None | `eraser` |
| `pencil_case` | STATIONERY | None | `pencil_case` |

exact alias는 `compact_lookup` 키로 저장. 아래는 **코드에 나열된 원문 패턴** → 결과.

| raw patterns (코드 리터럴) | category | subject_key | item_key | 비고 |
|---|---|---|---|---|
| 국어교재완료, 국어 교재 완료, 교재완료(국어), 교재완료국어 | TEXTBOOK_COMPLETE | korean | | |
| 수학교재완료, 수학 교재 완료, 교재완료(수학), 교재완료수학 | TEXTBOOK_COMPLETE | math | | |
| 쎈교재완료, 쎈 교재 완료, 교재완료(쎈), 교재완료쎈 | TEXTBOOK_COMPLETE | ssen | | |
| 영어교재완료, 영어 교재 완료, 교재완료(영어), 교재완료영어, **영어교재** | TEXTBOOK_COMPLETE | english | | |
| 칭찬, 칭찬점수, 칭찬 점수, 선생님 칭찬, 오늘 잘함, 오늘잘함 | PRAISE | | | |
| 프린트 | ACTIVITY_MATERIAL | | print | |
| 클레이, 아이클레이 | ACTIVITY_MATERIAL | | clay | |
| 비즈 | ACTIVITY_MATERIAL | | beads | |
| 연필 | STATIONERY | | pencil | |
| 지우개 | STATIONERY | | eraser | |
| 필통 | STATIONERY | | pencil_case | |
| 학용품 구입, 학용품구입, 문구류 구입, 문구류구입 | STATIONERY | | **None** | 세부 품목 없음 |

**명시적으로 PRAISE가 아님:** `선생님 도움`, `정리 도움` → UNCLASSIFIED (`test_help_labels_are_not_praise`).

keyword (exact 실패 후, haystack compact/normalized):

| 조건 | 결과 |
|---|---|
| compact에 `교재완료` 또는 normalized에 `교재 완료` | TEXTBOOK_COMPLETE + 과목 토큰 0~1개 (`국어/수학/쎈/영어`). 과목 2개면 UNCLASSIFIED |
| compact에 `칭찬` 또는 `오늘잘함` / normalized `오늘 잘함` | PRAISE |
| compact에 아이클레이\|클레이\|프린트\|비즈 중 **item_key 하나** | ACTIVITY_MATERIAL |
| compact에 연필\|지우개\|필통 중 **하나** | STATIONERY |
| 위 카테고리 hit가 0개 또는 2개 이상 | UNCLASSIFIED |
| 같은 카테고리 안 item_key 2개 (예: 프린트+비즈) | UNCLASSIFIED |

lookup blob: `subject`, `reason`, `subject+' '+reason` 각각의 compact. exact에서 **서로 다른 (category, subject_key, item_key)** 가 2개 이상이면 UNCLASSIFIED.

`EVENT_REWARD` / `OTHER_EARN` / `OTHER_SPEND` / `READING_REWARD` / `UNKNOWN` **카테고리 상수 없음** (v1 미구현).

---

## category contract

| category | 정의 |
|---|---|
| `TEXTBOOK_COMPLETE` | 교재 완료로 확정된 수동 이벤트. `subject_key`가 있으면 과목까지 확정 |
| `PRAISE` | 칭찬류로 확정 |
| `ACTIVITY_MATERIAL` | 프린트/클레이/비즈류 |
| `STATIONERY` | 연필/지우개/필통 또는 학용품·문구 구입 (item_key 없을 수 있음) |
| `UNCLASSIFIED` | **오류가 아니다.** 현재 규칙으로 의미를 안전하게 확정할 수 없는 **정상 상태**. 금액은 회계에 남긴다 |

daily_subject의 `category`는 None. 과목 학습 점수를 TEXTBOOK_COMPLETE로 바꾸지 않음.

---

## item_key / subject_key (mapping이 실제로 내는 값)

**item_key:** `print`, `clay`, `beads`, `pencil`, `eraser`, `pencil_case`. 학용품/문구 generic은 `None`.

**subject_key (교재완료 mapping):** `korean`, `math`, `ssen`, `english`.  
(피아노/독서는 교재완료 alias에 없음. 과목 컬럼 쪽 `reading`/`piano`는 daily_subject.)

**daily_subject subject_key:** fetch 키 그대로 (`advanced_math`, `writing` 포함).

category만 남기고 item/subject를 버리면 “교재완료 +3000”이 어느 과목인지, “재료 -100”이 프린트인지 비즈인지 복원 불가. 그래서 별도 보존.

---

## classifier 알고리즘 (실제 순서)

`classify_manual`:

1. `item`이 dict가 아니면 `UNCLASSIFIED`.
2. **text 파생값** `_blobs(subject, reason)` — 원문 필드는 안 바꿈.
3. **presetKey / preset_key** strip+casefold가 `_PRESET_CATEGORY`에 있으면 `_from_preset` 후 **즉시 return** (exact/keyword 생략). textbook preset은 과목 토큰만 추가 추출.
4. **exact alias** (`_exact`). 충돌 → UNCLASSIFIED. 1히트 → return.
5. **keyword** (`_keyword`). 충돌/0히트/2+카테고리 → UNCLASSIFIED.

금액 분기 없음.

---

## text normalization contract

`features/points/text.py`만.

`normalize_lookup`:

- `None` → `''`
- Unicode **NFKC**
- `strip`
- `casefold`
- 연속 공백 `\s+` → 공백 1개

`compact_lookup`:

- 위 결과에 정규식 `[\s()[\]{}（）【】〔〕]+` 를 빈 문자열로 치환  
  (공백과 **괄호류만**. 마침표·느낌표를 전부 지우지 않음)

원문 `raw_subject` / `raw_reason`은 projector가 `str(value)`로만 복사. NFKC하지 않음 (`test_raw_text_is_not_rewritten`).

normalized/compact는 classification용 파생값. DB 컬럼을 업데이트하지 않음.

---

## 금액 기반 의미 추론 금지

**INVARIANT.**

금지:

- `+3000` → 교재완료
- `-100` → 프린트
- `+200` → 국어 만점
- 추천완독 기본표 200이니까 이 row는 완독보상

`category`와 `amount`는 독립. 정본은 원장에 **저장된 amount**.

다른 센터는 같은 활동을 500 / 1000 / 0 / 제도 없음으로 둘 수 있다.

테스트: `test_amount_does_not_decide_category`, `test_textbook_keeps_stored_amount`, `test_preset_key_is_hint_not_amount`.

---

## 현재 센터 policy vs product core

| 항목 | CURRENT CENTER POLICY (NOT A PRODUCT INVARIANT) | PRODUCT CORE |
|---|---|---|
| 과목 집합 | DailyPoints 8컬럼, `CURRENT_SUBJECTS`, UI 라디오 | “활동일 + 과목키 + 정수 금액”이 있을 수 있음. 목록은 주입 |
| 점수 선택지 | 국어/수학 200·100·0, 쎈/독서/영/피아노/쓰기 라디오 값 (`templates/points/input.html`) | 저장된 정수. 해석하지 않음 |
| 교재완료 | 프리셋 `textbook` 기본 +3000, “교재 완료” 문구, 센터별 3000/2000/1000 관행 | 수동 이벤트 + 저장된 amount. 완료 테이블 없음 |
| 영어 / 피아노 | 컬럼 + UI 100점. **코드에 월/수/목 없음** | 실측 `english_points` / `piano_points` |
| 독서 포인트 | `reading_points` UI 100/200 등 | 과목 컬럼 값 |
| reading reward | `READING_REWARD_POLICIES` 학년표 100/200/400 | 사건 테이블 + DailyPoints mirror + XOR 총액. overlay 분리 |
| manual preset | `DEFAULT_PRESETS` 프린트 -100, 연필 -300, 지우개 -500, 필통 -1000 | 프리셋은 UI. 원장은 JSON points |
| stationery/material | 위 프리셋 + alias (클레이/비즈는 기본 프리셋 **없음**, keyword만) | 부호 있는 수동 이벤트 |
| exemption subject | `EXEMPTION_SUBJECT_KEYS` 국/수/쎈/독서 | 면제는 별 domain |
| 명칭 “포인트” | UI/카피 | 원장은 정수 ledger. 달란트/스티커/없음 가능해야 함 |
| 진도 과목 | `PROGRESS_SUBJECT_KEYS` 국/수/쎈 | 진도 별 domain |

모든 왼쪽 칸: **CENTER-SPECIFIC. NOT A PRODUCT INVARIANT.**

---

## 다기관 dependency boundary (CURRENT)

`project_point_events(records, *, classify_manual=None)`

- `features/points/project.py`는 `features.points.mapping` / `current.py`를 **import하지 않음**.
- 테스트 `test_project_module_does_not_import_current_mapping`이 소스와 `sys.modules`로 잠금.
- `test_injected_classifier_changes_category_without_projector_change`: 같은 raw `특별포인트` +80 → current classifier는 UNCLASSIFIED, fake는 PRAISE. projector 수정 없음.

향후 center A/B는 `classify_manual` (및 fetch가 넣는 subjects 키)만 교체.

포인트 제도가 없는 센터: 원장이 비면 PointEvent 튜플이 비고, Growth는 기존 insufficient/빈 원장 경로. projector core에 “반드시 포인트가 있다”를 넣지 않는 이유.

`features/points/__init__.py`는 `project_point_events`를 재export할 뿐 current mapping을 기본 주입하지 않음. 현재 센터 분류를 쓰려면 호출부가 `classify_manual=classify_manual`을 넘긴다.

---

## Raw text privacy boundary

`raw_subject` / `raw_reason`:

- DB 원문 보존 (normalization이 UPDATE하지 않음)
- 재분류·디버깅에 필요
- PointEvent 내부에 둘 수 있음

**향후 Evidence / Luna에 기본적으로 그대로 넣지 않는다.**

`docs/growth-data-contract.md`도 teacher packet에서 `manual_history`의 `reason` / `created_by`를 금지한다.

나중 방향 (FUTURE, 미구현): `PRAISE` · 30일 4회 · +900점 같은 deterministic aggregate만.

**현재(`e57d4b7`):** PointEvent는 Evidence에 연결되지 않음. 연결 시에도 raw를 packet에 넣지 않는 것이 계약.

---

## 현재 Growth point evidence (composition은 packet 미연결)

확인: `features/growth` 전역에 `PointEvent` / `project_point_events` import **없음**.

기존 흐름:

```
DailyPoints
  → fetch_child_daily_point_records
  → points_metrics / reward_metrics / learning.observed_study_days
  → metrics_bundle
  → build_teacher_evidence_packet   # SCHEMA_VERSION growth_teacher_evidence_v1
  → AI (버튼, 이 문서의 SOT 아님)
```

window: 기본 30일 current / previous. `as_of` 이하만 (`_records_as_of`). 미래 `date`는 Growth가 자름. PointEvent projector는 미래일을 **자체 필터하지 않음**.

| evidence_id prefix | metric payload | source | 계산 |
|---|---|---|---|
| `points.period` `.current/.previous/.delta` | `points_metrics` `period_points` | 재계산 daily `total_points` window 합 | 과목+수동(미러 포함). 구성 분해 없음 |
| `points.cumulative_as_of` | `cumulative_as_of` | as_of 이하 재계산 total 합. 오늘+빈원장만 `Child.cumulative_points` | |
| `points.rwb.period.*` | recent window best | insight 선정 시에만 packet에 포함 | period_points 3창 |
| `learning.observed_study_days` | `point_activity_days` | **DailyPoints 날짜 개수 proxy**. 출석 아님 (`attendance: False`, source `daily_points.date`) | |
| `rewards.manual.points` | `reward_metrics.manual_points` | JSON에서 reading `source_type` **제외** 후 합. 없으면 컬럼 1건 | period에 다시 더하지 말 것 |
| `rewards.manual.event_count` | 위 event_count | 동일 | |
| `rewards.manual.points.peer.*` | peer median 등 | 또래 수동 합 | `MIN_PEER_N=2` 아니면 insufficient |
| `rewards.reading_event.points` | `reading_reward_points` | **ReadingRewardEvent** `awarded_on` window, `revoked_at IS NULL` | period와 **합산 금지** |
| `rewards.exemption.usage` | 사용 **건수** | ExemptionUsage `used_on` | 포인트 아님 |
| `rewards.exemption.usage.peer.*` | peer | | |
| `reading.activity_days` / `reading.completions` | 독서 활동 | ChildReading+ReadingDay | 포인트 구성 아님 |
| `reading.recommended.activity_days` / `.completions` | 추천 프로그램 | | 포인트 아님 |

`points_metrics`는 추가로 `subject_active_days`, `manual_points_sum`을 payload에 넣지만, `_points_facts`는 period/cumulative(/rwb)만 packet에 복사한다. `child_cumulative_points`는 metrics에 실려도 evidence 금지.

delta: `_period_pair`가 current−previous 형태의 필드를 만듦 (`points.period.delta` 등).

---

## 현재 Growth에서 손실되는 정보

canonical fetch에는 있으나 **teacher Evidence Packet에는** 없음.
`metrics_bundle['point_composition']`에는 subject/manual/category 구성이 내부적으로 계산된다. packet/AI에는 아직 복사되지 않는다.

| 정보 | 살아 있는 곳 | 사라지는 곳 |
|---|---|---|
| 과목별 amount | fetch `subjects`, PointEvent daily_subject | `_points_slice`가 `period_points` 한 숫자로 합침 |
| 과목별 active days | `_points_slice.subject_active_days` | `_points_facts`가 복사 안 함 |
| 수동 item별 amount/사유/preset | `manual_items`, PointEvent | `_manual_slice` 합·건수 (미러 제외). packet은 합만 |
| 교재완료 / 칭찬 / 재료 / 문구 | mapping 있으면 PointEvent.category | Growth 미연결. packet 없음 |
| earn/spend composition | PointEvent.direction | Growth 없음 |
| 영어/피아노 breakdown | subjects.english/piano | period total에 흡수 |
| XOR 이전 컬럼 vs JSON | raw DB | fetch가 이미 한쪽으로 접음 |
| PointsHistory | audit table | 미사용 |
| stored `total_points` | DB 컬럼 | fetch가 재계산으로 대체 |

압축 예: 국어 200 + 수학 100 + 교재 JSON +3000 + 프린트 -200 → `points.period` **3100** 한 값. (아래 예제 B는 200+3000-200=3000.)

---

## Accounting examples

### A. 기본 과목

```
korean +200
math +100
manual 없음
T = 300
S = 300, M = 0
```

PointEvent 2개: daily_subject korean, daily_subject math.

### B. 교재완료 + 사용

```
korean +200
manual TEXTBOOK_COMPLETE +3000   (저장된 값. 3000이라서가 아님)
manual ACTIVITY_MATERIAL print -200
T = 200 + 3000 + (-200) = 3000
```

### C. 독서 + 완독보상 (가장 중요)

```
reading_points = +100          ← 일반 독서 활동 (다른 실제 포인트)
manual mirror  = +200          ← 완독보상 DailyPoints 반영
ReadingRewardEvent.points = +200  ← 같은 보상의 사건 기록
```

PointEvent 합 = **300**. canonical T = **300**.  
ReadingRewardEvent를 더하면 500 → **금지**.  
mirror를 지우면 100 → **금지**.

### D. manual fallback

```
manual_history 없음/빈 list
manual_points = +500
→ PointEvent 1: provenance=manual_sum, UNCLASSIFIED, +500
T = S + 500
```

세부 사유 추측 금지.

### E. 금액이 같아도 의미는 다를 수 있음

`points=3000`, `subject=기타지급` → UNCLASSIFIED +3000. TEXTBOOK_COMPLETE가 아님.

---

## Known edge cases

| case | 원장/fetch | PointEvent |
|---|---|---|
| duplicate child/date | `MAX(id)` 1행 | fetch 결과만 봄 |
| malformed JSON | `manual_items=[]` → 컬럼 XOR | `manual_sum` if column ≠ 0 |
| XOR | JSON 우선 | 동일 |
| multiple manual items | JSON array | 항목당 1 이벤트 |
| amount 0 과목/수동 | 컬럼 0 / points 0 | 이벤트 없음 |
| negative manual | 허용 (차감) | SPEND, 분류는 텍스트 |
| negative subject | UI 거부, DB는 INTEGER | 그대로 보존 |
| unknown text | JSON 원문 유지 | UNCLASSIFIED |
| classifier conflict | n/a | UNCLASSIFIED |
| invalid classifier return | n/a | UNCLASSIFIED |
| classifier omitted | n/a | JSON도 UNCLASSIFIED, 금액 유지 |
| manual_sum | 컬럼만 | 한 건 UNCLASSIFIED |
| reading reward mirror | JSON + 이벤트 테이블 | manual 이벤트 유지 + flag. 테이블 미읽음 |
| future date | row 존재 가능 | projector 포함. **Growth window가 as_of로 제외** |
| created_at ≠ date | 둘 다 저장 | `activity_date=date`만 |
| stored total mismatch | fetch는 저장 total 무시 | `accounting_parts`는 넘긴 `total_points`와 S+M 비교 |
| old JSON without source_* | 미러 메타 없음 | `is_reading_reward_mirror` False. 자유 텍스트면 UNCLASSIFIED. 금액을 사건 테이블과 합치지 말 것 |

쓰기 경로 `.first()` vs 읽기 `MAX(id)` 불일치 가능 (`docs/growth-data-contract.md` §6). 해결된 상태가 아님. 읽기 canonical은 MAX(id).

---

## Debugging Playbook

실제 경로.

### Case A: 화면 포인트와 Growth 포인트가 다르다

1. `daily_points` raw (`date`, 과목 컬럼, `manual_history`, `manual_points`, stored `total_points`).
2. `app.fetch_child_daily_point_records(child_id)` — 재계산 `total_points`, XOR, MAX(id).
3. canonical T vs 화면이 쓰는 저장 total / `Child.cumulative_points`.
4. Growth window: `features/growth/windows.py`, `as_of`, 30일, `_records_as_of` (미래일·창 밖 제외).
5. `points_metrics._points_slice` `period_points`.
6. `features/growth/evidence_packet.py` `_points_facts`.

화면이 저장 `total_points`나 live cumulative를 보여 주고 Growth는 재계산+window면 차이가 날 수 있다. 먼저 fetch T를 기준으로 삼을 것.

### Case B: 총포인트가 예상보다 크다

1. 과목 컬럼 합 S.
2. `manual_history` JSON 합.
3. **컬럼 `manual_points`를 JSON과 더했는지** (XOR 위반).
4. 같은 날짜 여러 row — fetch는 MAX(id)만, 다른 합계 경로가 전 row SUM인지 (`update_cumulative_points`).
5. **`ReadingRewardEvent.points`를 DailyPoints T에 다시 더했는지.**

### Case C: 독서 완독보상이 두 번 계산된다

1. `reading_reward_event` row (`points`, `awarded_on`, `revoked_at`).
2. 그날 `manual_history` mirror (`source_type`, `source_event_id`).
3. metadata 존재 여부.
4. PointEvent: mirror amount가 M에 있는지, 별도 reading_reward 이벤트를 projector가 만들었는지 (**만들면 안 됨**).
5. canonical T = reading_points + mirror (예: 100+200=300).
6. `reward_metrics.reading_reward_points`를 `period_points`에 더했는지.

### Case D: 독서 보상이 빠졌다

두 상황을 구분:

- **A.** mirror를 중복으로 보고 DailyPoints/JSON에서 지움 → 총액에서 실보상 소실. ReadingRewardEvent만 남음. Growth period는 줄어듦. overlay만 남음.
- **B.** `ReadingRewardEvent`만 있고 DailyPoints 반영 실패 (`test_reward_event_without_daily_points_does_not_add_period_points`처럼 period 0). 사건 기록은 있으나 **실제 포인트 총액에 안 들어감.**

실총액 정본은 항상 DailyPoints fetch.

### Case E: 교재완료가 잘못 분류된다

1. JSON `raw_subject` / `raw_reason` (원문).
2. `normalize_lookup` / `compact_lookup`.
3. `presetKey`.
4. exact alias 표.
5. keyword `교재완료` + 과목 토큰 충돌 (국어+수학).
6. UNCLASSIFIED가 맞는지 — 강제 TEXTBOOK_COMPLETE 금지.

### Case F: T != S + M

1. `accounting_parts`에 넣은 `record['total_points']`가 fetch 재계산인지 저장 컬럼인지.
2. subject 이벤트 vs `subjects` 0 필터.
3. JSON 이벤트 vs 비dict/0 points skip.
4. `manual_sum` vs JSON 경로 혼용.
5. fetch XOR vs projector 분기 불일치 (둘 다 `manual_items` truthy).
6. `normalize_points` vs `_as_int` (둘 다 실패 시 0).

원장을 고쳐서 항등식을 맞추지 말고, 어느 입력이 비권위인지 먼저 본다.

---

## 금지되는 위험한 리팩터링

Data Contract 검토 없이 하지 말 것.

- ReadingRewardEvent와 mirror가 중복처럼 보인다고 **하나 삭제**
- ReadingRewardEvent amount를 DailyPoints **total에 추가**
- `manual_history` + `manual_points` **동시 합산**
- stored `total_points`를 canonical로 승격
- amount만 보고 category 추론
- `mapping/current.py`를 `project.py`에 하드코딩 import
- unknown/UNCLASSIFIED를 특정 category에 강제 배정
- `raw_subject` / `raw_reason` / `created_by`를 LLM packet에 그대로 포함
- Exemption을 임의로 PointEvent에 통합
- PointEvent를 DB SOT처럼 persist/migration
- `source_kind=reading_reward`를 총액 파이프에 삽입
- 영어/피아노 요일을 분석 코어에 하드코딩
- 200/100/3000을 product invariant로 코드화

---

## Test contract

baseline commit: **`e57d4b7`** (PointEvent). composition 이후 full suite **885 OK**.

### `tests/test_point_events.py` — 25 OK

| 그룹 | 테스트 |
|---|---|
| 과목 | `test_zero_subject_creates_no_event`, `test_positive_subject`, `test_negative_subject_is_preserved`, `test_multiple_subjects` |
| 수동 | `test_manual_positive_and_negative`, `test_multiple_manual_events_same_day`, `test_zero_manual_creates_no_event`, `test_unknown_is_unclassified`, `test_help_labels_are_not_praise`, `test_conflict_is_unclassified`, `test_raw_text_is_not_rewritten`, `test_activity_date_not_created_at`, `test_manual_sum_fallback`, `test_textbook_keeps_stored_amount`, `test_amount_does_not_decide_category`, `test_keyword_examples`, `test_stationery_generic_has_no_item_key`, `test_preset_key_is_hint_not_amount` |
| 독서 미러 +300 | `test_reading_subject_plus_completion_mirror_is_300`, `test_mirror_is_kept_in_manual_sum`, `test_fetch_reading_plus_mirror_stays_300_even_if_reward_event_exists` |
| 회계 | `test_balanced_subjects_and_manual`, `test_mismatch_does_not_invent_residual` |
| 다기관 경계 | `test_injected_classifier_changes_category_without_projector_change`, `test_project_module_does_not_import_current_mapping` |

특히 중요한 invariant:

- `test_fetch_reading_plus_mirror_stays_300_even_if_reward_event_exists`
- `test_amount_does_not_decide_category`
- `test_project_module_does_not_import_current_mapping`

### `tests/test_point_composition.py`

- `test_subject_korean_math_net_300`
- `test_textbook_and_print_composition`
- `test_reading_plus_mirror_net_300_excludes_mirror_from_manual`
- `test_praise_two_events`
- `test_unclassified_earn_and_spend`
- `test_textbook_by_subject_math_and_ssen`
- `test_stationery_without_item_key_stays_generic`
- `test_empty_window_is_zero`
- `test_current_previous_date_boundaries`
- `test_output_has_no_raw_text_fields`
- `test_period_total_matches_composition_net_current_and_previous`
- `test_reading_mirror_and_reward_event_stay_300`

### 기존 regression (문서 작성 시점 묶음 122 OK에 포함됐던 축)

`tests/test_growth_data_contract.py` invariant 이름:

- `test_points_history_audit_does_not_change_period_points`
- `test_reward_event_without_daily_points_does_not_add_period_points`
- `test_reward_reflected_in_manual_history_is_counted_once`
- `test_manual_history_xor_does_not_add_column_and_history`
- `test_empty_manual_history_uses_manual_points_column`
- `test_stored_total_points_is_not_authoritative`

관련: `tests/test_manual_point_presets.py`, `tests/test_recommended_rewards.py`, `tests/test_growth_reward_metrics.py`, `tests/test_growth_metrics.py`, `tests/test_exemption.py`.

---

## Point composition metrics (CURRENT)

파일: `features/growth/point_composition.py`.

순수 집계. `PointEvent` iterable만 받는다. `mapping/current.py`를 import하지 않는다.
`ReadingRewardEvent` 테이블을 조회하거나 금액을 다시 더하지 않는다.

함수:

- `summarize_point_events(events, *, start_date, end_date)` — inclusive `activity_date` 창
- `point_composition_from_events(events, *, as_of=None, window_days=30)` — 기존 `current_window` / `previous_window`

창 정의는 `features/growth/windows.py`와 동일. `created_at` 사용 금지. current `end` = `as_of` 이므로 미래일은 제외.

Growth 연결 (`features/growth/metrics.py`):

1. `_canonical_daily_point_records` → `_records_as_of`
2. `features.points.project_current_center_events` (classifier 주입은 **points 패키지**에서만)
3. `point_composition_from_events`
4. `metrics_bundle['point_composition']`

`features/growth/*`는 `mapping/current.py`를 직접 import하지 않는다.

### 창 결과 키

`current` / `previous` 각각:

| 키 | 의미 |
|---|---|
| `net_points` | 창 안 **모든** PointEvent `amount` 합 (mirror 포함). canonical `points.period`와 같아야 함 |
| `total_earn_points` | `amount > 0` 합 |
| `total_spend_points` | `amount < 0` 합. **부호 있는 음수** (예: `-900`). 절대값 필드를 따로 두지 않음 |
| `subjects.{key}.points` / `active_days` | `source_kind=daily_subject`. 0이 아닌 이벤트가 있는 서로 다른 `activity_date` 수 |
| `manual.earn_points/count` `spend_points/count` | `manual` 중 **mirror 제외** |
| `textbook.points/count/by_subject` | non-mirror `TEXTBOOK_COMPLETE`. `subject_key=None`은 total에만 |
| `praise.points/count` | non-mirror `PRAISE` |
| `material.points/count/by_item` | non-mirror `ACTIVITY_MATERIAL`. `item_key=None`은 total에만 |
| `stationery.points/count/by_item` | non-mirror `STATIONERY` |
| `unclassified.earn_*/spend_*` | non-mirror `UNCLASSIFIED` |

정본: `net_points = Σ PointEvent.amount`.
category 합 = net 이 **아님** (daily_subject + UNCLASSIFIED + mirror 때문에).

결과 dict에 `raw_subject` / `raw_reason` 없음.

delta는 v1에 넣지 않음 (Evidence 단계).

빈 창: `net_points=0`, `subjects={}`, 카테고리 count 0. insufficient 판정은 이 함수가 하지 않음.

테스트: `tests/test_point_composition.py`.

---

## FUTURE — Evidence / Luna (아직 구현 안 됨)

```
metrics_bundle['point_composition']
  → Evidence Packet aggregate     # 없음
  → Luna
```

구현됐다고 쓰지 말 것. packet에 composition을 넣을 때 raw text를 넣지 말 것. `ReadingRewardEvent` overlay를 period/`net_points`에 더하지 말 것.
---

## FUTURE — 다기관화

미구현. 목표: 센터마다 코드를 포크하지 않고 **설정/mapping 교체**.

향후 설정 후보:

- reward system on/off
- display name: 포인트 / 달란트 / 스티커 / 없음
- subjects
- input values (200/100 등)
- manual aliases / classifier
- textbook-completion reward 사용 여부·금액
- catalog/item
- reading reward policy
- exemption subject

현재 구현이 보존하는 것: `classify_manual` 주입, projector의 센터 alias 비의존, 금액≠의미, 미러≠이중지급, 면제 분리.

Rule Engine / 센터 설정 UI / 새 ledger table은 **없음**.

---

## Change Log

### 2026-09-03 (composition)

- PointEvent[] → current/previous composition metrics 구현
- `features/growth/point_composition.py` 순수 집계
- `metrics_bundle['point_composition']` 내부 연결. Evidence/AI 미연결
- net = 모든 PointEvent 합 (mirror 포함). manual/category는 mirror 제외
- `points.period` == `composition.net_points` regression
- total_spend_points는 signed 음수
- raw_subject/raw_reason 결과 제외
- full suite 885 OK

### 2026-09-03

- Initial Point / Reward 구조를 이 파일에 잠금
- Runtime PointEvent projection (`e57d4b7`) 문서화
- current-center deterministic normalization 문서화
- Reading reward mirror semantics 문서화
- accounting invariant `T = S + M` 문서화
- center-specific policy / product-core boundary 문서화
- AI raw-text privacy boundary 문서화 (연결은 FUTURE)
- PointEvent가 아직 Growth에 연결되지 않음을 명시

Baseline: `e57d4b7`
