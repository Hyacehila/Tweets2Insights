from . import threads, runs, events, datasets, artifacts, system

ROUTERS = [
    threads.router,
    runs.router,
    events.router,
    datasets.router,
    artifacts.router,
    system.router,
]
