#!/bin/bash
# CI barrier script: Check Python files for size limit violations
# Fails if any .py file exceeds the maximum lines of code limit

set -euo pipefail

# Maximum lines of code allowed per file
MAX_LOC=${1:-500}

echo "Checking Python files for size violations (max: ${MAX_LOC} LOC)..."

# Find all Python files and check their line counts
violations=$(git ls-files '*.py' | xargs wc -l | awk -v max="$MAX_LOC" '$1 > max {print $2 ": " $1 " lines"}')

if [ -n "$violations" ]; then
    echo "❌ Files over ${MAX_LOC} LOC found:"
    echo "$violations"
    echo ""
    echo "Please refactor these files to stay within the ${MAX_LOC} line limit."
    echo "This helps maintain code readability and testability."
    exit 1
else
    echo "✅ All Python files are within the ${MAX_LOC} line limit."
fi
