# Runbook 1 trang — Region chính down

Runbook phải chạy được lúc 3h sáng bởi người KHÔNG viết nó. Mỗi bước: lệnh copy-paste
được + cách biết bước đó xong.

| # | Bước | Lệnh | Biết là xong khi | Ai làm |
|---|---|---|---|---|
| 1 | Xác nhận outage | `python chaos/kill_region.py status` | `a.alive=false` 3 lần liên tiếp | on-call |
| 2 | Mở incident + bấm giờ RTO | `date` | ts ghi vào `reports/runbook-run.jsonl` | on-call |
| 3 | Restore state ở region phụ | `python dr/failover.py --target b --backend fs` | `reports/failover-events.jsonl` có `2_restore_snapshot` | on-call |
| 4 | Scale pool warm→full | (included in failover.py) | `/readyz` của b trả 200 | on-call |
| 5 | DNS/LB cutover | (included in failover.py) | `curl localhost:8080/edge/state` cho `active_region=b` | on-call |
| 6 | Verify golden signals | `curl localhost:8080/v1/infer?q=golden` | p95 < 500ms, error rate < 1% | on-call |
| 7 | Đo RTO + postmortem | `python tools/measure_rto.py --loadgen reports/drill-2-withdr.jsonl` | `rto_verdict` = "PASS" | on-call |

**Rollback (failover ngược):** Trả traffic về region A khi `region-a` trở lại `HEALTHY` (probe /readyz trả 200) trong 5 phút liên tiếp và được phê duyệt bởi Site Reliability Engineer (SRE).
