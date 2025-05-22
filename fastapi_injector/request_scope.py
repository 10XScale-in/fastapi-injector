import asyncio
import threading
import uuid
from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    AsyncExitStack,
    asynccontextmanager,
)
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Dict, Optional, Type, Callable, TypeVar # Added Callable, TypeVar

# from injector import Inject, Injector, InstanceProvider, Provider # Old
# from injector import Scope as InjectorScope # Old
# from injector import ScopeDecorator, T # Old
from custom_injector.core import Injector # New
from custom_injector.scopes import Scope as CustomInjectorScope # New
from starlette.types import Receive, Scope, Send # Scope here is starlette.types.Scope

from fastapi_injector.exceptions import RequestScopeError

T = TypeVar("T") # Defined T
_request_id_ctx: ContextVar[uuid.UUID] = ContextVar("request_id")


@dataclass
class RequestScopeOptions:
    """
    Defines the behavioural options for a request scope.
    """

    enable_cleanup: bool = False
    """
    If True, dependencies that were created from the request scope will be cleaned up
    when the scope is exited. Only dependencies that implement one of the context
    manager protocols will be considered for cleanup.
    """


class RequestScope(CustomInjectorScope[T]): # Changed inheritance
    """
    Caches dependencies within a single request.
    Needs the InjectorMiddleware to be installed to the FastAPI app.

    Example usage:
    ::
        from injector import Injector
        from fastapi import FastAPI
        from fastapi_injector import InjectorMiddleware, request_scope, attach_injector

        from foo.bar import Interface, Implementation

        inj = Injector()
        # Use request_scope when binding the dependency
        inj.binder.bind(Interface, to=Implementation, scope=request_scope)

        app = FastAPI()
        # Add the injector middleware to the app instance
        app.add_middleware(InjectorMiddleware, injector=inj)
        attach_injector(app, inj)
    """

    cache: Dict[uuid.UUID, Dict[Any, Any]] # Key can be Any (binding_key)

    def __init__(self, injector: Injector) -> None: # injector type hint is now custom_injector.core.Injector
        super().__init__(injector) # Call super
        self.options = self.injector.get(RequestScopeOptions) # Use self.injector
        self.cache = {} # Initialize cache
        self._loop = asyncio.new_event_loop()
        self._thr = threading.Thread(
            target=self._loop.run_forever,
            name="fastapi-injector-enter-context",
            daemon=True,
        )

    def get_instance(self, binding_key: Any, provider_callable: Callable[[], T], injector_cache: Dict[Any, Any]) -> T: # Renamed and new signature
        try:
            request_id = _request_id_ctx.get()
        except LookupError as exc:
            raise RequestScopeError(
                "Request ID missing in cache. "
                "Make sure InjectorMiddleware has been added to the FastAPI instance."
            ) from exc
        
        stack: Optional[AsyncExitStack] = None
        if self.options.enable_cleanup:
            # Ensure the cache for request_id exists before trying to access AsyncExitStack from it
            if request_id not in self.cache: # Should be created by add_key
                 self.cache[request_id] = {}

            if AsyncExitStack in self.cache[request_id]:
                stack = self.cache[request_id][AsyncExitStack]
            else:
                stack = self.cache[request_id][AsyncExitStack] = AsyncExitStack()
        
        if binding_key in self.cache[request_id]:
            dependency = self.cache[request_id][binding_key]
        else:
            dependency = provider_callable() # Call the provided factory
            self.cache[request_id][binding_key] = dependency
            if stack: # Register for cleanup if stack exists for this request_id
                self._register(dependency, stack)
        return dependency # Return the instance directly

    def add_key(self, key: uuid.UUID) -> None:
        """Add a new request key to the cache."""
        self.cache[key] = {}

    async def clear_key(self, key: uuid.UUID) -> None:
        """Clear the cache for a given request key."""
        stack: AsyncExitStack = self.cache[key].get(AsyncExitStack, None)
        if stack:
            await stack.aclose()
        del self.cache[key]

    def _register(self, obj: Any, stack: AsyncExitStack):
        if isinstance(obj, AbstractContextManager):
            stack.enter_context(obj)
        elif isinstance(obj, AbstractAsyncContextManager):
            self._enter_async_context(obj, stack)

    def _enter_async_context(self, obj: Any, stack: AsyncExitStack) -> None:
        # This is the classic "how to call async from sync" problem. See
        # https://stackoverflow.com/a/74710015/260213 for a detailed explanation of how
        # we solve this. In brief, we have a background thread that runs a separate
        # event loop, and the async context is entered on that thread while the calling
        # thread blocks
        try:
            asyncio.get_running_loop()
        except RuntimeError:  # 'RuntimeError: There is no current event loop...'
            # Starting new event loop
            asyncio.run(stack.enter_async_context(obj))
        else:
            # Event loop is running, enter the context on a background thread
            self._run_async(stack.enter_async_context(obj))

    def _run_async(self, coroutine):
        # This will block the calling thread until the coroutine is finished.
        # Any exception that occurs in the coroutine is raised in the caller
        if not self._thr.is_alive():
            self._thr.start()
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        return future.result()


# request_scope = ScopeDecorator(RequestScope) # Removed this line


class RequestScopeFactory:
    """
    Allows to create request scopes.
    """

    def __init__(self, request_scope_instance: RequestScope) -> None: # Removed Inject, type hint directly
        self.request_scope_instance = request_scope_instance

    @asynccontextmanager
    async def create_scope(self):
        """Creates a new request scope within dependencies are cached."""
        rid = uuid.uuid4()
        rid_ctx = _request_id_ctx.set(rid)
        self.request_scope_instance.add_key(rid)
        try:
            yield
        finally:
            await self.request_scope_instance.clear_key(rid)
            _request_id_ctx.reset(rid_ctx)


class InjectorMiddleware:
    """
    Middleware that enables request-scoped injection through ContextVar-based cache.
    """

    def __init__(self, app, injector: Injector) -> None: # injector type hint is now custom_injector.core.Injector
        self.app = app
        self.request_scope_factory = injector.get(RequestScopeFactory)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None: # scope here is starlette.types.Scope
        """
        Add an identifier to the request
        that can be used retrieve scoped dependencies.
        """
        async with self.request_scope_factory.create_scope():
            await self.app(scope, receive, send)
