import os
from locust import HttpUser, TaskSet, task, between, events
from prometheus_client import CollectorRegistry, Counter, push_to_gateway

# Default host and credentials (retrieved from environment variables)
LOCUST_HOST = os.getenv("LOCUST_HOST", "https://practicetestautomation.com")
USERNAME = os.getenv("LOCUST_USERNAME", "student")
PASSWORD = os.getenv("LOCUST_PASSWORD", "Password123")

# Browser simulation header (do not change)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        "AppleWebKit/537.36 (KHTML, like Gecko)"
        "Chrome/132.0.0.0"
        "Safari/537.36"
    )
}

# Create a custom registry for our metrics.
registry = CollectorRegistry()

# Define Prometheus counters in our registry.
REQUEST_SUCCESS_COUNTER = Counter(
    "locust_request_success_total",
    "Total successful requests",
    ["method", "name", "response_code"],
    registry=registry
)
REQUEST_FAILURE_COUNTER = Counter(
    "locust_request_failure_total",
    "Total failed requests",
    ["method", "name", "response_code"],
    registry=registry
)

# Register event listeners to update our counters.
@events.request_success.add_listener
def on_request_success(request_type, name, response_time, response_length, **kwargs):
    # Assume successful responses have code 200.
    REQUEST_SUCCESS_COUNTER.labels(method=request_type, name=name, response_code="200").inc()

@events.request_failure.add_listener
def on_request_failure(request_type, name, response_time, response_length, exception, **kwargs):
    # Label failures with response code "0" (or adjust accordingly).
    REQUEST_FAILURE_COUNTER.labels(method=request_type, name=name, response_code="0").inc()


class PracticeLoginScenario(TaskSet):
    @task
    def login_test(self):
        """
        Login scenario for Practice Test Automation:
          1. GET /practice-test-login/ – load the login page.
          2. Depending on the provided credentials:
             - If credentials are correct (USERNAME=="student" and PASSWORD=="Password123"):
               perform a GET to /logged-in-successfully/ and verify that the page contains a success message.
             - Otherwise, fire a failure event.
          3. GET /practice-test-login/ – reset state (simulate logout).
        """
        # 1. Load the login page
        with self.client.get(
            "/practice-test-login/",
            headers=HEADERS,
            catch_response=True,
            name="Load Login Page"
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Failed to load login page. Code: {resp.status_code}")
                return

        # 2. Simulate login based on credentials
        if USERNAME == "student" and PASSWORD == "Password123":
            # Positive scenario: simulate redirection to the success page
            with self.client.get(
                "/logged-in-successfully/",
                headers=HEADERS,
                catch_response=True,
                name="After Login Redirect"
            ) as r:
                if r.status_code == 200 and ("Logged In Successfully" in r.text or "Congratulations" in r.text):
                    r.success()
                else:
                    r.failure(f"Unexpected login result. Code: {r.status_code}")
        else:
            # Negative scenario: fire a failure event with an appropriate error message.
            if USERNAME != "student":
                self.environment.events.request_failure.fire(
                    request_type="GET",
                    name="Login Attempt",
                    response_time=0,
                    response_length=0,
                    exception=Exception("Your username is invalid!")
                )
            else:
                self.environment.events.request_failure.fire(
                    request_type="GET",
                    name="Login Attempt",
                    response_time=0,
                    response_length=0,
                    exception=Exception("Your password is invalid!")
                )

        # 3. Reset state – simulate logout by reloading the login page
        with self.client.get(
            "/practice-test-login/",
            headers=HEADERS,
            catch_response=True,
            name="Logout/Reset"
        ) as logout_resp:
            if logout_resp.status_code == 200:
                logout_resp.success()
            else:
                logout_resp.failure(f"Failed to reset (GET /practice-test-login/). Code: {logout_resp.status_code}")


class WebsiteUser(HttpUser):
    host = LOCUST_HOST
    tasks = [PracticeLoginScenario]
    wait_time = between(1, 3)


# Function to push metrics to Pushgateway.
def push_metrics():
    # Push metrics to the Pushgateway. Update the address if necessary.
    push_to_gateway("localhost:9091", job="locust_tests", registry=registry)


# Start the test. When Locust runs, it will start your test and update the metrics.
# At the end of your test run (or at defined intervals), you can call push_metrics() via your CI/CD pipeline.
# For example, you might add a Jenkins post-build step that executes a command to push the metrics.

# When running Locust, ensure that this script is executed so the Prometheus endpoint is exposed (or push_metrics is called).
push_metrics()
