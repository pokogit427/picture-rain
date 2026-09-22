# Picture Rain 코드 구현 과정

이 문서는 G03 로컬 기능 구현(D01~D31)을 단계별로 설명하는 기록입니다. 각 단계는 실제 변경 목적, 구현 흐름, 사용 기술, 검증 방법, 파일 경로를 같은 형식으로 정리했습니다.

실제 코드 경로는 WSL `/home/daks/projects/picture-rain`이며 아래 경로는 저장소 루트 기준입니다. G04 이후 컨테이너·클라우드·배포 과정은 이 문서 범위에 포함하지 않습니다.

## D01 — 로컬 웹 개발 기반 구성

### 1. 무엇을 구현?

React/TypeScript 웹 셸과 기존 FastAPI health/photos API 연결, 웹 테스트·빌드 기준을 구현했습니다.

### 2. 구현 과정

Vite 프로젝트, API 클라이언트, 기본 화면, `/api` 개발 프록시와 회귀 테스트를 추가했습니다.

### 3. 사용 기술

Vite, React, TypeScript, Vitest, Fetch API.

### 4. 검증 방법

`cd web && npm run test && npm run build` 및 `/api/health` 프록시 응답을 확인했습니다.

### 5. 파일 경로와 파일명

`web/package.json`, `web/vite.config.ts`, `web/src/main.tsx`, `web/src/App.tsx`, `web/src/api.ts`, `web/src/api.test.ts`, `web/src/main.test.tsx` — 커밋 `58e1652`.

## D02 — 사용자 모델과 데이터베이스 마이그레이션

### 1. 무엇을 구현?

사용자 계정 모델과 Alembic 기반 초기 마이그레이션을 추가했습니다.

### 2. 구현 과정

기존 초기화 흐름을 마이그레이션 적용 흐름으로 보강하고, 기존 사진 데이터 보존과 빈 DB 적용 경로를 확인했습니다.

### 3. 사용 기술

SQLAlchemy 2, Alembic, PostgreSQL, FastAPI lifespan.

### 4. 검증 방법

API 이미지 빌드, `alembic check`, Python 컴파일, 기존 DB·빈 DB 마이그레이션을 확인했습니다.

### 5. 파일 경로와 파일명

`app/models.py`, `app/db.py`, `app/main.py`, `migrations/env.py`, `migrations/versions/0001_initial_schema.py`, `alembic.ini` — 커밋 `23e4f70`.

## D03 — 아이디/비밀번호 인증과 세션

### 1. 무엇을 구현?

공개 가입, 로그인, 로그아웃, 현재 사용자 조회와 30일 세션 쿠키를 구현했습니다.

### 2. 구현 과정

비밀번호를 Argon2id로 해시하고 세션 토큰은 해시해 저장했습니다. 인증 의존성을 보호 API와 웹 인증 화면에 연결했습니다.

### 3. 사용 기술

FastAPI, `argon2-cffi`, HttpOnly·SameSite 쿠키, SQLAlchemy.

### 4. 검증 방법

등록·정상 로그인·오인증·로그아웃·로그아웃 후 접근 차단과 웹 테스트·빌드를 확인했습니다.

### 5. 파일 경로와 파일명

`app/auth.py`, `app/models.py`, `app/schemas.py`, `app/main.py`, `migrations/versions/0002_auth_sessions.py`, `web/src/components/AuthPanel.tsx` — 커밋 `a122bf9`.

## D04 — 복수 1:1 연결 모델

### 1. 무엇을 구현?

두 사용자로 구성된 독립적인 연결 모델을 추가했습니다.

### 2. 구현 과정

사용자 ID를 정규화해 동일 쌍의 중복 연결을 막고 자기 연결을 거부했습니다. 연결 상태와 생성 시각을 저장했습니다.

### 3. 사용 기술

SQLAlchemy unique/check 제약조건, Alembic.

### 4. 검증 방법

정확히 두 멤버인지, 자기 연결과 중복 쌍이 차단되는지 모델·마이그레이션을 확인했습니다.

### 5. 파일 경로와 파일명

`app/models.py`, `app/pairing.py`, `migrations/versions/0003_pair_connections.py` — 커밋 `aa19b8d`.

## D05 — 초대 코드 기반 연결

