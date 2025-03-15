// index.js

const fs = require('fs');
const http = require('http');
const client = require('prom-client');

// Odczyt scenariusza z ENV, np. "negative", "positive" lub inny (generic)
const scenario = process.env.SCENARIO || 'generic';

// Konfiguracja rejestru metryk z domyślnymi etykietami
const registry = new client.Registry();
registry.setDefaultLabels({
  instance: scenario === 'positive'
    ? 'cypress_jenkins_positive'
    : scenario === 'negative'
      ? 'cypress_jenkins_negative'
      : 'cypress_jenkins'
});

// Definicja liczników – w zależności od scenariusza
let TEST_PASSED_COUNTER;
let TEST_POSITIVE_UNEXPECTED_FAIL_COUNTER;
let TEST_FAILED_COUNTER;
let TEST_NEGATIVE_UNEXPECTED_PASS_COUNTER;

if (scenario === 'positive') {
  // Dla testów, które powinny przejść – nie potrzebujemy metryk dla negatywnych
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
  // Dla testów, które powinny failować – nie potrzebujemy metryki dla sukcesów
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
  // W przypadku scenariusza ogólnego – definiujemy wszystkie metryki
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
    console.log('>>> Próba zapisu metryk do pliku:', filePath);
    const metrics = await registry.metrics();
    fs.writeFileSync(filePath, metrics);
    console.log('✅ Metryki zapisane do pliku:', filePath);
    if (fs.existsSync(filePath)) {
      console.log('✅ Plik metryk istnieje:', filePath);
    } else {
      console.error('❌ Plik metryk NIE został utworzony!');
    }
  } catch (err) {
    console.error('❌ Błąd przy zapisywaniu metryk do pliku:', err);
  }
}

// Funkcja wyświetlająca metryki z pliku w konsoli
function displayMetricsFromFile(filePath) {
  try {
    console.log('>>> Próba odczytu metryk z pliku:', filePath);
    const data = fs.readFileSync(filePath, 'utf8');
    console.log('✅ Metryki odczytane z pliku:\n', data);
  } catch (err) {
    console.error('❌ Błąd przy odczycie pliku z metrykami:', err);
  }
}

// Funkcja pushująca metryki do Pushgateway
function pushMetricsFromFile(filePath, pushgatewayUrl, jobName, groupingKey) {
  try {
    console.log('>>> Próba pushowania metryk z pliku:', filePath);
    console.log(`>>> Wysyłanie metryk do: ${pushgatewayUrl}`);
    if (!fs.existsSync(filePath)) {
      console.error('❌ Plik metryk nie istnieje! Pushowanie anulowane.');
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
        console.log('✅ Odpowiedź Pushgateway:', res.statusCode, responseData);
      });
    });
    req.on('error', (err) => {
      console.error('❌ Błąd przy wysyłaniu metryk:', err);
    });
    req.write(metricsData);
    req.end();
  } catch (err) {
    console.error('❌ Błąd przy odczycie pliku z metrykami do wysyłki:', err);
  }
}

// Ustalanie jobName oraz instanceName w zależności od scenariusza
let jobName = 'cypress_tests';
let instanceName = 'cypress_jenkins';
if (scenario === 'negative') {
  jobName = 'cypress_tests_negative';
  instanceName = 'cypress_jenkins_negative';
} else if (scenario === 'positive') {
  jobName = 'cypress_tests_positive';
  instanceName = 'cypress_jenkins_positive';
}

// Aktualizacja metryk na podstawie wyników testów
// Zakładamy, że wyniki testów są zapisane w pliku 'cypress_results.json'
// Dla scenariusza pozytywnego oczekujemy formatu:
// {
//   "expectedPass": <number>,
//   "unexpectedFail": <number>
// }
// Dla scenariusza negatywnego:
// {
//   "expectedFail": <number>,
//   "unexpectedPass": <number>
// }
// W scenariuszu generic aktualizowane są wszystkie cztery metryki.
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

// Funkcja odczytująca wyniki testów z pliku JSON
function readResultsFromFile(filePath) {
  try {
    const data = fs.readFileSync(filePath, 'utf8');
    return JSON.parse(data);
  } catch (err) {
    console.error('❌ Błąd przy odczycie wyników testów z pliku:', err);
    return null;
  }
}

// Główna funkcja – aktualizuje metryki, zapisuje je do pliku, wyświetla oraz pushuje do Pushgateway
(async () => {
  console.log('>>> Aktualizacja liczników Cypress na podstawie wyników testów...');
  const resultsFile = 'cypress_results.json';
  const results = readResultsFromFile(resultsFile);
  if (results) {
    updateMetricsFromResults(results);
  } else {
    console.error('❌ Brak wyników testów – metryki nie zostały zaktualizowane.');
  }

  // Wybór pliku metryk w zależności od scenariusza
  const filePath = scenario === 'positive'
    ? 'cypress_metrics_positive.txt'
    : scenario === 'negative'
      ? 'cypress_metrics_negative.txt'
      : 'cypress_metrics.txt';

  const pushgatewayUrl = process.env.PUSHGATEWAY_ADDRESS || 'http://localhost:9091';
  await collectMetricsToFile(filePath);
  displayMetricsFromFile(filePath);
  pushMetricsFromFile(filePath, pushgatewayUrl, jobName, { instance: instanceName });
})();
