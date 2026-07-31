# goldea

MT5 자동매매 개발 저장소.

## 현재 기준 소스

- `src/mt5/GoldMiner_v5_5_4_internal_20260730.mq5`: 내부 개발 기준본
- `src/mt5/GoldMiner_v5_5_4_TEST_A_20260730.mq5`: 테스트 기준본
- `docs/claude-import/`: Claude에서 이어받은 비민감 개발 문서
- `_local_archive/`: PC와 Claude 작업 폴더에서 수집한 원본 보관본. GitHub 업로드 제외.

## 작업 규칙

1. 변경 전 현재 기준 소스와 변경 목적을 먼저 확인한다.
2. 한 번에 한 기능만 수정하고, 변경 이유를 커밋 메시지에 남긴다.
3. F7 컴파일과 MT5 백테스트 결과를 확인한 뒤 push한다.
4. 계정번호, 웹훅 시크릿, API 키, 라이선스 서명키는 저장소에 올리지 않는다.
5. 잠금/배포본은 기준 소스와 분리해서 보관한다.

## 시작 방법

MetaEditor에서 `src/mt5`의 기준 `.mq5` 파일을 열어 작업하고, 결과물과 백테스트 리포트는 별도 검증 기록으로 남긴다.

## 자료 출처

Claude Desktop의 로컬 세션 DB 자체는 앱 내부 캐시이므로 저장소에 복사하지 않는다. Claude에서 작업한 파일과 내보낸 문서는 `docs/claude-import` 또는 `_local_archive`에 보관한다.
