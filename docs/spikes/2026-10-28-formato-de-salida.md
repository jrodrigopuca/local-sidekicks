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

## Corrección (misma noche): opencode sí acepta `options`, y eso cambia la tabla

La conclusión de arriba —"no se arregla desde opencode"— era cierta para
el frontmatter del agente y falsa para la configuración del modelo. En
`opencode.json`, `provider.ollama.models.<id>.options` **se copia tal cual
al body del request** (verificado con el proxy: llegaron `think`,
`temperature` y `reasoning_effort`). Y medido campo por campo contra `/v1`
con la misma pregunta de una palabra:

| Campo en el request `/v1` | Razonamiento | Tokens | Tiempo |
|---|---:|---:|---:|
| ninguno | 14.572 chars | 3.466 | 180 s |
| `think: false` | 2.896 chars | 740 | 38 s |
| `temperature: 0.2` sola | 1.241 chars | 340 | 18 s |
| **`reasoning_effort: "none"`** | **0** | **1** | **0,6 s** |

El endpoint OpenAI-compatible de ollama lee `reasoning_effort`, no `think`
(ese es el nombre de la API nativa, que usa el runner). Qwen 3.5 ignora el
`/no_think` en el prompt (1.476 chars igual).

Con `options: {reasoning_effort: "none", temperature: 0.2}` en el modelo,
la variante `probe-ex` (ejemplo completo + "empezá con USES OF") por
opencode, tres corridas:

| | antes (matriz de arriba) | con `options` |
|---|---|---|
| Formato | 0/3 | **3/3** |
| Tiempo | 44 · 708 · 28 s | **14 · 8 · 6 s** |
| Recall de los 10 usos | no medido | **6/10, 6/10, 6/10** |
| Acceso dinámico | — | 0/3 |

Lectura honesta: el formato **sí** era alcanzable con prompt una vez
apagado el razonamiento y bajada la temperatura — la matriz de la mañana
medía el prompt con el thinking encendido, y eso tapaba todo. Pero el
contenido empeoró respecto del runner de control (10/10 en 5/5): las tres
corridas omitieron las tres líneas del archivo de test y una de `Cart.tsx`.
Hipótesis, sin probar: el runner vuelve a pegar la evidencia junto al pedido
final y opencode no; a 2B, lo que quedó lejos se cae. Es el próximo
experimento, y es barato.

### El experimento de re-anclaje por prompt (tres variantes, 3 corridas cada una)

La hipótesis era que el runner llega a 10/10 porque vuelve a pegar la
evidencia junto al pedido final. En opencode no se controla el flujo de
mensajes, así que el re-anclaje tiene que pedirlo el prompt:

| Variante | Instrucción | Formato | Recall (bloque `USES OF`) |
|---|---|:---:|---|
| `probe-ex` (base) | ejemplo completo | 3/3 | 6/10 · 6/10 · 6/10 |
| `probe-map` | "una línea por match, mismo orden, mismo número que grep" | 3/3 | 6/10 · 6/10 · 6/10 |
| `probe-copy` | "copiá primero las líneas del grep, después clasificá" | 0/3 | 8/10 · 8/10 · (ilegible) |

Lectura: la instrucción de mapeo no mueve nada; copiar la evidencia antes de
clasificar sube el recall (6 → 8) pero rompe el formato (negritas, bloque
renombrado) y sigue inventando una línea (`Receipt.tsx:5`). **El re-anclaje
estructural del runner (la evidencia en el mismo mensaje que el pedido, y
un esquema que el sampler hace cumplir) no se reproduce por prompt con un
2B.** Las tres variantes se quedaron sin las tres líneas del archivo de test
que grep sí devolvió.

### El "cuelgue" de opencode era un arranque lento

Durante esta tanda, `opencode run --standalone` tardó en arrancar 105 s y
**479 s** en dos corridas que después terminaron bien, y en otra franja de
una hora ninguna corrida pasó del boot dentro de topes de 60-300 s. El log
muestra el servidor detenido antes de su primera acción, con *watchers*
sobre directorios padre hasta `/Users/juan` y `/`. Es intermitente: tras
una corrida que arranca, las siguientes arrancan en segundos. Los topes del
harness no pueden distinguirlo de un modelo colgado; `spike-run.py` ahora
registra el tiempo hasta el primer evento para separarlos. La salida que
opencode ofrece y no se probó: un `opencode serve --port N` persistente por
tanda y `run --server http://127.0.0.1:N`, que paga el boot una vez.

Lo que sigue valiendo del bloque de arriba: `format` con esquema solo lo da
la API nativa; la varianza de tiempos venía del thinking; y la temperatura
por frontmatter de agente no se pasa — va por `options` del modelo o por
`PARAMETER` del Modelfile (que opencode heredaría; `think` no existe como
parámetro de Modelfile, verificado).

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