### 1. 무엇을 구현?

4자리 숫자 초대 코드 발급·재발급·조회·수락을 구현했습니다.

### 2. 구현 과정

코드 원문 대신 해시를 저장하고 5분 만료, 수락 시도 제한, 자기 연결·중복 연결 검사를 추가했습니다. 재발급과 기존 연결 수명을 분리했습니다.

### 3. 사용 기술

FastAPI Router, 해시 저장, SQLAlchemy, Alembic.

### 4. 검증 방법

정상 수락·만료·반복 실패·자기 연결·중복 연결·재발급 후 기존 연결 유지 흐름을 HTTP로 확인했습니다.

### 5. 파일 경로와 파일명

`app/invite_api.py`, `app/pairing.py`, `app/models.py`, `app/schemas.py`, `migrations/versions/0004_invite_codes.py` — 커밋 `f76ae65`.

## D06 — 연결 목록과 초대 화면

### 1. 무엇을 구현?

로그인 후 연결된 상대 목록, 내 초대 코드, 상대 코드 입력 화면을 추가했습니다.

### 2. 구현 과정

연결 목록·현재 코드 API를 웹 클라이언트에 연결하고 코드 재발급과 연결 성공 후 목록 갱신 동선을 배치했습니다.

### 3. 사용 기술

React hooks, TypeScript Fetch client, FastAPI schema.

### 4. 검증 방법

웹 테스트·빌드와 인증 화면의 목록·코드 표시·연결 요청 동선을 확인했습니다.

### 5. 파일 경로와 파일명

`app/invite_api.py`, `web/src/api.ts`, `web/src/components/ConnectionPanel.tsx`, `web/src/App.tsx`, `web/src/styles.css` — 커밋 `d8a27ca`.

## D07 — 사진 소유자 접근 통제

### 1. 무엇을 구현?

기존 사진 목록·업로드·변환·다운로드 API를 로그인 사용자 소유 범위로 제한했습니다.

### 2. 구현 과정

`Photo.owner_id`와 마이그레이션을 추가하고 사진 관련 모든 경로에서 현재 사용자와 소유자를 함께 검사했습니다.

### 3. 사용 기술

FastAPI dependency injection, SQLAlchemy ownership query, Alembic.

### 4. 검증 방법

본인 사진은 접근되고 다른 사용자의 목록·원본·변환본은 404로 은닉되는 HTTP 흐름을 확인했습니다.

### 5. 파일 경로와 파일명

`app/main.py`, `app/models.py`, `app/auth.py`, `migrations/versions/0005_photo_owners.py` — 커밋 `aa98c80`.

## D08 — 사진 교환 라운드

### 1. 무엇을 구현?

연결별 교환 라운드와 양쪽 입력 사진을 저장하는 모델·API를 추가했습니다.

### 2. 구현 과정

라운드 상태와 24시간 만료 시각을 만들고 각 멤버가 한 번씩 입력을 등록하도록 제한했습니다. 라운드 상세·목록은 연결 멤버만 접근합니다.

### 3. 사용 기술

FastAPI Router, SQLAlchemy unique constraint, PostgreSQL, Alembic.

### 4. 검증 방법

라운드 생성·입력 등록·중복 입력·만료·연결 외 사용자 접근 차단을 HTTP로 확인했습니다.

### 5. 파일 경로와 파일명

`app/models.py`, `app/round_api.py`, `app/schemas.py`, `migrations/versions/0006_rounds.py` — 커밋 `88eb1d2`.

## D09 — 편집용 임시 사진 입력

### 1. 무엇을 구현?

입력·삽입·초안에 사용하는 임시 이미지 자산과 이미지 검증을 구현했습니다.

### 2. 구현 과정

JPEG/PNG/WebP 실제 디코딩, 크기·픽셀 수·긴 변 제한, EXIF 제거와 임시 저장 경로를 분리했습니다. Docker 볼륨 권한 문제도 정리했습니다.

### 3. 사용 기술

Pillow, FastAPI multipart upload, 로컬 파일 저장소, Docker bind mount.

### 4. 검증 방법

허용 형식·손상 파일·크기 초과·메타데이터 제거·두 사용자 간 자산 접근 차단을 확인했습니다.

### 5. 파일 경로와 파일명

