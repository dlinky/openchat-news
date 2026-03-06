# ChatDigest v1.1 개발 계획

> 기준 버전: v1.0 (2026-03-06)

---

## 변경 사항 요약

| # | 분류 | 항목 | 난이도 |
|---|------|------|--------|
| 1 | 버그 | 업로드 완료 후 모달 자동 닫힘 제거 | 낮음 |
| 2 | 로직 | 채팅방 이름 끝 숫자 제거 | 낮음 |
| 3 | 콘텐츠 | 레퍼런스(출처) 삭제 | 낮음 |
| 4 | 콘텐츠 | 토픽 가중치 + 상위 2개 3배 증량 | 중간 |
| 5 | 로직 | 주/월간 생성 배치 방식 + 거부 조건 | 높음 |
| 6 | UI | 다중 파일 업로드 + 인라인 요약 생성 | 높음 |
| 7 | UI | 진행 표시 단순화 (2단계) | 낮음 |

---

## Phase 1 — 빠른 버그 수정 (항목 1~3)

### 1. 업로드 완료 후 모달 자동 닫힘 제거

**현재 동작**
`Sidebar.tsx:163`의 `onSuccess` 콜백이 모달을 즉시 닫음:
```ts
onSuccess={() => { setUploadOpen(false); fetchNav(); }}
```

**변경 내용**
- `onSuccess`에서 `setUploadOpen(false)` 제거 → 완료 화면은 유저가 닫기 버튼을 눌러야만 닫힘
- `UploadModal`의 `done` 단계 "닫기" 버튼은 그대로 유지

**수정 파일**
- `frontend/components/layout/Sidebar.tsx` — `onSuccess` 콜백 1줄 수정

---

### 2. 채팅방 이름 끝 숫자 제거

**현재 문제**
카카오 오픈채팅 내보내기 파일 1행 예:
```
스터디방 42 님과 카카오톡 대화
```
참여인원이 43명이 되면 파일 1행이 `스터디방 43`으로 바뀌어 다른 채팅방으로 DB에 등록됨.

**변경 내용**
`parse_kakao_file()` 내 room_name 추출 직후, 끝에 붙은 `\s+\d+` 패턴을 제거:
```python
# 변경 전
room_name = room_name_match.group(1).strip()

# 변경 후
room_name = re.sub(r'\s+\d+$', '', room_name_match.group(1)).strip()
```

**주의 사항: DB 마이그레이션**
기존 DB에 `스터디방 42`, `스터디방 43` 처럼 숫자 포함 이름으로 저장된 채팅방이 있을 수 있음.
파서가 `스터디방`을 반환하면 DB에 존재하는 `스터디방 42`와 매칭 실패 → 새 채팅방이 생성됨.

→ 구현 시 기존 채팅방 이름의 끝 숫자를 정리하는 DB 마이그레이션 스크립트 또는 일회성 SQL 실행 포함.

**수정 파일**
- `backend/app/services/parser.py` — room_name 정제 로직 1줄 추가
- 마이그레이션 SQL 또는 스크립트

---

### 3. 레퍼런스(출처) 삭제

**현재 동작**
`combine_daily_digest` 프롬프트가 각 항목 끝에 출처 채팅방 이름을 달도록 지시:
```
- 출처 채팅방은 각 항목 끝에: `> 출처: 채팅방이름`
```

**변경 내용**
- 프롬프트에서 해당 규칙 제거
- 입력 데이터 구성 시 `room` 필드도 불필요하므로 제거 (프롬프트 텍스트에서만 제거해도 무방)

**수정 파일**
- `backend/app/services/gemini.py` — `combine_daily_digest` 프롬프트 수정

---

## Phase 2 — 콘텐츠 개선 (항목 4)

### 4. 토픽 가중치 + 상위 2개 3배 증량

**변경 내용**

