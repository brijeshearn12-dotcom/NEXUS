import { loadEnvConfig } from "@next/env";
import path from "path";
import { fileURLToPath } from "url";

// Load the single root-level .env (one directory above /frontend)
const __dirname = path.dirname(fileURLToPath(import.meta.url));
loadEnvConfig(path.resolve(__dirname, ".."));

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Expose selected env vars to the browser (NEXT_PUBLIC_ prefix already handled by Next.js)
};

export default nextConfig;
