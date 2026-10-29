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
| `bonsai-2:27b` (ternario, Q2_0, 8,3 GB; 9,0 GB cargado con 16K) | 192.168.1.144 por red, M2 Pro 16 GB | 0.40.6 | `f3c4f4208659` |

Mismo runner, mismos fixtures (`runner/fixtures/`), `think: false`,
`temperature: 0.2`, `num_ctx` 16384, piso de prompt 545 tokens.

### Nivel 1 — `find-usages` (10 usos, uno dinámico)

| | 2B | 9B | bonsai-2 27B |
|---|---|---|---|
| Formato válido (esquema) | 5/5 | 3/3 | 3/3 |
| Recall de los 10 usos | 10/10 en 5/5 | 10/10 en 3/3 | 10/10 en 3/3 |
| Inventados | 0 en 4/5 | 0 en 3/3 | 0 en 3/3 |
| `kind: dynamic` en `fmt["formatPrice"]` | 1/5 | **3/3** | **3/3** |
| `path` con la línea pegada | 2/5 corridas | 0/3 | 0/3 |
| Tiempo por corrida | 28-38 s | 23-32 s | 81-90 s |

### Nivel 2 — `update-vitest-test` (agregar un test, suite 1 → 2 en verde, diff con `formatPercent(0.125)`)

| | 2B | 9B | bonsai-2 27B |
|---|---|---|---|
| Correctas, con la regla del import en el prompt | 2/3 (spike 3, tanda 5) | **3/3** | **3/3** |
| Correctas, **sin** la regla del import | 0/3 (spike 3, tanda 4) | **3/3** | sin medir |
| Pasos | 6 (las correctas) · 8 (las que fallan) | 5 con regla · **4 sin regla** | 6 |
| Rechazos de las guardas | varios por tanda | 0 | 0 |
| Tiempo por corrida | 33-62 s | 15-25 s | 54-65 s |

### Nivel 3 — `change-react-component` (prop `discount` opcional en `Cart`; typecheck + tests propios + 4 tests oráculo que el modelo no ve)

| | 2B | 9B | bonsai-2 27B |
|---|---|---|---|
| Oráculo débil (sin exigir markup idéntico con `discount={0}`) | 0/1 | 3/3 | — |
| **Oráculo estricto**, sin regla de React | — | **0/3** — las tres escribieron `{discount && discount > 0 && …}`, que renderiza un `0` suelto | sin medir |
| Oráculo estricto, **con** la regla "`&&` con número renderiza 0; usá ternario" | — | **2/3** (una ignoró la regla) | **3/3** — ternario con `: null` las tres veces |
| Pasos / tiempo | 10 (tope) | 6-8 · 38-150 s ¹ | 9-10 · 112-134 s |

Las tres corridas de bonsai siguieron la misma secuencia: primer `edit`,
`tsc` falla con `TS18048: 'discount' is possibly 'undefined'`, dos edits
chicos, verde. **Se corrigió solo a partir de un error de tipos** — eso es
lo que el 9B no mostró (no lo necesitó: su primer intento ya tipaba, con el
bug del `0` adentro). También eligió `Math.round` para el monto, que nadie
pidió y es lo correcto con centavos.

¹ Una corrida tardó 1.494 s por un `Operation timed out` de red: la máquina
remota estaba bajando otro modelo. No es del modelo.

El cambio de 3/3 a 0/3 lo produjo **el oráculo, no el modelo**: el primero
chequeaba "sin línea de Descuento y total 30,00" y un `0` perdido pasaba. Se
verificó aplicando el diff grabado de la corrida 1 al fixture y corriendo el
oráculo nuevo sin modelo: `…</li>0<li>Total…`. Lección de método: el oráculo
es parte de la especificación; uno débil hace quedar bien al modelo. Esta es
hoy la tarea que discrimina, y por la razón correcta — es el bug que un
revisor senior marca en un PR.

Fuentes: `runs/20261028-1700-qwen3.5-2b-16k/`, `runs/20261028-1711-qwen3.5-9b/`
(incluye `change-react-component/`, `…-con-regla-and/` y `update-vitest-test-sin-regla-import/`)
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
- **La apuesta ternaria salió bien en resultados y cara en tiempo.**
  `bonsai-2:27b` (27B en 8,3 GB) igualó al 9B en niveles 1 y 2 y lo superó
  en el 3 (3/3 contra 2/3 bajo el oráculo estricto), pero tarda **2,5-3×**
  por corrida con el mismo piso de tokens: son 27B de parámetros por token
  aunque pesen lo que un 9B. Para tareas de nivel 1-2 el 9B alcanza y es más
  rápido; para las que exigen criterio (nivel 3) el 27B ternario paga su
  tiempo. En una máquina de 16 GB es, hoy, el techo de calidad medido.
- Los tiempos del 9B en nivel 3 no son limpios (la máquina bajaba bonsai
  durante esa tanda); los de bonsai sí. Repetir el nivel 3 del 9B con la
  máquina quieta antes de citar una relación de tiempos exacta.

## Velocidad de bonsai-2:27b: qué la mueve y qué no (misma noche)

Medido con un prompt de 1.551 tokens directo a `/api/chat`, y después con la
tarea de nivel 3 completa (3 corridas por fila; todas 3/3 correctas).

| Palanca | Prefill | Generación | Nivel 3 por corrida |
|---|---:|---:|---:|
| Base | 52 tok/s | 10,7 tok/s | 112-134 s |
| **`OLLAMA_FLASH_ATTENTION=1`** en la máquina que sirve | **81 tok/s** (+56 %) | 11,1 | — |
| + runner: sin `glob` en el agente, salida de `run_tests` compactada a errores y resumen | — | — | **100-109 s** (−15 %) |
| + reglas de prompt "leé directo, no busques" y "old_string corto" | — | — | 119-126 s (**peor**): el modelo las ignoró y agregó un edit |

Con flash attention el prefill deja de ser el problema (1-6 s por paso); el
tiempo queda en la **generación**: ~800 tokens de salida por corrida a 10,7
tok/s ≈ 75 de los ~105 s, con el primer `edit` solo (~340 tokens, 32 s) como
mayor costo. Eso no lo baja ningún prompt — las reglas de *forma de
trabajar* no prendieron en bonsai (las de *criterio*, como la del `&&`, sí).
Lo que sí lo bajaría: un modelo con menos parámetros por token
(`bonsai-2:9b`, 3,2 GB, sin medir) o decodificación especulativa, que
ollama no ofrece para este modelo. Tres cosas más, medidas: el caché de
prefijo funciona con bonsai (segunda llamada idéntica, 0,2 s); el 9B y
bonsai **no conviven** en 16 GB (cargar uno desaloja al otro, ~8 GB de
recarga por cambio); y `num_ctx` no afecta la velocidad, solo la memoria.

## Cómo actualizarlo

`./runner/run-remote.sh <ip> <modelo> 3` deja una carpeta en `runs/` con
`meta.txt` (host, versión, digest, fecha) y un JSON por corrida; para el
modelo local, el mismo script con `127.0.0.1`. Un modelo o una versión nueva
es una fila nueva, nunca se pisa una medida.