#### 4-1. `summarize_room_daily` 프롬프트 개선
우선순위 토픽 목록을 명시하여 Gemini가 분류 시 해당 토픽을 우선 인식하도록 지시:

```
우선순위 토픽 (이 키워드가 포함된 내용은 반드시 별도 항목으로 분리):
- 개인사업자 관련 (세금, 계약, 사업 운영)
- 1인개발 / 바이브코딩 (솔로 개발, AI 코딩 도구 활용법, 개발 워크플로우)
- 고충 / 문제 해결 (막히는 점, 실패 사례, 어려움 공유)
- 아이디어 제안 (새 기능, 서비스, 사업 아이디어)
- 리뷰 요청 (피드백, 코드 리뷰, 서비스 리뷰)
```

#### 4-2. `combine_daily_digest` 프롬프트 개선
전체 토픽 중 위 우선순위 토픽에 해당하는 것을 상위 2개로 선정, 해당 섹션은 내용을 3배 분량(더 많은 맥락, 구체적 사례, 인사이트 포함)으로 작성하도록 지시:

```
가중치 규칙:
1. 우선순위 토픽(개인사업자, 1인개발/바이브코딩, 고충, 아이디어, 리뷰 요청)에 해당하는 섹션이 있으면
   그 중 내용이 가장 풍부한 2개를 선정하여 "핵심 섹션"으로 처리
2. 핵심 섹션은 일반 섹션보다 3배 분량으로 작성:
   - 각 항목에 맥락, 논의 흐름, 실용적 인사이트까지 포함
   - 발언자들의 다양한 관점을 정리하여 서술
3. 핵심 섹션은 문서 상단에 배치
```

**수정 파일**
- `backend/app/services/gemini.py` — `summarize_room_daily`, `combine_daily_digest` 프롬프트 수정

---

## Phase 3 — 생성 로직 개선 (항목 5)

### 5. 주/월간 생성 배치 방식 + 채팅방 커버리지 체크

**현재 문제**
- 주간: 해당 주의 일간 다이제스트가 하나라도 있으면 생성, 없으면 404
- 월간: 해당 월의 주간 다이제스트가 하나라도 있으면 생성, 없으면 404
- 즉 일간을 먼저 수동으로 하나씩 생성해야 주간/월간을 만들 수 있는 불편한 구조

---

#### 5-1. 채팅방 커버리지 체크 (사전 확인 대화상자)

**문제 상황**
모든 파일을 한 번에 업로드하더라도, 특정 채팅방은 이후로 더 이상 올리지 않을 수 있음.
이 경우 해당 채팅방의 마지막 메시지 날짜가 다른 채팅방보다 뒤처지게 됨.

예:
- 채팅방 A: 마지막 날짜 `2026-02-28`
- 채팅방 B: 마지막 날짜 `2026-02-20` ← 최신 날짜보다 뒤처짐

**체크 기준**
- 전체 채팅방 최신 메시지 날짜의 **최대값(global max)** 기준
- `room.max_date < global_max_date`인 채팅방 = "뒤처진 채팅방"

**새 API: `GET /rooms/coverage`**
```json
{
  "global_max_date": "2026-02-28",
  "rooms": [
    {"id": 1, "name": "스터디방", "max_date": "2026-02-28", "stale": false},
    {"id": 2, "name": "사이드프로젝트방", "max_date": "2026-02-20", "stale": true}
  ]
}
```

**새 API: `DELETE /rooms/{room_id}`**
해당 채팅방의 모든 데이터 삭제:
- `chat_messages` (해당 room_id)
- `daily_summaries` (해당 room_id)
- `chat_rooms` (해당 row)
- 단, DailyDigest / WeeklyDigest / MonthlyDigest는 여러 채팅방의 통합본이므로 삭제하지 않음

**UI 흐름**

