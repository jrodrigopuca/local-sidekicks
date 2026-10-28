# Spike 2 — ¿Se puede hacer que el 2B respete un formato de salida?

Fecha: 2026-10-28, misma tarde que el spike 1. `qwen3.5:2b` nuevo (digest
`dfaf2605162e`) vía alias `qwen3.5:2b-16k`, opencode v2.1.3 con `execute:
deny` (piso 1.310 tokens), ollama 0.40.12 (runner `mlx`).

**Pregunta:** en siete corridas del spike 1 el contenido fue correcto y el
formato pedido (`USES OF … / TOTAL: n`) se ignoró siempre. ¿Lo arregla el
prompt, la temperatura, o ninguno de los dos?

**Respuesta: ninguno de los dos desde opencode. Se arregla en el sampler,
que opencode no expone.**

## Matriz: 4 variantes × 3 corridas, `tools/spike-run.py`

Juez: regex (empieza con `USES OF` y contiene `TOTAL:`), no un modelo.

| Variante | Qué cambia | Formato | Segundos (3 corridas) |
|---|---|---|---|
| `probe` | plantilla `<path>:<line>`, regla al medio | 0/3 | 105 · 154 · 39 |
| `probe-ex` | ejemplo completo + "Start your reply with USES OF" al final | 0/3 ¹ | 44 · 708 · 28 |
| `probe-t` | plantilla + `temperature: 0.2` en frontmatter | 0/3 | 1490 ² · 365 · 89 |
| `probe-ex-t` | ejemplo + temperatura | 1/3 | 50 · 73 · 49 |

¹ `probe-ex-2` produjo el formato exacto pero dentro de un bloque ```` ``` ````.
² Terminó con `Timed out waiting for response data` de opencode; el tope de
300 s del runner no la cortó (sin explicar; el runner ahora impone el tope
por sí mismo).

Dos hechos salen del dump del proxy, no de la tabla:

- **opencode no pasa `temperature`** al provider: el request lleva solo
  `model` y `max_completion_tokens: 32000`. Las variantes `-t` eran
  idénticas a las otras; el 1/3 es ruido.
- **La varianza es el problema más grave**: 28 s a 1.490 s para la misma
  tarea, con corridas que encadenan cinco o seis `read` de paseo. El
  razonamiento de Qwen 3.5 (thinking) ocurre del lado de ollama; opencode
  no lo muestra (cero partes `reasoning` en las 12 corridas) y no lo apaga.

## Directo a ollama (`/api/chat`), misma tarea

System prompt de una línea, el grep ya hecho pegado en el mensaje, `format`
con un esquema JSON (`{symbol, uses: [{path, line, kind}], total_files}`),
`temperature: 0.2`:

| | Tokens generados | Tiempo | Formato |
|---|---:|---:|---|
| `think: true` | 3.443 (11.500 caracteres de razonamiento) | 175 s | válido |
| **`think: false`** | **240** | **12 s** | **válido** |

Misma clasificación en ambas salvo una (`format.test.ts:6`: `test` con
thinking, `call` sin). **14× más rápido, y el formato garantizado por el
sampler**, no por el prompt.

## Lo que esto decide

- El formato de salida **no es un problema de prompt** para un 2B; es un
  parámetro de generación (`format` con esquema). Pedirlo en texto da 1/12.
- `think: false` es el control que más tiempo compra, y ningún host de los
  que pasan por `/v1` lo expone hoy (verificado en opencode; Codex y Crush
  sin medir).
- Para el harness: medir **tokens generados** además de segundos — es lo que
  separa "pensó 11K caracteres" de "la máquina estaba lenta".
- Esto es la evidencia a favor del **runner de control** (ADR pendiente):
  un loop propio contra `/api/chat` tiene `think`, `format`, `temperature`
  y `num_ctx` por llamada. Lo que un host no deja tocar, ahí se mide.

## Runner de control: primer número (`runner/control.py`, misma tarde)

Loop propio contra `/api/chat` (nativo), `grep`/`read`/`glob` confinadas al
fixture, `think: false`, `temperature: 0.2`, y una llamada final con el
esquema JSON de la tarea (`runner/examples/find-usages/`). Misma pregunta,
mismo fixture, mismo modelo.

| | opencode (`execute: deny`) | Runner de control |
|---|---:|---:|
| Piso de prompt (1.ª llamada) | 1.310 tokens | **545 tokens** |
| Formato válido | 1/12 | **5/5** |
| Recall de los 10 usos | correcto en prosa, sin medir exacto | **10/10 en 5/5** |
| Entradas inventadas | 1 path inventado en 1 corrida | 0 en 4/5 ¹ |
| Tiempo por corrida | 28 s – 1.490 s | **28 – 33 s** |
| Tokens generados | sin medir (opencode no los muestra) | ~550 |

¹ La quinta escribió `"path": "src/x.ts:1"` (línea pegada al path) en las
diez entradas: contenido correcto, forma desviada; el scorer lo cuenta
aparte (`path:line=10`), no como diez errores.

Lo que costó llegar a 5/5, en orden, porque cada paso es una regla:

1. **La primera versión degeneró**: la llamada final con esquema produjo 58
   entradas (`format.test.ts` líneas 6, 8, 10… 112) hasta agotar
   `num_predict`. El resultado del grep había quedado dos mensajes atrás,
   detrás de la prosa del modelo. **Volver a pegar los resultados de las
   herramientas junto al pedido del JSON** lo arregló: 0 inventadas.
2. **`total_files` salió mal 3/3** (9, 9, 10 contra 5): el 2B cuenta entradas,
   no archivos. Se sacó del esquema. **Lo que el código puede calcular no
   se le pide al modelo.**
3. **`kind: dynamic`** para `fmt["formatPrice"]` acertó 1/5 (las otras: `call`
   o `definition`). Brecha del modelo, no del runner: queda como escenario
   del sidekick `find-usages`, y es el tipo de criterio que el juez del
   harness tiene que mirar además del recall.

Las defensas que lleva adentro, todas usadas en estas corridas o en las de
opencode: argumentos rotos devueltos como error, salida de herramienta
truncada (6.000 caracteres), tool call idéntico repetido rechazado, tope de
pasos, timeout por llamada, `num_predict` como cortafuegos de loops.

## Pendiente que abre

1. ~~Runner de control.~~ Hecho; arriba. Siguiente: el mismo brazo contra
   Codex y Crush (bake-off, ADR-0004 pendiente) — el runner es el control.
2. Averiguar si Codex o Crush pasan `temperature`/`reasoning` al provider.
3. Por qué `timeout -s KILL` no cortó la corrida de 1.490 s.