`app/models.py`, `app/asset_images.py`, `app/storage.py`, `app/round_api.py`, `docker-compose.yml`, `migrations/versions/0007_assets.py` — 커밋 `e98853c`.

## D10 — 받은 사진 화면

### 1. 무엇을 구현?

연결·라운드별로 받은 사진을 열람하는 inbox API와 화면을 추가했습니다.

### 2. 구현 과정

현재 사용자의 연결만 조회하고 각 라운드의 상대 입력을 편집 대상으로 표시했습니다. 이미지 응답은 `private, no-store`로 제공했습니다.

### 3. 사용 기술

FastAPI 권한 검사, FileResponse, React 상태 관리.

### 4. 검증 방법

연결별 받은 사진 목록·직접 자산 URL·다른 연결 접근을 HTTP로 확인하고 웹 빌드를 실행했습니다.

### 5. 파일 경로와 파일명

`app/round_api.py`, `app/schemas.py`, `web/src/api.ts`, `web/src/components/InboxPanel.tsx` — 커밋 `48391d4`.

## D11 — 편집 캔버스와 확대 보기

### 1. 무엇을 구현?

받은 사진을 캔버스에 맞춰 표시하고 확대·축소할 수 있는 편집 화면을 추가했습니다.

### 2. 구현 과정

이미지 비율을 유지하는 fit 계산, 캔버스 크기 조정, 확대 슬라이더, 포인터 이벤트 기반 영역을 만들었습니다.

### 3. 사용 기술

HTML Canvas 2D, React refs/hooks, Pointer Events, TypeScript.

### 4. 검증 방법

웹 테스트·프로덕션 빌드와 데스크톱 포인터·모바일 터치 입력 구조를 확인했습니다.

### 5. 파일 경로와 파일명

`web/src/components/EditorCanvas.tsx`, `web/src/components/InboxPanel.tsx`, `web/src/styles.css` — 커밋 `598439b`.

## D12 — 그리기와 실행 취소

### 1. 무엇을 구현?

브러시, 선 지우기, 실행 취소와 다시 실행을 추가했습니다.

### 2. 구현 과정

선 좌표를 0~1로 정규화하고 현재·과거·미래 snapshot으로 undo/redo 상태를 관리했습니다.

### 3. 사용 기술

Canvas 2D path, Pointer Events, React immutable state.

### 4. 검증 방법

캔버스 포인터 입력과 snapshot 이동, 웹 TypeScript 빌드를 확인했습니다.

### 5. 파일 경로와 파일명

`web/src/components/EditorCanvas.tsx`, `web/src/styles.css` — 커밋 `b297998`.

## D13 — 스티커와 텍스트 레이어

### 1. 무엇을 구현?

이모지 스티커와 텍스트를 레이어로 배치하고 선택·이동·크기·회전·삭제할 수 있게 했습니다.

### 2. 구현 과정

레이어에 종류·값·좌표·크기·회전·색상을 저장하고 캔버스 렌더링과 선택 상자를 연결했습니다. 레이어 변경도 snapshot에 포함했습니다.

### 3. 사용 기술

Canvas text rendering, React state, Unicode emoji, Pointer Events.

### 4. 검증 방법

스티커·텍스트 추가와 레이어 조작 UI가 렌더링되고 웹 빌드가 통과하는지 확인했습니다.

### 5. 파일 경로와 파일명

`web/src/components/EditorCanvas.tsx`, `web/src/styles.css` — 커밋 `c3417c8`.

## D14 — 기본 사진 보정

### 1. 무엇을 구현?

정사각형 자르기, 90도 회전, 밝기 조정을 추가했습니다.

### 2. 구현 과정

crop 상태에 맞춰 draw 영역을 계산하고 회전 변환과 Canvas brightness filter를 적용했습니다. 조정값을 편집 문서에 포함했습니다.

### 3. 사용 기술

Canvas transform/filter, React range input, TypeScript.

### 4. 검증 방법

조정 컨트롤의 상태 반영, 편집 문서 직렬화, 웹 테스트·빌드를 확인했습니다.

### 5. 파일 경로와 파일명

`web/src/components/EditorCanvas.tsx`, `web/src/styles.css` — 커밋 `0fa2c43`.

## D15 — 커스텀 이모지 삽입

