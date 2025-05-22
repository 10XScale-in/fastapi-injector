from fastapi import FastAPI
# from injector import Injector, InstanceProvider, singleton # Old import
from custom_injector.core import Injector # New import
from custom_injector.scopes import SingletonScope # New import
from taskiq import TaskiqState # Ensure this is active

from fastapi_injector.exceptions import InjectorNotAttached
# RequestScopeMiddleware was removed in previous version, let's keep it like this.
from fastapi_injector.request_scope import RequestScopeFactory, RequestScopeOptions, RequestScope 


def attach_injector(
    app: FastAPI,
    injector: Injector, # Hint should now point to custom_injector.core.Injector
    options: RequestScopeOptions = RequestScopeOptions(),
) -> None:
    """
    Call this function on app startup to attach an injector to the app.
    """
    app.state.injector = injector
    # injector.binder.bind(
    #     RequestScopeOptions, InstanceProvider(options), scope=singleton
    # ) # Old way
    injector.bind(RequestScopeOptions, to_value=options, scope=SingletonScope) # New way
    # injector.binder.bind(RequestScopeFactory, to=RequestScopeFactory, scope=singleton) # Old way
    injector.bind(RequestScopeFactory, to_class=RequestScopeFactory, scope=SingletonScope) # New way
    injector.bind(RequestScope, to_class=RequestScope, scope=SingletonScope) # Bind RequestScope itself
    # app.add_middleware(RequestScopeMiddleware, injector=injector, options=options) # This line was in the target, but not in source for this specific file version. Keep it commented.


def get_injector_instance(app: FastAPI) -> Injector: # Return hint should be custom_injector.core.Injector
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
    injector: Injector, # Type hint updated to custom_injector.core.Injector implicitly by import
    options: RequestScopeOptions = RequestScopeOptions(),
) -> None:
    """
    Call this function on taskiq startup to attach an injector to the taskiq.
    """
    state.injector = injector
    # injector.binder.bind(
    #     RequestScopeOptions, InstanceProvider(options), scope=singleton
    # ) # Old way
    injector.bind(RequestScopeOptions, to_value=options, scope=SingletonScope) # New way
    # injector.binder.bind(RequestScopeFactory, to=RequestScopeFactory, scope=singleton) # Old way
    injector.bind(RequestScopeFactory, to_class=RequestScopeFactory, scope=SingletonScope) # New way
    injector.bind(RequestScope, to_class=RequestScope, scope=SingletonScope) # Bind RequestScope itself


def get_injector_instance_taskiq(state: TaskiqState) -> Injector: # Return hint updated to custom_injector.core.Injector implicitly
    """
    Returns the injector instance attached to the taskiq.
    """
    try:
        return state.injector
    except AttributeError as exc:
        raise InjectorNotAttached(
            "No injector instance has been attached to the app." # Message can be updated to taskiq context
        ) from exc
