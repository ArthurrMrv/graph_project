#!/bin/bash
set -e

echo "Starting Quality Verification Pipeline..."

# 1. Run Unit Tests
echo "Running unit tests..."
PYTHONPATH=. ./graph_env/bin/pytest tests/test_api.py

# 2. Run Integration Tests
echo "Running integration tests..."
PYTHONPATH=. ./graph_env/bin/pytest tests/test_integration.py

# 3. Run Pylint
echo "Running Pylint check (Target > 9.5)..."
PYTHONPATH=. ./graph_env/bin/pylint app

echo "All checks passed! The codebase is healthy."
