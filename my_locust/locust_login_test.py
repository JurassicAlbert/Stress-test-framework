#!/usr/bin/env python3
"""
locust_login_test.py

This file runs a login test repeatedly using Locust and records Prometheus metrics.
Instead of exposing metrics via an HTTP server, metrics are collected to a file,
displayed in the console, and then pushed to Pushgateway.
"""

import os
from locust import HttpUser, TaskSet, task, between, events
from prometheus_client import (
    CollectorRegistry, Counter, Histogram, push_to_gateway, generate_latest, REGISTRY
)
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


# Funkcje do zbierania, wyświetlania i pushowania metryk
def collect_metrics_to_file(file_path):
    """
    Generuje metryki z rejestru, zapisuje je do pliku
    oraz wypisuje zawartość pliku w konsoli.
    """
    try:
        print(f">>> Próba zapisu metryk do pliku: {file_path}")
        metrics_data = generate_latest(registry).decode('utf-8')
        with open(file_path, 'w') as f:
            f.write(metrics_data)
        print(f"✅ Metryki zapisane do pliku: {file_path}")

        if os.path.exists(file_path):
            print(f"✅ Plik metryk istnieje: {file_path}")
        else:
            print(f"❌ Plik metryk NIE został utworzony!")

    except Exception as e:
        print(f"❌ Błąd przy zbieraniu metryk: {e}")


def push_metrics_from_file(file_path):
    """
    Odczytuje metryki z pliku i pushuje je do Pushgateway.
    """
    try:
        if not os.path.exists(file_path):
            print(f"❌ Plik {file_path} nie istnieje, pushowanie anulowane.")
            return

        pushgateway_address = os.getenv("PUSHGATEWAY_ADDRESS", "http://localhost:9091")
        print(f">>> Próba pushowania metryk do {pushgateway_address} z pliku: {file_path}")

        push_to_gateway(
            pushgateway_address,
            job="locust_tests",
            grouping_key={"instance": "locust_jenkins"},
            registry=registry
        )
        print(f"✅ Metryki spushowane do Pushgateway: {pushgateway_address}")
    except Exception as e:
        print(f"❌ Błąd przy pushowaniu metryk: {e}")


def collect_and_push_metrics():
    """
    Zbiera metryki, zapisuje je do pliku, wyświetla i pushuje do Pushgateway.
    """
    file_path = "locust_metrics.txt"
    collect_metrics_to_file(file_path)
    push_metrics_from_file(file_path)


# Listener dla każdego żądania - rejestruje metryki
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """
    Obsługuje metryki dla każdego requesta.
    """
    print(f">>> Rejestrowanie żądania: {request_type} - {name}")
    REQUEST_DURATION_HISTOGRAM.observe(response_time / 1000)

    if exception is None:
        REQUEST_SUCCESS_COUNTER.labels(method=request_type, name=name, response_code="200").inc()
    else:
        REQUEST_FAILURE_COUNTER.labels(method=request_type, name=name, response_code="0").inc()


class PracticeLoginScenario(TaskSet):
    @task
    def login_test(self):
        print(">>> Rozpoczynam test logowania...")

        # 1. Load the login page.
        with self.client.get("/practice-test-login/", headers=HEADERS, catch_response=True,
                             name="Load Login Page") as resp:
            if resp.status_code == 200:
                print("✅ Login page loaded successfully.")
                resp.success()
            else:
                print(f"❌ Failed to load login page. Code: {resp.status_code}")
                resp.failure(f"Failed to load login page. Code: {resp.status_code}")
                return

        # 2. Attempt login.
        if USERNAME == "student" and PASSWORD == "Password123":
            with self.client.get("/logged-in-successfully/", headers=HEADERS, catch_response=True,
                                 name="After Login Redirect") as r:
                if r.status_code == 200 and ("Logged In Successfully" in r.text or "Congratulations" in r.text):
                    print("✅ Login successful!")
                    r.success()
                else:
                    print(f"❌ Unexpected login result. Code: {r.status_code}")
                    r.failure(f"Unexpected login result. Code: {r.status_code}")
        else:
            error_msg = "Your username is invalid!" if USERNAME != "student" else "Your password is invalid!"
            print(f"❌ Login failed: {error_msg}")
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
                print("✅ Logout/reset successful.")
                logout_resp.success()
            else:
                print(f"❌ Failed to reset. Code: {logout_resp.status_code}")
                logout_resp.failure(f"Failed to reset. Code: {logout_resp.status_code}")


class WebsiteUser(HttpUser):
    host = LOCUST_HOST
    tasks = [PracticeLoginScenario]
    wait_time = between(1, 3)


# Listener, który po zakończeniu testów (gdy pipeline kończy Locusta) zbiera i pushuje metryki
@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print(">>> Testy zakończone. Zbieramy i pushujemy metryki...")
    collect_and_push_metrics()
