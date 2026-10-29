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
| `bonsai-2:9b` (ternario, Q2_0, 3,2 GB) | ídem, con flash attention | 0.40.6 | `c8b5462f8688` |
| `gemma4:12b` (nvfp4, 7,7 GB; **16,5 GB cargado con 16K** — la KV cache de Gemma 4 es enorme) | ídem | 0.40.6 | `c7597fc90b86` |

Mismo runner, mismos fixtures (`runner/fixtures/`), `think: false`,
`temperature: 0.2`, `num_ctx` 16384, piso de prompt 545 tokens.

### Nivel 1 — `find-usages` (10 usos, uno dinámico)

| | 2B | 9B | bonsai-2 27B | bonsai-2 9B | gemma4 12B |
|---|---|---|---|---|---|
| Formato válido (esquema) | 5/5 | 3/3 | 3/3 | 3/3 | 3/3 |
| Recall de los 10 usos | 10/10 en 5/5 | 10/10 en 3/3 | 10/10 en 3/3 | 10/10 · 10/10 · 9/10 | 10/10 en 3/3 |
| Inventados | 0 en 4/5 | 0 en 3/3 | 0 en 3/3 | 0 · 0 · 1 | 0 en 3/3 |
| `kind: dynamic` en `fmt["formatPrice"]` | 1/5 | **3/3** | **3/3** | sin medir | sin medir |
| `path` con la línea pegada | 2/5 corridas | 0/3 | 0/3 | 3/3 corridas | 0/3 |
| Tiempo por corrida | 28-38 s | 23-32 s | 81-90 s | 27-29 s | 27-34 s |

### Nivel 2 — `update-vitest-test` (agregar un test, suite 1 → 2 en verde, diff con `formatPercent(0.125)`)

| | 2B | 9B | bonsai-2 27B | bonsai-2 9B | gemma4 12B |
|---|---|---|---|---|---|
| Correctas, con la regla del import en el prompt | 2/3 (spike 3, tanda 5) | **3/3** | **3/3** | **3/3** ¹ | 2/3 con `think:false` · **3/3 con `think:true`** ² |
| Correctas, **sin** la regla del import | 0/3 (spike 3, tanda 4) | **3/3** | sin medir | sin medir | sin medir |
| Pasos | 6 (las correctas) · 8 (las que fallan) | 5 con regla · **4 sin regla** | 6 | 4-5 | 5-6 |
| Rechazos de las guardas | varios por tanda | 0 | 0 | 0 | 0 (3 errores de `edit` ambiguo repetidos en la que falló) |
| Tiempo por corrida | 33-62 s | 15-25 s | 54-65 s | 13-22 s | 28-44 s · 41-58 s con razonamiento |

¹ Dos de las tres reescribieron el archivo entero con `write` en vez de
`edit`; la guarda de identidad las dejó pasar porque el test existente
sobrevivió. Correcto, pero es la forma más frágil de hacerlo.
² Con `think: false`, gemma4 en ollama 0.40.6 **devuelve un turno vacío
después de un resultado de herramienta** (verificado con una llamada
directa: contenido `''`, sin tool calls, 11 tokens, `done_reason: stop`);
con `think: true` contesta, con un `<channel|>` suelto en el texto —
artefacto de la plantilla de chat. Por eso su medición válida es con
razonamiento, y por eso en la tanda sin razonamiento una corrida se quedó
sin correr los tests.

### Nivel 3 — `change-react-component` (prop `discount` opcional en `Cart`; typecheck + tests propios + 4 tests oráculo que el modelo no ve)

