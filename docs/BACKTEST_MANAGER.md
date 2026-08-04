# 백테스트 자동 관리

`tools/backtest_manager.py`는 MT4/MT5의 HTML, XLSX, CSV, TSV 결과를 읽어 다음을 자동으로 처리한다.

- 골드/FX/기타 분류
- 전략·파일·기간별 원본 보관
- 거래 공통 테이블 생성
- 승률, 순이익, Gross Profit/Loss, Profit Factor, 평균 손익, 최대낙폭 계산
- `data/backtests/index.csv`, `data/backtests/trades.csv`, `reports/backtest_summary.xlsx` 생성

## 한 번 실행

PowerShell에서:

```powershell
cd D:\GitHub\goldea
.\tools\run_backtest_manager.ps1 -Mode scan
```

## 계속 감시

```powershell
.\tools\run_backtest_manager.ps1 -Mode watch -Interval 30
```

새 백테스트 파일은 `D:\GitHub\goldea\incoming_backtests`에 저장하거나, 기존 Downloads/MetaTrader 결과 폴더에 저장하면 다음 검사 때 자동으로 수집된다.

원본·계좌정보가 포함될 수 있는 `data/backtests/`와 `reports/`는 GitHub에 올리지 않는다. 먼저 파일을 수집하고, 이후 전략 버전별 비교와 파라미터 민감도 분석을 추가한다.
