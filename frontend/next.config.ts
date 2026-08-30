import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // FASE 18: en produccion Dokploy expone una unica URL (frontend:3000).
  // Este rewrite enruta /api del mismo origen hacia el backend interno
  // (api:8000), evitando CORS y dominios adicionales. Se evalua en el
  // arranque del servidor Next, asi que API_INTERNAL_URL es runtime.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;