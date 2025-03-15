const fs = require('fs');
const http = require('http');
const client = require('prom-client');

// Odczyt scenariusza z ENV: "positive", "negative" lub "generic"
const scenario = process.env.SCENARIO || 'generic';

// Konfiguracja rejestru metryk z domyślnymi etykietami
const registry = new client.Registry();
registry.setDefaultLabels({
  instance:
    scenario === 'positive'
      ? 'cypress_jenkins_positive'
      : scenario === 'negative'
        ? 'cypress_jenkins_negative'
        : 'cypress_jenkins'
});

// Definicja liczników w zależności od scenariusza
let TEST_PASSED_COUNTER;
let TEST_POSITIVE_UNEXPECTED_FAIL_COUNTER;
let TEST_FAILED_COUNTER;
let TEST_NEGATIVE_UNEXPECTED_PASS_COUNTER;

if (scenario === 'positive') {
  // Testy, które mają przejść – oczekujemy, że wynik "expectedPass" > 0, a "unexpectedFail" = 0
  TEST_PASSED_COUNTER = new client.Counter({
    name: 'cypress_test_passed_total',
    help: 'Total number of positive tests that passed as expected',
    registers: [registry],
  });
  TEST_POSITIVE_UNEXPECTED_FAIL_COUNTER = new client.Counter({
    name: 'cypress_test_positive_unexpected_fail_total',
    help: 'Total number of positive tests that unexpectedly failed',
    registers: [registry],
  });
} else if (scenario === 'negative') {
  // Testy, które mają sfailować – oczekujemy, że wynik "expectedFail" > 0, a "unexpectedPass" = 0
  TEST_FAILED_COUNTER = new client.Counter({
    name: 'cypress_test_failed_total',
    help: 'Total number of negative tests that failed as expected',
    registers: [registry],
  });
  TEST_NEGATIVE_UNEXPECTED_PASS_COUNTER = new client.Counter({
    name: 'cypress_test_negative_unexpected_pass_total',
    help: 'Total number of negative tests that unexpectedly passed',
    registers: [registry],
  });
} else {
  // Scenariusz generic – definiujemy wszystkie liczniki
  TEST_PASSED_COUNTER = new client.Counter({
    name: 'cypress_test_passed_total',
    help: 'Total number of positive tests that passed as expected',
    registers: [registry],
  });
  TEST_POSITIVE_UNEXPECTED_FAIL_COUNTER = new client.Counter({
    name: 'cypress_test_positive_unexpected_fail_total',
    help: 'Total number of positive tests that unexpectedly failed',
    registers: [registry],
  });
  TEST_FAILED_COUNTER = new client.Counter({
    name: 'cypress_test_failed_total',
    help: 'Total number of negative tests that failed as expected',
    registers: [registry],
  });
  TEST_NEGATIVE_UNEXPECTED_PASS_COUNTER = new client.Counter({
    name: 'cypress_test_negative_unexpected_pass_total',
    help: 'Total number of negative tests that unexpectedly passed',
    registers: [registry],
  });
}

// Funkcja zapisująca metryki do pliku
async function collectMetricsToFile(filePath) {
  try {
    console.log('>>> Writing metrics to file:', filePath);
    const metrics = await registry.metrics();
    fs.writeFileSync(filePath, metrics);
    console.log('✅ Metrics written to file:', filePath);
  } catch (err) {
    console.error('❌ Error writing metrics to file:', err);
  }
}

// Funkcja wyświetlająca metryki z pliku
function displayMetricsFromFile(filePath) {
  try {
    console.log('>>> Reading metrics from file:', filePath);
    const data = fs.readFileSync(filePath, 'utf8');
    console.log('✅ Metrics read from file:\n', data);
  } catch (err) {
    console.error('❌ Error reading metrics file:', err);
  }
}

