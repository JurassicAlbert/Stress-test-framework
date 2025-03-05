const express = require('express');
const client = require('prom-client');
const app = express();
const port = process.env.METRICS_PORT || 3100;

// Tworzymy własny rejestr metryk
const registry = new client.Registry();

// Ustaw domyślne etykiety oraz zbieraj domyślne metryki
registry.setDefaultLabels({ instance: 'cypress_jenkins' });
client.collectDefaultMetrics({ register: registry });

// Zdefiniuj niestandardowe liczniki
const testSuccessCounter = new client.Counter({
  name: 'cypress_test_success_total',
  help: 'Total number of successful Cypress tests',
  registers: [registry],
});
const testFailureCounter = new client.Counter({
  name: 'cypress_test_failure_total',
  help: 'Total number of failed Cypress tests',
  registers: [registry],
});
const performancePositiveCounter = new client.Counter({
  name: 'cypress_positive_performance_failures_total',
  help: 'Total number of positive tests that exceeded the expected duration threshold',
  registers: [registry],
});
const performanceNegativeCounter = new client.Counter({
  name: 'cypress_negative_performance_unexpected_pass_total',
  help: 'Total number of negative tests that unexpectedly passed or had a very short duration',
  registers: [registry],
});

// Inicjalizacja liczników
testSuccessCounter.inc(0);
testFailureCounter.inc(0);
performancePositiveCounter.inc(0);
performanceNegativeCounter.inc(0);

// Definicja histogramu dla czasów testów
const testDurationHistogram = new client.Histogram({
  name: 'cypress_test_duration_seconds',
  help: 'Histogram of test durations in seconds',
  buckets: [0.1, 0.3, 1.5, 10.0],
  registers: [registry],
});

// Funkcja pluginu Cypress (np. w pliku plugins/index.js)
module.exports = (on, config) => {
  on('after:run', async (results) => {
    if (results) {
      testSuccessCounter.inc(results.totalPassed);
      testFailureCounter.inc(results.totalFailed);
      let positivePerfIssues = 0;
      let negativePerfIssues = 0;
      if (results.runs && Array.isArray(results.runs)) {
        results.runs.forEach(run => {
          const duration = run.duration || 0;
          // Rejestracja czasu testu (konwersja z milisekund na sekundy)
          testDurationHistogram.observe(duration / 1000);
          const isPositive = (process.env.LOGIN === 'student' && process.env.PASSWORD === 'Password123');
          if (isPositive) {
            if (duration > 4000) {
              positivePerfIssues++;
            }
          } else {
            if (run.state === 'passed' || duration < 1000) {
              negativePerfIssues++;
            }
          }
        });
      }
      performancePositiveCounter.inc(positivePerfIssues);
      performanceNegativeCounter.inc(negativePerfIssues);
    }
    return config;
  });
};

// Uruchomienie serwera metryk
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', registry.contentType);
  res.end(await registry.metrics());
});

app.listen(port, () => {
  console.log(`Cypress metrics server is running on port ${port}`);
});