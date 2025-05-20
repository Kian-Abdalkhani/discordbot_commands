import pytest
import asyncio

# Helper function to run async tests
def run_async(coro):
    """Run an async coroutine and return its result."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)

# Enable asyncio tests
def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as an asyncio test")

# Define a fixture to handle asyncio event loops
@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
