#!/usr/bin/env python3
import os
import time
import argparse
from playwright.sync_api import sync_playwright
from prometheus_client import (
    CollectorRegistry, Counter, generate_latest, push_to_gateway
)
from colorama import init

init(autoreset=True)

parser = argparse.ArgumentParser()
parser.add_argument("--export-metrics", action="store_true")
parser.add_argument("--metrics-file", type=str, default="playwright_metrics.txt")
args = parser.parse_args()

# Ustawienia z ENV lub domyślne
NUM_TESTS = int(os.getenv("NUM_TESTS", 1))
LOGIN = os.getenv("LOGIN", "student")
PASSWORD = os.getenv("PASSWORD", "Password123")
PUSHGATEWAY_ADDRESS = os.getenv("PUSHGATEWAY_ADDRESS", "localhost:9091").rstrip("/")

# Limit czasu (w sekundach) – dla pozytywnych testów
MAX_DURATION = 3.8

# Rejestr do Prometheusa
registry = CollectorRegistry()

# ========== METRYKI ==========
TEST_PASSED_COUNTER = Counter(
    "playwright_test_passed_total",
    "Total number of tests that passed as expected",
    registry=registry
)
TEST_FAILED_COUNTER = Counter(
    "playwright_test_failed_total",
    "Total number of tests that failed (unexpected outcome)",
    registry=registry
)
TEST_NEGATIVE_UNEXPECTED_PASS_COUNTER = Counter(
    "playwright_test_negative_unexpected_pass_total",
    "Total negative tests that unexpectedly passed",
    registry=registry
)
TEST_POSITIVE_UNEXPECTED_FAIL_COUNTER = Counter(
    "playwright_test_positive_unexpected_fail_total",
    "Total positive tests that unexpectedly failed",
    registry=registry
)
# =============================

def run_login_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for _ in range(NUM_TESTS):
            start_time = time.time()

            try:
                # Przechodzimy do strony logowania
                page.goto("https://practicetestautomation.com/practice-test-login/")
                page.fill("#username", LOGIN)
                page.fill("#password", PASSWORD)
                page.click("#submit")
                time.sleep(0.2)

                duration = time.time() - start_time
                current_url = page.url

                # Rozpoznajemy scenariusz (positive/negative)
                scenario = "positive" if (LOGIN == "student" and PASSWORD == "Password123") else "negative"

                if scenario == "positive":
                    # Pozytywny scenariusz: oczekujemy, że użytkownik zostanie zalogowany
                    if "logged-in-successfully" in current_url:
                        content = page.content()
                        if ("Logged In Successfully" in content or "Congratulations" in content):
                            # Sprawdzamy wylogowanie
                            page.click("text=Log out")
                            time.sleep(0.2)
                            if "practice-test-login" in page.url:
                                # Jeśli czas jest w normie, test "przeszedł"
                                if duration <= MAX_DURATION:
                                    TEST_PASSED_COUNTER.inc()
                                else:
                                    # Jeśli trwa za długo – tylko nieoczekiwane niepowodzenie
                                    TEST_POSITIVE_UNEXPECTED_FAIL_COUNTER.inc()
                            else:
                                TEST_POSITIVE_UNEXPECTED_FAIL_COUNTER.inc()
                        else:
                            TEST_POSITIVE_UNEXPECTED_FAIL_COUNTER.inc()
                    else:
                        TEST_POSITIVE_UNEXPECTED_FAIL_COUNTER.inc()

                else:
                    # Negatywny scenariusz: oczekujemy błędnego logowania (czyli nie zalogowania się)
                    if "logged-in-successfully" in current_url:
                        # Użytkownik zalogował się nieoczekiwanie
                        TEST_NEGATIVE_UNEXPECTED_PASS_COUNTER.inc()
                    else:
                        # Test negatywny – niezależnie od czasu, zwiększamy tylko TEST_FAILED_COUNTER
                        TEST_FAILED_COUNTER.inc()

            except Exception:
                TEST_FAILED_COUNTER.inc()

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
