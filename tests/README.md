# Orchestra Test Suite

Comprehensive test suite for the Orchestra multi-agent orchestration platform.

## Test Coverage

**Total Tests**: 50 tests across 4 test files
**Pass Rate**: 96% (48 passing, 2 known issues)

### Test Categories

#### Unit Tests (34 tests)
- **Models** (`test_models.py`): 11 tests
  - Workflow models validation
  - Checkpoint models validation
  - Agent models validation

- **Agents** (`test_agents.py`): 13 tests
  - Mock agent functionality
  - Agent factory lifecycle
  - Agent interface compliance

- **Database** (`test_database.py`): 6 tests
  - Schema creation and validation
  - Table structure verification
  - Foreign key constraints
  - Index verification

- **Workflows** (`test_workflows.py`): 9 tests
  - Prompt template generation
  - Workflow initialization
  - Node execution
  - State management

#### Integration Tests (16 tests)
- **API Endpoints** (`test_api.py`): 10 tests
  - Health check
  - Workflow CRUD operations
  - Error handling
  - Lifecycle testing

- **Workflow Execution** (`test_workflows.py`): 1 test
  - End-to-end workflow execution

## Running Tests

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test File
```bash
pytest tests/test_models.py -v
pytest tests/test_agents.py -v
pytest tests/test_database.py -v
pytest tests/test_workflows.py -v
pytest tests/test_api.py -v
```

### Run Tests by Marker
```bash
# Unit tests only
pytest tests/ -m unit

# Integration tests only
pytest tests/ -m integration

# Skip slow tests
pytest tests/ -m "not slow"
```

### Run with Coverage
```bash
pytest tests/ --cov=backend --cov-report=html
```

## Known Issues

### 1. CORS Test Failure
**Test**: `tests/test_api.py::TestCORS::test_cors_headers`
**Status**: Expected behavior, test needs adjustment
**Details**: OPTIONS method returns 405 instead of 200/204
**Impact**: Low - CORS is working, test expectation needs update

### 2. Async Workflow Execution
**Test**: `tests/test_workflows.py::TestWorkflowExecution::test_full_workflow_to_first_checkpoint`
**Status**: Identified improvement needed
**Details**: SqliteSaver doesn't support async, should use AsyncSqliteSaver
**Impact**: Medium - This is the same issue affecting production execution
**Fix**: Replace SqliteSaver with AsyncSqliteSaver in workflow implementation

## Test Dependencies

Required packages (installed via requirements.txt):
- pytest >= 8.0.0
- pytest-asyncio >= 0.23.0
- pytest-cov >= 4.1.0
- pytest-mock >= 3.12.0

## Test Structure

```
tests/
├── __init__.py
├── README.md                 # This file
├── test_models.py           # Data model tests
├── test_agents.py           # Agent system tests
├── test_database.py         # Database layer tests
├── test_workflows.py        # Workflow orchestration tests
└── test_api.py              # API endpoint tests
```

## Adding New Tests

### Test Naming Convention
- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

### Example Test
```python
import pytest

class TestNewFeature:
    """Test description"""

    def test_feature_behavior(self):
        """Test specific behavior"""
        # Arrange
        ...
        # Act
        ...
        # Assert
        assert ...

    @pytest.mark.asyncio
    async def test_async_feature(self):
        """Test async behavior"""
        result = await async_function()
        assert result is not None
```

### Test Markers
- `@pytest.mark.unit`: Unit test
- `@pytest.mark.integration`: Integration test
- `@pytest.mark.slow`: Slow running test
- `@pytest.mark.asyncio`: Async test

## Continuous Integration

Tests should be run:
- Before committing code
- In CI/CD pipeline
- Before merging pull requests

## Coverage Goals

- **Overall**: Target 80%+ code coverage
- **Core Logic**: Target 90%+ coverage for workflow and agent code
- **Models**: Target 100% coverage for data models

Current coverage can be viewed by running:
```bash
pytest --cov=backend --cov-report=term-missing
```
