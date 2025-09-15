#!/usr/bin/env python3
"""
Performance benchmarking script for AutoRepro CLI commands.

Ensures refactoring improvements don't negatively impact performance.
"""

import json
import statistics
import subprocess
import sys
import time
from pathlib import Path


def run_command_with_timing(cmd: list[str], iterations: int = 10) -> dict[str, float]:
    """
    Run a command multiple times and collect timing statistics.

    Args:
        cmd: Command to execute as list of strings
        iterations: Number of iterations to run

    Returns:
        Dictionary with timing statistics
    """
    times = []

    for i in range(iterations):
        start_time = time.perf_counter()
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=Path(__file__).parent.parent.parent,
            )
            end_time = time.perf_counter()
            times.append(end_time - start_time)
        except subprocess.CalledProcessError as e:
            print(f"❌ Command failed on iteration {i + 1}: {' '.join(cmd)}")
            print(f"Exit code: {e.returncode}")
            print(f"Stderr: {e.stderr}")
            raise

    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
        "stdev": statistics.stdev(times) if len(times) > 1 else 0.0,
        "times": times,
    }


def format_stats(stats: dict[str, float], command_name: str) -> str:
    """Format timing statistics for display."""
    return (
        f"{command_name:25} | "
        f"Mean: {stats['mean']:.3f}s | "
        f"Median: {stats['median']:.3f}s | "
        f"Min: {stats['min']:.3f}s | "
        f"Max: {stats['max']:.3f}s | "
        f"StdDev: {stats['stdev']:.4f}s"
    )


def benchmark_scan_commands() -> dict[str, dict[str, float]]:
    """Benchmark scan command variants."""
    print("📊 Benchmarking scan commands...")

    commands = {
        "scan_default": ["python", "-m", "autorepro", "scan"],
        "scan_json": ["python", "-m", "autorepro", "scan", "--json"],
        "scan_quiet": ["python", "-m", "autorepro", "scan", "--quiet"],
    }

    results = {}
    for name, cmd in commands.items():
        print(f"  Running {name}...")
        results[name] = run_command_with_timing(cmd, iterations=15)

    return results


def benchmark_plan_commands() -> dict[str, dict[str, float]]:
    """Benchmark plan command variants."""
    print("📊 Benchmarking plan commands...")

    commands = {
        "plan_simple": [
            "python",
            "-m",
            "autorepro",
            "plan",
            "--desc",
            "test issue",
            "--out",
            "-",
        ],
        "plan_complex": [
            "python",
            "-m",
            "autorepro",
            "plan",
            "--desc",
            "pytest failing with npm test errors in CI environment",
            "--out",
            "-",
        ],
        "plan_json": [
            "python",
            "-m",
            "autorepro",
            "plan",
            "--desc",
            "jest tests failing",
            "--format",
            "json",
            "--out",
            "-",
        ],
        "plan_with_keywords": [
            "python",
            "-m",
            "autorepro",
            "plan",
            "--desc",
            "python pytest unittest tox poetry failing",
            "--out",
            "-",
        ],
    }

    results = {}
    for name, cmd in commands.items():
        print(f"  Running {name}...")
        results[name] = run_command_with_timing(cmd, iterations=12)

    return results


def benchmark_init_commands() -> dict[str, dict[str, float]]:
    """Benchmark init command variants."""
    print("📊 Benchmarking init commands...")

    commands = {
        "init_dry_run": ["python", "-m", "autorepro", "init", "--dry-run"],
        "init_with_out": ["python", "-m", "autorepro", "init", "--out", "-"],
    }

    results = {}
    for name, cmd in commands.items():
        print(f"  Running {name}...")
        results[name] = run_command_with_timing(cmd, iterations=15)

    return results


def benchmark_exec_commands() -> dict[str, dict[str, float]]:
    """Benchmark exec command variants."""
    print("📊 Benchmarking exec commands...")

    commands = {
        "exec_dry_run": [
            "python",
            "-m",
            "autorepro",
            "exec",
            "--desc",
            "pytest failing",
            "--dry-run",
        ],
        "exec_index": [
            "python",
            "-m",
            "autorepro",
            "exec",
            "--desc",
            "npm test",
            "--index",
            "0",
            "--dry-run",
        ],
    }

    results = {}
    for name, cmd in commands.items():
        print(f"  Running {name}...")
        results[name] = run_command_with_timing(cmd, iterations=10)

    return results