// Funkcja pushująca metryki do Pushgateway
function pushMetricsFromFile(filePath, pushgatewayUrl, jobName, groupingKey) {
  try {
    console.log('>>> Pushing metrics from file:', filePath);
    console.log(`>>> Sending metrics to: ${pushgatewayUrl}`);
    if (!fs.existsSync(filePath)) {
      console.error('❌ Metrics file does not exist! Aborting push.');
      return;
    }
    const metricsData = fs.readFileSync(filePath, 'utf8');
    const url = new URL(pushgatewayUrl);
    let path = `/metrics/job/${jobName}`;
    if (groupingKey) {
      for (const key in groupingKey) {
        path += `/${encodeURIComponent(key)}/${encodeURIComponent(groupingKey[key])}`;
      }
    }
    const options = {
      hostname: url.hostname,
      port: url.port || 80,
      path: path,
      method: 'PUT',
      headers: {
        'Content-Type': 'text/plain',
        'Content-Length': Buffer.byteLength(metricsData),
      },
    };
    const req = http.request(options, (res) => {
      let responseData = '';
      res.on('data', (chunk) => {
        responseData += chunk;
      });
      res.on('end', () => {
        console.log('✅ Pushgateway response:', res.statusCode, responseData);
      });
    });
    req.on('error', (err) => {
      console.error('❌ Error pushing metrics:', err);
    });
    req.write(metricsData);
    req.end();
  } catch (err) {
    console.error('❌ Error during metrics push:', err);
  }
}

// Ustalanie jobName oraz instanceName na podstawie scenariusza
let jobName = 'cypress_tests';
let instanceName = 'cypress_jenkins';
if (scenario === 'negative') {
  jobName = 'cypress_tests_negative';
  instanceName = 'cypress_jenkins_negative';
} else if (scenario === 'positive') {
  jobName = 'cypress_tests_positive';
  instanceName = 'cypress_jenkins_positive';
}

// Funkcja odczytująca wyniki testów z pliku JSON.
// Plik "cypress_results.json" powinien być wygenerowany przez Cypress i zawierać odpowiednie pola:
// dla scenariusza "positive": { "expectedPass": <number>, "unexpectedFail": <number> }
// dla scenariusza "negative": { "expectedFail": <number>, "unexpectedPass": <number> }
// dla generic: wszystkie cztery.
function readResultsFromFile(filePath) {
  try {
    const data = fs.readFileSync(filePath, 'utf8');
    return JSON.parse(data);
  } catch (err) {
    console.error('❌ Error reading test results file:', err);
    return null;
  }
}

// Aktualizacja metryk na podstawie wyników testów
function updateMetricsFromResults(results) {
  if (scenario === 'positive') {
    TEST_PASSED_COUNTER.inc(results.expectedPass || 0);
    TEST_POSITIVE_UNEXPECTED_FAIL_COUNTER.inc(results.unexpectedFail || 0);
  } else if (scenario === 'negative') {
    TEST_FAILED_COUNTER.inc(results.expectedFail || 0);
    TEST_NEGATIVE_UNEXPECTED_PASS_COUNTER.inc(results.unexpectedPass || 0);
  } else {
    TEST_PASSED_COUNTER.inc(results.expectedPass || 0);
    TEST_POSITIVE_UNEXPECTED_FAIL_COUNTER.inc(results.unexpectedFail || 0);
    TEST_FAILED_COUNTER.inc(results.expectedFail || 0);
    TEST_NEGATIVE_UNEXPECTED_PASS_COUNTER.inc(results.unexpectedPass || 0);
  }
}

// Główna funkcja: odczytuje wyniki, aktualizuje liczniki, zapisuje metryki do pliku, wyświetla je i pushuje do Pushgateway.
(async () => {
  console.log('>>> Updating Cypress metrics based on test results...');
  const resultsFile = '../results/cypress_results.json';
  const results = readResultsFromFile(resultsFile);
  if (results) {
    updateMetricsFromResults(results);
  } else {
    console.error('❌ No test results – metrics not updated.');
  }

  const filePath =
    scenario === 'positive'
      ? 'cypress_metrics_positive.txt'
      : scenario === 'negative'
        ? 'cypress_metrics_negative.txt'
        : 'cypress_metrics.txt';

  const pushgatewayUrl = process.env.PUSHGATEWAY_ADDRESS || 'http://localhost:9091';
  await collectMetricsToFile(filePath);
  displayMetricsFromFile(filePath);
  pushMetricsFromFile(filePath, pushgatewayUrl, jobName, { instance: instanceName });
})();
