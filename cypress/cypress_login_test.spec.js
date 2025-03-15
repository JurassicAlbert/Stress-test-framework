const numTests = Cypress.env("NUM_TESTS") || 1;
const username = Cypress.env("LOGIN") || "student";
const password = Cypress.env("PASSWORD") || "Password123";

// Obiekt przechowujący wyniki testów.
// Dla scenariusza "positive" oczekujemy: { expectedPass, unexpectedFail }
// dla scenariusza "negative": { expectedFail, unexpectedPass }
// a dla generic: wszystkie cztery.
let testResults = {
  expectedPass: 0,
  unexpectedFail: 0,
  expectedFail: 0,
  unexpectedPass: 0
};

describe("Practice Test Automation - Login Test", () => {
  for (let i = 0; i < numTests; i++) {
    it(`Login Test Iteration ${i + 1}`, function() {
      // 1. Odwiedź stronę logowania
      cy.visit("https://practicetestautomation.com/practice-test-login/");

      // 2. Wprowadź dane logowania
      cy.get("#username").type(username, { log: false });
      cy.get("#password").type(password, { log: false });
      cy.get("#submit").click();
      cy.wait(200);

      // 3. Sprawdź, czy użytkownik został zalogowany
      cy.url().should("include", "logged-in-successfully");
      cy.contains("Log out").should("be.visible").click();
      cy.url().should("include", "/practice-test-login/");

      // Dodatkowa walidacja dla negatywnego scenariusza
      if (username !== "student" || password !== "Password123") {
        cy.contains("Test Failed: Incorrect login or password").should('not.exist');
      }
    });
  }

  // Po każdym teście aktualizujemy obiekt wyników
  afterEach(function() {
    if (this.currentTest.state === 'passed') {
      if (username === "student" && password === "Password123") {
        // Test pozytywny, który przeszedł
        testResults.expectedPass++;
      } else {
        // Test negatywny, który nie powinien przejść, ale przeszedł
        testResults.unexpectedPass++;
      }
    } else if (this.currentTest.state === 'failed') {
      if (username === "student" && password === "Password123") {
        // Test pozytywny, który nie przeszedł
        testResults.unexpectedFail++;
      } else {
        // Test negatywny, który zakończył się porażką – oczekiwany wynik
        testResults.expectedFail++;
      }
    }
  });

  // Po zakończeniu testów zapisz wyniki do pliku JSON
  after(() => {
    cy.writeFile('./results/cypress_results.json', testResults);
  });
});
