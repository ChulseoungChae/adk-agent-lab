# 5. Chapter 5: Analyzing Process History and Recipe Execution

# Chapter 5: Analyzing Process History and Recipe Execution

In semiconductor manufacturing, the ability to trace back the exact execution path of a process is fundamental to Root Cause Analysis (RCA). This chapter explores how the AI Assistant Platform provides a structured view of process history, enabling engineers to analyze the stability and reproducibility of specific recipes like `RUN\0_P_IH_HD02` and `RUN\0_P_IH_HD02-1`.

## 5.1 The Importance of Traceability in ALD/PVD
Every single wafer processed in an ALD or PVD chamber undergoes a specific sequence of steps (PJOB). A deviation in a single recipe execution can lead to thickness non-uniformity or impurity issues. By maintaining a digital log of every `pjob_id`, the platform allows engineers to correlate historical anomalies with specific production runs.

## 5.2 Analyzing Equipment History via PJOB Logs
The platform's `fetch_equipment_history` tool provides a granular view of recent executions. Let's examine a subset of the actual production data from the platform:

### Table 5.1: Recent Process Execution Summary (Sample Data)

| No. | PJOB ID | Process Recipe | Start Time | End Time | End Status |
|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | KE-PJ00000000012 | `RUN\0_P_IH_HD02` | 2026-01-12 14:12:17 | 2026-01-12 16:58:57 | NORMAL END |
| 2 | KE-PJ00000000011 | `RUN\0_P_IH_HD02` | 2026-01-11 09:40:35 | 2026-01-11 12:27:15 | NORMAL END |
| 3 | KE-PJ00000000010 | `RUN\0_P_IH_HD02-1` | 2026-01-10 19:40:42 | 2026-01-10 23:50:42 | NORMAL END |
| 4 | KE-PJ00000000009 | `RUN\0_P_IH_HD02-1` | 2026-01-09 22:35:43 | 2026-01-10 02:45:43 | NORMAL END |
| 5 | KE-PJ00000000008 | `RUN\0_P_IH_HD02` | 202 nghiệm 08 15:52:30 | 2026-01-08 18:39:10 | NORMAL END |

*Data sourced from `fetch_equipment_history`.*

### 5.2.1 Pattern Recognition in Recipe Durations
From the data above, we can observe the execution duration of the `RUN\0_P_IH_HD02` recipe. For instance, PJOB `KE-PJ00000000012` lasted approximately 2 hours and 46 minutes. Comparing this to PJOB `KE-PJ00000000011` (approx. 2 hours and 47 minutes) shows high temporal stability. However, a sudden change in duration (e.g., a 30% increase) would serve as a secondary indicator of a potential hardware issue, such as a slower gas switching time or a vacuum pump degradation.

## 5.3 Correlating History with Anomalies
The true power of the platform lies in the correlation between **History** and **Anomaly Logs**. When an engineer identifies an anomaly in `MFC8_NH3` (as seen in Chapter 2), they can immediately query the `pjob_id` active during that timestamp. 

If the `end_status` in the history log were to change from `NORMAL END` to `ABORTED` or `ERROR`, the engineer can:
1. Identify the exact recipe used.
2. Retrieve the parameter logs for that specific `pjob_id`.
3. Execute RAG-based documentation searches to find previous repair logs for that specific chamber.

## 5.4 Conclusion
The history module is not just a passive log; it is the foundation for longitudinal studies of process health. By monitoring the stability of `start_time` and `end_time` across multiple PJOBs, engineers can transition from reactive troubleshooting to proactive process control.