### 1. 무엇을 구현?

사용자가 입력한 유니코드 이모지를 별도 스티커 레이어로 추가했습니다.

### 2. 구현 과정

커스텀 이모지 입력을 최대 12 code point로 제한하고 외부 URL이나 영구 라이브러리 없이 현재 편집 문서에만 저장했습니다.

### 3. 사용 기술

Unicode code point 처리, React controlled input, Canvas text rendering.

### 4. 검증 방법

정상 추가·빈 값·길이 초과 비활성화와 TypeScript 빌드를 확인했습니다.

### 5. 파일 경로와 파일명

`web/src/components/EditorCanvas.tsx`, `web/src/styles.css` — 커밋 `eebc769`.

## D16 — 추가 사진 레이어

### 1. 무엇을 구현?

편집 화면에서 별도 사진을 업로드해 이미지 레이어로 삽입했습니다.

### 2. 구현 과정

현재 라운드의 임시 자산 업로드 API를 만들고 비공개 URL로 이미지를 불러와 레이어에 배치했습니다. 서버에서 형식·개수·소유권을 검사했습니다.

### 3. 사용 기술

FastAPI multipart, Pillow 검증, Canvas image layer, React File input.

### 4. 검증 방법

허용 이미지 업로드·레이어 렌더링·권한 없는 라운드 접근 차단과 웹 빌드를 확인했습니다.

### 5. 파일 경로와 파일명

`app/round_api.py`, `app/asset_images.py`, `web/src/api.ts`, `web/src/components/EditorCanvas.tsx` — 커밋 `3c91897`.

## D17 — 초안과 수정본 생성

### 1. 무엇을 구현?

편집 문서와 Canvas preview를 제출 전 초안으로 저장·복원·취소했습니다.

### 2. 구현 과정

라운드·편집자별 Draft를 만들고 버전·만료 시각·문서 JSON·임시 preview 자산을 저장했습니다. 본인 초안만 조회·취소하게 하고 입력·교환 자체는 보존했습니다.

### 3. 사용 기술

SQLAlchemy, Alembic, multipart FormData, Canvas `toBlob`, React async state.

### 4. 검증 방법

두 사용자 초안 격리·저장·복원·취소와 웹 테스트·빌드를 확인했습니다.

### 5. 파일 경로와 파일명

`app/models.py`, `app/round_api.py`, `app/schemas.py`, `web/src/api.ts`, `web/src/components/EditorCanvas.tsx`, `migrations/versions/0008_drafts.py` — 커밋 `7a40b78`.

## D18 — 완료 제출 고정

### 1. 무엇을 구현?

저장된 초안을 수정본 제출로 확정하고 제출 후 편집·취소를 차단했습니다.

### 2. 구현 과정

Draft preview를 Submission 자산으로 전환하고 편집자별 중복 제출 unique 제약을 추가했습니다. 같은 제출 재시도는 기존 결과를 반환하고 다른 변경은 거부했습니다.

### 3. 사용 기술

SQLAlchemy transaction, unique constraint, FastAPI 409 error, React submit state.

### 4. 검증 방법

첫 제출·동일 제출 재시도·제출 후 저장/취소 409를 HTTP로 확인했습니다.

### 5. 파일 경로와 파일명

`app/models.py`, `app/round_api.py`, `app/schemas.py`, `web/src/api.ts`, `web/src/components/EditorCanvas.tsx`, `migrations/versions/0009_round_submissions.py` — 커밋 `7ab8298`.

## D19 — 제출 결과 모자이크 보호

### 1. 무엇을 구현?

양쪽 제출 전 결과 원본 대신 서버 생성 모자이크만 제공했습니다.

### 2. 구현 과정

결과 자산에 모자이크 경로를 만들고 결과 목록·콘텐츠 URL에서 라운드 상태에 따라 모자이크를 선택했습니다. 원본 URL 우회도 서버 권한 검사로 차단했습니다.

### 3. 사용 기술

Pillow mosaic 처리, FileResponse, private/no-store 응답, FastAPI authorization.

### 4. 검증 방법

한쪽 제출 상태에서 원본 접근은 404이고 모자이크 응답은 200인지 HTTP로 확인했습니다.

### 5. 파일 경로와 파일명

