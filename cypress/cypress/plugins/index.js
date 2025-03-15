const fs = require('fs');
const http = require('http');
const client = require('prom-client');

// Odczyt scenariusza z ENV, np. "negative", "positive" lub brak
const scenario = process.env.SCENARIO || 'generic';

// Konfiguracja rejestru metryk
const registry = new client.Registry();
registry.setDefaultLabels({ instance: 'cypress_jenkins' });
// Przechwyć funkcję do czyszczenia interwału zbierania metryk
const clearMetricsInterval = client.collectDefaultMetrics({ register: registry });

// Definicja liczników oraz histogramu
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

const testDurationHistogram = new client.Histogram({
    name: 'cypress_test_duration_seconds',
    help: 'Histogram of test durations in seconds',
    buckets: [0.1, 0.3, 1.5, 10.0],
    registers: [registry],
});

// Funkcja zapisująca metryki do pliku
async function collectMetricsToFile(filePath) {
    try {
        console.log('>>> Próba zapisu metryk do pliku:', filePath);
        const metrics = await registry.metrics();
        fs.writeFileSync(filePath, metrics);
        console.log('✅ Metryki zapisane do pliku:', filePath);

        // Sprawdzenie, czy plik istnieje
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

// Ustalanie jobName i instanceName w zależności od scenariusza
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
// Format pliku JSON powinien być następujący:
// {
//   "success": <number>,
//   "failure": <number>,
//   "duration": <number>,
//   "performancePositive": <number>,
//   "performanceNegative": <number>
// }
function updateMetricsFromResults(results) {
    testSuccessCounter.inc(results.success);
    testFailureCounter.inc(results.failure);
    testDurationHistogram.observe(results.duration);
    performancePositiveCounter.inc(results.performancePositive);
    performanceNegativeCounter.inc(results.performanceNegative);
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

(async () => {
    console.log('>>> Aktualizacja liczników Cypress na podstawie wyników testów...');
    const resultsFile = 'cypress_results.json';
    const results = readResultsFromFile(resultsFile);
    if (results) {
        updateMetricsFromResults(results);
    } else {
        console.error('❌ Brak wyników testów – metryki nie zostały zaktualizowane.');
    }

    const filePath = 'cypress_metrics.txt';
    const pushgatewayUrl = process.env.PUSHGATEWAY_ADDRESS || 'http://localhost:9091';

    await collectMetricsToFile(filePath);
    displayMetricsFromFile(filePath);

    // Push z uwzględnieniem jobName i instanceName
    pushMetricsFromFile(filePath, pushgatewayUrl, jobName, { instance: instanceName });

    // Czyszczenie interwału, aby proces zakończył się szybciej
    clearInterval(clearMetricsInterval);
})();
