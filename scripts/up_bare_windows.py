import subprocess
import time
import os
import pathlib
import sys
import httpx

os.makedirs("run", exist_ok=True)
os.makedirs("reports", exist_ok=True)

def start_proc(args, env, log_file, pid_file):
    f_log = open(log_file, "w", encoding="utf-8")
    full_env = {**os.environ, **env}
    proc = subprocess.Popen(args, env=full_env, stdout=f_log, stderr=subprocess.STDOUT)
    pathlib.Path(pid_file).write_text(str(proc.pid) + "\n")
    return proc

print("Starting region A...")
proc_a = start_proc(
    [sys.executable, "-m", "uvicorn", "serving.app:app", "--host", "127.0.0.1", "--port", "8001", "--log-level", "warning"],
    {"REGION": "a", "STATE_DIR": "state/region-a", "WARMUP_SECONDS": "6"},
    "run/region-a.log",
    "run/region-a.pid"
)
print(f"region-a pid={proc_a.pid} port=8001")

print("Starting region B...")
proc_b = start_proc(
    [sys.executable, "-m", "uvicorn", "serving.app:app", "--host", "127.0.0.1", "--port", "8002", "--log-level", "warning"],
    {"REGION": "b", "STATE_DIR": "state/region-b", "WARMUP_SECONDS": "6"},
    "run/region-b.log",
    "run/region-b.pid"
)
print(f"region-b pid={proc_b.pid} port=8002")

print("Starting edge proxy...")
proc_edge = start_proc(
    [sys.executable, "-m", "uvicorn", "edge.proxy:app", "--host", "127.0.0.1", "--port", "8080", "--log-level", "warning"],
    {"EDGE_TTL_SECONDS": "5"},
    "run/edge.log",
    "run/edge.pid"
)
print(f"edge pid={proc_edge.pid} port=8080")

print("cho service len (toi da 10s)...")
ok = True
for name_port in ["region-a:8001", "region-b:8002", "edge:8080"]:
    name, port = name_port.split(":")
    up = False
    for _ in range(10):
        try:
            if name.startswith("region"):
                url = f"http://127.0.0.1:{port}/healthz"
            else:
                url = f"http://127.0.0.1:{port}/edge/state"
            r = httpx.get(url, timeout=1.0)
            if r.status_code == 200:
                up = True
                break
        except Exception:
            pass
        time.sleep(1)
    if up:
        print(f"  {name} (port {port}): UP")
    else:
        print(f"  {name} (port {port}): KHONG PHAN HOI -- xem run/{name}.log (co the cong da bi chiem)")
        ok = False

if not ok:
    print("MOT SO SERVICE CHUA LEN -- doc log truoc khi chay drill")
    sys.exit(1)

try:
    r = httpx.get("http://localhost:8080/edge/state")
    print(r.text)
except Exception as e:
    print("Cannot get edge state:", e)
