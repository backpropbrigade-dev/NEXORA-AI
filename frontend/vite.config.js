import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const cloudTarget = env.VITE_CLOUD_API_PROXY_TARGET || "http://127.0.0.1:8002";
  const localTarget = env.VITE_LOCAL_API_PROXY_TARGET || "http://127.0.0.1:8765";
  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": cloudTarget,
        "/local-api": {
          target: localTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/local-api/, "/api"),
          ws: true,
        },
      },
    },
  };
});
