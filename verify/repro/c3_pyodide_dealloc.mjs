// Run with: npm install pyodide@314.0.7 && node verify/repro/c3_pyodide_dealloc.mjs <depth>   (Node 22; crashes with "Maximum call stack size exceeded" at depth 10000)
// Builds a core-schema-shaped nested graph of <depth> list_schema dicts in Pyodide (CPython on Emscripten) and deletes it.
import { loadPyodide } from "pyodide";
const depth = parseInt(process.argv[2] || "10000");
const py = await loadPyodide();
console.log("pyodide python:", py.runPython("import sys; sys.version"));
const code = `
import sys
depth = ${depth}
schema = {'type': 'definition-ref', 'schema_ref': 'Model'}
for _ in range(depth):
    schema = {'type': 'list', 'items_schema': schema}
print('built depth', depth, 'recursion limit', sys.getrecursionlimit())
del schema
print('deleted OK depth', depth)
`;
try {
  py.runPython(code);
} catch (e) {
  console.log("ERROR during run:", String(e).split("\n").slice(0, 6).join("\n"));
  process.exitCode = 1;
}
