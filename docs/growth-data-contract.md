# Growth Data Contract

이 문서는 `HEAD` 기준 Growth 코드가 **실제로 사용하는** 운영 데이터 정본을 잠근다.
여기에 적힌 규칙은 구현 의도가 아니라 `features/growth/`와
`app.py`의 `fetch_child_daily_point_records()`에서 확인된 semantics다.

sanitized LLM payload, anonymizer, Subject 일반화, DailyPoints unique 제약은
**구현되어 있지 않다.** 없는 것을 있는 것처럼 쓰지 않는다.

---

## 1. Purpose / Non-goals

이 문서는 Growth 및 향후 AI 계층이 어떤 운영 데이터를 사실의 정본으로
사용하는지 잠그는 계약이다.

이번 계약은 다음이 **아니다**.

- schema 재설계 / migration
- 기존 데이터를 새 테이블로 이관
- multi-tenancy 설계
- Subject 일반화
- LLM / prompt / vector DB 구현
- Growth Story / rank / 새 metric / threshold 변경
- 운영 DB cleanup
- Step 4 dashboard UI

코드가 이미 하는 일을 명시하고, 최소 regression test로 그 일을 고정한다.

---

## 2. Reading source-of-truth

| 모델 | 역할 |
|---|---|
| `ChildReading` | 한 아동 / 한 책 lifecycle source |
| `ReadingDay` | 실제 날짜별 독서 활동 source |
| `Book` | 책 metadata / master |
| `ReadingRewardEvent` | 추천·도전 프로그램 reward ledger. **독서 활동 자체의 source가 아님** |

Growth reading metrics (`reading_metrics`)는 **`ChildReading` + `ReadingDay`만** 읽는다.
`Book.ai_difficulty_*`, `ReadingRewardEvent`, `ReadingDay.review_text`는 쓰지 않는다.

### 날짜

Growth window / snapshot에 쓰는 컬럼:

- 활동일: `ReadingDay.date`
- 시작: `ChildReading.started_on`
- 완독: `ChildReading.completed_on` (`status == completed`)
- 중단: `ChildReading.ended_on` (`status == abandoned`)

`created_at` / `updated_at`(UTC datetime)은 Growth activity date가 아니다.

### 집계 의미

- `reading_days`: `ReadingDay` **row 수가 아니라** `date`의 unique 달력일 집합.
  같은 아동이 같은 날짜에 두 row를 가져도 하루로 센다.
- `started_count`: `started_on`이 window ∩ as_of 이하인 권 수.
  시작만 있고 `ReadingDay`가 없으면 `reading_days`에 들어가지 않는다.
- `completed_count` / `completed_by_program`: `status == completed` 이고
  `completed_on`이 window ∩ as_of 이하.
- `abandoned_count`: `status == abandoned` 이고 `ended_on`이 window ∩ as_of 이하.

운영 쓰기는 아동당 진행 중 책 1권, 아동당 달력일 1건을 추가로 막는다.
스키마 unique는 `(child_reading_id, date)`다. 아동+날짜 unique는 DB 제약이 아니다.

### rating

- `difficulty_rating`, `fun_rating`은 **완독 시점 `ChildReading` 평가** source다.
- 평균은 해당 window에서 완독되고 as_of 이하인 표본만 사용한다.
- 값이 `None`인 평가는 표본에서 제외한다. 빈 표본의 `average`는 `None`이지 0이 아니다.
- `paired_experience_rating`은 한 `ChildReading`에 difficulty와 fun이 **둘 다** 있는
  completed 표본만 쓴다. 개별 평균과 다를 수 있다.
- cross insight는 이 paired family만 쓴다.

`review_text`는 현재 Growth 분석 source가 아니다.

---

## 3. Learning Progress source-of-truth

| 모델 | 역할 |
|---|---|
| `LearningProgressEntry` | 특정 날짜에 기록된 교재 / page **snapshot** source-of-truth |
| `LearningSubject` | 현재 임시 subject master (`korean` / `math` / `ssen`) |
| `LearningRecord` | legacy. **Growth source가 아님** |

