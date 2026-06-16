# 2. Chapter 2: Real-time Anomaly Detection in ALD/PVD Processes

# Chapter 2: Real-time Anomaly Detection in ALD/PVD Processes

In the high-precision world of semiconductor manufacturing, particularly in Atomic Layer Deposition (ALD) and Physical Vapor Deposition (PVD), even a micro-fluctuation in gas flow or pressure can lead to catastrophic yield loss. Traditional monitoring relies on static thresholding, which often fails to capture the dynamic nature of complex plasma-enhanced processes.

This chapter explores the **Real-time Anomaly Detection** capabilities of the AI Assistant Platform, focusing on how it identifies deviations in Mass Flow Controllers (MFC) and other critical parameters as they occur.

## 2.1 The Mechanism of Real-time Monitoring

The platform utilizes a streaming architecture to ingest sensor data from equipment (e.g., ALD chambers). Unlike batch processing, real-time detection evaluates incoming data points against established operational envelopes.

### Key Detection Metrics:
- **Parameter Deviation**: Identifying when a specific sensor (e.g., `MFC8_NH3`) exceeds its predefined upper (`u`) or lower (`l`) limit.
- **Violation Types**:
    - **Type 1 (Threshold Violation)**: The value exceeds the boundary.
    - **Type 2 (Step-specific Violation)**: The violation is context-aware, specific to a process step like `N-FL1`.
    - **Type 3/4 (Complex Patterns)**: Advanced patterns involving rate of change or duration.

## 2.2 Case Study: NH3 Flow Instability

To understand the practical application, let's examine actual logs from the platform. During a recent process run on the `N-FL1` step, the platform flagged multiple anomalies related to the `MFC8_NH3` parameter.

### Data Analysis of Detected Anomalies

| Timestamp | Parameter | Actual Value | Limit (Upper) | Deviation (%) | Violation Type |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-03-18 15:11:47 | `MFC8_NH3` | 5.332 | 4.7 | +13.45% | Type 2 |
| 2026-0rypt-18 15:11:08 | `MFC8_NH3` | 6.133 | 4.7 | +30.49% | Type 1 |
| 2026-03-18 15:09:11 | `MFC8_NH3` | 6.875 | 4.7 | +46.28% | Type 1 |
| 2026-03-18 15:08:32 | `MFC8_NH3` | 6.553 | 4.7 | +39.43% | Type 3 |

**Engineering Insight:**
The logs show a recurring pattern where the `MFC8_NH3` flow rate is consistently above the upper limit of **4.7 sccm**. Specifically, at `15:09:11`, the value spiked to **6.875 sccm**, a **46.28% deviation**. 

The presence of both `Violation Type 1` and `Type 2` indicates that while the value exceeded the absolute limit, the platform also recognized that this was occurring during the `N-FL1` step, allowing engineers to pinpoint whether the issue is a hardware-wide failure or a recipe-specific instability.

## 2.3 Impact on Yield and Maintenance

Real-time detection allows for:
1. **Immediate Interruption**: If `is_interrupted` is flagged, the system can trigger an automated tool shutdown to prevent wafer scrap.
2. **Reduced False Alarms**: By using step-specific limits (e.g., `step_id: [115]`), the system avoids flagging intentional flow changes during different process stages.
3. **Root Cause Acceleration**: Engineers don't have to hunt through hours of logs; the exact timestamp and the magnitude of the `diff_percent` are immediately available.
