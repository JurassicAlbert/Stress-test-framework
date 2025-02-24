#!/usr/bin/env python3
"""
playwright_login_test.py

This script runs a login test repeatedly using Playwright (Python) and records Prometheus metrics.
It measures:
  - The number of tests that passed/failed.
  - For positive tests (with valid credentials), if the test duration exceeds a threshold (e.g., 4000 ms),
    it counts that as a performance issue.
  - For negative tests (with invalid credentials), if the test either passes unexpectedly or runs too quickly
    (< 1000 ms), it counts that as a performance issue.

At the end of the run, it pushes all metrics to a Prometheus Pushgateway.

Note: This version never throws an exception or terminates the process with a nonzero exit code.
It always completes the test loop and pushes metrics.
"""

import os
import time
from playwright.sync_api import sync_playwright
from prometheus_client import CollectorRegistry, Counter, push_to_gateway
from colorama import init

# Initialize colorama (minimal logging; no colored output is printed to speed up execution)
init(autoreset=True)

# Retrieve configuration from environment variables
NUM_TESTS = int(os.getenv("NUM_TESTS", 1))
LOGIN = os.getenv("LOGIN", "student")
PASSWORD = os.getenv("PASSWORD", "Password123")  # Correct credentials: "student"/"Password123"
PUSHGATEWAY_ADDRESS = os.getenv("PUSHGATEWAY_ADDRESS", "localhost:9091")

# Set up Prometheus registry (do not collect default metrics)
registry = CollectorRegistry()

# Define counters for test outcomes
TEST_SUCCESS_COUNTER = Counter(
    "playwright_test_success_total",
    "Total number of successful Playwright tests",
    registry=registry
)
TEST_FAILURE_COUNTER = Counter(
    "playwright_test_failure_total",
    "Total number of failed Playwright tests",
    registry=registry
)

# Define additional counters for performance issues:
# For positive tests: if the duration exceeds the threshold (e.g., 4000 ms)
PERFORMANCE_POSITIVE_COUNTER = Counter(
    "playwright_positive_performance_failures_total",
    "Total number of positive tests that exceeded the expected duration threshold",
    registry=registry
)
# For negative tests: if a test either passes unexpectedly or runs too quickly (< 1000 ms)
PERFORMANCE_NEGATIVE_COUNTER = Counter(
    "playwright_negative_performance_unexpected_pass_total",
    "Total number of negative tests that unexpectedly passed or had very short duration",
    registry=registry
)


def push_metrics():
    """
    Push the collected metrics to the Prometheus Pushgateway.
    Any push errors are silently ignored.
    """
    try:
        push_to_gateway(PUSHGATEWAY_ADDRESS, job="playwright_tests", registry=registry)
    except Exception:
        pass


def run_login_test():
    """
    Runs the login test repeatedly using Playwright. In the positive scenario (valid credentials),
    it verifies that the user is redirected correctly, sees a success message, and can log out.
    In the negative scenario, it verifies that the login fails and the expected error message is displayed.
    Performance issues are recorded based on test duration.

    This function does not throw exceptions or exit with nonzero codes; it simply records failures in metrics.
    """
    positive_perf_issues = 0
    negative_perf_issues = 0
    overall_start = time.time() * 1000  # Start time in ms
    failures = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for i in range(NUM_TESTS):
            iteration_start = time.time() * 1000  # in ms
            try:
                page.goto("https://practicetestautomation.com/practice-test-login/")
                page.fill("#username", LOGIN)
                page.fill("#password", PASSWORD)
                page.click("#submit")
                time.sleep(0.2)
                current_url = page.url

                if LOGIN == "student" and PASSWORD == "Password123":
                    # Positive scenario
                    if "logged-in-successfully" not in current_url:
                        TEST_FAILURE_COUNTER.inc()
                        failures.append(f"Iteration {i + 1}: Expected redirection but got URL: {current_url}")
                    else:
                        content = page.content()
                        if not ("Logged In Successfully" in content or "Congratulations" in content):
                            TEST_FAILURE_COUNTER.inc()
                            failures.append(f"Iteration {i + 1}: Success message missing.")
                        else:
                            page.click("text=Log out")
                            time.sleep(0.2)
                            if "practice-test-login" not in page.url:
                                TEST_FAILURE_COUNTER.inc()
                                failures.append(f"Iteration {i + 1}: Failed to return to login page after logout.")
                            else:
                                TEST_SUCCESS_COUNTER.inc()
                    duration = time.time() * 1000 - iteration_start
                    if duration > 4000:
                        positive_perf_issues += 1
                else:
                    # Negative scenario
                    if "logged-in-successfully" in current_url:
                        TEST_FAILURE_COUNTER.inc()
                        failures.append(f"Iteration {i + 1}: Unexpected login with invalid credentials.")
                        page.click("text=Log out")
                    else:
                        error_text = page.text_content("#error")
                        if error_text and (
                                "Your username is invalid!" in error_text or "Your password is invalid!" in error_text):
                            TEST_SUCCESS_COUNTER.inc()
                        else:
                            TEST_FAILURE_COUNTER.inc()
                            failures.append(f"Iteration {i + 1}: Unexpected error message: {error_text}")
                        duration = time.time() * 1000 - iteration_start
                        if duration < 1000:
                            negative_perf_issues += 1
            except Exception as e:
                TEST_FAILURE_COUNTER.inc()
                failures.append(f"Iteration {i + 1}: Exception occurred: {e}")

        PERFORMANCE_POSITIVE_COUNTER.inc(positive_perf_issues)
        PERFORMANCE_NEGATIVE_COUNTER.inc(negative_perf_issues)
        overall_duration = time.time() * 1000 - overall_start
        push_metrics()
        browser.close()


if __name__ == "__main__":
    run_login_test()
