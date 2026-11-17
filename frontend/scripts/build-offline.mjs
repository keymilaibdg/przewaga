// Offline production build (no Vite): esbuild for TS/TSX + Tailwind v4 compile API for CSS.
// Used where the npm registry is unreachable. The normal path is `npm run build` (Vite).
//
// Usage: NODE_PATH=<dir with node_modules> node scripts/build-offline.mjs [--single]
//   --single  also emits dist-single/index.html with JS, CSS and fonts inlined (for previews).
import { createHash } from "node:crypto";
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const nodePaths = (process.env.NODE_PATH ?? "").split(":").filter(Boolean);
const require = createRequire(join(nodePaths[0] ?? root, "noop.js"));
const esbuild = require("esbuild");
const { compile } = require("tailwindcss");

const dist = join(root, "dist");
rmSync(dist, { recursive: true, force: true });
mkdirSync(join(dist, "assets"), { recursive: true });

function walk(dir) {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

// ---- CSS ----
const twDir = dirname(require.resolve("tailwindcss/package.json"));
const cssEntry = join(root, "src/styles/index.css");
const compiler = await compile(readFileSync(cssEntry, "utf8"), {
  base: dirname(cssEntry),
  loadStylesheet: async (id, base) => {
    const file = id === "tailwindcss" ? join(twDir, "index.css") : id.startsWith("tailwindcss/") ? join(twDir, id.slice(12)) : join(base, id);
    return { path: file, base: dirname(file), content: readFileSync(file, "utf8") };
  },
});
const sources = [...walk(join(root, "src")).filter((f) => /\.(tsx?|html)$/.test(f)), join(root, "index.html")];
const candidates = new Set();
for (const f of sources) for (const tok of readFileSync(f, "utf8").split(/[\s"'`{}();,]+/)) if (tok && tok.length < 120) candidates.add(tok);
const rawCss = compiler.build([...candidates]);
const { code: css } = await esbuild.transform(rawCss, { loader: "css", minify: true, target: ["chrome110"] });

// ---- JS ----
const result = await esbuild.build({
  entryPoints: [join(root, "src/main.tsx")],
  bundle: true,
  minify: true,
  format: "esm",
  target: ["chrome110", "safari16"],
  jsx: "automatic",
  nodePaths,
  write: false,
  metafile: true,
  define: {
    "process.env.NODE_ENV": '"production"',
    __DATA_URL__: JSON.stringify(process.env.DATA_URL ?? "data"),
    __NATIVE__: JSON.stringify(process.env.NATIVE === "1"),
    __APP_VERSION__: JSON.stringify(process.env.APP_VERSION ?? JSON.parse(readFileSync(join(root, "package.json"), "utf8")).version),
    __REPO__: JSON.stringify(process.env.GITHUB_REPOSITORY ?? ""),
  },
  logLevel: "warning",
});
const js = result.outputFiles[0].text;

const hash = (s) => createHash("sha256").update(s).digest("hex").slice(0, 10);
const jsName = `assets/app-${hash(js)}.js`;
const cssName = `assets/app-${hash(css)}.css`;
writeFileSync(join(dist, jsName), js);
writeFileSync(join(dist, cssName), css);
cpSync(join(root, "public"), dist, { recursive: true });

const html = readFileSync(join(root, "index.html"), "utf8")
  .replace('<link rel="stylesheet" href="/src/styles/index.css" />', `<link rel="stylesheet" href="/${cssName}" />`)
  .replace('<script type="module" src="/src/main.tsx"></script>', `<script type="module" src="/${jsName}"></script>`);
writeFileSync(join(dist, "index.html"), html);

// Precache list for the service worker.
const sw = readFileSync(join(dist, "sw.js"), "utf8").replace(
  'const SHELL = ["/", "/index.html",',
  `const SHELL = ["/", "/index.html", "/${jsName}", "/${cssName}", "/fonts/Inter-Regular.woff", "/fonts/Inter-Medium.woff", "/fonts/Inter-SemiBold.woff", "/fonts/Inter-Bold.woff",`,
);
writeFileSync(join(dist, "sw.js"), sw);

console.log(`JS  ${(js.length / 1024).toFixed(1)} KB  ${jsName}`);
console.log(`CSS ${(css.length / 1024).toFixed(1)} KB  ${cssName}`);

// ---- single-file preview ----
if (process.argv.includes("--single")) {
  const out = join(root, "dist-single");
  mkdirSync(out, { recursive: true });
  const inlineCss = css.replace(/url\(\/fonts\/([\w-]+\.woff)\)/g, (_, f) => `url(data:font/woff;base64,${readFileSync(join(root, "public/fonts", f)).toString("base64")})`);
  const svgIcon = readFileSync(join(root, "public/icons/icon.svg"), "utf8");
  const single = html
    .replace(/<link rel="(manifest|apple-touch-icon|preload)"[^>]*>\n?\s*/g, "")
    .replace(/<link rel="icon"[^>]*>/, `<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,${encodeURIComponent(svgIcon)}" />`)
    .replace(`<link rel="stylesheet" href="/${cssName}" />`, `<style>${inlineCss}</style>`)
    .replace(`<script type="module" src="/${jsName}"></script>`, () => `<script type="module">${js.replace(/<\/script/g, "<\\/script")}</script>`);
  writeFileSync(join(out, "index.html"), single);
  console.log(`single-file ${(single.length / 1024).toFixed(1)} KB  ${relative(root, join(out, "index.html"))}`);
}
if (!existsSync(join(dist, "index.html"))) process.exit(1);
