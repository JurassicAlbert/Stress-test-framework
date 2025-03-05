#!/usr/bin/env python3
"""
locust_login_test.py

This file runs a login test repeatedly using Locust and records Prometheus metrics.
Instead of pushing metrics to Pushgateway, metrics are now exposed directly via an HTTP server.
"""

import os
from locust import HttpUser, TaskSet, task, between, events
from prometheus_client import CollectorRegistry, Counter, Histogram, start_http_server, REGISTRY
from colorama import init

# Initialize colorama
init(autoreset=True)

# Ustawienia hosta i danych logowania
LOCUST_HOST = os.getenv("LOCUST_HOST", "https://practicetestautomation.com")
USERNAME = os.getenv("LOCUST_USERNAME", "student")
PASSWORD = os.getenv("LOCUST_PASSWORD", "Password123")

# Nagłówki symulujące przeglądarkę
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/132.0.0.0 Safari/537.36"
    )
}

# Utwórz własny rejestr metryk
registry = CollectorRegistry(auto_describe=False)

# Odczepienie domyślnych kolektorów
for collector in list(REGISTRY._collector_to_names.keys()):
    try:
        REGISTRY.unregister(collector)
    except Exception as e:
        print("Nie udało się odczepić kolektora:", e)

# Definicja liczników z etykietami stałymi
REQUEST_SUCCESS_COUNTER = Counter(
    "locust_request_success_total",
    "Total successful requests",
    ["method", "name", "response_code"],
    registry=registry,
    const_labels={"instance": "locust_jenkins"}
)
REQUEST_SUCCESS_COUNTER.inc(0)

REQUEST_FAILURE_COUNTER = Counter(
    "locust_request_failure_total",
    "Total failed requests",
    ["method", "name", "response_code"],
    registry=registry,
    const_labels={"instance": "locust_jenkins"}
)
REQUEST_FAILURE_COUNTER.inc(0)

# Definicja histogramu dla czasów odpowiedzi
REQUEST_DURATION_HISTOGRAM = Histogram(
    "locust_request_duration_seconds",
    "Histogram of request durations in seconds",
    buckets=[0.1, 0.3, 1.5, 10.0],
    registry=registry,
    const_labels={"instance": "locust_jenkins"}
)

# Uruchomienie serwera metryk podczas inicjalizacji Locusta
@events.init.add_listener
def on_locust_init(environment, **kwargs):
    port = int(os.getenv("METRICS_PORT", "5000"))
    start_http_server(port, registry=registry)
    print(f"Locust metrics server is running on port {port}")

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    # Rejestracja czasu trwania (przeliczamy ms na sekundy)
    REQUEST_DURATION_HISTOGRAM.observe(response_time / 1000)
    if exception is None:
        REQUEST_SUCCESS_COUNTER.labels(method=request_type, name=name, response_code="200").inc()
    else:
        REQUEST_FAILURE_COUNTER.labels(method=request_type, name=name, response_code="0").inc()

class PracticeLoginScenario(TaskSet):
    @task
    def login_test(self):
        # 1. Load the login page.
        with self.client.get("/practice-test-login/", headers=HEADERS, catch_response=True,
                               name="Load Login Page") as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Failed to load login page. Code: {resp.status_code}")
                return

        # 2. Attempt login.
        if USERNAME == "student" and PASSWORD == "Password123":
            with self.client.get("/logged-in-successfully/", headers=HEADERS, catch_response=True,
                                   name="After Login Redirect") as r:
                if r.status_code == 200 and ("Logged In Successfully" in r.text or "Congratulations" in r.text):
                    r.success()
                else:
                    r.failure(f"Unexpected login result. Code: {r.status_code}")
        else:
            error_msg = "Your username is invalid!" if USERNAME != "student" else "Your password is invalid!"
            self.environment.events.request.fire(
                request_type="GET",
                name="Login Attempt",
                response_time=0,
                response_length=0,
                exception=Exception(error_msg)
            )

        # 3. Logout/reset.
        with self.client.get("/practice-test-login/", headers=HEADERS, catch_response=True,
                               name="Logout/Reset") as logout_resp:
            if logout_resp.status_code == 200:
                logout_resp.success()
            else:
                logout_resp.failure(f"Failed to reset. Code: {logout_resp.status_code}")

class WebsiteUser(HttpUser):
    host = LOCUST_HOST
    tasks = [PracticeLoginScenario]
    wait_time = between(1, 3)
