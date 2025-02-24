#!/usr/bin/env python3
"""
selenium_login_test.py

This script runs a login test repeatedly using Selenium and records Prometheus metrics.
It measures:
  - The number of tests that passed/failed.
  - For positive tests (with valid credentials), if the test duration exceeds a threshold (e.g., 4000 ms),
    it counts that as a performance issue.
  - For negative tests (with invalid credentials), if the test either passes unexpectedly or runs too quickly
    (< 1000 ms), it counts that as a performance issue.

At the end of the run, all metrics are pushed to a Prometheus Pushgateway.

Note: This script never throws exceptions or terminates with a nonzero exit code.
It always completes the test loop and pushes metrics.
"""

import os
import time
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from prometheus_client import CollectorRegistry, Counter, push_to_gateway
from colorama import init, Fore, Style

# Initialize colorama for colored terminal output (if needed)
init(autoreset=True)

# Retrieve configuration from environment variables
NUM_TESTS = int(os.getenv("NUM_TESTS", 1))
LOGIN = os.getenv("LOGIN", "student")
PASSWORD = os.getenv("PASSWORD", "Password123")  # Correct credentials: "student"/"Password123"
PUSHGATEWAY_ADDRESS = os.getenv("PUSHGATEWAY_ADDRESS", "localhost:9091")

# Set up Prometheus registry and define counters
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


def push_metrics():
    """
    Push the collected metrics to the Prometheus Pushgateway.
    Any push errors are silently ignored.
    """
    try:
        push_to_gateway(PUSHGATEWAY_ADDRESS, job="selenium_tests", registry=registry)
    except Exception:
        pass


def run_login_test(driver):
    """
    Runs the login test repeatedly using Selenium.

    For positive tests (valid credentials):
      - Expects redirection to a URL containing "logged-in-successfully"
      - Expects a success message in the page source and a visible "Log out" button.
      - Clicks the "Log out" button and expects a return to the login page.
      - If the test duration exceeds 4000 ms, it is recorded as a performance issue.

    For negative tests (invalid credentials):
      - Expects that the URL does not contain "logged-in-successfully".
      - Expects to see an error message ("Your username is invalid!" or "Your password is invalid!").
      - If the test passes unexpectedly or the duration is less than 1000 ms, it is recorded as a performance issue.

    This function collects all failure messages and returns them along with the overall duration.
    """
    wait = WebDriverWait(driver, 10)
    positive_perf_issues = 0
    negative_perf_issues = 0
    failures = []
    overall_start = time.time() * 1000  # milliseconds

    for i in range(NUM_TESTS):
        iteration_start = time.time() * 1000
        try:
            driver.get("https://practicetestautomation.com/practice-test-login/")
            wait.until(EC.presence_of_element_located((By.ID, "username")))
            driver.find_element(By.ID, "username").clear()
            driver.find_element(By.ID, "username").send_keys(LOGIN)
            driver.find_element(By.ID, "password").clear()
            driver.find_element(By.ID, "password").send_keys(PASSWORD)
            driver.find_element(By.ID, "submit").click()
            time.sleep(2)
            current_url = driver.current_url

            # Positive scenario
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
                        try:
                            logout_button = wait.until(
                                EC.visibility_of_element_located((By.XPATH, "//*[contains(text(),'Log out')]"))
                            )
                            if logout_button:
                                logout_button.click()
                                time.sleep(2)
                                if "practice-test-login" not in driver.current_url:
                                    TEST_FAILURE_COUNTER.inc()
                                    failures.append(f"Iteration {i + 1}: Failed to return to login page after logout.")
                                else:
                                    TEST_SUCCESS_COUNTER.inc()
                            else:
                                TEST_FAILURE_COUNTER.inc()
                                failures.append(f"Iteration {i + 1}: 'Log out' button not visible.")
                        except Exception as ex:
                            TEST_FAILURE_COUNTER.inc()
                            failures.append(f"Iteration {i + 1}: Error during logout: {ex}")
                duration = time.time() * 1000 - iteration_start
                if duration > 4000:
                    positive_perf_issues += 1
            else:
                # Negative scenario
                if "logged-in-successfully" in current_url:
                    TEST_FAILURE_COUNTER.inc()
                    failures.append(f"Iteration {i + 1}: Unexpected login with invalid credentials.")
                    try:
                        logout_button = wait.until(
                            EC.visibility_of_element_located((By.XPATH, "//*[contains(text(),'Log out')]")))
                        if logout_button:
                            logout_button.click()
                            time.sleep(2)
                    except Exception:
                        pass
                else:
                    error_elem = wait.until(EC.visibility_of_element_located((By.ID, "error")))
                    error_text = error_elem.text.strip()
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
            failures.append(f"Iteration {i + 1}: Exception: {e}")

    PERFORMANCE_POSITIVE_COUNTER.inc(positive_perf_issues)
    PERFORMANCE_NEGATIVE_COUNTER.inc(negative_perf_issues)
    overall_duration = time.time() * 1000 - overall_start
    push_metrics()
    return failures, overall_duration


def main():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=chrome_options)
    try:
        failures, overall_duration = run_login_test(driver)
    finally:
        driver.quit()
    # Do not exit with a nonzero code; always exit normally.
    sys.exit(0)


if __name__ == "__main__":
    main()
