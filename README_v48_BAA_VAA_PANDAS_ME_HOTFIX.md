# Magic Split v48 - BAA/VAA pandas 월말 주기 핫픽스

## 수정 이유
BAA/VAA 백테스트 실행 시 pandas 3.x 환경에서 아래 오류가 발생했습니다.

```text
Invalid frequency: M. Failed to parse with error message: ValueError("'M' is no longer supported for offsets. Please use 'ME' instead.")
```

## 수정 내용
BAA/VAA 월말 종가 생성 함수에서 deprecated 된 월말 주기 `M`을 pandas 3.x 호환 주기 `ME`로 변경했습니다.

```python
# 기존
prices.resample("M").last()

# 수정
prices.resample("ME").last()
```

## 영향 범위
- BAA Aggressive
- BAA Balanced
- VAA G4
- 월말 리밸런싱용 monthly close 생성

기존 T100 / 073 / 064 / CAP5 / Turbo 빠른 실행 로직은 그대로 유지했습니다.

## 검사
```text
python -m py_compile app.py
```
통과.
