import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  // Réduire les recompilations
  onDemandEntries: {
    maxInactiveAge: 5 * 60 * 1000, // 5 minutes (augmenté pour réduire les recompilations)
    pagesBufferLength: 2, // Réduire encore le buffer
  },
  // Configuration Turbopack pour Next.js 16
  turbopack: {},
  // Désactiver certaines optimisations en dev pour réduire la charge
  webpack: (config, { dev }) => {
    if (dev) {
      // Réduire la fréquence de watch pour économiser CPU
      config.watchOptions = {
        ...config.watchOptions,
        aggregateTimeout: 500, // Attendre 500ms avant de recompiler après un changement
        poll: false, // Ne pas utiliser polling (utiliser les événements système)
        ignored: [
          '**/node_modules/**',
          '**/.next/**',
          '**/dist/**',
          '**/build/**',
        ],
      };
    }
    return config;
  },
};

export default nextConfig;