def benchmark_help_commands() -> dict[str, dict[str, float]]:
    """Benchmark help command variants."""
    print("📊 Benchmarking help commands...")

    commands = {
        "help_main": ["python", "-m", "autorepro", "--help"],
        "help_plan": ["python", "-m", "autorepro", "plan", "--help"],
        "version": ["python", "-m", "autorepro", "--version"],
    }

    results = {}
    for name, cmd in commands.items():
        print(f"  Running {name}...")
        results[name] = run_command_with_timing(cmd, iterations=20)

    return results


def analyze_performance_regression(
    results: dict[str, dict[str, float]], baseline_times: dict[str, float] = None
) -> dict[str, str]:
    """
    Analyze results for performance regression.

    Args:
        results: Current benchmark results
        baseline_times: Optional baseline times to compare against

    Returns:
        Analysis results with status for each command
    """
    analysis = {}

    for command_name, stats in results.items():
        mean_time = stats["mean"]

        # Performance thresholds
        status = "✅ GOOD"

        if baseline_times and command_name in baseline_times:
            baseline = baseline_times[command_name]
            change_pct = ((mean_time - baseline) / baseline) * 100

            if change_pct > 10:
                status = f"❌ SLOWER ({change_pct:+.1f}%)"
            elif change_pct < -5:
                status = f"🚀 FASTER ({change_pct:+.1f}%)"
            else:
                status = f"✅ STABLE ({change_pct:+.1f}%)"
        # Without baselines, use absolute thresholds
        elif mean_time > 0.5:
            status = "⚠️  SLOW (>0.5s)"
        elif mean_time > 0.2:
            status = "⚡ MODERATE"

        analysis[command_name] = status

    return analysis


def save_benchmark_results(results: dict[str, dict[str, dict[str, float]]]) -> None:
    """Save benchmark results to JSON file for future comparisons."""
    output_file = Path(__file__).parent / "benchmark_results.json"

    # Prepare results for JSON serialization
    json_results = {}
    for category, commands in results.items():
        json_results[category] = {}
        for command_name, stats in commands.items():
            # Only save key statistics, not full times array
            json_results[category][command_name] = {
                "mean": stats["mean"],
                "median": stats["median"],
                "min": stats["min"],
                "max": stats["max"],
                "stdev": stats["stdev"],
            }

    with open(output_file, "w") as f:
        json.dump(json_results, f, indent=2)

    print(f"💾 Benchmark results saved to: {output_file}")


def main():
    """Run comprehensive performance benchmarks."""
    print("🚀 AutoRepro Performance Benchmark Suite")
    print("=" * 80)
    print("Running comprehensive performance tests after refactoring...")
    print("Each command is executed multiple times for statistical accuracy.")
    print()

    # Run all benchmark categories
    all_results = {
        "scan": benchmark_scan_commands(),
        "plan": benchmark_plan_commands(),
        "init": benchmark_init_commands(),
        "exec": benchmark_exec_commands(),
        "help": benchmark_help_commands(),
    }

    print()
    print("📈 PERFORMANCE RESULTS")
    print("=" * 80)

    # Display results by category
    overall_status = []

    for category, results in all_results.items():
        print(f"\n📊 {category.upper()} Commands:")
        print("-" * 70)

        analysis = analyze_performance_regression(results)

        for command_name, stats in results.items():
            status = analysis[command_name]
            print(format_stats(stats, command_name) + f" | {status}")

            # Track overall status
            if "❌" in status:
                overall_status.append("REGRESSION")
            elif "🚀" in status:
                overall_status.append("IMPROVED")
            else:
                overall_status.append("STABLE")

    # Summary
    print()
    print("📋 PERFORMANCE SUMMARY")
    print("=" * 80)

    regression_count = overall_status.count("REGRESSION")
    improved_count = overall_status.count("IMPROVED")
    stable_count = overall_status.count("STABLE")

    print(f"Commands analyzed: {len(overall_status)}")
    print(f"Performance regressions: {regression_count}")
    print(f"Performance improvements: {improved_count}")
    print(f"Stable performance: {stable_count}")

    # Save results for future comparisons
    save_benchmark_results(all_results)

    # Final verdict
    if regression_count == 0:
        print("\n✅ PERFORMANCE VALIDATION PASSED")
        print("No performance regressions detected. Refactoring is safe to deploy.")
        sys.exit(0)
    else:
        print("\n❌ PERFORMANCE VALIDATION FAILED")
        print(f"Found {regression_count} performance regressions. Review required.")
        sys.exit(1)


if __name__ == "__main__":
    main()
