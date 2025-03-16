const numTests = Cypress.env("NUM_TESTS") || 1;
const username = Cypress.env("LOGIN") || "student";
const password = Cypress.env("PASSWORD") || "Password123";

// Obiekt zbierający wyniki testów.
// Dla "positive": oczekujemy { expectedPass, unexpectedFail }
// Dla "negative": { expectedFail, unexpectedPass }
let testResults = {
  expectedPass: 0,
  unexpectedFail: 0,
  expectedFail: 0,
  unexpectedPass: 0
};

describe("Practice Test Automation - Login Test", () => {
  for (let i = 0; i < numTests; i++) {
    it(`Login Test Iteration ${i + 1}`, function() {
      // Odwiedź stronę logowania
      cy.visit("https://practicetestautomation.com/practice-test-login/");

      // Wprowadź dane logowania
      cy.get("#username").type(username, { log: false });
      cy.get("#password").type(password, { log: false });
      cy.get("#submit").click();

      // Sprawdź, czy URL wskazuje na pomyślne logowanie
      cy.url().should("include", "logged-in-successfully");

      // Jeśli test przeszedł, wykonaj wylogowanie
      cy.contains("Log out").click();
      cy.url().should("include", "/practice-test-login/");
    });
  }

  afterEach(function() {
    // Aktualizujemy wyniki na podstawie stanu testu.
    if (this.currentTest.state === 'passed') {
      if (username === "student" && password === "Password123") {
        // Test pozytywny – oczekiwany sukces
        testResults.expectedPass++;
      } else {
        // Test negatywny, który nie powinien przejść, ale przeszedł
        testResults.unexpectedPass++;
      }
    } else if (this.currentTest.state === 'failed') {
      if (username === "student" && password === "Password123") {
        // Test pozytywny, który sfailował – nieoczekiwany błąd
        testResults.unexpectedFail++;
      } else {
        // Test negatywny, który sfailował – oczekiwany wynik
        testResults.expectedFail++;
      }
    }
  });

  after(() => {
    // Zapisujemy zebrane wyniki do pliku JSON, którego użyje index.js.
    cy.writeFile('./results/cypress_results.json', testResults);
  });
});
