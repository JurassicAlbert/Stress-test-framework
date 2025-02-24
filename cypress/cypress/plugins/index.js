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

// Additional counters for performance issues:
// - For positive tests (with correct credentials), if the test duration exceeds the expected threshold,
//   it is counted as a performance failure.
// - For negative tests (with invalid credentials), if a test either passes or runs too quickly,
//   it is considered an unexpected result.
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

module.exports = (on, config) => {
  // After the test run finishes, update our counters and push metrics to the Pushgateway.
  on('after:run', (results) => {
    if (results) {
      // Increase basic counters using the totals from the test run
      testSuccessCounter.inc(results.totalPassed);
      testFailureCounter.inc(results.totalFailed);

      // Iterate over each test run to detect performance-related issues.
      // We assume:
      // - If the environment has valid credentials (LOGIN === 'student' && PASSWORD === 'Password123'),
      //   the test should pass. If its duration exceeds 5000 ms, count it as a performance issue.
      // - If the environment has invalid credentials, the test should fail.
      //   If the test either passes or runs very quickly (< 1000 ms), count it as an unexpected result.
      let positivePerfIssues = 0;
      let negativePerfIssues = 0;

      if (results.runs && Array.isArray(results.runs)) {
        results.runs.forEach(run => {
          const duration = run.duration || 0;
          const isPositive = (process.env.LOGIN === 'student' && process.env.PASSWORD === 'Password123');

          if (isPositive) {
            if (duration > 4000) { // Threshold for positive tests
              positivePerfIssues++;
            }
          } else {
            // For negative tests, count as performance issue if the test passed or its duration is very short.
            if (run.state === 'passed' || duration < 1000) {
              negativePerfIssues++;
            }
          }
        });
      }

      performancePositiveCounter.inc(positivePerfIssues);
      performanceNegativeCounter.inc(negativePerfIssues);
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
