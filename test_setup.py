#!/usr/bin/env python3
"""
Simple test script to verify the dashboard setup
"""

import os
import json
import subprocess
import sys

def test_file_structure():
    """Test if all required files exist"""
    required_files = [
        'app.py',
        'requirements.txt',
        'Dockerfile',
        'nixpacks.toml',
        'templates/dashboard.html',
        'templates/error.html',
        'update_data.py',
        'setup_cron.sh'
    ]

    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)

    if missing_files:
        print(f"❌ Missing files: {', '.join(missing_files)}")
        return False
    else:
        print("✅ All required files present")
        return True

def test_data_structure():
    """Test if data file has correct structure"""
    data_files = [
        'lounge_thread_filtered_comments.json',
        'data/lounge_thread_filtered_comments.json'
    ]

    for data_file in data_files:
        if os.path.exists(data_file):
            try:
                with open(data_file, 'r') as f:
                    data = json.load(f)

                if isinstance(data, list) and len(data) > 0:
                    first_item = data[0]
                    required_keys = ['id', 'body', 'author', 'score', 'tickers']

                    if all(key in first_item for key in required_keys):
                        print(f"✅ Data file valid: {data_file} ({len(data)} records)")
                        return True
                    else:
                        print(f"❌ Data file missing required keys: {data_file}")
                        return False

            except json.JSONDecodeError:
                print(f"❌ Invalid JSON in data file: {data_file}")
                return False

    print("⚠️  No data file found - you'll need to add your Reddit data")
    return True  # Not critical for initial setup

def test_dependencies():
    """Test if all dependencies can be imported"""
    try:
        import flask
        import pandas
        print("✅ Core dependencies available")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Reddit Dashboard Setup")
    print("=" * 40)

    tests = [
        test_file_structure,
        test_data_structure,
        test_dependencies
    ]

    results = []
    for test in tests:
        results.append(test())
        print()

    if all(results):
        print("🎉 All tests passed! Ready for deployment.")
        print("Next steps:")
        print("1. Add your reddit_scrapper.py and tickers.json")
        print("2. Add your Reddit data file")
        print("3. Configure .env with API credentials")
        print("4. Test locally: python app.py")
        print("5. Deploy to Coolify")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
