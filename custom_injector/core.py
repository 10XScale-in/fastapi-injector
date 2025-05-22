from typing import Any, Type, Callable, Dict, TypeVar, Optional, Set, TYPE_CHECKING
from .scopes import Scope, TransientScope, SingletonScope
from .providers import Provider, ClassProvider, FactoryProvider, ValueProvider
from .exceptions import BindingError, ResolutionError, CircularDependencyError

if TYPE_CHECKING:
    pass # No specific imports needed here for core.py itself for now

T = TypeVar("T")

class Binding:
    def __init__(self, key: Type[T], provider: Provider, scope: Scope):
        self.key = key
        self.provider = provider
        self.scope = scope

class Injector:
    def __init__(self):
        self._bindings: Dict[Type[Any], Binding] = {}
        self._instances: Dict[Type[Any], Any] = {}  # Cache for scoped instances, primarily singletons
        self._currently_resolving: Set[Type[Any]] = set() # For circular dependency detection
        self._scopes_instances: Dict[Type[Scope], Scope] = {} # Cache for scope instances

    def _get_scope_instance(self, scope_class: Type[Scope]) -> Scope:
        if scope_class not in self._scopes_instances:
            try:
                # Try to initialize with the injector instance itself
                scope_instance = scope_class(self)
            except TypeError:
                # If scope_class.__init__ doesn't take an argument (or not an injector)
                try:
                    scope_instance = scope_class()
                except Exception as e:
                    raise BindingError(f"Could not instantiate scope {scope_class.__name__}: {e}")
            self._scopes_instances[scope_class] = scope_instance
        return self._scopes_instances[scope_class]

    def bind(
        self,
        key: Type[T],
        *,
        to_class: Optional[Type[Any]] = None,
        to_factory: Optional[Callable[..., Any]] = None,
        to_value: Optional[Any] = None,
        scope: Type[Scope] = TransientScope  # Pass the class, not an instance
    ):
        if [to_class, to_factory, to_value].count(None) < 2:
            raise BindingError(f"Provide only one of to_class, to_factory, or to_value for key {key}")

        if to_class:
            provider = ClassProvider(to_class)
        elif to_factory:
            provider = FactoryProvider(to_factory)
        elif to_value is not None: # Check for `is not None` because to_value could be False or 0
            provider = ValueProvider(to_value)
            # Values are inherently singletons in behavior, binding to a specific scope class doesn't change the value.
            # We can enforce that values are always effectively singleton by wrapping them in a specific scope if needed,
            # or just let the ValueProvider return the value. For now, scope applies like others.
        else:
            # Default to binding the key to itself if it's a class
            if isinstance(key, type):
                provider = ClassProvider(key)
            else:
                raise BindingError(f"Cannot determine provider for key {key}. Please specify to_class, to_factory, or to_value.")
        
        self._bindings[key] = Binding(key, provider, self._get_scope_instance(scope))

    def get(self, key: Type[T]) -> T:
        if key in self._currently_resolving:
            raise CircularDependencyError(f"Circular dependency detected for key {key}")
        self._currently_resolving.add(key)

        try:
            binding = self._bindings.get(key)
            if not binding:
                # Attempt to auto-bind if 'key' is a class and not yet bound
                if isinstance(key, type):
                    self.bind(key, to_class=key, scope=TransientScope) # Default to Transient for auto-bindings
                    binding = self._bindings.get(key)
                    if not binding: # Should not happen after auto-bind
                         raise ResolutionError(f"Auto-binding failed for key {key}")
                else:
                    raise ResolutionError(f"No binding found for key {key} and it's not a class type for auto-binding.")

            # The scope's get_instance will use the provider.
            # The scope's get_instance will use the provider.
            # The SingletonScope needs to be more robust to use the injector's _instances cache.
            # Let's refine how SingletonScope interacts with the injector cache.

            # Replace the existing scope handling block with this:
            return binding.scope.get_instance(
                binding_key=key, 
                provider_callable=lambda: binding.provider.get_instance(self), 
                injector_cache=self._instances
            )
        finally:
            self._currently_resolving.remove(key)
