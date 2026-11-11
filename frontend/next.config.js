// Hosted build: when BACKEND_URL is set (e.g. on Vercel), the browser only ever
// talks to this site and Next proxies /api/* to the backend. Same origin means
// the device cookie (SameSite=Lax) is sent and no CORS is involved. Without
// BACKEND_URL (local dev) the browser calls NEXT_PUBLIC_API_URL directly.
const backendUrl = (process.env.BACKEND_URL || "").replace(/\/+$/, "");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  ...(backendUrl && {
    // Empty base URL makes lib/api.ts request relative paths (/api/...).
    env: { NEXT_PUBLIC_API_URL: "" },
    async rewrites() {
      return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
    },
  }),
};
module.exports = nextConfig;