`app/round_api.py`, `app/storage.py`, `app/models.py` — 커밋 `3350345`.

## D20 — 양쪽 완료 후 동시 공개

### 1. 무엇을 구현?

같은 라운드의 두 제출이 모두 저장된 경우에만 두 결과를 ORIGINAL로 전환했습니다.

### 2. 구현 과정

제출 트랜잭션에서 제출 수를 확인하고 두 번째 제출 시 라운드를 `REVEALED`로 변경했습니다. 첫 제출 시에는 모자이크 상태를 유지했습니다.

### 3. 사용 기술

SQLAlchemy transaction/row lock, 상태 머신, FastAPI result API.

### 4. 검증 방법

첫 제출 결과가 MOSAIC이고 두 번째 제출 직후 양쪽 결과가 ORIGINAL이며 원본 콘텐츠가 접근 가능한지 확인했습니다.

### 5. 파일 경로와 파일명

`app/round_api.py`, `app/schemas.py`, `web/src/api.ts` — 커밋 `1c2efba`.

## D21 — 수정본 이력

### 1. 무엇을 구현?

공개된 수정본을 사용자별 연결 이력에서 열람하게 했습니다.

### 2. 구현 과정

결과 제출마다 viewer별 HistoryEntry를 만들고 연결·사용자·상태를 검사하는 history API와 웹 이력 패널을 연결했습니다. 입력 원본은 이력에서 제외했습니다.

### 3. 사용 기술

SQLAlchemy viewer-scoped records, FastAPI FileResponse, React HistoryPanel.

### 4. 검증 방법

양쪽 사용자에게 결과 두 건만 보이고 입력 자산·다른 연결 결과는 보이지 않는지 HTTP로 확인했습니다.

### 5. 파일 경로와 파일명

`app/models.py`, `app/round_api.py`, `app/schemas.py`, `web/src/api.ts`, `web/src/components/HistoryPanel.tsx`, `migrations/versions/0010_history_entries.py` — 커밋 `a592061`.

## D22 — 임시 자산 정리

### 1. 무엇을 구현?

만료된 라운드·초안·미공개 결과·완료 라운드의 입력/삽입 임시 자산을 정리하는 명령을 추가했습니다.

### 2. 구현 과정

DB 상태를 확인하고 삭제 대상 파일을 모은 뒤 상태를 갱신하고, 커밋 후 파일을 삭제하도록 멱등 정리 흐름을 만들었습니다.

### 3. 사용 기술

SQLAlchemy batch query, Python pathlib, PostgreSQL 상태 모델.

### 4. 검증 방법

`tests/test_retention.py` 격리 테스트로 만료 라운드·초안·입력 자산 정리를 확인했습니다. 실제 개발 DB 정리 명령은 실행하지 않았습니다.

### 5. 파일 경로와 파일명

`app/retention.py`, `tests/test_retention.py`, `tests/__init__.py` — 커밋 `d857f65`, `68ba011`.

## D23 — 개인 기록 휴지통

### 1. 무엇을 구현?

이력 사진을 한 장 또는 여러 장 선택해 본인 휴지통으로 옮기고 복원했습니다.

### 2. 구현 과정

HistoryEntry에 TRASH 상태·삭제 시각·30일 purge 시각을 저장하고 목록·휴지통·복원 API와 체크박스 UI를 연결했습니다. 삭제된 사용자의 직접 콘텐츠 URL도 차단했습니다.

### 3. 사용 기술

FastAPI batch endpoint, SQLAlchemy state transition, React checkbox UI.

### 4. 검증 방법

두 항목을 한 번에 삭제하고 본인 콘텐츠는 404, 상대 콘텐츠는 200, 복원 후 본인 접근이 회복되는지 HTTP로 확인했습니다.

### 5. 파일 경로와 파일명

`app/round_api.py`, `app/schemas.py`, `web/src/api.ts`, `web/src/components/HistoryPanel.tsx` — 커밋 `40a39d5`.

## D24 — 휴지통 만료 완전 삭제

### 1. 무엇을 구현?

30일이 지난 본인 기록을 PURGED 처리하고 양쪽 참조가 모두 사라진 결과 파일만 삭제했습니다.

### 2. 구현 과정

