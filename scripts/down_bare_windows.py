import os
import pathlib
import signal

print("Stopping Windows bare services...")
pid_dir = pathlib.Path("run")
for f in pid_dir.glob("*.pid"):
    if not f.is_file():
        continue
    try:
        pid_text = f.read_text().strip()
        if pid_text:
            pid = int(pid_text)
            print(f"Stopping process {pid} from {f.name}...")
            try:
                import ctypes
                PROCESS_SUSPEND_RESUME = 0x0800
                handle = ctypes.windll.kernel32.OpenProcess(PROCESS_SUSPEND_RESUME, False, pid)
                if handle:
                    ctypes.windll.ntdll.NtResumeProcess(handle)
                    ctypes.windll.kernel32.CloseHandle(handle)
            except Exception:
                pass
            try:
                os.kill(pid, 9)
            except Exception:
                pass
    except Exception as e:
        print(f"Error stopping process for {f.name}: {e}")
    try:
        f.unlink()
    except Exception:
        pass
print("All stopped.")
