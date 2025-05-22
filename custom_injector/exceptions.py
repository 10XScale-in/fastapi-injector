class DIError(Exception):
    """Base class for all dependency injection errors."""
    pass

class BindingError(DIError):
    """Error during binding registration."""
    pass

class ResolutionError(DIError):
    """Error during dependency resolution."""
    pass

class CircularDependencyError(ResolutionError):
    """Circular dependency detected."""
    pass
