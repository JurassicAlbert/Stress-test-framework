import os
from my_locust import HttpUser, TaskSet, task, between, events
from prometheus_client import CollectorRegistry, Counter, push_to_gateway

# Domyślny host i dane logowania (zaciągane z zmiennych środowiskowych)
LOCUST_HOST = os.getenv("LOCUST_HOST", "https://practicetestautomation.com")
USERNAME = os.getenv("LOCUST_USERNAME", "student")
PASSWORD = os.getenv("LOCUST_PASSWORD", "Password123")

# Nagłówek symulujący przeglądarkę (NIE ZMIENIAMY)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/132.0.0.0 Safari/537.36"
    )
}

# Tworzymy rejestr i liczniki Prometheus
registry = CollectorRegistry()

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


# Słuchacze zdarzeń w locust, aktualizujące nasze liczniki
@events.request_success.add_listener
def on_request_success(request_type, name, response_time, response_length, **kwargs):
    # Zakładamy, że udane żądania mają kod 200
    REQUEST_SUCCESS_COUNTER.labels(
        method=request_type, name=name, response_code="200"
    ).inc()


@events.request_failure.add_listener
def on_request_failure(request_type, name, response_time, response_length, exception, **kwargs):
    # Porazki etykietujemy np. kodem "0"
    REQUEST_FAILURE_COUNTER.labels(
        method=request_type, name=name, response_code="0"
    ).inc()


class PracticeLoginScenario(TaskSet):
    @task
    def login_test(self):
        """
        Scenariusz logowania do Practice Test Automation:
          1. GET /practice-test-login/ - ładowanie strony logowania.
          2. Jeśli dane poprawne (USERNAME=="student" i PASSWORD=="Password123"):
             -> GET /logged-in-successfully/ i weryfikacja tekstu sukcesu.
             W przeciwnym razie generujemy event porażki.
          3. GET /practice-test-login/ - symulacja wylogowania.
        """
        # 1. Ładujemy stronę logowania
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

        # 2. Logika logowania
        if USERNAME == "student" and PASSWORD == "Password123":
            # Scenariusz pozytywny
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
            # Scenariusz negatywny
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

        # 3. Symulacja wylogowania
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


def push_metrics():
    """
    Funkcja do pushowania metryk do Pushgateway.
    """
    push_to_gateway("localhost:9091", job="locust_tests", registry=registry)


# Po starcie pliku wywołujemy push_metrics(), aby np. zainicjować stan.
push_metrics()
