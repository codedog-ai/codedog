#!/usr/bin/env python
import unittest
import pytest
import sys

if __name__ == "__main__":
    # Run with unittest
    unittest_suite = unittest.defaultTestLoader.discover('tests')
    unittest_result = unittest.TextTestRunner().run(unittest_suite)
    
    # Or run with pytest (recommended)
    pytest_result = pytest.main(["-xvs", "tests"])
    
    # Exit with proper code
    sys.exit(not (unittest_result.wasSuccessful() and pytest_result == 0)) 