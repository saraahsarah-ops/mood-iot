const path = require("path");

/** @type {import('next').NextConfig} */
const nextConfig = {
  // "standalone" pour Docker, desactive sur Vercel via env var
  ...(process.env.VERCEL ? {} : { output: "standalone" }),
  turbopack: {
    root: path.resolve(__dirname),
  },
  webpack: (config) => {
    config.resolve.alias["@"] = path.resolve(__dirname, "src");
    return config;
  },
};

module.exports = nextConfig;
