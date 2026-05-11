/** @type {import('next').NextConfig} */
const nextConfig = {
  // "standalone" pour Docker, desactive sur Vercel via env var
  ...(process.env.VERCEL ? {} : { output: "standalone" }),
};

module.exports = nextConfig;
