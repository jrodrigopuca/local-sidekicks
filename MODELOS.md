# Cómo le va a cada modelo

Lo que hizo cada modelo en las tareas medidas, con el runner de control
(`runner/control.py`), tres corridas por celda. Cada número sale de una
carpeta en `runs/` que se puede volver a leer; fuera de estas tareas y estos
fixtures no dice nada. Formato de la tabla: igual que `interaction/MODELOS.md`.

## Foto del 2026-10-28

| Modelo | Máquina | ollama | Digest |
|---|---|---|---|
| `qwen3.5:2b` (alias `2b-16k`, Q8/mxfp8) | M1 8 GB, local | 0.40.12 | `0817328c8f11` |
| `qwen3.5:9b` (nvfp4) | 192.168.1.144 por red | 0.40.6 | `d63f830f28d5` |

Mismo runner, mismos fixtures (`runner/fixtures/`), `think: false`,
`temperature: 0.2`, `num_ctx` 16384, piso de prompt 545 tokens.

### Nivel 1 — `find-usages` (10 usos, uno dinámico)

| | 2B | 9B |
|---|---|---|
| Formato válido (esquema) | 5/5 | 3/3 |
| Recall de los 10 usos | 10/10 en 5/5 | 10/10 en 3/3 |
| Inventados | 0 en 4/5 | 0 en 3/3 |
| `kind: dynamic` en `fmt["formatPrice"]` | 1/5 | **3/3** |
| `path` con la línea pegada | 2/5 corridas | 0/3 |
| Tiempo por corrida | 28-38 s | 23-32 s |

### Nivel 2 — `update-vitest-test` (agregar un test, suite 1 → 2 en verde, diff con `formatPercent(0.125)`)

| | 2B | 9B |
|---|---|---|
| Correctas, con la regla del import en el prompt | 2/3 (spike 3, tanda 5) | **3/3** |
| Correctas, **sin** la regla del import | 0/3 (spike 3, tanda 4) | **3/3** |
| Pasos | 6 (las correctas) · 8 (las que fallan) | 5 con regla · **4 sin regla** |
| Rechazos de las guardas | varios por tanda | 0 |
| Tiempo por corrida | 33-62 s | 15-25 s |

Fuentes: `runs/20261028-1700-qwen3.5-2b-16k/`, `runs/20261028-1711-qwen3.5-9b/`
(incluye `update-vitest-test-sin-regla-import/`), y las tandas del 2B en
`docs/spikes/2026-10-28-nivel-2-vitest.md`.

## Lo que la foto dice

- **La regla "si aguanta en 2B aguanta en 9B" se cumplió** en todo lo medido,
  y el 9B además resolvió lo que el 2B no: la clasificación `dynamic` y el
  nivel 2 sin ayuda.
- **La regla del import era una muleta para el 2B.** El 9B hace import y test
  en un solo `edit`. Las reglas específicas de tarea se miden por modelo: lo
  que el piso necesita puede sobrar en el modelo de salida — y sobra, no
  molesta: con la regla el 9B tardó un paso más, nada peor.
- **Las guardas del runner no saltaron ni una vez con el 9B.** No por eso se
  sacan: son la red para el día que un modelo las necesite, y lo que hace que
  "verde" signifique correcto.
- El 9B por Wi‑Fi (~95 ms de ping) fue **más rápido** que el 2B local: el
  costo de la red es nada al lado del costo por token en un M1 de 8 GB.

## Cómo actualizarlo

`./runner/run-remote.sh <ip> <modelo> 3` deja una carpeta en `runs/` con
`meta.txt` (host, versión, digest, fecha) y un JSON por corrida; para el
modelo local, el mismo script con `127.0.0.1`. Un modelo o una versión nueva
es una fila nueva, nunca se pisa una medida.
