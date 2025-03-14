#!/usr/bin/env python3
import os
import sys
import time
import argparse
from playwright.sync_api import sync_playwright
from prometheus_client import (
    CollectorRegistry, Counter, Gauge, Histogram, generate_latest, push_to_gateway
)
from colorama import init

init(autoreset=True)
parser = argparse.ArgumentParser()
parser.add_argument("--export-metrics", action="store_true")
parser.add_argument("--metrics-file", type=str, default="playwright_metrics.txt")
args = parser.parse_args()

NUM_TESTS = int(os.getenv("NUM_TESTS", 1))
LOGIN = os.getenv("LOGIN", "student")
PASSWORD = os.getenv("PASSWORD", "Password123")
PUSHGATEWAY_ADDRESS = os.getenv("PUSHGATEWAY_ADDRESS", "localhost:9091").rstrip("/")

registry = CollectorRegistry()

# Liczniki główne
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
# Dodatkowe liczniki dla specyficznych przypadków
PERFORMANCE_POSITIVE_COUNTER = Counter(
    "playwright_positive_performance_failures_total",
    "Total number of positive tests that exceeded the expected duration threshold",
    registry=registry
)
PERFORMANCE_NEGATIVE_COUNTER = Counter(
    "playwright_negative_performance_unexpected_pass_total",
    "Total number of negative tests that unexpectedly passed or had a very short duration",
    registry=registry
)
POSITIVE_EXPECTED_PASS = Counter(
    "playwright_positive_performance_expected_pass_total",
    "Total positive tests that passed as expected",
    registry=registry
)
NEGATIVE_EXPECTED_FAIL = Counter(
    "playwright_negative_performance_expected_fail_total",
    "Total negative tests that failed as expected",
    registry=registry
)

# Nowa metryka – licznik testów uruchomionych
TEST_ATTEMPT_COUNTER = Counter(
    "playwright_test_attempt_total",
    "Total number of attempted Playwright tests",
    registry=registry
)

# Histogram czasu trwania testu (w sekundach)
TEST_DURATION_HISTOGRAM = Histogram(
    "playwright_test_duration_seconds",
    "Histogram of Playwright test durations in seconds",
    buckets=[0.5, 1, 2, 4, 8],
    registry=registry
)

# Przykładowa metryka 2D (oryginalna)
CLASSIFICATION_2D = Gauge(
    "playwright_classification_2d",
    "2D data from test scenario (X->value=Y)",
    ["test_name", "x_value"],
    registry=registry
)

def run_login_test():
    positive_perf_issues = 0
    negative_perf_issues = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for i in range(NUM_TESTS):
            TEST_ATTEMPT_COUNTER.inc()  # Zwiększenie licznika prób testów
            iteration_start = time.time()
            try:
                page.goto("https://practicetestautomation.com/practice-test-login/")
                page.fill("#username", LOGIN)
                page.fill("#password", PASSWORD)
                page.click("#submit")
                time.sleep(0.2)
                current_url = page.url

                x_num = i * 10
                duration = time.time() - iteration_start
                # Rejestracja czasu trwania testu
                TEST_DURATION_HISTOGRAM.observe(duration)
                # Ustawiamy wartość metryki 2D
                CLASSIFICATION_2D.labels(test_name="positive" if (LOGIN=="student" and PASSWORD=="Password123") else "negative",
                                          x_value=str(x_num)).set(duration * 1000)  # zapis w ms

                scenario_name = "positive" if (LOGIN == "student" and PASSWORD == "Password123") else "negative"
                if scenario_name == "positive":
                    if "logged-in-successfully" not in current_url:
                        TEST_FAILURE_COUNTER.inc()
                        PERFORMANCE_POSITIVE_COUNTER.inc()  # Nieoczekiwane niepowodzenie
                    else:
                        content = page.content()
                        if not ("Logged In Successfully" in content or "Congratulations" in content):
                            TEST_FAILURE_COUNTER.inc()
                            PERFORMANCE_POSITIVE_COUNTER.inc()
                        else:
                            page.click("text=Log out")
                            time.sleep(0.2)
                            if "practice-test-login" not in page.url:
                                TEST_FAILURE_COUNTER.inc()
                                PERFORMANCE_POSITIVE_COUNTER.inc()
                            else:
                                TEST_SUCCESS_COUNTER.inc()
                                POSITIVE_EXPECTED_PASS.inc()
                    if duration > 4:
                        positive_perf_issues += 1
                else:
                    if "logged-in-successfully" in current_url:
                        TEST_FAILURE_COUNTER.inc()
                        PERFORMANCE_NEGATIVE_COUNTER.inc()  # Nieoczekiwane przejście
                    else:
                        error_text = page.text_content("#error")
                        if error_text and ("Your username is invalid!" in error_text or "Your password is invalid!" in error_text):
                            TEST_SUCCESS_COUNTER.inc()
                            NEGATIVE_EXPECTED_FAIL.inc()
                        else:
                            TEST_FAILURE_COUNTER.inc()
                    if duration < 1:
                        negative_perf_issues += 1
            except Exception as ex:
                TEST_FAILURE_COUNTER.inc()
        PERFORMANCE_POSITIVE_COUNTER.inc(positive_perf_issues)
        PERFORMANCE_NEGATIVE_COUNTER.inc(negative_perf_issues)
        browser.close()

if __name__ == "__main__":
    run_login_test()

    if args.export_metrics:
        metrics_output = generate_latest(registry).decode("utf-8")
        with open(args.metrics_file, "w", encoding="utf-8") as f:
            f.write(metrics_output)
        print("[INFO] Metrics exported to file:", args.metrics_file)

        # Ustalamy nazwę jobu na podstawie pliku
        job_name = "playwright_tests"
        if "negative" in args.metrics_file.lower():
            job_name = "playwright_tests_negative"
        elif "positive" in args.metrics_file.lower():
            job_name = "playwright_tests_positive"

        try:
            push_to_gateway(
                PUSHGATEWAY_ADDRESS,
                job=job_name,
                registry=registry
            )
            print(f"[INFO] Metrics pushed to Pushgateway at: {PUSHGATEWAY_ADDRESS} with job: {job_name}")
        except Exception as e:
            print("[ERROR] Failed to push metrics:", e)
