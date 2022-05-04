module.exports = {
  root: true,
  env: {
    node: true
  },
  extends: [
    'plugin:vue/essential',
    '@vue/standard'
  ],
  parserOptions: {
    parser: '@babel/eslint-parser'
  },
  rules: {
    'no-console': process.env.NODE_ENV === 'production' ? 'warn' : 'off',
    'no-debugger': process.env.NODE_ENV === 'production' ? 'warn' : 'off',
    'vue/multi-word-component-names': 'off', // Allow single word component names
    'semi': [1, 'always'], // Require semicolons
    'space-before-function-paren': ['warn', 'never'], // Always require space before function parentheses
    'comma-dangle': ['error', 'always-multiline'], // Always require trailing commas
  }
};