| | 2B | 9B | bonsai-2 27B | bonsai-2 9B | gemma4 12B |
|---|---|---|---|---|---|
| Oráculo débil (sin exigir markup idéntico con `discount={0}`) | 0/1 | 3/3 | — | — | — |
| **Oráculo estricto**, sin regla de React | — | **0/3** — las tres escribieron `{discount && discount > 0 && …}`, que renderiza un `0` suelto | sin medir | — | — |
| Oráculo estricto, **con** la regla "`&&` con número renderiza 0; usá ternario" | — | **4/12** a temp 0,2 — por tandas 2/3, 0/3, 2/6 — **5/12 con el preset oficial** (temp 0,7 · top_p 0,8 · top_k 20 · presence 1,5) y **0/6 a temperatura 0, las seis idénticas**: el `&&` es lo que el modelo más cree; el ternario es ruido ⁴ | **12/12** en cuatro tandas, la última con su preset oficial (temp 0,7 · top_p 0,8 · top_k 20 · presence 1,5) — ternario con `: null` siempre ⁶ | **0/3** ² | **0/3** con `think:false` · **0/3** con `think:true` ³ · **0/3** con ollama 0.40.13 y 8K · **1/3 con el preset de Google + `think_after_tool`** ⁵ |
| Pasos / tiempo | 10 (tope) | 6 · **21-33 s** (máquina quieta; 16-18 s de generación) | 9-10 · 100-134 s | 10 (tope) · 71-81 s | 5 · 28-37 s · con razonamiento 64-1.273 s |