주간/월간 생성 버튼 클릭 시:
```
1. GET /rooms/coverage 호출
2. stale 채팅방이 없으면 → 바로 생성 진행
3. stale 채팅방이 있으면 → 확인 대화상자 표시:

┌─────────────────────────────────────────┐
│ 일부 채팅방의 데이터가 최신 날짜보다     │
│ 뒤처져 있습니다.                         │
│                                          │
│ 사이드프로젝트방  마지막: 2026-02-20     │
│   ○ 그대로 유지  ● 삭제                 │
│                                          │
│ [취소]                    [확인 후 생성] │
└─────────────────────────────────────────┘

4. "삭제" 선택한 채팅방 → DELETE /rooms/{room_id} 호출
5. 이후 생성 진행
```

**거부 조건 (별도)**
`global_max_date < 요청 기간의 마지막 날`이면 생성 거부.

- `global_max_date` = DB 전체 ChatMessage에서 `max(chat_date)` (모든 채팅방 합산)
- 주간: `global_max_date < 해당 주 일요일` → 거부
- 월간: `global_max_date < 해당 월 마지막 날` → 거부

예:
```
global_max_date = 2026-02-20

2월 요약 요청   → 2월 마지막 날 2026-02-28 > 2026-02-20 → 거부
9주차 요약 요청 → 9주차 일요일 2026-03-01 > 2026-02-20 → 거부
7주차 요약 요청 → 7주차 일요일 2026-02-15 ≤ 2026-02-20 → 허용
```

거부 시 UI에 오류 메시지 표시: "2월 28일까지의 데이터가 필요합니다. 현재 마지막 날짜: 2026-02-20"

> 기간 내에 채팅 활동이 없는 날(메시지 0개)은 거부 사유가 아님.
> 거부 기준은 "업로드된 파일이 해당 기간을 끝까지 커버하는가"임.

**실행 순서**
```
① 거부 조건 확인 (global_max_date < period_last_day → 즉시 거부, 이하 단계 없음)
② stale 채팅방 체크 (room.max_date < global_max_date → 대화상자)
③ 배치 생성 진행
```

---

#### 5-2. 배치 생성 흐름

주간 생성 `POST /generate/weekly/{year_week}` (SSE):
```
1. 해당 주에 ChatMessage가 없으면 → error 이벤트 반환
2. 해당 주의 날짜(월~일) 중 ChatMessage가 있는 날짜 조회
3. 각 날짜에 DailyDigest가 없으면 자동 생성 (daily 로직 인라인 호출)
4. 주간 다이제스트 생성
```

월간 생성 `POST /generate/monthly/{year_month}` (SSE):
```
1. 해당 월에 ChatMessage가 없으면 → error 이벤트 반환
2. 해당 월에 포함된 주차 목록 산출
3. 각 주차에 WeeklyDigest가 없으면 → 위 배치 흐름으로 자동 생성
4. 월간 다이제스트 생성
```

**SSE 이벤트 (주간/월간 공통)**
```json
{"status": "batch_daily", "date": "2026-02-10"}
{"status": "batch_weekly", "week": "2026-W07"}
{"status": "combining"}
{"status": "done"}
```

주간/월간도 SSE 방식으로 변경하여 GeneratePanel에서 진행 상황 표시.

**수정 파일**
- `backend/app/routers/generate.py` — `generate_weekly`, `generate_monthly` SSE 재설계 + 배치 로직
- `backend/app/routers/rooms.py` — `GET /rooms/coverage`, `DELETE /rooms/{room_id}` 추가
- `frontend/lib/api.ts` — `rooms.coverage()`, `rooms.delete()`, SSE 반환 타입 변경
- `frontend/components/generate/GeneratePanel.tsx` — 커버리지 체크 + 대화상자 + SSE 읽기 통합

---

## Phase 4 — UI/워크플로우 개선 (항목 6~7)

### 6. 다중 파일 업로드 + 인라인 요약 생성

