// Retrieve data from the pipeline using Cypress.env
// If not set, default values are used.
const numTests = Cypress.env("NUM_TESTS") || 1;
const validUsername = Cypress.env("LOGIN") || "student";
const validPassword = Cypress.env("PASSWORD") || "Password123";

describe('Practice Test Automation - Login Test', () => {
  for (let i = 0; i < numTests; i++) {
    it(`Login Test Iteration ${i + 1}`, () => {
      // 1. Visit the login page
      cy.visit('https://practicetestautomation.com/practice-test-login/');

      // 2. Enter login credentials (as provided from the pipeline)
      cy.get('#username').clear().type(validUsername);
      cy.get('#password').clear().type(validPassword);
      cy.get('#submit').click();

      // 3. Depending on the provided credentials, expect either a successful or unsuccessful login result
      if (validUsername === "student" && validPassword === "Password123") {
        // Positive scenario: Expect successful login
        cy.url().should('include', 'logged-in-successfully');
        cy.contains(/(Logged In Successfully|Congratulations)/).should('be.visible');
        cy.contains('Log out').should('be.visible');
        // Logout:
        cy.contains('Log out').click();
        cy.url().should('include', '/practice-test-login/');
      } else {
        // Negative scenario: We expect that login does NOT occur
        cy.url().then(url => {
          if (url.includes('logged-in-successfully')) {
            // If login unexpectedly occurs, we consider it a real error => fail the test
            cy.contains('Log out').should('be.visible').click();
            cy.url().should('include', '/practice-test-login/');
            throw new Error("Test FAILED: Unexpected login with invalid credentials");
          } else {
            // If login did not succeed, verify the correct error message is displayed
            if (validUsername !== "student") {
              cy.get('#error')
                .should('be.visible')
                .and('contain', 'Your username is invalid!');
            } else {
              cy.get('#error')
                .should('be.visible')
                .and('contain', 'Your password is invalid!');
            }
            // We do NOT force a failure here; negative scenario is expected => test passes
            cy.log("Negative scenario test passed: login blocked, error message displayed.");
          }
        });
      }
    });
  }
});
