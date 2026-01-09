/** @type {import('next').NextConfig} */
const nextConfig = {
  // Proxy API requests to the FastAPI backend
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:12050/api/:path*",
      },
    ];
  },
};

export default nextConfig;