**현재 워크플로우**
```
파일 업로드 버튼 → 모달 (1개 파일) → 완료 → 닫기
요약 생성 버튼 → 사이드바에 패널 펼침 → 날짜 선택 → 생성
```

**변경 워크플로우**
```
파일 업로드 버튼 → 모달 → 파일 여러 개 선택
  → 각 파일 순서대로: 미리보기 확인 → 업로드
  → 전체 완료 후 → 모달 내에서 바로 요약 생성 단계
    → 날짜/주/월 선택 → 생성 → 완료 → 닫기
```

**UploadModal 변경 사항**
- `input[type=file]`에 `multiple` 속성 추가
- 여러 파일을 순차 처리하는 큐 방식으로 스텝 머신 재설계:
  ```
  Step: idle → previewing → preview_ready → committing → [다음 파일 or all_done] → generating → done
  ```
- 각 파일의 업로드 결과를 누적 표시 (완료된 파일 목록)
- `all_done` 단계에서 GeneratePanel 컴포넌트를 모달 하단에 인라인으로 렌더링
- "건너뛰고 닫기" 버튼으로 생성 단계 패스 가능

**Sidebar 변경 사항**
- "요약 생성" 별도 버튼 제거 (업로드 모달 내로 이관)
- 사이드바 하단에는 "파일 업로드" 버튼만 유지
- `GeneratePanel` 컴포넌트는 `UploadModal` 내에서만 사용되도록 이동

**수정 파일**
- `frontend/components/upload/UploadModal.tsx` — 전면 재설계
- `frontend/components/layout/Sidebar.tsx` — 요약 생성 버튼 및 GeneratePanel 제거
- `frontend/components/generate/GeneratePanel.tsx` — props 조정 (onDone 콜백 추가)

---

### 7. 진행 상태 표시 단순화 (2단계)

**현재 동작**
채팅방 이름별로 `⏳ 채팅방A 분석 중...`, `⏳ 채팅방B 분석 중...` 로그가 쌓임.

**변경 내용**
채팅방 단위 로그 → 2단계 표시:

```
⏳ 데이터 분석 중...      ← processing 이벤트 (여러 개라도 하나만 표시, 마지막 갱신)
🔗 다이제스트 생성 중...  ← combining 이벤트
✅ 완료!                  ← done 이벤트
```

백엔드 SSE 이벤트 구조 변경 (선택):
- 현재: `{"status": "processing", "room": "채팅방A"}`
- 변경: `{"status": "processing", "progress": 2, "total": 5}` (채팅방 수 기반 진행률)

또는 프론트에서만 처리:
- `processing` 이벤트를 누적하지 않고 단일 항목으로 교체 갱신

**수정 파일**
- `frontend/components/generate/GeneratePanel.tsx` — 로그 렌더링 로직 수정
- (선택) `backend/app/routers/generate.py` — SSE 이벤트에 progress/total 추가

---

## 구현 순서

```
Phase 1 (빠른 수정) → Phase 2 (콘텐츠) → Phase 3 (로직) → Phase 4 (UI)
```

Phase 3과 Phase 4는 Phase 1~2 완료 후 진행. Phase 3의 SSE 확장과 Phase 4의 UploadModal 재설계는
서로 의존하므로 Phase 3을 먼저 완료한 뒤 Phase 4 진행.

---

## DB 마이그레이션 체크리스트

- [ ] `chat_rooms.name` 끝 숫자 정리 SQL
  ```sql
  UPDATE chat_rooms
  SET name = regexp_replace(name, '\s+\d+$', '')
  WHERE name ~ '\s+\d+$';
  ```
- 신규 스키마 변경 없음 (테이블 구조 유지)

---

## 버전 히스토리 (예정)

| 버전 | 날짜 | 내용 |
|------|------|------|
| v1.0 | 2026-03-06 | 최초 릴리즈 |
| v1.1 | TBD | 콘텐츠 가중치, 배치 생성, 다중 업로드, UI 개선 |
