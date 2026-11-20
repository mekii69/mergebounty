import { defineConfig } from "vite";

export default defineConfig({
  // Static site: `npm run build` emits dist/ ready for any static host.
  build: { outDir: "dist", emptyOutDir: true },
});
