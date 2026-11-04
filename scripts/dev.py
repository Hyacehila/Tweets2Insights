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
WORKSPACE_URL = "http://127.0.0.1:3000/"


def wait_for_workspace(timeout=60):
    deadline = time.monotonic() + timeout
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            with urlopen(WORKSPACE_URL, timeout=min(3, remaining)) as response:
                if response.status == 200:
                    with urlopen(WORKSPACE_URL + 'api/health', timeout=min(3, remaining)) as health:
                        if health.status == 200:
                            return True
        except (URLError, OSError):
            pass
        time.sleep(min(0.5, max(0, deadline - time.monotonic())))
    return False


def open_workspace(open_browser=True):
    print("正在等待前端页面与研究服务就绪……", flush=True)
    if not wait_for_workspace():
        print(
            "前端或研究服务尚未就绪（已等待 60 秒）。\n"
            f"请查看日志：{STATE / 'frontend.log'}\n"
            f"服务仍在后台运行，可稍后访问：{WORKSPACE_URL}"
        )
        return False
    print("前端已启动成功！", flush=True)
    if open_browser:
        print("正在自动打开系统默认浏览器……", flush=True)
        try:
            opened = webbrowser.open(WORKSPACE_URL, new=2)
        except (webbrowser.Error, OSError):
            opened = False
        if opened:
            print("若浏览器未自动打开，请使用以下网址打开：")
        else:
            print("自动打开浏览器失败，请使用以下网址打开：")
    else:
        print("请使用以下网址打开：")
    print(WORKSPACE_URL)
    print(f"运行日志：{STATE}")
    return True


def services_running():
    try:
        items = json.loads((STATE / "services.json").read_text(encoding="utf-8"))
        if len(items) != 3 or {item["name"] for item in items} != {
            "gateway",
            "worker",
            "frontend",
        }:
            return False
        for item in items:
            proc = psutil.Process(item["pid"])
            if abs(proc.create_time() - item["created"]) > 0.01:
                return False
            if not proc.is_running() or proc.cmdline() != item["command"]:
                return False
    except (psutil.Error, OSError, ValueError, KeyError, TypeError):
        return False
    return True


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
    state_path = STATE / "services.json"
    if state_path.exists():
        if services_running():
            print("检测到本项目服务已在运行。", flush=True)
            return open_workspace(open_browser=open_browser)
        items = json.loads(state_path.read_text(encoding="utf-8"))
        if all(not psutil.pid_exists(item["pid"]) for item in items):
            state_path.unlink()
            print("上次运行的服务已退出，正在重新启动……", flush=True)
        else:
            raise RuntimeError(
                "已有服务记录，但部分服务已退出或进程信息不匹配。\n"
                "请先执行 uv run --project backend python scripts/dev.py stop，再重新启动。"
            )
    node = shutil.which("node")
    next_bin = ROOT / "frontend/node_modules/next/dist/bin/next"
    if not node or not next_bin.exists():
        raise RuntimeError(
            "请先安装 Node.js 22+，并执行 npm --prefix frontend ci 安装前端依赖。"
        )
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
    return open_workspace(open_browser=open_browser)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop"])
    parser.add_argument(
        "--no-browser", action="store_true", help="启动服务，但不自动打开浏览器"
    )
    args = parser.parse_args()
    try:
        if args.action == "start":
            sys.exit(0 if start(open_browser=not args.no_browser) else 1)
        else:
            stop()
    except (RuntimeError, OSError) as exc:
        print(f"操作失败：{exc}", file=sys.stderr)
        sys.exit(1)
