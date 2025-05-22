# FastAPI Injector

A powerful dependency injection integration for FastAPI and Taskiq applications, now featuring a self-contained dependency injection core designed for robustness and flexibility.

## Features

- Seamless integration with FastAPI and Taskiq
- Support for both synchronous and asynchronous dependencies
- Request-scoped dependency management
- Clean separation of concerns through dependency injection
- Resource cleanup for context-managed dependencies
- Easy testing support with dependency overrides

## Installation

```bash
pip install git+https://github.com/10XScale-in/fastapi-injector.git
```

## Quick Start

### FastAPI Integration

```python
from fastapi import FastAPI, Body
from fastapi_injector import attach_injector, Injected
from custom_injector.core import Injector # Updated import
from custom_injector.scopes import SingletonScope # Added for example
from typing import Annotated
import abc # Added for UserRepository example

# Define your interfaces and implementations
# Example User class (add for context if needed)
class User:
    def __init__(self, name: str):
        self.name = name
class UserRepository(abc.ABC):
    @abc.abstractmethod
    async def save_user(self, user: User) -> None:
        pass

class PostgresUserRepository(UserRepository):
    async def save_user(self, user: User) -> None:
        # Implementation details
        pass

# Create and configure your FastAPI application
app = FastAPI()
injector = Injector()
# injector.binder.bind(UserRepository, to=PostgresUserRepository) # Old way
injector.bind(UserRepository, to_class=PostgresUserRepository, scope=SingletonScope) # New way
attach_injector(app, injector)

# Use injection in your routes
@app.post("/users")
async def create_user(
    data: Annotated[dict, Body()],
    repo: UserRepository = Injected(UserRepository)
):
    await repo.save_user(data)
    return {"status": "success"}
```

### Taskiq Integration

```python
from taskiq import TaskiqState, Context # Assuming TaskiqBroker is defined elsewhere
from fastapi_injector import attach_injector_taskiq, InjectedTaskiq
from custom_injector.core import Injector # Updated import
from custom_injector.scopes import SingletonScope # Added for example
import abc # Added for UserRepository example

# Example User class (add for context if needed)
class User:
    def __init__(self, name: str):
        self.name = name

# Define your interfaces and implementations (assuming from FastAPI example)
class UserRepository(abc.ABC):
    @abc.abstractmethod
    async def save_user(self, user: User) -> None:
        pass

class PostgresUserRepository(UserRepository):
    async def save_user(self, user: User) -> None:
        # Implementation details
        print(f"Saving user {user.name} to Postgres")
        pass


# Initialize Taskiq broker and state
# broker = TaskiqBroker() # Assuming broker is defined
state = TaskiqState()

# Configure injection
injector = Injector()
# injector.binder.bind(UserRepository, to=PostgresUserRepository) # Old way
injector.bind(UserRepository, to_class=PostgresUserRepository, scope=SingletonScope) # New way
attach_injector_taskiq(state, injector)

# Use injection in your tasks
@broker.task
async def process_user(
    user_id: int,
    repo: UserRepository = InjectedTaskiq(UserRepository)
):
    # Task implementation
    pass
```

## Request Scope

Enable request-scoped dependencies for better resource management:

```python
from fastapi_injector import InjectorMiddleware, RequestScope, RequestScopeOptions # Updated import
from custom_injector.core import Injector # Ensure Injector is imported if used in a standalone example
# Assuming app and injector are already defined as in Quick Start
# from custom_injector.scopes import SingletonScope # Not needed if RequestScope is the focus

# Example Connection classes (add for context)
class DatabaseConnection:
    def query(self, sql: str):
        print(f"Executing query: {sql} with {self}")
        return "some_data"

class PostgresConnection(DatabaseConnection):
    def __init__(self):
        print(f"PostgresConnection {id(self)} created")
    # Add __enter__ and __exit__ if enable_cleanup=True has effect
    def __enter__(self):
        print(f"PostgresConnection {id(self)} entered")
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        print(f"PostgresConnection {id(self)} exited")


# Configure request scope
# app = FastAPI() # Assuming app is defined
# injector = Injector() # Assuming injector is defined
options = RequestScopeOptions(enable_cleanup=True)
app.add_middleware(InjectorMiddleware, injector=injector) # This should be before attach_injector if RequestScope itself is bound by attach_injector
attach_injector(app, injector, options) # attach_injector also binds RequestScope, RequestScopeFactory and RequestScopeOptions

# Bind with request scope
# injector.binder.bind(DatabaseConnection, to=PostgresConnection, scope=request_scope) # Old way
injector.bind(DatabaseConnection, to_class=PostgresConnection, scope=RequestScope) # New way
```

## Synchronous Dependencies

Use `SyncInjected` for synchronous dependencies in FastAPI:

```python
from fastapi_injector import SyncInjected

@app.get("/sync-endpoint")
def get_data(service: SyncService = SyncInjected(SyncService)):
    return service.process()
```

Or `SyncInjectedTaskiq` for Taskiq:

```python
@broker.task
def sync_task(service: SyncService = SyncInjectedTaskiq(SyncService)):
    return service.process()
```

## Testing

Override dependencies in your tests:

```python
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def test_app():
    from custom_injector.core import Injector # Updated import
    from custom_injector.scopes import SingletonScope # Added for example
    # Assuming UserRepository and MockUserRepository are defined
    # class UserRepository(abc.ABC): ...
    # class MockUserRepository(UserRepository): ...

    injector = Injector()
    # injector.binder.bind(UserRepository, to=MockUserRepository) # Old way
    injector.bind(UserRepository, to_class=MockUserRepository, scope=SingletonScope) # New way
    app = FastAPI()
    attach_injector(app, injector)
    return app

def test_create_user(test_app):
    client = TestClient(test_app)
    response = client.post("/users", json={"name": "Test User"})
    assert response.status_code == 200
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the BSD License - see the LICENSE file for details.
