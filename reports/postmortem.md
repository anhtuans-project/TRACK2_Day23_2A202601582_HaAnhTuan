# Postmortem — DR Drill Lab 23

Theo đúng template §4 "Sau Failover: Blameless Postmortem". Blameless: câu hỏi là
"hệ thống/process nào cho phép chuyện này", không phải "ai làm sai".

## 1. Timeline (mọi dòng phải có evidence path:line)

| ISO time | Sự kiện | Evidence |
|---|---|---|
| 2026-08-25T17:12:43 | outage bắt đầu | `chaos/chaos-events.jsonl:last` |
| 2026-08-25T17:12:45 | user đầu tiên bị ảnh hưởng | `reports/drill-2-withdr.jsonl:1` |
| 2026-08-25T17:12:42 | health check alert | `reports/health-events.jsonl:last` |
| 2026-08-25T17:12:48 | operator confirm cutover | `reports/runbook-run.jsonl:last` |
| 2026-08-25T17:12:52 | resolved (request đầu tiên OK từ region phụ) | `reports/drill-2-withdr.jsonl:9` |

## 2. RTO/RPO đo được vs mục tiêu — gap ở bước nào?

- RTO mục tiêu: 300s · đo được: `9.1s` · gap: `-290.9s`
- RPO mục tiêu: 300s · đo được: `4.0s` (`2` doc bị mất) · gap: `-296.0s`
- **Bước tốn nhiều giây nhất:** `Operator Confirmation` — vì runbook yêu cầu xác nhận thủ công trước khi trigger failover.

## 3. Root cause (5 whys)

Nếu đây là outage thật, bước rủi ro nhất là "xác nhận thủ công". Nếu operator không trực hoặc phản ứng chậm, RTO sẽ tăng vọt. Hệ thống hiện tại phụ thuộc vào con người để bắt đầu quá trình phục hồi.

## 4. Action items (có owner + deadline)

| # | Action | Owner | Deadline | Giảm RTO/RPO bao nhiêu giây |
|---|---|---|---|---|
| 1 | Tự động hóa failover với circuit breaker | SRE | 2026-09-01 | ~5-10s |
| 2 | Giảm DNS TTL của edge proxy | Network | 2026-09-01 | ~1-2s |

## 5. Ba câu hỏi bắt buộc trả lời

1. `interval × threshold` của bạn là `5s * 3 = 15s`. Trong bài chạy này, nó không đóng góp vào RTO vì operator đã confirm thủ công trước khi health check kịp alert. Thông thường nó chiếm ~50% RTO.
2. Nếu hạ interval xuống 1s, RTO giảm khoảng 10-12s. Tuy nhiên, rủi ro là "flapping": một lỗi mạng thoáng qua (transient glitch) cũng có thể trigger failover nhầm, gây mất ổn định hệ thống.
3. `docs_lost` có nghĩa là khách hàng sẽ không thấy các bản ghi mới nhất (trong khoảng 4 giây cuối trước outage). Tùy nghiệp vụ, điều này có thể gây sai lệch số dư hoặc mất dữ liệu giao dịch quan trọng.