Growth (`progress_metrics`)는 `LearningProgressEntry`만 읽는다.

현재 보는 것:

- `progress_entry_count` / `progress_entry_count_by_subject`: window 안 **기록 건수**
- `latest_snapshot_by_subject`: `recorded_on <= as_of` 중 `(recorded_on, id)` 오름차순 마지막 1건.
  current window 밖이어도 as_of 이전이면 스냅샷으로 남는다.

page delta, 학습량, “공부를 시작했다” 같은 추론은 현재 Growth metric이 아니다.

날짜 컬럼: `recorded_on`.
`created_at`은 Growth activity date가 아니다.

동일 `(child_id, learning_subject_id, recorded_on)`은 DB unique다.
같은 날 저장은 overwrite다. 포인트식 `MAX(id)` 중복 규칙은 progress에 적용하지 않는다.

Planning storage (`LearningWorkbookPlan`, `CenterStudyCalendar`, `ChildStudyWeekdays`)는
학습 계획 foundation이다.

deterministic planner (`features/planning/planner.py`)는
`LearningProgressEntry` snapshot + matching `LearningWorkbookPlan`
+ effective weekdays를 읽어 아동/과목 상태를 계산한다.
**Growth `learning` metric family**는 planner canonical 결과를 재사용한다.
page advance / peer median / observed study days는 planner 입력이 아니며
planner 숫자를 다시 계산하지 않는다.

exclusion 미입력(`exclusion_ranges_json` NULL)은 v1 20% estimated fallback이다.
명시적 `[]`(제외 0개)와 구분한다. planner는 `workload_kind`로 이 구분을 보존한다.

### Learning Growth metrics (deterministic facts)

`progress_entry_count` / `latest_snapshot_by_subject` 의미는 그대로다.
아래는 별도 `bundle['learning']` family다. 이번 Step에서 insight candidate는 만들지 않는다.

- **page advance**: window 종료 시점 최신 same-book snapshot − `recorded_on < window.start` 인 최신 same-book baseline.
  window 내부 첫 기록을 baseline으로 쓰지 않는다. future row 제외.
- **freshness**: `MAX_PROGRESS_SNAPSHOT_AGE_DAYS = 21`.
  baseline은 `window.start` 기준, endpoint는 `window.end` 기준, age > 21이면 stale.
  stale/no-baseline/cross-book은 숫자 0이 아니라 unavailable (`comparable=false`).
- **cross-book subtraction 금지**. `normalize_textbook_title` 정확 일치만.
- **current vs previous trend**: 양쪽 page advance가 available이고 endpoint 교재가 같을 때만 delta.
  교재가 바뀌면 current advance는 남을 수 있으나 trend `comparable=false`.
- **raw negative delta는 보존**. 능력 저하 해석은 하지 않는다.
- **peer**: self 제외, `Child.grade` + subject + target의 **현재 latest snapshot 교재**가 동일,
  `include_in_stats=True`, peer/target latest snapshot age ≤ 21 (`as_of` 기준).
  peer의 최신 subject snapshot이 다른 교재면, 과거 same-book 기록이 있어도 제외.
- **peer_n / median**: target은 n에 넣지 않음. n=0 → median None. 작은 n도 숨기지 않음.
  짝수 n의 .5 median은 core에서 그대로 둔다.
- **observed study days**: canonical `point_activity_days` 재사용 (DailyPoints 날짜 proxy).
  Attendance source가 아니다. pages/day 비율은 만들지 않는다.
- **plan**: Step C `build_child_learning_plan_statuses` 결과를 복사. 재계산 없음.

---

## 4. Points source-of-truth

Growth의 canonical point reader는 `app.fetch_child_daily_point_records()`다.
`points_metrics`는 이 함수의 결과만 기간 집계한다.

