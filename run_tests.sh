#!/bin/bash
# Ensure OPENAI_API_KEY is set to a dummy value if tests need it for module loading
export OPENAI_API_KEY="dummy_test_key"

# Discover and run tests using unittest module
# This assumes tests are in files named test_*.py in the current directory or subdirectories
# and that the project root (where 'brd' and 'tests' are) is the current directory.
# To ensure 'brd' package is found, run from project root.
echo "Running unit tests..."
python -m unittest discover -s tests -p "test_*.py"

# If you prefer pytest:
# pip install pytest
# pytest
