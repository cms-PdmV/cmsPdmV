const { defineConfig } = require('@vue/cli-service');
module.exports = defineConfig({
  transpileDependencies: [
    'vuetify'
  ],
  publicPath: '/mcm',
  assetsDir: 'static/',
  devServer: {
    port: 8003,
    logLevel: 'debug'
  }
});
