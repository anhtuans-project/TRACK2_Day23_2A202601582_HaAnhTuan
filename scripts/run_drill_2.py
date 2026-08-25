import subprocess
import time
import sys

print("Starting ingest and replication...")
ingest_proc = subprocess.Popen([
    sys.executable, "state/ingest.py",
    "--region", "a",
    "--rate", "0.5",
    "--duration", "150"
])

replicate_proc = subprocess.Popen([
    sys.executable, "state/replicate.py",
    "--every", "30",
    "--duration", "150",
    "--backend", "fs"
])

print("Waiting 5 seconds for the first replication cycle to complete...")
time.sleep(5)

print("Starting traffic generator and health checker...")
traffic_proc = subprocess.Popen([
    sys.executable, "loadgen/traffic.py",
    "--duration", "100",
    "--rps", "2",
    "--out", "reports/drill-2-withdr.jsonl"
])

health_proc = subprocess.Popen([
    sys.executable, "dr/health_checker.py",
    "--interval", "5",
    "--threshold", "3",
    "--duration", "100",
    "--out", "reports/health-events.jsonl"
])

print("Waiting 12 seconds before killing region A...")
time.sleep(12)

print("Killing region a (mode=netblock)...")
subprocess.run([
    sys.executable, "chaos/kill_region.py",
    "--region", "a",
    "--mode", "netblock",
    "--mock"
], check=True)

print("Running runbook for failover...")
subprocess.run([
    sys.executable, "dr/runbook.py",
    "--primary", "a",
    "--target", "b",
    "--backend", "fs",
    "--auto"
], check=True)

print("Waiting for traffic and health checker to finish...")
traffic_proc.wait()
health_proc.wait()

print("Cleaning up ingest and replication...")
ingest_proc.terminate()
replicate_proc.terminate()
ingest_proc.wait()
replicate_proc.wait()

print("Drill 2 finished.")
