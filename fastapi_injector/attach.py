from fastapi import FastAPI
from injector import Injector, InstanceProvider, singleton
from taskiq import TaskiqState

from fastapi_injector.exceptions import InjectorNotAttached
from fastapi_injector.request_scope import RequestScopeFactory, RequestScopeOptions


def attach_injector(
        app: FastAPI,
        injector: Injector,
        options: RequestScopeOptions = RequestScopeOptions(),
) -> None:
    """
    Call this function on app startup to attach an injector to the app.
    """
    app.state.injector = injector
    injector.binder.bind(
        RequestScopeOptions, InstanceProvider(options), scope=singleton
    )
    injector.binder.bind(RequestScopeFactory, to=RequestScopeFactory, scope=singleton)


def get_injector_instance(app: FastAPI) -> Injector:
    """
    Returns the injector instance attached to the app.
    """
    try:
        return app.state.injector
    except AttributeError as exc:
        raise InjectorNotAttached(
            "No injector instance has been attached to the app."
        ) from exc


def attach_injector_taskiq(
        state: TaskiqState,
        injector: Injector,
        options: RequestScopeOptions = RequestScopeOptions(),
) -> None:
    """
    Call this function on taskiq startup to attach an injector to the taskiq.
    """
    state.injector = injector
    injector.binder.bind(
        RequestScopeOptions, InstanceProvider(options), scope=singleton
    )
    injector.binder.bind(RequestScopeFactory, to=RequestScopeFactory, scope=singleton)


def get_injector_instance_taskiq(state: TaskiqState, ) -> Injector:
    """
    Returns the injector instance attached to the taskiq.
    """
    try:
        return state.injector
    except AttributeError as exc:
        raise InjectorNotAttached(
            "No injector instance has been attached to the app."
        ) from exc
