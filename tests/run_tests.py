#!/usr/bin/env python
"""
Run all tests for Algebras CLI
"""

import os
import sys
import pytest


def main():
    """Run all tests."""
    # Add the project root to the Python path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    
    # Run pytest
    args = [
        "--verbose",
        "--cov=algebras",
        "--cov-report=term",
        "--cov-report=html"
    ]
    
    # Add any command-line arguments
    args.extend(sys.argv[1:])
    
    return pytest.main(args)


if __name__ == "__main__":
    sys.exit(main()) 