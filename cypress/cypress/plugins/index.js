const client = require('prom-client');
const {Pushgateway} = client;

// Upewnij się, że adres zawiera protokół "http://"
const pushgatewayAddress = process.env.PUSHGATEWAY_ADDRESS || 'http://localhost:9091';
const pushgateway = new Pushgateway(pushgatewayAddress);

// Utwórz dedykowaną rejestrację i zbierz domyślne metryki
const registry = new client.Registry();
client.collectDefaultMetrics({register: registry});

// Zdefiniuj niestandardowe liczniki dla metryk Cypress
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
    help: 'Total number of positive tests (with correct credentials) that exceeded the expected duration threshold',
    registers: [registry],
});

const performanceNegativeCounter = new client.Counter({
    name: 'cypress_negative_performance_unexpected_pass_total',
    help: 'Total number of negative tests (with invalid credentials) that unexpectedly passed or had a very short duration',
    registers: [registry],
});

// Inicjalizacja liczników, aby były widoczne z wartością 0
testSuccessCounter.inc(0);
testFailureCounter.inc(0);
performancePositiveCounter.inc(0);
performanceNegativeCounter.inc(0);

module.exports = (on, config) => {
    on('after:run', async (results) => {
        if (results) {
            // Aktualizuj liczniki w oparciu o wyniki testów
            testSuccessCounter.inc(results.totalPassed);
            testFailureCounter.inc(results.totalFailed);

            let positivePerfIssues = 0;
            let negativePerfIssues = 0;

            if (results.runs && Array.isArray(results.runs)) {
                results.runs.forEach(run => {
                    const duration = run.duration || 0;
                    const isPositive = (process.env.LOGIN === 'student' && process.env.PASSWORD === 'Password123');

                    if (isPositive) {
                        if (duration > 4000) { // Próg dla pozytywnych testów
                            positivePerfIssues++;
                        }
                    } else {
                        if (run.state === 'passed' || duration < 1000) { // Próg dla negatywnych testów
                            negativePerfIssues++;
                        }
                    }
                });
            }
            performancePositiveCounter.inc(positivePerfIssues);
            performanceNegativeCounter.inc(negativePerfIssues);
        }

        console.log(`Pushing metrics to Pushgateway at ${pushgatewayAddress}`);
        try {
            const metricsData = await registry.metrics();
            console.log('Metrics data:', metricsData);
        } catch (err) {
            console.warn('Error fetching metrics data:', err);
        }

        // Użyj metody push, aby nadpisać poprzednie metryki
        pushgateway.push({jobName: 'cypress_tests'}, (err, resp, body) => {
            if (err) {
                console.error('Error pushing metrics at', new Date().toISOString(), err);
            } else {
                console.log('Successfully pushed metrics at', new Date().toISOString());
            }
        });
    });

    return config;
};