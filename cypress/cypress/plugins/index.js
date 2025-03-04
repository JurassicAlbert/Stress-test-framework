const client = require('prom-client');
const {Pushgateway} = client;

const pushgatewayAddress = process.env.PUSHGATEWAY_ADDRESS || 'http://localhost:9091';
const registry = new client.Registry();

// Ustaw domyślne etykiety dla rejestru
registry.setDefaultLabels({instance: 'cypress_jenkins'});

client.collectDefaultMetrics({register: registry});

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

// Inicjalizacja liczników, aby były widoczne z wartością 0
testSuccessCounter.inc(0);
testFailureCounter.inc(0);
performancePositiveCounter.inc(0);
performanceNegativeCounter.inc(0);

module.exports = (on, config) => {
    on('after:run', async (results) => {
        // Loguj wyniki testów dla diagnostyki
        console.log("Test results:", results);
        console.log("Test results (JSON):", JSON.stringify(results, null, 2));

        if (results) {
            // Upewnij się, że results zawiera oczekiwane pola (dostosuj nazwy jeśli to konieczne)
            testSuccessCounter.inc(results.totalPassed);
            testFailureCounter.inc(results.totalFailed);

            let positivePerfIssues = 0;
            let negativePerfIssues = 0;

            if (results.runs && Array.isArray(results.runs)) {
                results.runs.forEach(run => {
                    const duration = run.duration || 0;
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

            // Loguj aktualne wartości liczników
            console.log("Success counter value:", testSuccessCounter.get().values);
            console.log("Failure counter value:", testFailureCounter.get().values);
            console.log("Performance positive counter value:", performancePositiveCounter.get().values);
            console.log("Performance negative counter value:", performanceNegativeCounter.get().values);
        }

        console.log(`Pushing metrics to Pushgateway at ${pushgatewayAddress}`);
        try {
            // Wypisz metryki z rejestru – jako tekst
            const metricsData = await registry.metrics();
            console.log('Custom registry metrics (string):', metricsData);
            // Wypisz metryki w formacie JSON
            console.log('Custom registry metrics (JSON):', registry.getMetricsAsJSON());
        } catch (err) {
            console.warn('Error fetching metrics data:', err);
        }

        // Używamy funkcji pushToGateway, przekazując niestandardowy rejestr oraz unikalny klucz grupujący
        const {pushToGateway} = require('prom-client');
        pushToGateway(pushgatewayAddress, 'cypress_tests', registry, {instance: 'cypress_jenkins'}, (err, resp, body) => {
            if (err) {
                console.error('Error pushing metrics:', err);
            } else {
                console.log('Successfully pushed metrics at', new Date().toISOString());
            }
        });

        return config;
    });
};
