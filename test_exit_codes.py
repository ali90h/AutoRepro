#!/usr/bin/env python3
"""Test exit codes for scan command."""

import subprocess
import sys
import tempfile

# Test scan in current directory
print("=== Test 1: Scan in current directory ===")
result = subprocess.run([sys.executable, "-m", "autorepro", "scan"], capture_output=True, text=True)
print(f"Exit code: {result.returncode}")
print(f"Stdout: {result.stdout.strip()}")
if result.stderr:
    print(f"Stderr: {result.stderr.strip()}")

# Test scan in empty directory
print("\n=== Test 2: Scan in empty directory ===")
with tempfile.TemporaryDirectory() as tmpdir:
    result = subprocess.run(
        [sys.executable, "-m", "autorepro", "scan"],
        cwd=tmpdir,
        capture_output=True,
        text=True,
    )
    print(f"Exit code: {result.returncode}")
    print(f"Stdout: {result.stdout.strip()}")
    if result.stderr:
        print(f"Stderr: {result.stderr.strip()}")

# Test direct function call
print("\n=== Test 3: Direct function call ===")
try:
    from autorepro.cli import cmd_scan

    exit_code = cmd_scan()
    print(f"Direct call exit code: {exit_code}")
except Exception as e:
    print(f"Direct call error: {e}")

print("\n=== Summary ===")
print("Scan command should always return exit code 0")
