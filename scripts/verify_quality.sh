#!/bin/bash
set -e

echo "Starting Quality Verification Pipeline..."

# Detect environment
if [ -f /.dockerenv ]; then
    echo "Running inside Docker, using system-wide commands..."
    PYTEST="pytest"
    PYLINT="pylint"
elif [ -x "./graph_env/bin/pytest" ] && [ -x "./graph_env/bin/pylint" ]; then
    echo "Using local virtualenv (graph_env)..."
    PYTEST="./graph_env/bin/pytest"
    PYLINT="./graph_env/bin/pylint"
else
    echo "graph_env missing or incomplete, falling back to system-wide commands..."
    PYTEST="pytest"
    PYLINT="pylint"
fi


# 1. Run Unit Tests
echo "Running unit tests with coverage..."
PYTHONPATH=. $PYTEST --cov=app --cov-report=term-missing tests/test_api.py tests/test_utils.py tests/test_analytics.py tests/test_quantitative.py tests/test_services.py

# 2. Run Integration Tests
echo "Running integration tests..."
# We append coverage to the same .coverage file
PYTHONPATH=. $PYTEST --cov=app --cov-append --cov-report=term-missing tests/test_integration.py

# 3. Run Pylint
echo "Running Pylint check (Target > 9.5)..."
PYTHONPATH=. $PYLINT app

echo "All checks passed! The codebase is healthy."

