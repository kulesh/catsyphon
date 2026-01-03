#!/usr/bin/env python3
"""
Test script to verify startup checks work correctly.

Run this to test startup validation without starting the full server.
"""

import sys

sys.path.insert(0, "src")

from catsyphon.startup import run_all_startup_checks

if __name__ == "__main__":
    print("\n🧪 Testing startup checks...\n")
    try:
        run_all_startup_checks()
        print("\n✅ All checks passed! Backend is ready to start.\n")
    except SystemExit as e:
        print(f"\n❌ Startup checks failed (exit code: {e.code})\n")
        sys.exit(e.code)
