"""Cross-platform local service launcher. Stops only processes it started and still owns."""

import argparse, json, os, shutil, subprocess, sys
from pathlib import Path
import psutil
from src.config import load_settings

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = load_settings()
STATE = SETTINGS.state_root


def stop():
    path = STATE / "services.json"
    if not path.exists():
        return
    for item in json.loads(path.read_text(encoding="utf-8")):
        try:
            proc = psutil.Process(item["pid"])
            if abs(proc.create_time() - item["created"]) > 0.01:
                continue
            if proc.cmdline() != item["command"]:
                continue
            processes = proc.children(recursive=True) + [proc]
            for child in processes:
                child.terminate()
            _, remaining = psutil.wait_procs(processes, timeout=5)
            for child in remaining:
                child.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    path.unlink()


def start():
    STATE.mkdir(exist_ok=True)
    if (STATE / "services.json").exists():
        raise RuntimeError(
            "service state exists; stop the owned services before starting again"
        )
    node = shutil.which("node")
    next_bin = ROOT / "frontend/node_modules/next/dist/bin/next"
    if not node or not next_bin.exists():
        raise RuntimeError("install Node 22+ and frontend dependencies first")
    host, port = SETTINGS.gateway_host, str(SETTINGS.gateway_port)
    proxy_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    if ":" in proxy_host:
        proxy_host = "[" + proxy_host + "]"
    environment = {**os.environ, "GATEWAY_URL": f"http://{proxy_host}:{port}"}
    commands = [
        (
            "gateway",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "src.gateway.app:app",
                "--host",
                host,
                "--port",
                port,
            ],
            ROOT / "backend",
        ),
        ("worker", [sys.executable, "-m", "src.tools.worker"], ROOT / "backend"),
        (
            "frontend",
            [node, str(next_bin), "dev", "--hostname", "127.0.0.1", "--port", "3000"],
            ROOT / "frontend",
        ),
    ]
    items = []
    try:
        for name, command, cwd in commands:
            with (STATE / (name + ".log")).open("ab") as log:
                process = subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    start_new_session=os.name != "nt",
                )
            proc = psutil.Process(process.pid)
            items.append(
                {
                    "name": name,
                    "pid": process.pid,
                    "created": proc.create_time(),
                    "command": proc.cmdline(),
                }
            )
            (STATE / "services.json").write_text(json.dumps(items), encoding="utf-8")
    except Exception:
        stop()
        raise
    print(f"Started local services. Workspace: http://127.0.0.1:3000 ; logs: {STATE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop"])
    args = parser.parse_args()
    (start if args.action == "start" else stop)()
