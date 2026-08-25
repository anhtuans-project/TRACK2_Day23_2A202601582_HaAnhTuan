# RTO/RPO Evidence — Lab 23

Quy tắc duy nhất: mỗi con số ở đây phải trỏ được về **một dòng log thật**
(`đường/dẫn.jsonl:số_dòng`). `pytest tests/test_rto_evidence.py` sẽ mở từng file ra kiểm tra.
Con số không có evidence = trượt, bất kể các phần khác.

## 1. Drill 1 — không có DR (baseline)

| Chỉ số | Giá trị | Cách đo | Evidence |
|---|---|---|---|
| t_outage | 2026-08-25T16:56:16 | chaos kill | `chaos/chaos-events.jsonl:last` |
| Request fail đầu tiên | +3.4s | dòng `ok:false` đầu tiên sau t_outage | `reports/drill-1-nodr.jsonl:1` |
| Request thành công sau đó | không có | không có dòng `ok:true` nào sau t_outage | `reports/measure-drill-1.json` |
| RTO | `NO_RECOVERY` | `tools/measure_rto.py` | `reports/measure-drill-1.json` |

## 2. Drill 2 — có DR

| Mốc | +giây từ t_outage | Cách đo | Evidence |
|---|---|---|---|
| t_outage (mốc 0) | 0 | `action:kill` | `chaos/chaos-events.jsonl:last` |
| User thấy lỗi đầu tiên | +0.2s | dòng `ok:false` đầu | `reports/drill-2-withdr.jsonl:1` |
| Health check phát hiện | +4.9s | `to:UNHEALTHY, region:a` | `reports/health-events.jsonl:6` |
| Snapshot restore xong | +5.3s | `step:2_restore_snapshot` | `reports/failover-events.jsonl:27` |
| Region phụ ready | +5.3s | `step:4_wait_ready` | `reports/failover-events.jsonl:29` |
| DNS cutover | +5.6s | `step:5_dns_cutover` | `reports/failover-events.jsonl:30` |
| **RTO đo được** | +7.2s | dòng `ok:true` đầu sau lỗi | `reports/drill-2-withdr.jsonl:9` |

| Chỉ số | Đo được | Mục tiêu (slide §1) | Verdict |
|---|---|---|---|
| RTO — Inference API | 7.2s | 300s (5 phút) | PASS |
| RPO — Vector DB | 2.0s / 1 doc | 300s (5 phút) | PASS |

## 3. RTO của tôi gồm những gì (bắt buộc — đây là phần chấm điểm hiểu bài)

| Thành phần | Giây | Nó đến từ đâu | Giảm được bằng cách nào |
|---|---|---|---|
| Health-check detect floor | 15.0s | `interval_s × threshold` trong `reports/health-events.jsonl:6` | Giảm interval hoặc threshold |
| Snapshot restore | 0.4s | 2_restore → 3_scale | Sử dụng snapshot nhanh hơn hoặc incremental restore |
| GPU pool warm-up | 0.0s | `waited_s` ở `4_wait_ready` | Giữ pool ở trạng thái warm thay vì cold |
| DNS/LB TTL cache | 1.8s | t_recovered − t_cutover | Giảm TTL của DNS/LB |
