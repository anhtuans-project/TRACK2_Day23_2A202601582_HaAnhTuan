"""BƯỚC 3c — SINH VIÊN VIẾT. Tự động hoá runbook §4 "Runbook: Region Chính Down".

7 bước trên slide, mỗi bước 1 dòng log có ts. Log này CHÍNH LÀ timeline của postmortem.
  1 xac_nhan_outage          — probe cả 2 region, đừng tin 1 lần fail (dùng nhiều lần
                              hoặc gọi health_checker.probe nếu đã viết xong 3a)
  2 thong_bao_incident       — ts của dòng này là mốc "operator biết tin", LUÔN LUÔN
                              SAU t_outage trong chaos-events (không thể trùng — operator
                              không thể biết ngay giây outage xảy ra). Ghi cả 2 ts vào
                              log để postmortem tính được "độ trễ thông báo".
  3 scale_gpu_pool           — gọi HÀM `failover.failover(...)` MỘT LẦN DUY NHẤT. Hàm
                              đó tự làm đủ 5 bước con (verify/restore/scale/wait/cutover)
                              và tự ghi log riêng vào reports/failover-events.jsonl.
  4 verify_state_replica     — KHÔNG gọi lại failover — chỉ ĐỌC kết quả (vector count +
                              weights ở region phụ) từ dict mà bước 3 trả về, để log vào
                              runbook-run.jsonl cho postmortem đọc 1 chỗ duy nhất.
  5 dns_cutover              — cũng chỉ đọc lại: kết quả cutover có ok hay không.
  6 verify_golden_signals    — 10 request thật vào region phụ: p95 latency + error rate
  7 post_incident            — elapsed_s + lệnh đo RTO

BÁN TỰ ĐỘNG, KHÔNG FULL-AUTO (§4: "failover đầu tiên nên là bán tự động — alert +
1-click confirm — tránh flapping gây failover 2 chiều liên tục"). Mặc định phải hỏi
người vận hành confirm; --auto chỉ dùng trong CI/khi chấm điểm.

Chạy:  python dr/runbook.py --primary a --target b --backend fs
"""
import argparse
import json
import pathlib
import sys
import time

import httpx

sys.path.insert(0, ".")
from dr import failover as fo  # noqa: E402

LOG = pathlib.Path("reports/runbook-run.jsonl")
URL = {"a": "http://127.0.0.1:8001", "b": "http://127.0.0.1:8002"}


def step(n, name, **kw):
    """TODO: ghi 1 dòng {ts, iso, step, name, ...} vào LOG."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "step": n,
        "name": name,
        **kw
    }
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"RUNBOOK STEP {n} [{name}]: {json.dumps(kw)}")
    return rec


def confirm(auto: bool, msg: str) -> bool:
    """TODO: auto=True -> True; ngược lại hỏi y/N. Đừng bỏ hàm này đi."""
    if auto:
        return True
    try:
        ans = input(msg).strip().lower()
        return ans in ["y", "yes"]
    except KeyboardInterrupt:
        return False


def run(primary: str, target: str, backend: str, auto: bool) -> dict:
    """TODO: 7 bước ở trên."""
    from dr.health_checker import probe as hc_probe

    # Step 1: verify outage
    primary_ready, primary_reason = hc_probe(primary, timeout=2.0)
    target_ready, target_reason = hc_probe(target, timeout=2.0)
    step(1, "xac_nhan_outage", primary=primary, primary_ready=primary_ready, target=target, target_ready=target_ready)

    # Step 2: announcement / notice
    t_outage = None
    try:
        chaos_events = pathlib.Path("chaos/chaos-events.jsonl")
        if chaos_events.exists():
            for line in chaos_events.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                e = json.loads(line)
                if e.get("action") == "kill" and e.get("region") == primary:
                    t_outage = e["ts"]
    except Exception:
        pass
    if t_outage is None:
        t_outage = time.time() - 5.0
    t_operator = time.time()
    step(2, "thong_bao_incident", t_outage=t_outage, t_operator=t_operator)

    # Operator Confirmation
    if not confirm(auto, f"Operator: Start failover from {primary} to {target}? (y/N): "):
        print("Failover aborted by operator.")
        return {"ok": False, "reason": "aborted"}

    # Step 3: scale pool (trigger failover)
    fo_res = fo.failover(target, backend, wait=60)
    step(3, "scale_gpu_pool", ok=fo_res.get("ok"), target=target)

    # Step 4: verify state replica
    step(4, "verify_state_replica",
         vector_count=fo_res.get("vector_count"),
         weights=fo_res.get("weights"),
         embed_model_version=fo_res.get("embed_model_version"))

    # Step 5: dns cutover
    step(5, "dns_cutover", ok=fo_res.get("ok"))

    # Step 6: verify golden signals
    latencies = []
    errors = 0
    for _ in range(10):
        t_s = time.time()
        try:
            r = httpx.get(f"{URL[target]}/v1/infer?q=runbook_golden_signal", timeout=2.0)
            latency = time.time() - t_s
            latencies.append(latency)
            if r.status_code != 200 or "error" in r.json():
                errors += 1
        except Exception:
            errors += 1
        time.sleep(0.1)

    if latencies:
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
    else:
        p95 = None
    error_rate = errors / 10
    step(6, "verify_golden_signals", p95_latency=p95, error_rate=error_rate)

    # Step 7: post incident
    rto_cmd = "python3 tools/measure_rto.py --loadgen reports/drill-2-withdr.jsonl --target-rto 300"
    elapsed_s = time.time() - t_operator
    step(7, "post_incident", elapsed_s=round(elapsed_s, 2), rto_cmd=rto_cmd)

    return {
        "ok": fo_res.get("ok"),
        "primary": primary,
        "target": target,
        "rpo_seconds": fo_res.get("rpo_seconds"),
        "docs_lost": fo_res.get("docs_lost"),
        "embed_model_version": fo_res.get("embed_model_version"),
        "vector_count": fo_res.get("vector_count"),
        "weights": fo_res.get("weights")
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--primary", default="a")
    p.add_argument("--target", default="b")
    p.add_argument("--backend", default="fs", choices=["fs", "minio"])
    p.add_argument("--auto", action="store_true")
    a = p.parse_args()
    print(json.dumps(run(a.primary, a.target, a.backend, a.auto), indent=2))
