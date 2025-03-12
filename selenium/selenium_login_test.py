#!/usr/bin/env python3
"""
selenium_login_test.py

Zmodyfikowany skrypt Selenium, który:
  - Definiuje metryki i rejestr,
  - Inicjalizuje liczniki i aktualizuje ich wartości na podstawie wyników testów,
  - Na końcu, jeśli przekazano flagę --export-metrics, zapisuje metryki do pliku,
    zamiast bezpośrednio pushować je do Pushgateway.

Testy wykonują się przy użyciu Selenium – symulując logowanie pozytywne (dla poprawnych danych)
oraz negatywne (dla błędnych danych). Metryki (sukcesy, porażki, "performance issues") są aktualizowane
na bieżąco.
"""

import os
import time
import sys
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from prometheus_client import CollectorRegistry, Counter, generate_latest
from colorama import init

# Inicjalizacja colorama
init(autoreset=True)

# --- Argumenty CLI ---
parser = argparse.ArgumentParser(description="Selenium Login Test with optional metrics export.")
parser.add_argument("--export-metrics", action="store_true",
                    help="Export metrics to a file instead of pushing them directly.")
parser.add_argument("--metrics-file", type=str, default="selenium_metrics.txt",
                    help="Name of the file where metrics will be saved (if --export-metrics is used).")
args = parser.parse_args()

# --- Konfiguracja z ENV ---
NUM_TESTS = int(os.getenv("NUM_TESTS", 1))
LOGIN = os.getenv("LOGIN", "student")
PASSWORD = os.getenv("PASSWORD", "Password123")
PUSHGATEWAY_ADDRESS = os.getenv("PUSHGATEWAY_ADDRESS", "localhost:9091")

# --- Prometheus registry i definicje liczników ---
registry = CollectorRegistry()
TEST_SUCCESS_COUNTER = Counter(
    "selenium_test_success_total",
    "Total number of successful Selenium tests",
    registry=registry
)
TEST_FAILURE_COUNTER = Counter(
    "selenium_test_failure_total",
    "Total number of failed Selenium tests",
    registry=registry
)
PERFORMANCE_POSITIVE_COUNTER = Counter(
    "selenium_positive_performance_failures_total",
    "Total number of positive tests that exceeded the expected duration threshold",
    registry=registry
)
PERFORMANCE_NEGATIVE_COUNTER = Counter(
    "selenium_negative_performance_unexpected_pass_total",
    "Total number of negative tests that unexpectedly passed or had very short duration",
    registry=registry
)