² Las tres escribieron `discount > 0` con `discount?: number`, `tsc` falló
con `TS18048: 'discount' is possibly 'undefined'`, y **repitieron el mismo
error cuatro veces** sin leer el mensaje: 4 × (`edit`, `run_tests`) con la
misma salida hasta el tope de pasos. La corrida 3 pasó los 6 tests y falló
solo el typecheck. El 27B se corrigió de ese mismo `TS18048` al primer
reintento. Es la diferencia de criterio entre los dos tamaños, en una línea.
³ Con razonamiento, tres fallas distintas: una corrida no editó nunca
(2.048 tokens de razonamiento hasta el tope de `num_predict`, sin acción);
otra escribió el ternario correcto pero `discount > 0` con `discount?:
number` → `TS18048` (el mismo tropiezo que bonsai 9B) y además tocó el test
con un formato de moneda inventado; la tercera, funcionalmente correcta
(6/6 tests), cayó por el mismo `TS18048` y terminó en `Connection reset by
peer` — la máquina con 16,5 GB cargados en 16 soltando conexiones.
⁴ Mismo agente, misma regla, misma temperatura 0,2, doce corridas en tres
tandas: 2/3, 0/3, 2/6. **Un tercio, estable**: que el 9B siga la regla del
`&&` es una moneda cargada, no una propiedad. En las doce tipa bien
(`discount ? … : 0`), calcula bien y entrega en 21-33 s; la única variable
es si escribe `&& (` o `? (` en esa línea — y lo decide el muestreo, no el
prompt. El 27B ternario, con 9 corridas sobre 9, escribe el ternario
siempre. Lección de método: tres corridas detectan un 0/3 o un 3/3; para
una tasa intermedia hacen falta diez o más, y hoy las tuvimos. Con el
preset oficial (`change-react-component-preset-oficial-x12/`): 5/12, mismos
tiempos (19-33 s), misma línea en disputa; 9/24 acumulado en dos
temperaturas. **A temperatura 0** (`…-temp0-x6/`): seis corridas con el
diff **byte a byte idéntico** (mismo hash las seis, 18-33 s) y las seis con
`{discount && discount > 0 && <li>…`. La decodificación greedy es
determinista en esta máquina, y lo que el 9B "más cree" para esa línea es el
`&&`: el ternario correcto solo aparece como ruido de muestreo. Es la
distinción que buscábamos — **no es que no siempre lo elija: no lo sabe**, y
la regla del prompt no le da vuelta la prior. Para esta clase de criterio el
9B no se arregla con parámetros; se arregla con otro modelo o con una guarda
(un lint de `{number && <jsx>}` en el oráculo, que ya tenemos).
⁵ Primera medición justa de gemma (`…-preset-oficial-think-after-tool/`):
temp 1,0 · top_p 0,95 · top_k 64 como pide Google, `num_ctx` 8K, y razonar
solo en el turno posterior a un resultado de herramienta (workaround del
issue #18861). **Su primera corrida correcta en nivel 3, y el mejor diff de
todos los modelos**: `const currentDiscount = discount ?? 0` (estrecha el
tipo de una) y `{currentDiscount > 0 ? … : null}`; corrió los tests, corrigió
y volvió a correrlos, 6/6 y typecheck en verde — en 121 s y sin mensaje
final (tope de pasos). Las otras dos: una no editó (2.048 tokens de
razonamiento sin acción, igual que antes) y otra escribió el `&&` y terminó
sin correr los tests. Gemma **puede**; lo que no tiene hoy en ollama es
consistencia: 1/3 con varianza de 34 a 121 s.
⁶ Bonsai a 0,7 (`change-react-component-preset-oficial/`): 3/3 en 103-125 s,
misma velocidad que a 0,2, y **tres soluciones distintas y correctas**:
`const hasDiscount = discount != null && discount > 0`, `const d = discount
?? 0`, y `discount && discount > 0 ? … : null`. La forma varía con la
temperatura; el invariante no: estrecha el tipo, ternario con `null`,
`Math.round` en centavos, y en las tres el primer `run_tests` rojo y el
segundo verde. Eso es criterio y no suerte de muestreo frío — la distinción
que en el 9B no se pudo establecer (4/12 a 0,2, 5/12 a 0,7).

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
- **`bonsai-2:9b` no es un atajo.** Tiene la velocidad del `qwen3.5:9b`
  (13-29 s en niveles 1-2) y resuelve 1 y 2, pero en el 3 queda en 0/3 por
  no saber salir de un error de tipos que el 27B resuelve al primer intento
  y el `qwen3.5:9b` ni comete. A igual velocidad, el `qwen3.5:9b` es mejor;
  a igual criterio, hace falta el 27B. El ternario paga en el tamaño grande,
  no en el chico — al menos en estas tareas.
- **`gemma4:12b`, hoy, no se puede evaluar limpio en esta máquina.** Tres
  cosas se mezclan: la plantilla de chat en ollama 0.40.6 (turnos vacíos
  con `think:false`, `<channel|>` en el texto), una KV cache que lleva la
  carga a 16,5 GB en 16 y hace que la máquina suelte conexiones, y lo que sí
  parece del modelo — razonamiento largo que a veces no termina en acción, y
  el mismo `discount > 0` sin estrechar el tipo que hunde a bonsai 9B.
  Resuelve niveles 1 y 2 (con razonamiento); en el 3, 0/6. **Repetido con
  ollama 0.40.13 y `num_ctx` 8K: 0/3 otra vez** (`change-react-component-
  ollama-nuevo-8k/`). La actualización descartó dos de los tres factores:
  la sonda del turno vacío con `think:false` dio exactamente lo mismo en
  0.40.13 (es cómo ollama sirve a Gemma 4 hoy, no un bug de una versión), y
  con 8K la carga bajó de 16,5 a 7,8 GB sin que nada cambiara en el
  resultado. Lo que queda es del modelo en este runner: en 2 de 3 corridas
  **no editó nunca** — leyó y razonó 2.048 tokens hasta el tope de
  `num_predict` sin una acción — y en la que editó, `discount > 0 &&` con
  `discount?: number` (`TS18048` y el `&&` juntos, con la regla en el
  prompt), 6/6 tests y typecheck rojo. Con el preset de Google y el
  workaround del turno vacío (nota ⁵): **1/3**, y esa una es el mejor diff
  de la serie. Veredicto corregido: `gemma4:12b` **sabe** hacer el nivel 3 —
  el problema es la consistencia en ollama hoy (loops de razonamiento,
  issues #18861 y #16562 abiertos), no el criterio. Para niveles 1-2 el
  `qwen3.5:9b` lo hace igual, más rápido y sin razonamiento; para el 3,
  bonsai 27B sigue siendo el único 9/9. Revisar gemma cuando ollama cierre
  #18861.
- Tiempos limpios del nivel 3, medidos con la máquina quieta: **qwen 9B
  21-33 s, bonsai 27B 100-109 s** — 3 a 5×. Ese es el precio del criterio
  en esa máquina: el 9B responde en medio minuto y acierta el `&&` una de
  cada tres veces; el 27B tarda minuto y medio y no falla.

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

## Lo que dicen los autores (leído el 2026-10-29, fuentes primarias)

Todo lo de arriba se midió con `temperature: 0.2` y los demás parámetros en
el default del modelo. Las model cards recomiendan otra cosa; esto es lo que
hay que probar antes de dar un modelo por bueno o malo.

| Modelo | Preset recomendado (sin razonamiento) | Con razonamiento | Notas del autor |
|---|---|---|---|
| [`Qwen3.5-9B`](https://huggingface.co/Qwen/Qwen3.5-9B) | temp 0.7 · top_p 0.8 · top_k 20 · min_p 0 · presence 1.5 | general: temp 1.0 · top_p 0.95 · presence 1.5; **código preciso: temp 0.6 · presence 0** | `presence_penalty` 0-2 contra repeticiones, "puede mezclar idiomas y bajar algo el rendimiento"; no soporta `/no_think` (verificado por nosotros); para tool use recomiendan el parser `qwen3_coder` en vLLM/SGLang |
| [`Ternary-Bonsai-2-27B`](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf) | temp 0.7 · top_p 0.8 · top_k 20 · presence 1.5 (igual que Qwen: deriva de **Qwen3.8-27B**, arquitectura sin cambios) | temp 1.0 · top_p 0.95 · min_p 0.05 · presence 0 | Benchmarks propios vs FP16: código 89,4 vs 89,1 (LiveCodeBench 90,07 vs 90,05), **tool calling BFCL 74,9 vs 76,7** — coincide con lo medido: criterio intacto, herramientas un poco más torpes. Avisa que **llama.cpp estándar carga el Q2_0 "sin aviso y produce basura"**; ollama 0.40 trae los kernels (nuestros 9/9 lo prueban) |
| [`gemma4:12b`](https://ollama.com/library/gemma4:12b) | temp 1.0 · top_p 0.95 · top_k 64, "para todos los usos"; Unsloth **desaconseja temperaturas bajas** | ídem | Lo corrimos a 0,2: en contra de la recomendación, y con razonamiento es receta de loop |

Y lo que ya sabíamos por síntoma tiene nombre y número en ollama:

- **Turno vacío de gemma con `think:false` tras un resultado de herramienta**:
  [#18861](https://github.com/ollama/ollama/issues/18861) (abierto; PR #18862
  sin mergear) y su duplicado [#19044](https://github.com/ollama/ollama/issues/19044).
  Causa: el renderer de gemma4 no escribe nada después de un tool response si
  el razonamiento está apagado, y el modelo a veces cierra el pensamiento
  vacío con un token de tool call y termina. Workaround del reporte: razonar
  solo en el turno siguiente a un tool result — implementado en el runner como
  `think_after_tool: true`.
- **"gemma4:12b prácticamente inusable en ollama en Apple Silicon"**:
  [#16562](https://github.com/ollama/ollama/issues/16562), abierto desde
  junio, sin diagnóstico de los mantenedores; generaciones de 8 minutos,
  cuelgues, respuestas vacías, "no usable" en 0.32-0.33. Nuestros 1.273 s y
  los 2.048 tokens sin acción son ese issue en 0.40.13.
- Las comparativas de blogs (qwen 9B vs gemma 12B) son direccionales y
  contradictorias entre sí; la única que coincide con nuestra medición es la
  de consenso: qwen 9B para tool calling, gemma para multimodal.

## Cómo actualizarlo

`./runner/run-remote.sh <ip> <modelo> 3` deja una carpeta en `runs/` con
`meta.txt` (host, versión, digest, fecha) y un JSON por corrida; para el
modelo local, el mismo script con `127.0.0.1`. Un modelo o una versión nueva
es una fila nueva, nunca se pisa una medida.
