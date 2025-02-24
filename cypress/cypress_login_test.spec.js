// cypress_login_test.spec.js

const numTests = Cypress.env("NUM_TESTS") || 1;
const username = Cypress.env("LOGIN") || "student";
const password = Cypress.env("PASSWORD") || "Password123";

describe("Practice Test Automation - Login Test", () => {
  for (let i = 0; i < numTests; i++) {
    it(`Login Test Iteration ${i + 1}`, () => {
      // 1. Visit the login page
      cy.visit("https://practicetestautomation.com/practice-test-login/");

      // 2. Enter login credentials
      cy.get("#username").type(username, { log: false });
      cy.get("#password").type(password, { log: false });
      cy.get("#submit").click();
      cy.wait(200)
      cy.url().should("include", "logged-in-successfully");
      cy.contains("Log out").should("be.visible").click();
      cy.url().should("include", "/practice-test-login/");
      if (username !== "student" || password !== "Password123") {
        cy.contains("Test Failed: Incorrect login or password").should('not.exist')
      }
    });
  }
});
