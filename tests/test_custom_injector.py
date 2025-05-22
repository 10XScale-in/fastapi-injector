import pytest
from abc import ABC, abstractmethod

from custom_injector.core import Injector
from custom_injector.scopes import TransientScope, SingletonScope
from custom_injector.exceptions import BindingError, ResolutionError, CircularDependencyError

# --- Interfaces and Classes for Testing ---

class ServiceInterface(ABC):
    @abstractmethod
    def serve(self) -> str:
        pass

class ConcreteServiceA(ServiceInterface):
    def serve(self) -> str:
        return "ServiceA"

class ConcreteServiceB(ServiceInterface):
    def __init__(self, val: int):
        self._val = val
    def serve(self) -> str:
        return f"ServiceB_with_{self._val}"

class ServiceWithDependency:
    def __init__(self, service: ServiceInterface):
        self.service = service

    def get_service_data(self) -> str:
        return f"Dependent_{self.service.serve()}"

def factory_service_c(val: int) -> ServiceInterface:
    # This factory expects 'val: int' to be injected
    return ConcreteServiceB(val + 100)

# --- Tests ---

def test_bind_and_get_class_to_self():
    injector = Injector()
    injector.bind(ConcreteServiceA)
    instance = injector.get(ConcreteServiceA)
    assert isinstance(instance, ConcreteServiceA)

def test_bind_interface_to_concrete():
    injector = Injector()
    injector.bind(ServiceInterface, to_class=ConcreteServiceA)
    instance = injector.get(ServiceInterface)
    assert isinstance(instance, ConcreteServiceA)
    assert instance.serve() == "ServiceA"

def test_bind_to_value():
    injector = Injector()
    injector.bind(int, to_value=42)
    injector.bind(str, to_value="hello")
    assert injector.get(int) == 42
    assert injector.get(str) == "hello"

def test_bind_to_factory():
    injector = Injector()
    injector.bind(int, to_value=10) # Dependency for the factory
    injector.bind(ServiceInterface, to_factory=factory_service_c, scope=TransientScope)
    
    instance = injector.get(ServiceInterface)
    assert isinstance(instance, ConcreteServiceB)
    assert instance.serve() == "ServiceB_with_110" # 10 (from int binding) + 100

def test_transient_scope():
    injector = Injector()
    injector.bind(ConcreteServiceA, scope=TransientScope)
    instance1 = injector.get(ConcreteServiceA)
    instance2 = injector.get(ConcreteServiceA)
    assert instance1 is not instance2

def test_singleton_scope():
    injector = Injector()
    injector.bind(ConcreteServiceA, scope=SingletonScope)
    instance1 = injector.get(ConcreteServiceA)
    instance2 = injector.get(ConcreteServiceA)
    assert instance1 is instance2

def test_dependency_injection_constructor():
    injector = Injector()
    injector.bind(ServiceInterface, to_class=ConcreteServiceA)
    injector.bind(ServiceWithDependency) # Binds to itself, will resolve ServiceInterface for its __init__

    dependent_instance = injector.get(ServiceWithDependency)
    assert isinstance(dependent_instance, ServiceWithDependency)
    assert isinstance(dependent_instance.service, ConcreteServiceA)
    assert dependent_instance.get_service_data() == "Dependent_ServiceA"

def test_auto_binding_class():
    injector = Injector()
    # ConcreteServiceA is not explicitly bound
    instance = injector.get(ConcreteServiceA)
    assert isinstance(instance, ConcreteServiceA)
    # Check it's transient by default for auto-binding
    instance2 = injector.get(ConcreteServiceA)
    assert instance is not instance2 

def test_resolve_unbound_non_class_key_raises_resolution_error():
    injector = Injector()
    class NonClassKey: pass # Just a unique object, not a type hint for DI usually
    
    with pytest.raises(ResolutionError):
        injector.get(NonClassKey) # type: ignore 

def test_resolve_unbound_interface_raises_resolution_error():
    injector = Injector()
    with pytest.raises(ResolutionError):
        injector.get(ServiceInterface)


def test_binding_error_multiple_targets():
    injector = Injector()
    with pytest.raises(BindingError):
        injector.bind(ServiceInterface, to_class=ConcreteServiceA, to_value="error")

# --- Circular Dependency Tests ---

class CircularA:
    def __init__(self, b: 'CircularB'): # Forward reference for type hint
        self.b = b

class CircularB:
    def __init__(self, a: 'CircularA'): # Forward reference for type hint
        self.a = a

