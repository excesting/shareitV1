#!/usr/bin/env python3
"""
Test script to verify the Inventory Management System setup
"""

import sys
import os

def test_imports():
    """Test if all required modules can be imported"""
    print("Testing imports...")
    
    try:
        import flask
        print("✓ Flask imported successfully")
    except ImportError as e:
        print(f"✗ Flask import failed: {e}")
        return False
    
    try:
        import pandas as pd
        print("✓ Pandas imported successfully")
    except ImportError as e:
        print(f"✗ Pandas import failed: {e}")
        return False
    
    try:
        import numpy as np
        print("✓ NumPy imported successfully")
    except ImportError as e:
        print(f"✗ NumPy import failed: {e}")
        return False
    
    try:
        import matplotlib.pyplot as plt
        print("✓ Matplotlib imported successfully")
    except ImportError as e:
        print(f"✗ Matplotlib import failed: {e}")
        return False
    
    try:
        from sklearn.preprocessing import MinMaxScaler
        print("✓ Scikit-learn imported successfully")
    except ImportError as e:
        print(f"✗ Scikit-learn import failed: {e}")
        return False
    
    return True

def test_data_file():
    """Test if data file exists and can be read"""
    print("\nTesting data file...")
    
    data_path = 'data_set/data.csv'
    if not os.path.exists(data_path):
        print(f"✗ Data file not found: {data_path}")
        return False
    
    try:
        import pandas as pd
        df = pd.read_csv(data_path)
        print(f"✓ Data file loaded successfully: {len(df)} rows, {len(df.columns)} columns")
        print(f"  Columns: {list(df.columns)}")
        return True
    except Exception as e:
        print(f"✗ Error reading data file: {e}")
        return False

def test_model_file():
    """Test if model file exists"""
    print("\nTesting model file...")
    
    model_path = 'trained_model.pkl'
    if os.path.exists(model_path):
        print(f"✓ Model file found: {model_path}")
        return True
    else:
        print(f"⚠ Model file not found: {model_path}")
        print("  You can train a model through the web interface")
        return True

def test_flask_app():
    """Test if Flask app can be created"""
    print("\nTesting Flask app...")
    
    try:
        from app import app
        print("✓ Flask app created successfully")
        return True
    except Exception as e:
        print(f"✗ Flask app creation failed: {e}")
        return False

def main():
    """Main test function"""
    print("Inventory Management System - Setup Test")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_data_file,
        test_model_file,
        test_flask_app
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed! The system is ready to run.")
        print("\nTo start the application, run:")
        print("  py run.py")
        print("  or")
        print("  start.bat")
    else:
        print("✗ Some tests failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 