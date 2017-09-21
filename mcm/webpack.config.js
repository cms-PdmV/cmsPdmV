var path = require('path');
var webpack = require('webpack');
var HtmlWebpackPlugin = require('html-webpack-plugin');

var HotReloader = new webpack.HotModuleReplacementPlugin();

var buildEntryPoint = function(entryPoint){
  return [
    'webpack-dev-server/client?http://localhost:3000',
    'webpack/hot/only-dev-server',
    entryPoint
  ]
}

var buildHTMLPlugin = function(filename){
  return new HtmlWebpackPlugin({
                template: __dirname + '/html2/'+filename+'.html',
                hash: true,
                filename: filename+'.html',
                chunks: [filename],
                inject: 'body'})
}

module.exports = [{
    devtool: 'source-map',
    entry: {
      settings:  ['./scripts2/settings.js'],
      news:  ['./scripts2/news.js']
    },
    output: {
        path: path.resolve(__dirname, '/scripts3'),
        publicPath: '/',
        filename: '[name].js'
    },
    module: {
      rules: [
        {
          test: /\.vue$/,
          loader: 'vue-loader',
        },
        {
          test: /\.js$/,
          loader: 'babel-loader',
          exclude: /node_modules/
        },
        {
          test: /\.(png|jpg|gif|svg)$/,
          loader: 'file-loader',
          options: {
            name: '[name].[ext]?[hash]'
          }
        }
      ]
    },
    plugins: [ buildHTMLPlugin("settings"),
               buildHTMLPlugin("news"),
              HotReloader],

    devServer: {
      contentBase: __dirname + '/scripts2',
      disableHostCheck : true,
      historyApiFallback: true,
      noInfo: false,
    },

    performance: {
      hints: false
    },
}];