### Canonical row

동일 `child_id` + `date`에 DailyPoints가 여러 개 있으면 **`MAX(id)` 1행**을 고른다.

### Canonical total (저장 `total_points`를 그대로 쓰지 않음)

선택된 행에서 total을 다시 계산한다.

```
canonical total
  = 과목 컬럼 합 (korean, math, ssen, reading, piano, english, advanced_math, writing)
  + canonical manual points
```

SELECT에 `total_points`가 있어도 Growth는 그 컬럼 값을 기간 합계에 쓰지 않는다.

### Canonical manual (XOR)

`fetch_child_daily_point_records()` 실제 규칙:

- `manual_history`를 JSON list로 파싱했을 때 **항목이 1개 이상**이면
  그 dict들의 `points` 합이 canonical manual이다. **컬럼 `manual_points`는 무시한다.**
- list가 비었거나 파싱 결과가 빈 list이면 컬럼 `manual_points`를 쓴다.
- 둘을 동시에 더하지 않는다.

### Growth period_points

as_of 이하 canonical row 중 current/previous window에 들어가는 행의
**재계산 total 합**이다.

표시용 `manual_points_sum`은 같은 canonical `manual_points`의 window 합이다.
이 값을 `period_points`에 다시 더하지 않는다.

### 명시적으로 Growth period sum source가 아닌 것

| 데이터 | 역할 | Growth 기간 합계 |
|---|---|---|
| `PointsHistory` | 입력/수정 **audit** | 사용하지 않음 |
| `Child.cumulative_points` | live / cache | ledger가 있으면 evidence로 쓰지 않음 |
| `ReadingRewardEvent` | reward ledger | DailyPoints / `manual_history`에 반영된 뒤 **다시 더하지 않음** |
| `manual_history` | 그날 수동항목 원장 | canonical total 계산에 XOR로 이미 들어감. period_points에 별도 재가산하지 않음 |

추천/도전 보상 쓰기는 `DailyPoints.reading_points`를 건드리지 않고
`manual_history`에 append한다. 일일 독서과목 포인트와 reward는 다른 필드다.

`update_cumulative_points()`는 모든 `DailyPoints.total_points`를 SUM한다
(`MAX(id)` 미적용, 저장 total 컬럼 사용). 이것은 live cache 갱신이지
Growth canonical이 아니다.

---

## 5. cumulative_as_of semantics

분석 정본은 `cumulative_as_of`다. `current_cumulative`는 같은 Optional alias다.

실제 구현 (`features/growth/metrics.py` `_cumulative_as_of`):

**A.** `as_of` 이하 canonical ledger row가 1건 이상 있으면
그 행들의 재계산 total 합. 값이 0이어도 **확정 0**.

**B.** `as_of == kst_today()` 이고 canonical ledger가 없으면
`Child.cumulative_points or 0` (오늘 시점 빈 원장 fallback).

**C.** historical `as_of` 이고 canonical ledger가 없으면 **`None`**.
잔존 원장이 없다고 그 시점 누적이 0이었다고 증명할 수 없다.
`reset_data`로 과거 DailyPoints가 사라진 경우도 같다.

`None`을 0으로 해석하지 않는다.
`child_cumulative_points` live cache는 Growth insight / comparison /
historical snapshot / AI evidence의 사실 source로 사용하지 않는다.
metrics payload에 실려도 evidence가 아니다.

---

## 6. Canonical / duplicate semantics

### Reading

`reading_days` = unique calendar date 집합.
스키마는 `(child_reading_id, date)` unique다.
아동당 같은 날짜 1건은 쓰기 경로 가드이며 DB 제약이 아니다.

### Progress

`(child_id, learning_subject_id, recorded_on)` unique.
동일 subject/date 중복을 정상 상태로 보지 않는다.

### Points

동일 child/date는 **`MAX(id)` canonical**.
`DailyPoints`에 `(child_id, date)` DB unique는 **없다**.
이 부재는 해결된 상태가 아니다. §12 known legacy.

