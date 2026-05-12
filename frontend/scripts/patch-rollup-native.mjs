import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const target = path.resolve(__dirname, "../node_modules/rollup/dist/native.js");

if (!fs.existsSync(target)) {
  console.log("[patch-rollup] rollup native.js no encontrado, se omite.");
  process.exit(0);
}

const source = fs.readFileSync(target, "utf8");

const needle = "throw new Error(\n\t\t\t`Cannot find module ${id}. ` +\n\t\t\t\t`npm has a bug related to optional dependencies (https://github.com/npm/cli/issues/4828). ` +\n\t\t\t\t'Please try `npm i` again after removing both package-lock.json and node_modules directory.',\n\t\t\t{ cause: error }\n\t\t);";
const replacement = "if (platform === 'win32' && error instanceof Error && (error.code === 'ERR_DLOPEN_FAILED' || /Access is denied/i.test(error.message))) {\n\t\t\t// ROLLUP_WASM_FALLBACK: use native wasm bindings API compatible with rollup/dist/native.js.\n\t\t\treturn require('@rollup/wasm-node/dist/native.js');\n\t\t}\n\t\tthrow new Error(\n\t\t\t`Cannot find module ${id}. ` +\n\t\t\t\t`npm has a bug related to optional dependencies (https://github.com/npm/cli/issues/4828). ` +\n\t\t\t\t'Please try `npm i` again after removing both package-lock.json and node_modules directory.',\n\t\t\t{ cause: error }\n\t\t);";

let patched = source
  .replace(/return require\('@rollup\/wasm-node'\);/g, "return require('@rollup/wasm-node/dist/native.js');")
  .replace(needle, replacement);

// If script was run before, collapse duplicated fallback blocks to a single one.
patched = patched.replace(
  /if \(platform === 'win32' && error instanceof Error && \(error\.code === 'ERR_DLOPEN_FAILED' \|\| \/Access is denied\/i\.test\(error\.message\)\)\) \{\n\t\t\t(?:\/\/[^\n]*\n)?\t\t\treturn require\('@rollup\/wasm-node\/dist\/native\.js'\);\n\t\t\}\n\n\t\tif \(platform === 'win32' && error instanceof Error && \(error\.code === 'ERR_DLOPEN_FAILED' \|\| \/Access is denied\/i\.test\(error\.message\)\)\) \{\n\t\t\t(?:\/\/[^\n]*\n)?\t\t\treturn require\('@rollup\/wasm-node\/dist\/native\.js'\);\n\t\t\}\n/g,
  "if (platform === 'win32' && error instanceof Error && (error.code === 'ERR_DLOPEN_FAILED' || /Access is denied/i.test(error.message))) {\n\t\t\t// ROLLUP_WASM_FALLBACK: use native wasm bindings API compatible with rollup/dist/native.js.\n\t\t\treturn require('@rollup/wasm-node/dist/native.js');\n\t\t}\n\n"
);

if (patched === source) {
  console.log("[patch-rollup] no hubo cambios (ya estaba corregido).");
  process.exit(0);
}

fs.writeFileSync(target, patched, "utf8");
console.log("[patch-rollup] parche aplicado correctamente.");
