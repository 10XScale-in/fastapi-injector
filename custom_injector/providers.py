import inspect
from abc import ABC, abstractmethod
from typing import Any, Type, Callable, TYPE_CHECKING, Dict, List, Tuple

if TYPE_CHECKING:
    from .core import Injector
    # from .core import T  # Import T if used for generic type hints in providers
    # T is not directly used in this file after the change, but Injector might need it.
    # For now, keeping it commented out unless a direct need arises in this file.

class Provider(ABC):
    @abstractmethod
    def get_instance(self, injector: 'Injector') -> Any:
        pass

class ValueProvider(Provider):
    def __init__(self, value: Any):
        self._value = value

    def get_instance(self, injector: 'Injector') -> Any:
        return self._value

def _resolve_dependencies(
    injector: 'Injector',
    callable_to_inspect: Callable[..., Any],
    is_method: bool = False
) -> Tuple[List[Any], Dict[str, Any]]:
    """
    Helper function to inspect a callable (function or method) and resolve its dependencies.
    Returns a tuple of (args, kwargs) for calling the callable.
    """
    args_to_pass = []
    kwargs_to_pass = {}
    
    # Need to import ResolutionError if we decide to raise it.
    # from .exceptions import ResolutionError 

    sig = inspect.signature(callable_to_inspect)
    params = list(sig.parameters.values())

    if is_method: # Skip 'self' or 'cls' for methods
        # Ensure there are parameters to skip, and that the first is 'self' or 'cls' by convention.
        # A more robust check might be needed for atypical method signatures.
        if params and (params[0].name == 'self' or params[0].name == 'cls'):
             params = params[1:]
        elif inspect.isclass(callable_to_inspect): # Check if it's a class constructor itself (e.g. __init__ of a metaclass)
            # This path is less common for typical DI scenarios with __init__
            # but added for robustness if callable_to_inspect is a class.
            # However, __init__ is usually an instance method.
            pass


    for param in params:
        param_type = param.annotation
        if param_type is inspect.Parameter.empty:
            # If there's a default, Python will use it if no value is provided.
            # We only inject if there's a type hint.
            if param.default is inspect.Parameter.empty:
                # This is a required parameter without a type hint. DI cannot fill it.
                # Python will raise a TypeError if it's not provided.
                # Optionally, raise ResolutionError here:
                # raise ResolutionError(f"Cannot inject parameter '{param.name}' for '{callable_to_inspect.__name__}': missing type annotation and no default value.")
                pass # Let Python handle it, or raise error.
            continue


        # Resolve the dependency using the injector
        # This assumes injector.get() can handle param_type.
        try:
            resolved_dependency = injector.get(param_type)
        except Exception as e: # Catching a broad exception to wrap it, consider more specific ones from injector
            # from .exceptions import ResolutionError # Ensure this is imported
            # raise ResolutionError(f"Failed to resolve dependency for parameter '{param.name}' of type {param_type} in '{callable_to_inspect.__name__}': {e}")
            # For now, re-raise to see original error from injector.get
            raise

        if param.kind == inspect.Parameter.POSITIONAL_ONLY:
            args_to_pass.append(resolved_dependency)
        elif param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
            # If a default value exists and DI resolves a value, DI takes precedence.
            # This is standard behavior: explicit injection overrides defaults.
            args_to_pass.append(resolved_dependency)
        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
            kwargs_to_pass[param.name] = resolved_dependency
        elif param.kind == inspect.Parameter.VAR_POSITIONAL:
            # print(f"Warning: VAR_POSITIONAL parameter (*{param.name}) in {callable_to_inspect.__name__} is not supported for DI.")
            pass 
        elif param.kind == inspect.Parameter.VAR_KEYWORD:
            # print(f"Warning: VAR_KEYWORD parameter (**{param.name}) in {callable_to_inspect.__name__} is not supported for DI.")
            pass
            
    return args_to_pass, kwargs_to_pass


class ClassProvider(Provider):
    def __init__(self, cls: Type[Any]):
        self._cls = cls

    def get_instance(self, injector: 'Injector') -> Any:
        constructor = self._cls.__init__
        
        # Check if the constructor is the default object.__init__ which takes no arguments (other than self)
        # or if it's a custom __init__ method.
        if constructor is object.__init__:
            # No custom __init__, so no dependencies to inject for constructor
            return self._cls()
        
        args, kwargs = _resolve_dependencies(injector, constructor, is_method=True)
        return self._cls(*args, **kwargs)

class FactoryProvider(Provider):
    def __init__(self, factory: Callable[..., Any]):
        self._factory = factory

    def get_instance(self, injector: 'Injector') -> Any:
        # Check if factory is a method (bound or unbound) to correctly adjust for 'self'/'cls'
        is_method = inspect.ismethod(self._factory) or \
                    (inspect.isfunction(self._factory) and '.' in self._factory.__qualname__ and not inspect.isclass(self._factory))
        
        # A more robust check for methods, especially for staticmethods or classmethods if they were passed directly
        # For simplicity, assuming typical functions or instance methods.
        # If self._factory is a bound method, 'self' is already part of its context.
        # inspect.signature() handles bound methods correctly, so is_method=False might be okay
        # if the 'self' is already bound. However, if it's an unbound method taken from a class,
        # then is_method=True would be needed if it were called like Class.method().
        # Let's stick to the provided logic for now and refine if test cases show issues.

        args, kwargs = _resolve_dependencies(injector, self._factory, is_method=is_method)
        return self._factory(*args, **kwargs)