쓰기 경로(`points_input`, `add_manual_points`, reward `_get_or_create_daily`)는
`.first()`를 쓴다. Growth 읽기는 `MAX(id)`다. 중복 row가 있으면
쓰기와 읽기가 다른 행을 볼 수 있다. 이번 계약은 읽기 canonical만 잠근다.

---

## 7. Date / snapshot contract

Activity calendar: **KST date** (`features/dates.py`).

production 기본 `as_of`: `kst_today()` → `actual_kst_today()`
(`datetime.now(KST).date()`).

`CLC_DEV_DATE_CONTROL=1` 이고 production이 아닐 때만 session override가 켜진다.
교사 Growth 라우트는 그 경우에만 `?as_of=`를 받는다. production은 query `as_of`를 무시한다.

### Window

- current = `as_of` 포함 최근 `window_days`일. start = `as_of - (window_days - 1)`.
  기본 30일.
- previous = 그 직전 같은 길이. `previous.end == current.start - 1 day`.
- 시작일과 종료일 **모두 inclusive**.

`on_or_before(value, as_of)`: `value is not None and value <= as_of`.

`as_of` **이후** 데이터는 다음을 바꾸면 안 된다.

- window metric
- latest snapshot
- cumulative_as_of

### Growth가 쓰는 날짜 컬럼

| 영역 | 컬럼 |
|---|---|
| reading 활동일 | `ReadingDay.date` |
| 시작 / 완독 / 중단 | `started_on` / `completed_on` / `ended_on` |
| progress | `LearningProgressEntry.recorded_on` |
| points | `DailyPoints.date` |

`created_at` UTC datetime을 Growth activity date로 사용하지 않는다.

`available_from`은 **현재 DB에 남아 있는 최초 관측일**이다.
정책 시작일, 배포일, 센터 개소일, 실제 활동 시작일이 아니다.
`comparable`은 그 날짜가 previous window 시작일을 덮는지 보는 보수적 heuristic이다.

---

## 8. Missing-value contract

`0`과 `None`을 구분한다.

| 값 | 의미 |
|---|---|
| `0` | 관측 가능한 원장에서 실제 값이 0 (예: window 안 canonical 합이 0, 기록 건수 0) |
| `None` | 해당 시점 값을 현재 retained data로 확정할 수 없음 (예: historical empty ledger의 `cumulative_as_of`, 빈 rating 표본의 `average`) |

추가로 구분하는 것:

- 빈 표본 (`sample_count == 0`, average `None`) ≠ 평균 0
- `comparable == false` ≠ 값이 0
- previous가 0인 일부 insight는 “원장 없이 0에서 늘었다”고 단정하지 않는다

UI나 향후 LLM이 `None`을 0으로 바꿔서는 안 된다.
현재 insight 코드는 비교에 쓰는 숫자가 `None`이면 delta를 만들지 않는다.

---

## 9. Deterministic Growth boundary

현재 구현된 사실 계층:

```
operational ledgers
    → metrics_bundle()
    → InsightCandidate + evidence
    → deterministic fallback copy
    → Growth view model (교사 HTML)
```

코드가 소유하는 것:

- metric 계산
- window / as_of
- delta / sample size
- comparability / `available_from`
- evidence `source` 라벨
- fallback headline (새 사실을 만들지 않음)

`importance`는 화면 노출 순서(0–100)이지 통계적 confidence가 아니다.

교사 라우트는 view model에서 raw `bundle`을 제거하고 HTML에 넘긴다.
이것은 UI 조립이지 LLM sanitizer가 아니다.

---

## 10. Future LLM boundary

**LLM은 아직 구현되지 않았다.** sanitized payload schema도 없다.

향후 계약 방향만 적는다. 아래 화살표의 마지막 두 단계는 미구현이다.

