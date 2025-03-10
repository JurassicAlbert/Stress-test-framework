const fs = require('fs');
const http = require('http');
const client = require('prom-client');

// Konfiguracja rejestru metryk
const registry = new client.Registry();
registry.setDefaultLabels({ instance: 'cypress_jenkins' });
client.collectDefaultMetrics({ register: registry });

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

// Inicjalizacja liczników
testSuccessCounter.inc(0);
testFailureCounter.inc(0);
performancePositiveCounter.inc(0);
performanceNegativeCounter.inc(0);

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

// Symulacja aktualizacji metryk, zapis, wyświetlenie i push do Pushgateway
(async () => {
    console.log('>>> Aktualizacja liczników Cypress...');
    testSuccessCounter.inc(3);
    testFailureCounter.inc(1);
    testDurationHistogram.observe(2.34);
    performancePositiveCounter.inc(1);
    performanceNegativeCounter.inc(0);

    const filePath = 'cypress_metrics.txt';
    const pushgatewayUrl = process.env.PUSHGATEWAY_ADDRESS || 'http://localhost:9091';
    const jobName = 'cypress_tests';
    const groupingKey = { instance: 'cypress_jenkins' };

    await collectMetricsToFile(filePath);
    displayMetricsFromFile(filePath);
    pushMetricsFromFile(filePath, pushgatewayUrl, jobName, groupingKey);
})();
