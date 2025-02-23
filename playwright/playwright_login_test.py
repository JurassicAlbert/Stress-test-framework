import os
import sys
from playwright.sync_api import sync_playwright
from prometheus_client import CollectorRegistry, Counter, push_to_gateway

# Pobieramy liczbę iteracji i dane logowania z environment
NUM_TESTS = int(os.getenv("NUM_TESTS", 1))
USERNAME = os.getenv("LOGIN", "student")
PASSWORD = os.getenv("PASSWORD", "Password123")  # Dane poprawne: "student"/"Password123"

# Adres Pushgateway
PUSHGATEWAY_ADDRESS = os.getenv("PUSHGATEWAY_ADDRESS", "localhost:9091")

# Rejestr Prometheus i liczniki
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
    Wypychanie metryk do Pushgateway.
    """
    push_to_gateway(PUSHGATEWAY_ADDRESS, job="playwright_login_test", registry=registry)

def run_login_test(page):
    """
    Wykonuje test logowania przez Playwright określoną liczbę razy (NUM_TESTS).
    """
    failures = []

    for i in range(NUM_TESTS):
        print(f"Running test iteration {i + 1}")
        page.goto("https://practicetestautomation.com/practice-test-login/")
        page.fill("#username", USERNAME)
        page.fill("#password", PASSWORD)
        page.click("#submit")
        page.wait_for_load_state("networkidle")

        current_url = page.url

        if USERNAME == "student" and PASSWORD == "Password123":
            # Scenariusz pozytywny
            if "logged-in-successfully" not in current_url:
                failures.append(f"Iteration {i + 1}: Expected redirection, got URL: {current_url}")
                TEST_FAILURE_COUNTER.inc()
            else:
                content = page.content()
                if not ("Logged In Successfully" in content or "Congratulations" in content):
                    failures.append(f"Iteration {i + 1}: Missing success message.")
                    TEST_FAILURE_COUNTER.inc()
                else:
                    try:
                        if not page.is_visible("text=Log out"):
                            failures.append(f"Iteration {i + 1}: 'Log out' button not visible.")
                            TEST_FAILURE_COUNTER.inc()
                        else:
                            page.click("text=Log out")
                            page.wait_for_load_state("networkidle")
                            if "practice-test-login" not in page.url:
                                failures.append(f"Iteration {i + 1}: Did not return to login page after logout.")
                                TEST_FAILURE_COUNTER.inc()
                            else:
                                print(f"Iteration {i + 1}: Positive test passed successfully.")
                                TEST_SUCCESS_COUNTER.inc()
                    except Exception as ex:
                        failures.append(f"Iteration {i + 1}: Error during logout: {ex}")
                        TEST_FAILURE_COUNTER.inc()
        else:
            # Scenariusz negatywny
            if "logged-in-successfully" in current_url:
                print(f"Iteration {i + 1}: ERROR: Logged in with invalid credentials. Logging out.")
                try:
                    page.click("text=Log out")
                    page.wait_for_load_state("networkidle")
                except Exception as ex:
                    failures.append(f"Iteration {i + 1}: Error during forced logout: {ex}")
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
        sys.exit(1)  # W razie chęci kontynuacji, można usunąć
    else:
        print("All iterations passed successfully.")
        push_metrics()

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        run_login_test(page)
        browser.close()

if __name__ == "__main__":
    main()
