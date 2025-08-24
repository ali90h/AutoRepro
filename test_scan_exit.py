#!/usr/bin/env python3
"""Test script to verify scan exit codes."""

import os
import subprocess
import sys
import tempfile


def test_scan_exit_code():
    """Test that scan command returns exit code 0."""
    print("Testing scan exit codes...")

    # Test 1: Scan in current directory (should have python files)
    result1 = subprocess.run(
        [sys.executable, "-m", "autorepro", "scan"], capture_output=True, text=True
    )
    print(f"Current directory scan - Exit code: {result1.returncode}")
    print(f"Output: {result1.stdout.strip()}")
    if result1.stderr:
        print(f"Stderr: {result1.stderr.strip()}")

    # Test 2: Scan in empty directory
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        result2 = subprocess.run(
            [sys.executable, "-m", "autorepro", "scan"], capture_output=True, text=True
        )
        print(f"Empty directory scan - Exit code: {result2.returncode}")
        print(f"Output: {result2.stdout.strip()}")
        if result2.stderr:
            print(f"Stderr: {result2.stderr.strip()}")

    # Test 3: Direct CLI module call
    result3 = subprocess.run(
        [sys.executable, "-m", "autorepro.cli", "scan"], capture_output=True, text=True
    )
    print(f"Direct CLI module scan - Exit code: {result3.returncode}")
    print(f"Output: {result3.stdout.strip()}")
    if result3.stderr:
        print(f"Stderr: {result3.stderr.strip()}")

    # Summary
    all_zero = all(r.returncode == 0 for r in [result1, result2, result3])
    print(f"\nAll scan commands returned exit code 0: {all_zero}")

    return all_zero


if __name__ == "__main__":
    success = test_scan_exit_code()
    sys.exit(0 if success else 1)
