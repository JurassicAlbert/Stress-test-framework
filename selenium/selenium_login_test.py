import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from colorama import init, Fore, Style
from prometheus_client import CollectorRegistry, Counter, push_to_gateway

# Initialize colorama
init(autoreset=True)

# Environment variables
NUM_TESTS = int(os.getenv("NUM_TESTS", 1))
LOGIN = os.getenv("LOGIN", "student")
PASSWORD = os.getenv("PASSWORD", "Password123")  # Correct credentials
PUSHGATEWAY_ADDRESS = os.getenv("PUSHGATEWAY_ADDRESS", "localhost:9091")

# Create Prometheus registry and counters
registry = CollectorRegistry()
TEST_SUCCESS_COUNTER = Counter(
    "selenium_login_test_success_total",
    "Total number of successful login test iterations",
    registry=registry
)
TEST_FAILURE_COUNTER = Counter(
    "selenium_login_test_failure_total",
    "Total number of failed login test iterations",
    registry=registry
)


def push_metrics():
    """Push collected metrics to the Prometheus Pushgateway."""
    push_to_gateway(PUSHGATEWAY_ADDRESS, job="selenium_login_test", registry=registry)


def run_login_test(driver):
    """
    Runs the login test NUM_TESTS times.
    Positive scenario (LOGIN="student", PASSWORD="Password123"):
      - Check 'logged-in-successfully' in URL
      - Check success message
      - Check "Log out" button
    Negative scenario (invalid credentials):
      - Ensure NOT redirected to success
      - Check error message "Your username is invalid!" or "Your password is invalid!"
      - If present, we consider it a pass (like Cypress)
    """
    wait = WebDriverWait(driver, 10)
    failures = []

    for i in range(NUM_TESTS):
        print(f"Running test iteration {i + 1}")
        try:
            driver.get("https://practicetestautomation.com/practice-test-login/")
            wait.until(EC.presence_of_element_located((By.ID, "username")))

            # Enter login credentials
            driver.find_element(By.ID, "username").clear()
            driver.find_element(By.ID, "username").send_keys(LOGIN)
            driver.find_element(By.ID, "password").clear()
            driver.find_element(By.ID, "password").send_keys(PASSWORD)
            driver.find_element(By.ID, "submit").click()
            time.sleep(2)

            current_url = driver.current_url

            # =================== POSITIVE SCENARIO ===================
            if LOGIN == "student" and PASSWORD == "Password123":
                if "logged-in-successfully" not in current_url:
                    failures.append(f"[Iteration {i + 1}] Expected success URL, got: {current_url}")
                    TEST_FAILURE_COUNTER.inc()
                else:
                    # Check success message
                    page_source = driver.page_source
                    if not ("Logged In Successfully" in page_source or "Congratulations" in page_source):
                        failures.append(f"[Iteration {i + 1}] Missing success message in page source.")
                        TEST_FAILURE_COUNTER.inc()
                    else:
                        try:
                            logout_button = wait.until(
                                EC.visibility_of_element_located((By.XPATH, "//*[contains(text(),'Log out')]"))
                            )
                            if logout_button is None:
                                failures.append(f"[Iteration {i + 1}] 'Log out' button not visible.")
                                TEST_FAILURE_COUNTER.inc()
                            else:
                                logout_button.click()
                                time.sleep(2)
                                if "practice-test-login" not in driver.current_url:
                                    failures.append(f"[Iteration {i + 1}] Not returned to login page after logout.")
                                    TEST_FAILURE_COUNTER.inc()
                                else:
                                    print(
                                        f"[Iteration {i + 1}] {Fore.GREEN}Positive test passed successfully.{Style.RESET_ALL}")
                                    TEST_SUCCESS_COUNTER.inc()
                        except Exception as ex:
                            failures.append(f"[Iteration {i + 1}] Error during logout: {ex}")
                            TEST_FAILURE_COUNTER.inc()

            # =================== NEGATIVE SCENARIO ===================
            else:
                # If we see 'logged-in-successfully' => real fail
                if "logged-in-successfully" in current_url:
                    print(
                        f"[Iteration {i + 1}] {Fore.RED}ERROR: Unexpected login with invalid credentials.{Style.RESET_ALL}")
                    failures.append(f"[Iteration {i + 1}] Unexpected success URL with invalid credentials.")
                    TEST_FAILURE_COUNTER.inc()
                    # Optionally attempt logout
                    try:
                        logout_button = wait.until(
                            EC.visibility_of_element_located((By.XPATH, "//*[contains(text(),'Log out')]"))
                        )
                        logout_button.click()
                        time.sleep(2)
                    except:
                        pass
                else:
                    # We expect an error message
                    error_elem = wait.until(EC.visibility_of_element_located((By.ID, "error")))
                    error_text = error_elem.text.strip()
                    if ("Your username is invalid!" in error_text) or ("Your password is invalid!" in error_text):
                        # For negative scenario, seeing this message is a PASS
                        print(
                            f"[Iteration {i + 1}] {Fore.GREEN}Negative test passed (invalid credentials => error).{Style.RESET_ALL}")
                        TEST_SUCCESS_COUNTER.inc()
                    else:
                        failures.append(f"[Iteration {i + 1}] Unexpected error message: {error_text}")
                        TEST_FAILURE_COUNTER.inc()

        except Exception as e:
            print(f"[Iteration {i + 1}] - Test FAILED: {Fore.RED}{e}{Style.RESET_ALL}")
            failures.append(f"[Iteration {i + 1}] Exception: {e}")
            TEST_FAILURE_COUNTER.inc()

    if failures:
        print("\nSummary of errors:")
        for f in failures:
            print(f)
        push_metrics()
        sys.exit(1)
    else:
        print("All iterations passed successfully.")
        push_metrics()


def main():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=chrome_options)
    try:
        run_login_test(driver)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