사용자별 이력 상태를 만료시키고 상대의 ACTIVE/TRASH 참조가 남아 있으면 공용 결과 자산을 유지하도록 참조 집합을 계산했습니다. 양쪽이 모두 만료된 경우에만 제출·결과 파일을 삭제했습니다.

### 3. 사용 기술

SQLAlchemy reference counting, Python retention worker, idempotent cleanup.

### 4. 검증 방법

한쪽 만료 시 상대 결과 보존, 양쪽 만료 시 결과 삭제, 같은 정리 작업 재실행 무변경을 격리 테스트로 확인했습니다.

### 5. 파일 경로와 파일명

`app/retention.py`, `tests/test_retention.py` — 커밋 `93d0245`.

## D25 — 연결 해제와 접근 철회

### 1. 무엇을 구현?

한쪽 최종 확인으로 연결을 해제하고 해당 연결에 대한 접근을 즉시 철회했습니다.

### 2. 구현 과정

DELETE 연결 API에서 `DISCONNECTED` 상태를 기록하고 모든 멤버·라운드·자산 조회가 활성 연결을 다시 검사하게 했습니다. 웹에는 삭제 범위를 안내하는 최종 확인 버튼을 추가했습니다.

### 3. 사용 기술

FastAPI DELETE endpoint, membership query, React confirmation flow.

### 4. 검증 방법

해제 후 양쪽 연결 목록·라운드·자산 접근이 404가 되고 반복 해제도 404인지 확인했습니다.

### 5. 파일 경로와 파일명

`app/invite_api.py`, `app/pairing.py`, `web/src/components/ConnectionPanel.tsx` — 커밋 `9106ee0`.

## D26 — 해제 연결 자료 완전 삭제

### 1. 무엇을 구현?

해제된 연결의 이력·휴지통·라운드·자산·임시 파일을 정리하고 다른 연결은 보존했습니다.

### 2. 구현 과정

정리 worker가 `DISCONNECTED` 연결을 찾아 하위 데이터를 연결 ID 기준으로 삭제하고 파일 삭제를 멱등 처리했습니다.

### 3. 사용 기술

SQLAlchemy bulk delete, PostgreSQL foreign key cascade, pathlib cleanup.

### 4. 검증 방법

해제 연결 데이터는 DB·파일에서 사라지고 다른 연결 데이터는 남으며 반복 실행이 안전한지 격리 테스트로 확인했습니다.

### 5. 파일 경로와 파일명

`app/retention.py`, `tests/test_retention.py` — 커밋 `f3ceb8a`.

## D27 — 무료 모의 이용 정책

### 1. 무엇을 구현?

실결제 없이 FREE/PREVIEW 플랜과 연결별·계정별 사용량 경계를 노출했습니다.

### 2. 구현 과정

정책을 별도 모듈로 분리하고 `/entitlements`와 연결별 usage API를 추가했습니다. 유료 플랜을 임의로 무제한 처리하지 않고 billing을 비활성으로 유지했습니다.

### 3. 사용 기술

Python policy object, FastAPI response schema, React API client.

### 4. 검증 방법

플랜 상태·billing false·연결 3회·계정 30회 값을 HTTP로 확인했습니다.

### 5. 파일 경로와 파일명

`app/entitlement.py`, `app/entitlement_api.py`, `app/schemas.py`, `web/src/api.ts` — 커밋 `f894ec3`.

## D28 — 사용량 기록과 중복 차감 방지

### 1. 무엇을 구현?

라운드 생성 시 사용량을 서버에서 원자적으로 예약하고 같은 라운드 재시도는 한 번만 차감했습니다.

### 2. 구현 과정

`UsageCharge`에 라운드 unique 제약을 두고 사용자 행 잠금 후 연결별 하루 3회·계정 전체 30회를 계산했습니다. 두 라운드 생성 경로에 같은 함수를 연결했습니다.

### 3. 사용 기술

SQLAlchemy row lock, unique constraint, PostgreSQL transaction, FastAPI 429.

### 4. 검증 방법

동일 라운드 차감 멱등성과 연결별 네 번째 생성 429를 격리 테스트로 확인하고 HTTP에서 `3/3`, `3/30` 경계를 확인했습니다.

### 5. 파일 경로와 파일명

