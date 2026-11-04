# 本机启动与运行

环境要求、获取代码和 `.env` 初始化见 [README：快速开始](../README.md#quickstart)。本页补充本机进程管理。

## 本机

```powershell
uv sync --project backend --frozen
npm --prefix frontend ci
uv run --project backend python scripts/dev.py start
uv run --project backend python scripts/dev.py stop
```

启动器管理 Gateway、领域 Worker、Next.js 开发服务器；默认前端 127.0.0.1:3000、Gateway 127.0.0.1:8001。
启动后等待启动页和研究 API 同时就绪，终端显示“前端已启动成功！”，再自动用系统默认浏览器打开 `http://127.0.0.1:3000/`。终端始终保留访问网址，浏览器未自动打开时可复制使用。
重复执行启动命令时，启动器核对已有服务的 PID、创建时间和命令，确认三个服务仍在运行后直接打开启动页。
上次记录的进程均已退出时，会自动清理旧记录并重新启动服务。
仅启动后台服务可使用：

```powershell
uv run --project backend python scripts/dev.py start --no-browser
```

服务就绪最多等待 60 秒；超时会提示“前端或研究服务尚未就绪”、显示日志位置并返回非零退出码，服务继续运行。浏览器打开失败时，显示“自动打开浏览器失败，请使用以下网址打开”，已启动的服务继续运行。
日志和进程记录位于 `.app-state`；停止前核对 PID、创建时间及命令，只停止本启动器拥有的进程。
Windows 后台服务以无窗口方式启动，浏览器正常显示。只运行一个 Gateway 进程，使用独立 Worker 执行领域任务。
主配置中的 Gateway host/port 同时用于启动器和前端代理；前端开发端口固定为 3000。
