/* eslint-disable @blueprintjs/classes-constants -- we don't import blueprint here  */
const path = require("path");
const fs = require("fs");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const ObsoleteWebpackPlugin = require("obsolete-webpack-plugin");
const ScriptExtHtmlWebpackPlugin = require("script-ext-html-webpack-plugin");
const webpack = require("webpack");

const src = path.resolve("src");
const nodeModules = path.resolve("node_modules");

const publicPath = "";

const rawObsoleteHTMLTemplate = fs.readFileSync(
  `${__dirname}/obsoleteHTMLTemplate.html`,
  "utf8"
);

const obsoleteHTMLTemplate = rawObsoleteHTMLTemplate.replace(/'/g, '"');

const deploymentStage = process.env.DEPLOYMENT_STAGE || "test";

module.exports = {
  entry: [
    "core-js",
    "regenerator-runtime/runtime",
    "whatwg-fetch",
    "abort-controller/polyfill",
    "./src/index",
  ],
  output: {
    path: path.resolve("build"),
    publicPath,
  },
  resolve: {
    extensions: [".ts", ".tsx", "..."],
  },
  module: {
    rules: [
      {
        test: /\.css$/,
        include: src,
        exclude: [path.resolve(src, "index.css")],
        use: [
          MiniCssExtractPlugin.loader,
          {
            loader: "css-loader",
            options: {
              modules: {
                localIdentName: "[name]__[local]___[contenthash:base64:5]",
              },
              importLoaders: 1,
            },
          },
        ],
      },
      {
        test: /index\.css$/,
        include: [path.resolve(src, "index.css")],
        use: [MiniCssExtractPlugin.loader, "css-loader"],
      },
      {
        test: /\.json$/,
        include: [src, nodeModules],
        loader: "json-loader",
        exclude: /manifest.json$/,
      },
    ],
  },
  plugins: [
    new ObsoleteWebpackPlugin({
      name: "obsolete",
      template: obsoleteHTMLTemplate,
      promptOnNonTargetBrowser: false,
    }),
    new ScriptExtHtmlWebpackPlugin({
      async: "obsolete",
    }),
    new webpack.DefinePlugin({
      PLAUSIBLE_DATA_DOMAIN: JSON.stringify(
        deploymentStage === "prod"
          ? "cellxgene.cziscience.com"
          : "cellxgene.staging.single-cell.czi.technology"
      ),
    }),
  ],
};
/* eslint-enable @blueprintjs/classes-constants -- we don't import blueprint here  */