def test_circular_dependency_direct():
    injector = Injector()
    # Bind with SingletonScope as circular dependencies are often an issue with singletons
    # due to their lifecycle and shared state. Transient might also fail if construction path is circular.
    injector.bind(CircularA, scope=SingletonScope) 
    injector.bind(CircularB, scope=SingletonScope)
    with pytest.raises(CircularDependencyError):
        injector.get(CircularA)
    
    # Test with TransientScope as well, as the resolution path itself is circular
    injector_transient = Injector()
    injector_transient.bind(CircularA, scope=TransientScope) 
    injector_transient.bind(CircularB, scope=TransientScope)
    with pytest.raises(CircularDependencyError):
        injector_transient.get(CircularA)


class CircularC:
    def __init__(self, d: 'CircularD'):
        self.d = d

class CircularD:
    def __init__(self, e: 'CircularE'):
        self.e = e

class CircularE:
    def __init__(self, c: 'CircularC'): # Points back to C
        self.c = c

def test_circular_dependency_indirect():
    injector = Injector()
    injector.bind(CircularC, scope=SingletonScope)
    injector.bind(CircularD, scope=SingletonScope)
    injector.bind(CircularE, scope=SingletonScope)
    with pytest.raises(CircularDependencyError):
        injector.get(CircularC)

def test_get_dependency_with_default_value_unannotated_param():
    # Test behavior for parameters without type annotations but with default values.
    # The current _resolve_dependencies logic skips injection for unannotated params.
    # Python's own mechanism should then use the default value.
    class ServiceWithDefaultUnannotated:
        def __init__(self, name="default_name"): # 'name' is unannotated
            self.name = name
    
    injector = Injector()
    injector.bind(ServiceWithDefaultUnannotated) # Auto-binds ServiceWithDefaultUnannotated to itself
    instance = injector.get(ServiceWithDefaultUnannotated)
    assert instance.name == "default_name"


def test_get_dependency_with_annotated_param_and_default_value():
    # Test behavior for parameters that have both a type annotation and a default value.
    # DI should take precedence if the type is bound.
    # If the type is not bound, DI should ideally not try to resolve it, letting default work.
    # However, current `Injector.get` might try to auto-bind `str` or `int` if not explicitly bound.
    # Let's test specific scenarios.

    class ServiceWithAnnotatedDefault:
        def __init__(self, name: str = "default_name", age: int = 30):
            self.name = name
            self.age = age
            
    # Scenario 1: One dependency (str) is bound, the other (int) is not.
    injector1 = Injector()
    injector1.bind(str, to_value="injected_name")
    injector1.bind(ServiceWithAnnotatedDefault) 
    
    instance1 = injector1.get(ServiceWithAnnotatedDefault)
    assert instance1.name == "injected_name" # Injected
    # For 'age: int = 30', since 'int' is not bound in injector1,
    # and if auto-binding for 'int' as a class doesn't make sense or fails,
    # it should ideally fall back to the default value.
    # Current auto-binding might try to instantiate `int()`, resulting in 0.
    # The _resolve_dependencies will try injector.get(int). If int is not bound,
    # injector.get(int) will auto-bind int to ClassProvider(int) which results in int().
    # So, we expect age to be 0, not 30, unless int is explicitly bound to a value.
    assert instance1.age == 0 # Due to auto-binding of int to int()

    # Scenario 2: Both dependencies are explicitly bound.
    injector2 = Injector()
    injector2.bind(str, to_value="injected_name_2")
    injector2.bind(int, to_value=99) # Explicitly bind int
    injector2.bind(ServiceWithAnnotatedDefault)
    instance2 = injector2.get(ServiceWithAnnotatedDefault)
    assert instance2.name == "injected_name_2"
    assert instance2.age == 99

    # Scenario 3: Neither dependency is bound.
    injector3 = Injector()
    injector3.bind(ServiceWithAnnotatedDefault)
    instance3 = injector3.get(ServiceWithAnnotatedDefault)
    # name: str will be str() -> ""
    # age: int will be int() -> 0
    assert instance3.name == "" 
    assert instance3.age == 0

def test_dependency_injection_factory_with_dependencies():
    class DepClient:
        def __init__(self, service: ServiceInterface, num: int):
            self.service_data = service.serve()
            self.num_val = num

    def my_factory(service: ServiceInterface, number_val: int) -> DepClient:
        # 'number_val: int' will be injected as 'num' for DepClient
        return DepClient(service, number_val * 2)

    injector = Injector()
    injector.bind(ServiceInterface, to_class=ConcreteServiceA)
    injector.bind(int, to_value=21) # This will be injected as 'number_val'
    injector.bind(DepClient, to_factory=my_factory)

    client = injector.get(DepClient)
    assert isinstance(client, DepClient)
    assert client.service_data == "ServiceA"
    assert client.num_val == 42 # 21 * 2