`app/models.py`, `app/usage.py`, `app/round_api.py`, `app/entitlement_api.py`, `app/schemas.py`, `tests/test_usage.py`, `migrations/versions/0011_usage_charges.py` — 커밋 `7ba6625`.

## D29 — 기본 꺼짐 모의 광고 영역

### 1. 무엇을 구현?

기본적으로 표시하지 않고 필요할 때만 로컬 문구를 보여주는 모의 광고 영역을 추가했습니다.

### 2. 구현 과정

환경변수는 `OFF`와 `MOCK`만 허용하고 알 수 없는 값은 `OFF`로 닫았습니다. 응답에 사진·상대방·토큰을 넣지 않고 외부 클릭 URL과 네트워크 광고 호출을 제공하지 않습니다.

### 3. 사용 기술

FastAPI policy endpoint, Pydantic schema, React component, 환경변수 fail-closed.

### 4. 검증 방법

기본 OFF·MOCK·알 수 없는 모드 정책 테스트와 웹 API client 테스트를 실행했습니다.

### 5. 파일 경로와 파일명

`app/ads.py`, `app/ads_api.py`, `app/schemas.py`, `app/main.py`, `web/src/api.ts`, `web/src/components/AdPlaceholder.tsx`, `web/src/App.tsx`, `tests/test_ads.py` — 커밋 `6fdb746`.

## D30 — 모바일 웹과 오류 복구 동선

### 1. 무엇을 구현?

오프라인 안내, 대시보드 재시도, 사진 로드 재시도, 초안 재저장, 모바일 안전영역과 PWA 기본 메타데이터를 추가했습니다.

### 2. 구현 과정

online/offline 이벤트를 화면에 반영하고 이미지·초안·대시보드 오류에 재시도 경로를 만들었습니다. 포인터 캡처가 끊겨도 편집 상태를 마무리하고 모바일 화면에서 도구가 줄바꿈되도록 조정했습니다.

### 3. 사용 기술

React lifecycle, Browser online/offline events, Pointer Events, Canvas, PWA manifest, responsive CSS.

### 4. 검증 방법

웹 테스트 17건과 TypeScript/Vite 프로덕션 빌드를 통과시키고 네트워크 복귀 컴포넌트 테스트를 확인했습니다.

### 5. 파일 경로와 파일명

`web/src/components/NetworkStatus.tsx`, `web/src/components/NetworkStatus.test.tsx`, `web/src/components/EditorCanvas.tsx`, `web/src/App.tsx`, `web/src/styles.css`, `web/index.html`, `web/public/manifest.webmanifest` — 커밋 `2210a97`.

## D31 — 다중 연결 통합 시나리오

### 1. 무엇을 구현?

두 개의 독립 연결에서 교환 공개·개인 삭제·사용량 분리·연결 해제 완전 삭제를 하나의 통합 시나리오로 검증했습니다.

### 2. 구현 과정

두 연결과 여러 라운드를 만들고 양쪽 제출 전 모자이크, 제출 후 동시 공개를 확인했습니다. 한 사용자의 이력만 휴지통으로 이동한 뒤 상대 기록을 확인하고, 한 연결을 해제한 후 다른 연결과 사용량 기록이 보존되는지 검증했습니다. 테스트 중 발견한 해제 연결 사용량 기록 누락도 정리 로직에 보완했습니다.

### 3. 사용 기술

FastAPI domain functions, SQLAlchemy in-memory integration test, retention cleanup, unittest mock time.

### 4. 검증 방법

Alembic check·Python compileall, 광고·사용량·보관 단위 테스트, D31 통합 테스트를 통과했습니다. 웹 테스트 17건과 프로덕션 빌드도 D30에서 통과했습니다.

### 5. 파일 경로와 파일명

`tests/test_exchange_integration.py`, `app/retention.py` — 커밋 `e07e36d`.

## 구현 결과와 다음 범위

D01~D31 로컬 기능 구현은 완료했고 모든 기능 단위 커밋을 `origin/main`에 push했습니다. 다음 큰 단계는 G04이지만 이 문서 작성과 함께 자동으로 시작하지 않습니다. 컨테이너화·클라우드·배포·운영·실결제·실광고·스토어 작업은 각 큰 단계의 새 채팅에서 별도로 진행합니다.
