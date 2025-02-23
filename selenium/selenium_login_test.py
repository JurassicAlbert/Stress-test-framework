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

# Initialize colorama for colored terminal output
init(autoreset=True)

# Environment variables
NUM_TESTS = int(os.getenv("NUM_TESTS", 1))
LOGIN = os.getenv("LOGIN", "student")
PASSWORD = os.getenv("PASSWORD", "Password123")  # Correct credentials: "student"/"Password123"
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
    """
    Push the collected metrics to the Prometheus Pushgateway.
    """
    push_to_gateway(PUSHGATEWAY_ADDRESS, job="selenium_login_test", registry=registry)

def run_login_test(driver):
    """
    Runs the login test for a given number of iterations.
    For each iteration:
      1. Opens the login page.
      2. Enters the login credentials.
      3. For positive scenarios (LOGIN=="student" and PASSWORD=="Password123"):
           - Verifies that the URL contains "logged-in-successfully"
           - Checks that the page contains a success message
           - Verifies that the "Log out" button is visible, then clicks it and confirms return to the login page.
         For negative scenarios:
           - Verifies that the login does NOT succeed, and that the appropriate error message is displayed.
    If any iteration fails (i.e. positive test does not pass or negative test does not show the error as expected),
    the failure is recorded and metrics are pushed to the Pushgateway.
    """
    wait = WebDriverWait(driver, 10)
    failures = []

    for i in range(NUM_TESTS):
        print(f"Running test iteration {i + 1}")
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

            if LOGIN == "student" and PASSWORD == "Password123":
                # Positive scenario
                if "logged-in-successfully" not in current_url:
                    failures.append(f"Iteration {i + 1}: Expected redirection, but got: {current_url}")
                    TEST_FAILURE_COUNTER.inc()
                else:
                    page_source = driver.page_source
                    if not ("Logged In Successfully" in page_source or "Congratulations" in page_source):
                        failures.append(f"Iteration {i + 1}: Missing success message upon login.")
                        TEST_FAILURE_COUNTER.inc()
                    else:
                        try:
                            logout_button = wait.until(
                                EC.visibility_of_element_located((By.XPATH, "//*[contains(text(),'Log out')]"))
                            )
                            if logout_button is None:
                                failures.append(f"Iteration {i + 1}: 'Log out' button not visible.")
                                TEST_FAILURE_COUNTER.inc()
                            else:
                                logout_button.click()
                                time.sleep(2)
                                if "practice-test-login" not in driver.current_url:
                                    failures.append(f"Iteration {i + 1}: Did not return to login page after logout.")
                                    TEST_FAILURE_COUNTER.inc()
                                else:
                                    print(f"Iteration {i + 1}: {Fore.GREEN}Positive test passed successfully.{Style.RESET_ALL}")
                                    TEST_SUCCESS_COUNTER.inc()
                        except Exception as ex:
                            failures.append(f"Iteration {i + 1}: Error during logout: {ex}")
                            TEST_FAILURE_COUNTER.inc()
            else:
                # Negative scenario
                if "logged-in-successfully" in current_url:
                    print(f"Iteration {i + 1}: {Fore.RED}ERROR: Logged in with invalid credentials. Logging out...{Style.RESET_ALL}")
                    try:
                        logout_button = wait.until(
                            EC.visibility_of_element_located((By.XPATH, "//*[contains(text(),'Log out')]"))
                        )
                        logout_button.click()
                        time.sleep(2)
                    except Exception as ex:
                        failures.append(f"Iteration {i + 1}: Error during forced logout: {ex}")
                    failures.append(f"Iteration {i + 1}: TEST FAILED: Unexpected login with invalid credentials.")
                    TEST_FAILURE_COUNTER.inc()
                else:
                    error_elem = wait.until(EC.visibility_of_element_located((By.ID, "error")))
                    error_text = error_elem.text
                    if ("Your username is invalid!" in error_text) or ("Your password is invalid!" in error_text):
                        failures.append(f"Iteration {i + 1}: TEST FAILED: Invalid login credentials.")
                        TEST_FAILURE_COUNTER.inc()
                    else:
                        failures.append(f"Iteration {i + 1}: Unexpected error message: {error_text}")
                        TEST_FAILURE_COUNTER.inc()

        except Exception as e:
            print(f"Iteration {i + 1} - Test FAILED: {Fore.RED}{e}{Style.RESET_ALL}")
            failures.append(f"Iteration {i + 1}: {e}")
            TEST_FAILURE_COUNTER.inc()

    if failures:
        print("\nSummary of errors:")
        for failure in failures:
            print(failure)
        push_metrics()
        sys.exit(1)
    else:
        print("All iterations passed successfully.")
        push_metrics()

def main():
    """
    Run the login test in headless mode.
    """
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
