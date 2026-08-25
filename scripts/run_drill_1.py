import subprocess
import time
import sys

print("Starting loadgen for Drill 1...")
loadgen_proc = subprocess.Popen([
    sys.executable, "loadgen/traffic.py",
    "--duration", "40",
    "--rps", "2",
    "--out", "reports/drill-1-nodr.jsonl"
])

print("Waiting 8 seconds before killing region A...")
time.sleep(8)

print("Killing region a (mode=netblock)...")
subprocess.run([
    sys.executable, "chaos/kill_region.py",
    "--region", "a",
    "--mode", "netblock",
    "--mock"
], check=True)

print("Waiting for loadgen to complete...")
loadgen_proc.wait()
print("Drill 1 finished.")
