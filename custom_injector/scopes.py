from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, TypeVar, Generic, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .core import Injector # To avoid circular import for type hinting

T = TypeVar("T")

class Scope(ABC, Generic[T]):
    def __init__(self, injector: Optional['Injector'] = None):
        self.injector = injector
        
    @abstractmethod
    def get_instance(self, binding_key: Any, provider_callable: Callable[[], T], injector_cache: Dict[Any, Any]) -> T:
        """
        Gets an instance from the scope.
        binding_key: The key the binding was registered with.
        provider_callable: A callable (often from a Provider) that creates the actual instance.
        injector_cache: The injector's cache of instances (e.g., for singletons).
        """
        pass

class TransientScope(Scope[T]):
    def get_instance(self, binding_key: Any, provider_callable: Callable[[], T], injector_cache: Dict[Any, Any]) -> T:
        return provider_callable()

class SingletonScope(Scope[T]):
    def get_instance(self, binding_key: Any, provider_callable: Callable[[], T], injector_cache: Dict[Any, Any]) -> T:
        if binding_key not in injector_cache:
            instance = provider_callable()
            injector_cache[binding_key] = instance
        return injector_cache[binding_key]
