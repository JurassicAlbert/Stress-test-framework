#!/usr/bin/env python3
"""
playwright_login_test.py
Zmodyfikowany tak, aby:
  - Na koniec generować plik z metrykami (jeśli podano --export-metrics),
  - NIE pushować metryk bezpośrednio do Pushgateway,
  - Zamiast tego pozwala pipeline'owi wykonać curl na gotowy plik.
"""

import os
import sys
import time
import argparse
from playwright.sync_api import sync_playwright
from prometheus_client import CollectorRegistry, Counter, generate_latest
from colorama import init

# Initialize colorama
init(autoreset=True)

# --- Argumenty CLI ---
parser = argparse.ArgumentParser(description="Playwright Login Test with optional metrics export.")
parser.add_argument("--export-metrics", action="store_true",
                    help="Export metrics to a file instead of pushing them directly.")
parser.add_argument("--metrics-file", type=str, default="playwright_metrics.txt",
                    help="Name of the file where metrics will be saved (if --export-metrics).")
args = parser.parse_args()

# --- Konfiguracja z ENV ---
NUM_TESTS = int(os.getenv("NUM_TESTS", 1))
LOGIN = os.getenv("LOGIN", "student")
PASSWORD = os.getenv("PASSWORD", "Password123")
PUSHGATEWAY_ADDRESS = os.getenv("PUSHGATEWAY_ADDRESS", "localhost:9091")

# --- Prometheus registry (bez defaultowych metryk) ---
registry = CollectorRegistry()

# --- Definicje liczników ---
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

PERFORMANCE_POSITIVE_COUNTER = Counter(
    "playwright_positive_performance_failures_total",
    "Total number of positive tests that exceeded the expected duration threshold",
    registry=registry
)
PERFORMANCE_NEGATIVE_COUNTER = Counter(
    "playwright_negative_performance_unexpected_pass_total",
    "Total number of negative tests that unexpectedly passed or had very short duration",
    registry=registry
)


def run_login_test():
    """
    Główna logika testu: logowanie z danymi poprawnymi lub błędnymi,
    zliczanie sukcesów/porażek oraz ewentualnych "performance issues".
    """
    positive_perf_issues = 0
    negative_perf_issues = 0
    overall_start = time.time() * 1000  # Start time w ms

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for i in range(NUM_TESTS):
            iteration_start = time.time() * 1000
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
                    else:
                        content = page.content()
                        if not ("Logged In Successfully" in content or "Congratulations" in content):
                            TEST_FAILURE_COUNTER.inc()
                        else:
                            page.click("text=Log out")
                            time.sleep(0.2)
                            if "practice-test-login" not in page.url:
                                TEST_FAILURE_COUNTER.inc()
                            else:
                                TEST_SUCCESS_COUNTER.inc()
                    duration = (time.time() * 1000) - iteration_start
                    if duration > 4000:
                        positive_perf_issues += 1
                else:
                    # Negative scenario
                    if "logged-in-successfully" in current_url:
                        TEST_FAILURE_COUNTER.inc()
                        page.click("text=Log out")
                    else:
                        error_text = page.text_content("#error")
                        if error_text and (
                           "Your username is invalid!" in error_text or
                           "Your password is invalid!" in error_text):
                            TEST_SUCCESS_COUNTER.inc()
                        else:
                            TEST_FAILURE_COUNTER.inc()

                        duration = (time.time() * 1000) - iteration_start
                        if duration < 1000:
                            negative_perf_issues += 1

            except Exception:
                TEST_FAILURE_COUNTER.inc()

        PERFORMANCE_POSITIVE_COUNTER.inc(positive_perf_issues)
        PERFORMANCE_NEGATIVE_COUNTER.inc(negative_perf_issues)
        browser.close()


if __name__ == "__main__":
    run_login_test()

    # Jeśli ktoś podał --export-metrics, to generujemy plik z metrykami
    if args.export_metrics:
        metrics_output = generate_latest(registry).decode("utf-8")
        with open(args.metrics_file, "w", encoding="utf-8") as f:
            f.write(metrics_output)
        print(f"[INFO] Metrics exported to file: {args.metrics_file}")