```
DB / raw ORM
    → deterministic metrics
    → InsightCandidate / evidence
    → sanitized structured payload     # 미구현
    → future LLM                       # 미구현
```

LLM이 직접 다음을 탐색하는 구조는 사용하지 않는다.

- ORM query / SQL
- `ChildReading` / `ReadingDay` / `LearningProgressEntry` raw
- `DailyPoints` raw
- `PointsHistory`
- live cache (`Child.cumulative_points`)
- arbitrary notes / `review_text` / `manual_history`

넘겨도 되는 후보(이미 deterministic인 것)는 metrics 숫자, window,
`comparable`, evidence source, fallback copy id다.
**구체 payload schema는 이 문서에서 확정하지 않는다.**

---

## 11. Privacy boundary

**future contract requirement.** anonymizer / sanitizer는 구현되어 있지 않다.

향후 외부 LLM 기본 입력에서 제외할 대상으로, 현재 코드에 존재하는 필드:

- `Child.name`
- `Child.viewer_slug` / viewer token
- `User` identity (`username`, `name`, `email`, `firebase_uid`, `id`)
- 내부 PK / FK (`child_id`, `book_id`, `child_reading_id` 등)
- 센터 식별 값 (`CENTER_NAME` env. 센터 전용 DB id 컬럼은 없음)
- `ChildNote.note`
- `ReadingDay.review_text`
- `DailyPoints.manual_history`의 `reason` / `created_by`
- `PointsHistory.change_reason`
- raw URL (viewer report URL, `/nfc/<child_id>` 등)

Book title, 교재명, `Child.grade` 등은 식별 가능성 판단이 끝나지 않았다.
이 문서에서 허용/금지를 확정하지 않는다.

교사 Growth HTML이 `child` 객체를 쓰는 것은 UI이며, 외부 LLM 경계와 별개다.

---

## 12. Known legacy issues intentionally out of scope

존재하지만 이번 Phase에서 수정하지 않는다.

- `DailyPoints` `(child_id, date)` DB unique 없음
- point write `.first()` vs Growth read `MAX(id)`
- `Child.cumulative_points` 전체 `SUM(DailyPoints.total_points)` vs Growth canonical
  (`MAX(id)` + 과목/manual 재계산)
- `/cumulative-points/input` lump-sum 행 (과목 0, 저장 `total_points`만 큰 행).
  canonical reader는 저장 total을 무시하므로 과목 합 0으로 본다
- `LearningRecord` 잔존 화면
- `app.py` 일부 `utcnow().date()` / `datetime.now().date()` 혼용
- DailyPoints 고정 컬럼 Subject 구조
- Exemption / NFC / viewer onepage를 Growth에 넣지 않음
- Step 4 UI stash (`wip: growth step 4 dashboard ui before data contract`)

이것들은 “깔끔하지 않다”는 이유로 Growth canonical을 바꾸지 않는다.

---

## 13. AI가 직접 읽으면 안 되는 raw / cache source

요약. Growth가 읽더라도, 향후 LLM은 raw로 읽지 않는다.

| source | Growth | future LLM |
|---|---|---|
| `ChildReading` / `ReadingDay` | metrics가 직접 읽음 | raw 탐색 금지. 숫자/evidence만 |
| `LearningProgressEntry` | metrics가 직접 읽음 | 동일 |
| `fetch_child_daily_point_records` | period / cumulative_as_of | 동일 |
| `Book` | 안 읽음 | 기본 제외 |
| `ReadingRewardEvent` | 안 읽음 (DailyPoints에 반영된 값만) | 직접 합산 금지 |
| `PointsHistory` | 안 읽음 | 금지 |
| `LearningRecord` | 안 읽음 | 금지 |
| `Child.cumulative_points` | 오늘+빈 원장 fallback만 | evidence 금지 |
| `ChildNote` / `review_text` | 안 읽음 | 금지 |
| `manual_history` raw JSON | fetch가 XOR에만 사용 | raw 금지 |
