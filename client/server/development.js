const chalk = require("chalk");
const express = require("express");
const favicon = require("serve-favicon");
const webpack = require("webpack");
const devMiddleware = require("webpack-dev-middleware");
const path = require("path");
const config = require("../configuration/webpack/webpack.config.dev");
const utils = require("./utils");

process.env.NODE_ENV = "development";

const CLIENT_PORT = process.env.CXG_CLIENT_PORT;

// Set up compiler
const compiler = webpack(config);

compiler.hooks.invalid.tap("invalid", () => {
  utils.clearConsole();
  console.log("Compiling...");
});

compiler.hooks.done.tap("done", (stats) => {
  utils.formatStats(stats, CLIENT_PORT);
});

// Launch server
const app = express();

app.use(
  devMiddleware(compiler, {
    publicPath: config.output.publicPath,
    index: true,
    writeToDisk: true // write files compiled by webpack -- do not just keep in memory
  })
);

// Serve the built index file from url that allows extraction of the base_url and dataset for api calls
app.get("/:baseUrl/:dataset", (_, res) => {
  res.sendFile(path.join(path.dirname(__dirname), "build/index.html")); // same location as prod index
});

app.use(express.static("/build"));

app.use(favicon("./favicon.png"));

app.get("/login", async (req, res) => {
  try {
    res.redirect(`${API.prefix}login?dataset=http://localhost:${CLIENT_PORT}`);
  } catch (err) {
    console.error(err);
  }
});

app.get("/logout", async (req, res) => {
  try {
    res.redirect(`${API.prefix}logout?dataset=http://localhost:${CLIENT_PORT}`);
  } catch (err) {
    console.error(err);
  }
});

app.listen(CLIENT_PORT, (err) => {
  if (err) {
    console.log(err);
    return;
  }

  utils.clearConsole();
  console.log(chalk.cyan("Starting the development server..."));
  console.log();
});
