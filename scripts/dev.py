"""Cross-platform local service launcher. Stops only processes it started and still owns."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import psutil
from src.config import load_settings

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = load_settings()
STATE = SETTINGS.state_root
WORKSPACE_URL = "http://127.0.0.1:3000/workspace"


def wait_for_workspace(timeout=60):
    deadline = time.monotonic() + timeout
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            with urlopen(WORKSPACE_URL, timeout=min(3, remaining)) as response:
                if response.status == 200:
                    return True
        except (URLError, OSError):
            pass
        time.sleep(min(0.5, max(0, deadline - time.monotonic())))
    return False


def open_workspace():
    print("Waiting for the workspace to be ready...", flush=True)
    if not wait_for_workspace():
        print(
            f"Workspace is not ready after 60 seconds; check {STATE / 'frontend.log'}. "
            f"Services remain running. Open {WORKSPACE_URL} when ready."
        )
        return
    try:
        opened = webbrowser.open(WORKSPACE_URL, new=2)
    except (webbrowser.Error, OSError):
        opened = False
    if opened:
        print(f"Requested the default browser to open {WORKSPACE_URL}")
    else:
        print(f"Could not open the default browser. Open {WORKSPACE_URL}")


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


def start(open_browser=True):
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
    print(f"Started local services. Workspace: {WORKSPACE_URL} ; logs: {STATE}", flush=True)
    if open_browser:
        open_workspace()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop"])
    parser.add_argument(
        "--no-browser", action="store_true", help="Start services without opening a browser"
    )
    args = parser.parse_args()
    if args.action == "start":
        start(open_browser=not args.no_browser)
    else:
        stop()
