# Fixtures

Proyectos chicos sobre los que se miden los sidekicks. Viven versionados en
este repo sin `.git` propio: `control.py --reset` los devuelve al estado
commiteado antes de cada corrida.

| Carpeta | Tarea | Verdad de referencia |
|---|---|---|
| `find-usages/` | nivel 1, `formatPrice` usado en 10 lugares (definición, imports, llamadas, test, y un acceso dinámico `fmt["formatPrice"]` plantado) | `find-usages.expect.json`, **al lado y no adentro**: contiene el símbolo y el grep del modelo lo encontraría |
| `vitest/` | nivel 2, `formatPercent` agregado en `src/lib/format.ts` sin test; línea de base 1 test verde | `npx vitest run` debe dar 2 en verde y el diff contener `formatPercent(0.125)` |

`vitest/` necesita `npm install` una vez (sale de la caché de npm si ya la
tenés; `run-remote.sh` lo hace solo). `node_modules` está ignorado.

Regla aprendida a los golpes (spike 1, corrida 6): **ninguna salida del
harness va dentro de un fixture** — dumps, logs, jsonl. El modelo las
encuentra con grep y le ensucian el contexto.

`find-usages/` trae además `.opencode/agents/probe*.md` y un `opencode.json`:
son las variantes medidas en el spike 2 por opencode, para reproducirlas con
`tools/spike-run.py --cwd runner/fixtures/find-usages`.
