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
    
    # Parse command line arguments to check for coverage options
    has_cov_report = any('--cov-report' in arg for arg in sys.argv[1:])
    has_cov = any('--cov=' in arg for arg in sys.argv[1:])
    
    # Run pytest
    args = ["--verbose"]
    
    # Only add default coverage options if not already specified
    if not has_cov:
        args.extend(["--cov=algebras"])
    
    if not has_cov_report:
        args.extend([
            "--cov-report=term",
            "--cov-report=html",
            "--cov-report=xml"
        ])
    
    # Add any command-line arguments
    args.extend(sys.argv[1:])
    
    return pytest.main(args)


if __name__ == "__main__":
    sys.exit(main()) 