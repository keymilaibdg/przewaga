import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8")) as { version: string };
const env = process.env;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    __DATA_URL__: JSON.stringify(env.DATA_URL ?? "data"),
    __NATIVE__: JSON.stringify(env.NATIVE === "1"),
    __APP_VERSION__: JSON.stringify(env.APP_VERSION ?? pkg.version),
    __REPO__: JSON.stringify(env.GITHUB_REPOSITORY ?? ""),
  },
  build: { target: "es2022", sourcemap: false },
});
