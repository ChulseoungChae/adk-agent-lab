# 센서 데이터 통계 분석 결과 보고서

생성 시각: 2026-06-18T18:52:56.042451

## 요약

본 분석은 센서 데이터(sample_sensor.csv)의 주요 수치형 변수와 범주형 변수의 특성을 진단한 결과입니다. 주요 변수인 챔버 압력, MFC 유량, 온도의 기술 통계 및 레시피별 평균값 차이를 확인하였으며, 변수 간의 상관관계와 이상치 여부를 검토하였습니다.

## 주요 발견

1. chamber_pressure와 temperature 간의 매우 높은 양의 상관관계(0.9711)가 관찰되었습니다.
2. recipe별 평균 온도 차이가 뚜렷합니다 (PVD_TiN_010: 320.5361, ALD_SiO2_001: 279.9157, ALD_SiO2_002: 280.1827).
3. chamber_pressure 컬럼에서 3.0%의 결측치가 발견되었으나, IQR 방식에 따른 이상치는 탐지되지 않았습니다.
4. equipment_id별 데이터 분포는 EQP-A01과 EQP-A02가 각각 100건으로 균등하게 분포되어 있습니다.

## 참고 파일

- 프로파일: `profile.json`
- 통계 결과: `statistics.json`
- ![correlation_heatmap](charts/correlation_heatmap.png)

- ![hist_chamber_pressure](charts/hist_chamber_pressure.png)

- ![hist_mfc_flow](charts/hist_mfc_flow.png)

- ![hist_temperature](charts/hist_temperature.png)
