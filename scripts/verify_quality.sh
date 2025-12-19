#!/bin/bash
set -e

echo "Starting Quality Verification Pipeline..."

# Detect environment
if [ -f /.dockerenv ]; then
    echo "Running inside Docker, using system-wide commands..."
    PYTEST="pytest"
    PYLINT="pylint"
elif [ -d "graph_env" ]; then
    echo "Using local virtualenv (graph_env)..."
    PYTEST="./graph_env/bin/pytest"
    PYLINT="./graph_env/bin/pylint"
else
    echo "No virtualenv found, using system-wide commands..."
    PYTEST="pytest"
    PYLINT="pylint"
fi


# 1. Run Unit Tests
echo "Running unit tests..."
PYTHONPATH=. $PYTEST tests/test_api.py

# 2. Run Integration Tests
echo "Running integration tests..."
PYTHONPATH=. $PYTEST tests/test_integration.py

# 3. Run Pylint
echo "Running Pylint check (Target > 9.5)..."
PYTHONPATH=. $PYLINT app

echo "All checks passed! The codebase is healthy."

