from fastapi import Request


def store(request: Request):
    return request.app.state.store


def runtime(request: Request):
    return request.app.state.runtime


def settings(request: Request):
    return request.app.state.settings
