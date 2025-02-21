const { defineConfig } = require('cypress')

module.exports = defineConfig({
  e2e: {
    baseUrl: 'https://practicetestautomation.com',
    specPattern: './*.spec.js',
    supportFile: false,
  },
})
