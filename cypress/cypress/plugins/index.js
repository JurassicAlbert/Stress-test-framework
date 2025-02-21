// cypress/plugins/index.js
const client = require('prom-client');
const { Pushgateway } = client;

// Set the Pushgateway address (can be passed via environment variable)
const pushgatewayAddress = process.env.PUSHGATEWAY_ADDRESS || 'localhost:9091';
const pushgateway = new Pushgateway(pushgatewayAddress);

// Create a custom registry and collect default metrics if desired
const registry = new client.Registry();
client.collectDefaultMetrics({ register: registry });

// Define custom counters for Cypress test metrics
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

module.exports = (on, config) => {
  // After the test run finishes, update our counters and push metrics to Pushgateway
  on('after:run', (results) => {
    if (results) {
      // Increase counters with the totals from the test run
      testSuccessCounter.inc(results.totalPassed);
      testFailureCounter.inc(results.totalFailed);
    }

    // Push the metrics to the Pushgateway under the job name "cypress_tests"
    pushgateway.pushAdd({ jobName: 'cypress_tests' }, (err, resp, body) => {
      if (err) {
        console.error('Error pushing metrics: ', err);
      } else {
        console.log('Metrics successfully pushed to Pushgateway.');
      }
    });
  });

  return config;
};
