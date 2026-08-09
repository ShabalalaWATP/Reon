import { readFile, stat } from "node:fs/promises";
import { resolve } from "node:path";
import { stdout } from "node:process";

const limits = {
  css: 110_000,
  javascript: 325_000,
};
const outputDirectory = resolve("dist");
const manifest = JSON.parse(
  await readFile(resolve(outputDirectory, ".vite/manifest.json"), "utf8"),
);
const entries = Object.entries(manifest).filter(([, chunk]) => chunk.isEntry);
if (entries.length !== 1) {
  throw new Error(`Expected one web entry chunk, found ${entries.length}.`);
}

const assets = new Set();
const visited = new Set();
function collect(chunkKey) {
  if (visited.has(chunkKey)) return;
  const chunk = manifest[chunkKey];
  if (!chunk) throw new Error(`Bundle manifest import is missing: ${chunkKey}`);
  visited.add(chunkKey);
  assets.add(chunk.file);
  for (const stylesheet of chunk.css ?? []) assets.add(stylesheet);
  for (const imported of chunk.imports ?? []) collect(imported);
}
collect(entries[0][0]);

let css = 0;
let javascript = 0;
for (const asset of assets) {
  const bytes = (await stat(resolve(outputDirectory, asset))).size;
  if (asset.endsWith(".css")) css += bytes;
  if (asset.endsWith(".js")) javascript += bytes;
}

if (javascript > limits.javascript || css > limits.css) {
  throw new Error(
    `Initial bundle exceeds its budget: JavaScript ${javascript}/${limits.javascript} bytes, CSS ${css}/${limits.css} bytes.`,
  );
}
stdout.write(
  `Initial bundle budget passed: JavaScript ${javascript}/${limits.javascript} bytes, CSS ${css}/${limits.css} bytes.\n`,
);
