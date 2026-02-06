# Testing Guide for Church Funds System Backend

## Overview

This document provides comprehensive guidance on testing the church funds system backend. We use a combination of **Test-Driven Development (TDD)** and **Behavior-Driven Development (BDD)** approaches to ensure code quality and reliability.

## Testing Stack

- **pytest**: Main testing framework
- **pytest-django**: Django integration for pytest
- **pytest-cov**: Code coverage reporting
- **pytest-bdd**: BDD scenario testing
- **factory-boy**: Test data factories
- **faker**: Realistic fake data generation
- **responses**: HTTP request mocking
- **freezegun**: Time mocking

## Test Structure

```
tests/
├── unit/                      # Unit tests for models and services
│   ├── test_models_*.py      # Model tests
│   └── test_*_service.py     # Service tests
├── integration/               # Integration tests for API
│   ├── test_*_mutations.py   # GraphQL mutation tests
│   └── test_*_queries.py     # GraphQL query tests
├── features/                  # BDD scenario tests
│   ├── *.feature             # Gherkin feature files
│   └── step_defs/            # Step definitions
└── utils/                     # Test utilities
    ├── factories.py          # Model factories
    ├── mocks.py              # API mocks
    └── graphql_helpers.py    # GraphQL test helpers
```

## Running Tests

### Run All Tests
```bash
cd /home/md/Tweny5/Kawangware/church-funds-system/church_BE
python -m pytest
```

### Run Specific Test Categories
```bash
# Unit tests only
python -m pytest tests/unit/

# Integration tests only
python -m pytest tests/integration/

# BDD tests only
python -m pytest tests/features/

# Tests with specific marker
python -m pytest -m unit
python -m pytest -m mpesa
python -m pytest -m sms
```

### Run Specific Test Files
```bash
python -m pytest tests/unit/test_models_member.py
python -m pytest tests/unit/test_mpesa_service.py
```

### Run with Coverage
```bash
# Generate coverage report
python -m pytest --cov=. --cov-report=html --cov-report=term

# View HTML coverage report
open htmlcov/index.html  # or xdg-open on Linux
```

### Run Tests in Verbose Mode
```bash
python -m pytest -v
```

### Run Tests and Stop on First Failure
```bash
python -m pytest -x
```

## Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.bdd` - BDD scenario tests
- `@pytest.mark.mpesa` - M-Pesa related tests
- `@pytest.mark.sms` - SMS related tests
- `@pytest.mark.slow` - Slow running tests

## Writing Tests

### Unit Test Example

```python
import pytest
from tests.utils.factories import MemberFactory

@pytest.mark.unit
class TestMemberModel:
    def test_create_member(self, db):
        """Test creating a member with valid data."""
        member = MemberFactory(
            first_name='John',
            last_name='Doe'
        )

        assert member.full_name == 'John Doe'
```

### Service Test with Mocking

```python
import pytest
import responses
from tests.utils.mocks import setup_mpesa_mocks

@pytest.mark.unit
@pytest.mark.mpesa
class TestMpesaService:
    @responses.activate
    def test_initiate_stk_push(self, db):
        """Test STK push initiation."""
        setup_mpesa_mocks(responses, scenario='success')

        # Your test code here
```

### Integration Test Example

```python
import pytest
from tests.utils.graphql_helpers import GraphQLClient, MUTATIONS

@pytest.mark.integration
class TestContributionMutations:
    def test_initiate_contribution(self, db, active_categories):
        """Test contribution mutation."""
        client = GraphQLClient()

        response = client.mutate(
            MUTATIONS['initiate_contribution'],
            variables={
                'phoneNumber': '254712345678',
                'amount': '1000.00',
                'categoryId': str(active_categories[0].id)
            }
        )

        client.assert_no_errors(response)
```

## Fixtures

Common fixtures are defined in `conftest.py`:

- `api_client` - Django test client
- `graphql_client` - GraphQL test helper
- `sample_member` - Test member
- `guest_member` - Guest member
- `active_categories` - Active contribution categories
- `mock_mpesa_api` - Mocked M-Pesa API
- `mock_sms_api` - Mocked SMS API

## Test Database

Tests use a separate PostgreSQL test database that is automatically created and destroyed. The database is configured in `conftest.py`.

**Important**: Tests use `--reuse-db` flag to speed up test runs by reusing the test database between runs.

## Mocking External APIs

### M-Pesa API Mocking

```python
import responses
from tests.utils.mocks import setup_mpesa_mocks

@responses.activate
def test_mpesa_integration():
    setup_mpesa_mocks(responses, scenario='success')
    # Your test code
```

### SMS API Mocking

```python
import responses
from tests.utils.mocks import setup_sms_mocks

@responses.activate
def test_sms_sending():
    setup_sms_mocks(responses, scenario='success')
    # Your test code
```

## Code Coverage Goals

- **Overall Coverage**: > 80%
- **Critical Paths** (models, services, mutations): > 90%
- **Edge Cases**: All error paths tested

## Best Practices

1. **Isolation**: Each test should be independent
2. **Clarity**: Test names should describe what they test
3. **Arrange-Act-Assert**: Follow AAA pattern
4. **Mock External Services**: Never make real API calls
5. **Use Factories**: Use factory_boy for test data
6. **Test Edge Cases**: Test both success and failure scenarios
7. **Keep Tests Fast**: Use `--nomigrations` flag

## Continuous Integration

Tests should run on every commit. Configure your CI/CD pipeline to:

1. Install dependencies
2. Run migrations on test database
3. Run all tests with coverage
4. Fail build if tests fail or coverage drops

Example CI command:
```bash
python -m pytest --cov=. --cov-report=term --cov-fail-under=80
```

## Debugging Failed Tests

### View Detailed Output
```bash
python -m pytest -vv
```

### Show Print Statements
```bash
python -m pytest -s
```

### Run Specific Test
```bash
python -m pytest tests/unit/test_models_member.py::TestMemberModel::test_create_member
```

### Use pytest debugger
```bash
python -m pytest --pdb  # Drop into debugger on failure
```

## Common Issues

### Database Errors
- Ensure PostgreSQL is running
- Check database credentials in `.env`
- Run migrations: `python manage.py migrate`

### Import Errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check PYTHONPATH includes project root

### Mock Not Working
- Ensure `@responses.activate` decorator is used
- Check URL matches exactly (including trailing slashes)

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-django documentation](https://pytest-django.readthedocs.io/)
- [factory_boy documentation](https://factoryboy.readthedocs.io/)
- [responses documentation](https://github.com/getsentry/responses)

## Support

For questions or issues with tests, please:
1. Check this documentation
2. Review existing tests for examples
3. Check test output for specific error messages