# TODO: Add more tests, e.g. for complex type hints if supported (List[ServiceInterface]),
# provider for already existing instance, more scope interactions.
# Test what happens if a dependency for a factory/class is missing and has no default.
# (Should be ResolutionError from within _resolve_dependencies, or TypeError from Python itself
# if we allow it to proceed without all args).
# The current _resolve_dependencies re-raises, so it would be ResolutionError if injector.get fails.
# If param_type is not inspect.Parameter.empty but injector.get fails, it's a ResolutionError.
# If param_type is inspect.Parameter.empty and no default, Python TypeError.

# Test for `to_value` with `None`
def test_bind_to_value_none():
    injector = Injector()
    SomeType = type("SomeType", (), {}) # Create a dummy type
    injector.bind(SomeType, to_value=None)
    assert injector.get(SomeType) is None

# Test that auto-binding creates transient instances by default
def test_auto_binding_is_transient():
    injector = Injector()
    instance1 = injector.get(ConcreteServiceA) # Auto-binds ConcreteServiceA
    instance2 = injector.get(ConcreteServiceA)
    assert instance1 is not instance2, "Auto-bound instances should be transient by default"

# Test that a value bound with SingletonScope is indeed a singleton (though ValueProvider inherently is)
def test_value_bound_as_singleton_scope():
    injector = Injector()
    my_object = object()
    # While ValueProvider itself doesn't use the scope's caching mechanism (it just returns the value),
    # binding with SingletonScope should still mean that if the "value" were somehow generated by a factory
    # and then wrapped by a ValueProvider, that generation should happen once.
    # Here, to_value is simple, so scope doesn't change much for ValueProvider.
    # The core.py's get() method now directly uses scope.get_instance for all,
    # so ValueProvider will be called by SingletonScope.get_instance.
    injector.bind(object, to_value=my_object, scope=SingletonScope)
    instance1 = injector.get(object)
    instance2 = injector.get(object)
    assert instance1 is my_object
    assert instance1 is instance2

def test_factory_bound_as_singleton_scope():
    injector = Injector()
    
    # A factory that should only be called once for a singleton
    call_count = 0
    def my_singleton_factory() -> ConcreteServiceA:
        nonlocal call_count
        call_count += 1
        return ConcreteServiceA()

    injector.bind(ServiceInterface, to_factory=my_singleton_factory, scope=SingletonScope)
    
    instance1 = injector.get(ServiceInterface)
    assert call_count == 1
    assert isinstance(instance1, ConcreteServiceA)
    
    instance2 = injector.get(ServiceInterface)
    assert call_count == 1 # Should not have incremented
    assert instance1 is instance2

def test_class_bound_as_singleton_scope_with_dependencies():
    injector = Injector()

    # Dependency for ServiceWithDependency
    injector.bind(ServiceInterface, to_class=ConcreteServiceA, scope=SingletonScope) 
    
    # ServiceWithDependency itself as a singleton
    injector.bind(ServiceWithDependency, scope=SingletonScope)

    # Resolve ServiceWithDependency multiple times
    instance1 = injector.get(ServiceWithDependency)
    instance2 = injector.get(ServiceWithDependency)

    assert instance1 is instance2, "ServiceWithDependency should be a singleton"
    
    # Also check its dependency (ServiceInterface) was also a singleton if resolved via injector
    # Get the singleton ServiceInterface directly
    service_instance1 = injector.get(ServiceInterface)
    
    assert instance1.service is service_instance1, "Injected service should be the singleton instance"
    assert instance2.service is service_instance1, "Injected service should be the singleton instance for all dependents"

    # Verify ConcreteServiceA (as ServiceInterface) was instantiated only once
    # This is implicitly tested if instance1.service is service_instance1,
    # but an explicit check on ConcreteServiceA if it had a counter would be more direct.
    # For now, object identity is sufficient.
    # Create another dependent that also uses ServiceInterface
    class AnotherDependent:
        def __init__(self, service: ServiceInterface):
            self.service = service
    
    injector.bind(AnotherDependent, scope=SingletonScope)
    another_dep_instance = injector.get(AnotherDependent)
    assert another_dep_instance.service is service_instance1, "Service in AnotherDependent should also be the same singleton"
