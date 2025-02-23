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
        // Expect a successful login:
        cy.url().should('include', 'logged-in-successfully');
        cy.contains(/(Logged In Successfully|Congratulations)/).should('be.visible');
        cy.contains('Log out').should('be.visible');
        // Logout:
        cy.contains('Log out').click();
        cy.url().should('include', '/practice-test-login/');
      } else {
        // Expect that login does not occur:
        cy.url().then(url => {
          if (url.includes('logged-in-successfully')) {
            // If login unexpectedly occurs, perform logout and throw an error.
            cy.contains('Log out').should('be.visible').click();
            cy.url().should('include', '/practice-test-login/');
            throw new Error("Test FAILED: Unexpected login with invalid credentials");
          } else {
            // Verify the appropriate error message:
            if (validUsername !== "student") {
              cy.get('#error')
                .should('be.visible')
                .and('contain', 'Your username is invalid!');
            } else {
              cy.get('#error')
                .should('be.visible')
                .and('contain', 'Your password is invalid!');
            }
            throw new Error("Test FAILED:invalid credentials");
          }
        });
      }
    });
  }
});
