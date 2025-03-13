#!/usr/bin/env python3
"""
locust_login_test.py
Requires: pip install psutil
"""

import os
import time
import threading
import psutil
from locust import HttpUser, TaskSet, task, between, events
from prometheus_client import (
    CollectorRegistry, Counter, Histogram, Gauge,
    push_to_gateway, generate_latest, REGISTRY
)
from colorama import init

init(autoreset=True)

LOCUST_HOST = os.getenv("LOCUST_HOST", "https://practicetestautomation.com")
USERNAME = os.getenv("LOCUST_USERNAME", "student")
PASSWORD = os.getenv("LOCUST_PASSWORD", "Password123")
PUSHGATEWAY_ADDRESS = os.getenv("PUSHGATEWAY_ADDRESS", "http://localhost:9091").rstrip("/")

print(f"LOCUST_HOST: {LOCUST_HOST}")
print(f"PUSHGATEWAY_ADDRESS: {PUSHGATEWAY_ADDRESS}")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/132.0.0.0 Safari/537.36")
}

registry = CollectorRegistry(auto_describe=False)
for collector in list(REGISTRY._collector_to_names.keys()):
    try:
        REGISTRY.unregister(collector)
    except Exception as e:
        print(f"Collector unregister error: {e}")

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
    ["instance"],
    buckets=[0.1, 0.3, 1.5, 10.0],
    registry=registry
)
LOCUST_CPU_USAGE_GAUGE = Gauge(
    "locust_cpu_usage_percent",
    "CPU usage of the Locust process (percent)",
    ["instance"],
    registry=registry
)
LOCUST_MEMORY_USAGE_GAUGE = Gauge(
    "locust_memory_usage_bytes",
    "Memory usage of the Locust process (in bytes)",
    ["instance"],
    registry=registry
)

def collect_metrics_to_file(file_path):
    try:
        metrics_data = generate_latest(registry).decode('utf-8')
        with open(file_path, 'w') as f:
            f.write(metrics_data)
    except Exception as e:
        print(f"Error collecting metrics: {e}")

def push_metrics_from_file(file_path):
    try:
        if not os.path.exists(file_path):
            print(f"File {file_path} does not exist.")
            return
        with open(file_path, 'r') as f:
            print(f.read())
        push_to_gateway(
            PUSHGATEWAY_ADDRESS,
            job="locust_tests",
            grouping_key={"instance": "locust_jenkins"},
            registry=registry
        )
    except Exception as e:
        print(f"Error pushing metrics: {e}")

def update_cpu_ram_metrics():
    process = psutil.Process(os.getpid())
    cpu_percent = process.cpu_percent(interval=None)
    memory_usage = process.memory_info().rss
    LOCUST_CPU_USAGE_GAUGE.labels(instance="locust_jenkins").set(cpu_percent)
    LOCUST_MEMORY_USAGE_GAUGE.labels(instance="locust_jenkins").set(memory_usage)

stop_event = threading.Event()
def cpu_ram_monitor():
    while not stop_event.is_set():
        update_cpu_ram_metrics()
        time.sleep(1)

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    global monitor_thread
    monitor_thread = threading.Thread(target=cpu_ram_monitor)
    monitor_thread.daemon = True
    monitor_thread.start()

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
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
        with self.client.get("/practice-test-login/", headers=HEADERS, catch_response=True, name="Load Login Page") as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Failed to load login page. Code: {resp.status_code}")
                return
        with self.client.get("/logged-in-successfully/", headers=HEADERS, catch_response=True, name="After Login Redirect") as r:
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
    stop_event.set()
    monitor_thread.join()
    file_path = "locust_metrics.txt"
    collect_metrics_to_file(file_path)
    push_metrics_from_file(file_path)