def run_login_test(driver):
    """
    Wykonuje test logowania NUM_TESTS razy przy użyciu Selenium.
    W scenariuszu pozytywnym (poprawne dane) sprawdzamy obecność określonych komunikatów
    i przycisku "Log out". W scenariuszu negatywnym (błędne dane) oczekujemy komunikatu o błędzie.
    Aktualizujemy liczniki sukcesów, porażek oraz "performance issues".
    """
    wait = WebDriverWait(driver, 10)
    positive_perf_issues = 0
    negative_perf_issues = 0
    failures = []
    overall_start = time.time() * 1000  # ms

    for i in range(NUM_TESTS):
        iteration_start = time.time() * 1000
        try:
            driver.get("https://practicetestautomation.com/practice-test-login/")
            wait.until(EC.presence_of_element_located((By.ID, "username")))

            # Wpisywanie danych do formularza
            driver.find_element(By.ID, "username").clear()
            driver.find_element(By.ID, "username").send_keys(LOGIN)
            driver.find_element(By.ID, "password").clear()
            driver.find_element(By.ID, "password").send_keys(PASSWORD)
            driver.find_element(By.ID, "submit").click()
            time.sleep(2)
            current_url = driver.current_url

            # --- SCENARIUSZ POZYTYWNY ---
            if LOGIN == "student" and PASSWORD == "Password123":
                if "logged-in-successfully" not in current_url:
                    TEST_FAILURE_COUNTER.inc()
                    failures.append(f"Iteration {i + 1}: Expected success URL, got: {current_url}")
                else:
                    page_source = driver.page_source
                    if not ("Logged In Successfully" in page_source or "Congratulations" in page_source):
                        TEST_FAILURE_COUNTER.inc()
                        failures.append(f"Iteration {i + 1}: Missing success message.")
                    else:
                        # Próbujemy znaleźć przycisk "Log out"
                        try:
                            logout_button = wait.until(
                                EC.visibility_of_element_located((By.XPATH, "//*[contains(text(),'Log out')]"))
                            )
                            if logout_button:
                                logout_button.click()
                                time.sleep(2)
                                if "practice-test-login" not in driver.current_url:
                                    TEST_FAILURE_COUNTER.inc()
                                    failures.append(
                                        f"Iteration {i + 1}: Failed to return to login page after logout."
                                    )
                                else:
                                    TEST_SUCCESS_COUNTER.inc()
                            else:
                                TEST_FAILURE_COUNTER.inc()
                                failures.append(f"Iteration {i + 1}: 'Log out' button not visible.")
                        except Exception as e:
                            TEST_FAILURE_COUNTER.inc()
                            failures.append(f"Iteration {i + 1}: Exception while clicking logout button: {e}")

                # Sprawdzenie czasu wykonania
                duration = time.time() * 1000 - iteration_start
                if duration > 4000:
                    positive_perf_issues += 1

            # --- SCENARIUSZ NEGATYWNY ---
            else:
                if "logged-in-successfully" in current_url:
                    TEST_FAILURE_COUNTER.inc()
                    failures.append(f"Iteration {i + 1}: Unexpected login with invalid credentials.")
                    # Spróbuj się wylogować, jeśli przycisk się pojawi
                    try:
                        logout_button = wait.until(
                            EC.visibility_of_element_located((By.XPATH, "//*[contains(text(),'Log out')]"))
                        )
                        if logout_button:
                            logout_button.click()
                            time.sleep(2)
                    except Exception:
                        pass
                else:
                    error_elem = wait.until(EC.visibility_of_element_located((By.ID, "error")))
                    error_text = error_elem.text.strip()
                    if error_text and (
                        "Your username is invalid!" in error_text or
                        "Your password is invalid!" in error_text
                    ):
                        TEST_SUCCESS_COUNTER.inc()
                    else:
                        TEST_FAILURE_COUNTER.inc()
                        failures.append(f"Iteration {i + 1}: Unexpected error message: {error_text}")

                # Sprawdzenie czasu wykonania
                duration = time.time() * 1000 - iteration_start
                if duration < 1000:
                    negative_perf_issues += 1

        except Exception as e:
            TEST_FAILURE_COUNTER.inc()
            failures.append(f"Iteration {i + 1}: Exception: {e}")

    # Zliczanie „performance issues”
    PERFORMANCE_POSITIVE_COUNTER.inc(positive_perf_issues)
    PERFORMANCE_NEGATIVE_COUNTER.inc(negative_perf_issues)

    overall_duration = time.time() * 1000 - overall_start
    return failures, overall_duration


def main():
    chrome_options = Options()
    # Dodatkowe argumenty dla uruchomienia w trybie headless
    chrome_options.add_argument("--headless")  # Można użyć "--headless=new" (dla Chrome 109+)
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")  # uniknięcie małej partycji /dev/shm
    chrome_options.add_argument("--no-sandbox")  # wyłącza sandbox, wymagane w niektórych środowiskach

    driver = webdriver.Chrome(options=chrome_options)
    try:
        failures, overall_duration = run_login_test(driver)
    finally:
        driver.quit()

    # Eksport metryk do pliku, jeśli użyto --export-metrics
    if args.export_metrics:
        metrics_output = generate_latest(registry).decode("utf-8")
        with open(args.metrics_file, "w", encoding="utf-8") as f:
            f.write(metrics_output)
        print(f"[INFO] Metrics exported to file: {args.metrics_file}")
    else:
        print("[INFO] Metrics were not exported to file (push not implemented).")

    # Możesz wypisać ewentualne błędy
    if failures:
        print("[ERROR] Test failures:")
        for fail in failures:
            print(" -", fail)

    print(f"[INFO] Overall test duration: {overall_duration:.2f} ms")
    sys.exit(0)


if __name__ == "__main__":
    main()
