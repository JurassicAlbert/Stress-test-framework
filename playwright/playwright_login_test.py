import os
import sys
from playwright.sync_api import sync_playwright
from prometheus_client import CollectorRegistry, Counter, push_to_gateway

# Retrieve data from the pipeline or use default values:
NUM_TESTS = int(os.getenv("NUM_TESTS", 1))
USERNAME = os.getenv("LOGIN", "student")
PASSWORD = os.getenv("PASSWORD", "Password123")  # Correct credentials: "student" / "Password123"

# Retrieve Pushgateway address from environment variable (default: localhost:9091)
PUSHGATEWAY_ADDRESS = os.getenv("PUSHGATEWAY_ADDRESS", "localhost:9091")

# Create a Prometheus registry and define counters:
registry = CollectorRegistry()
TEST_SUCCESS_COUNTER = Counter(
    "playwright_login_test_success_total",
    "Total number of successful login test iterations",
    registry=registry
)
TEST_FAILURE_COUNTER = Counter(
    "playwright_login_test_failure_total",
    "Total number of failed login test iterations",
    registry=registry
)

def push_metrics():
    """
    Push the collected metrics to the Prometheus Pushgateway.
    """
    push_to_gateway(PUSHGATEWAY_ADDRESS, job="playwright_login_test", registry=registry)

def run_login_test(page):
    """
    Runs the login test for a specified number of iterations.
    For each iteration:
      1. Opens the login page.
      2. Fills in the login credentials.
      3. If credentials are correct (USERNAME=="student" and PASSWORD=="Password123"):
           - Verifies that the user is redirected to the success page and the page contains a success message.
           - Checks that a "Log out" button is visible, then logs out and verifies that the user returns to the login page.
         Otherwise (negative scenario):
           - Verifies that the login does not succeed and that the appropriate error message is shown.
    Instead of immediately aborting, errors are collected and printed at the end, then metrics are pushed.
    """
    failures = []  # List to record errors from each iteration

    for i in range(NUM_TESTS):
        print(f"Running test iteration {i + 1}")
        page.goto("https://practicetestautomation.com/practice-test-login/")
        page.fill("#username", USERNAME)
        page.fill("#password", PASSWORD)
        page.click("#submit")
        page.wait_for_load_state("networkidle")
        current_url = page.url

        if USERNAME == "student" and PASSWORD == "Password123":
            # Positive scenario
            if "logged-in-successfully" not in current_url:
                failures.append(f"Iteration {i + 1}: Expected redirection, but received URL: {current_url}")
                TEST_FAILURE_COUNTER.inc()
            else:
                content = page.content()
                if not ("Logged In Successfully" in content or "Congratulations" in content):
                    failures.append(f"Iteration {i + 1}: Missing success message on login.")
                    TEST_FAILURE_COUNTER.inc()
                else:
                    try:
                        if not page.is_visible("text=Log out"):
                            failures.append(f"Iteration {i + 1}: 'Log out' button is not visible.")
                            TEST_FAILURE_COUNTER.inc()
                        else:
                            page.click("text=Log out")
                            page.wait_for_load_state("networkidle")
                            if "practice-test-login" not in page.url:
                                failures.append(f"Iteration {i + 1}: Failed to return to the login page after logout.")
                                TEST_FAILURE_COUNTER.inc()
                            else:
                                print(f"Iteration {i + 1}: Positive test passed successfully.")
                                TEST_SUCCESS_COUNTER.inc()
                    except Exception as ex:
                        failures.append(f"Iteration {i + 1}: Error during logout: {ex}")
                        TEST_FAILURE_COUNTER.inc()
        else:
            # Negative scenario – invalid credentials: test should fail
            if "logged-in-successfully" in current_url:
                print(f"Iteration {i + 1}: ERROR: Logged in with invalid credentials. Logging out...")
                try:
                    page.click("text=Log out")
                    page.wait_for_load_state("networkidle")
                except Exception as ex:
                    failures.append(f"Iteration {i + 1}: Error during logout: {ex}")
                failures.append(f"Iteration {i + 1}: TEST FAILED: Unexpected login with invalid credentials.")
                TEST_FAILURE_COUNTER.inc()
            else:
                error_text = page.text_content("#error") or ""
                if "Your username is invalid!" in error_text or "Your password is invalid!" in error_text:
                    failures.append(f"Iteration {i + 1}: TEST FAILED: invalid login credentials.")
                    TEST_FAILURE_COUNTER.inc()
                else:
                    failures.append(f"Iteration {i + 1}: Unexpected error message: {error_text}")
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
    Main function to run the login test in headless mode.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        run_login_test(page)
        browser.close()

if __name__ == "__main__":
    main()
