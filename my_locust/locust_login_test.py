#!/usr/bin/env python3
"""
locust_login_test.py

This file runs a login test repeatedly using Locust and records Prometheus metrics.
Metrics are collected to a file, displayed in the console, and then pushed to Pushgateway.
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
PUSHGATEWAY_ADDRESS = os.getenv("PUSHGATEWAY_ADDRESS", "http://localhost:9091").rstrip("/")

# Debugowanie zmiennych środowiskowych
print(f"🔍 LOCUST_HOST: {LOCUST_HOST}")
print(f"🔍 PUSHGATEWAY_ADDRESS: {PUSHGATEWAY_ADDRESS}")

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

# Odczepienie domyślnych kolektorów Prometheus
for collector in list(REGISTRY._collector_to_names.keys()):
    try:
        REGISTRY.unregister(collector)
    except Exception as e:
        print(f"⚠️ Nie udało się odczepić kolektora: {e}")

# Definicja liczników i histogramu (bez const_labels!)
REQUEST_SUCCESS_COUNTER = Counter(
    "locust_request_success_total",
    "Total successful requests",
    ["method", "name", "response_code", "instance"],
    registry=registry
)

REQUEST_FAILURE_COUNTER = Counter(
    "locust_request_failure_total",
    "Total failed requests",
    ["method", "name", "response_code", "instance"],
    registry=registry
)

REQUEST_DURATION_HISTOGRAM = Histogram(
    "locust_request_duration_seconds",
    "Histogram of request durations in seconds",
    ["instance"],   # Możesz dodać też np. ["instance","method","name"] jeśli chcesz bardziej szczegółowe metryki
    buckets=[0.1, 0.3, 1.5, 10.0],
    registry=registry
)

# Funkcja do zbierania metryk i zapisu do pliku
def collect_metrics_to_file(file_path):
    try:
        print(f"🔍 Próba zapisu metryk do pliku: {file_path}")
        metrics_data = generate_latest(registry).decode('utf-8')
        print(f"📊 Metryki do zapisania:\n{metrics_data}")

        with open(file_path, 'w') as f:
            f.write(metrics_data)
        print(f"✅ Metryki zapisane do pliku: {file_path}")
    except Exception as e:
        print(f"❌ Błąd przy zbieraniu metryk: {e}")

# Funkcje do pushowania metryk
def push_metrics_from_file(file_path):
    try:
        print(f"Sprawdzam, czy plik metryk istnieje: {file_path}")
        if not os.path.exists(file_path):
            print(f"❌ Plik {file_path} nie istnieje, pushowanie anulowane.")
            return

        print(f"Wyświetlam zawartość pliku metryk przed pushowaniem:")
        with open(file_path, 'r') as f:
            print(f.read())

        push_to_gateway(
            PUSHGATEWAY_ADDRESS,
            job="locust_tests",
            grouping_key={"instance": "locust_jenkins"},
            registry=registry
        )
        print(f"✅ Metryki spushowane do Pushgateway: {PUSHGATEWAY_ADDRESS}")
    except Exception as e:
        print(f"❌ Błąd przy pushowaniu metryk: {e}")

# Listener dla każdego żądania
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    # Najpierw rejestrujemy czas trwania (tu, tylko per 'instance'),
    # ale w razie potrzeby możesz dodać 'request_type' lub 'name' do etykiet.
    REQUEST_DURATION_HISTOGRAM.labels(instance="locust_jenkins").observe(response_time / 1000)

    if exception is None:
        REQUEST_SUCCESS_COUNTER.labels(
            method=request_type,
            name=name,
            response_code="200",
            instance="locust_jenkins"
        ).inc()
    else:
        REQUEST_FAILURE_COUNTER.labels(
            method=request_type,
            name=name,
            response_code="0",
            instance="locust_jenkins"
        ).inc()

class PracticeLoginScenario(TaskSet):
    @task
    def login_test(self):
        with self.client.get("/practice-test-login/", headers=HEADERS, catch_response=True,
                             name="Load Login Page") as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Failed to load login page. Code: {resp.status_code}")
                return

        with self.client.get("/logged-in-successfully/", headers=HEADERS, catch_response=True,
                             name="After Login Redirect") as r:
            if r.status_code == 200 and ("Logged In Successfully" in r.text or "Congratulations" in r.text):
                r.success()
            else:
                r.failure(f"Unexpected login result. Code: {r.status_code}")

class WebsiteUser(HttpUser):
    host = LOCUST_HOST
    tasks = [PracticeLoginScenario]
    wait_time = between(1, 3)

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    file_path = "locust_metrics.txt"
    collect_metrics_to_file(file_path)
    push_metrics_from_file(file_path)
