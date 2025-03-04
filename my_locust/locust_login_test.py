#!/usr/bin/env python3
"""
locust_login_test.py

This file runs a login test repeatedly using Locust and records Prometheus metrics.
It measures:
  - The number of successful and failed requests.
  - (Metrics are updated via an event listener on events.request.)

At the end, push_metrics() is called to push the metrics to the Prometheus Pushgateway.
"""

import os
from locust import HttpUser, TaskSet, task, between, events
from prometheus_client import CollectorRegistry, Counter, push_to_gateway, REGISTRY
from colorama import init

# Initialize colorama
init(autoreset=True)

# Default host and login credentials (from environment variables)
LOCUST_HOST = os.getenv("LOCUST_HOST", "https://practicetestautomation.com")
USERNAME = os.getenv("LOCUST_USERNAME", "student")
PASSWORD = os.getenv("LOCUST_PASSWORD", "Password123")

# Header simulating a browser – DO NOT CHANGE
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/132.0.0.0 Safari/537.36"
    )
}

# Tworzymy własny rejestr – nie rejestrujemy domyślnych kolektorów
registry = CollectorRegistry(auto_describe=False)

# Usuń wszystkie domyślne kolektory z globalnego rejestru, aby nie były zbierane
for collector in list(REGISTRY._collector_to_names.keys()):
    try:
        REGISTRY.unregister(collector)
    except Exception as e:
        print("Nie udało się odczepić kolektora:", e)

# Definiujemy własne liczniki z etykietami stałymi ("instance")
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


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    if exception is None:
        REQUEST_SUCCESS_COUNTER.labels(method=request_type, name=name, response_code="200").inc()
    else:
        REQUEST_FAILURE_COUNTER.labels(method=request_type, name=name, response_code="0").inc()


class PracticeLoginScenario(TaskSet):
    @task
    def login_test(self):
        # 1. Load the login page.
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

        # 2. Attempt login.
        if USERNAME == "student" and PASSWORD == "Password123":
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
            error_msg = "Your username is invalid!" if USERNAME != "student" else "Your password is invalid!"
            self.environment.events.request.fire(
                request_type="GET",
                name="Login Attempt",
                response_time=0,
                response_length=0,
                exception=Exception(error_msg)
            )

        # 3. Logout/reset.
        with self.client.get(
                "/practice-test-login/",
                headers=HEADERS,
                catch_response=True,
                name="Logout/Reset"
        ) as logout_resp:
            if logout_resp.status_code == 200:
                logout_resp.success()
            else:
                logout_resp.failure(f"Failed to reset. Code: {logout_resp.status_code}")


class WebsiteUser(HttpUser):
    host = LOCUST_HOST
    tasks = [PracticeLoginScenario]
    wait_time = between(1, 3)


def push_metrics():
    """
    Push the collected metrics to the Prometheus Pushgateway.
    """
    try:
        push_to_gateway("http://localhost:9091", job="locust_tests", registry=registry,
                        grouping_key={"instance": "locust_jenkins"})
        print("Metrics pushed successfully to Pushgateway")
    except Exception as e:
        print("Error pushing metrics to Pushgateway:", e)


# Push metrics once at startup (for initialization purposes)
push_metrics()
