# Spike 1 — ¿Un 2B hace tool calls en opencode?

Fecha: 2026-10-28. Máquina: M1, 8 GB. opencode v2.1.3, ollama 0.35.0,
`qwen3.5:2b` (digest `324d162be6ca`, Q8_0, pulled 2026-03-24 — hay una versión
más nueva disponible; esta tanda es con la vieja).

**Pregunta:** con un agente de solo lectura (`read` + `grep`), ¿`qwen3.5:2b`
hace tool calls a través de opencode, o contesta de memoria?

**Respuesta: sí, y bien — una vez que ve las herramientas.** Las dos primeras
corridas fallaron por la configuración, no por el modelo.

## Fixture

Proyecto TS/React de 5 archivos con `formatPrice` usado en 10 lugares:
definición, dos componentes (import + llamadas), un test, y un acceso dinámico
`fmt["formatPrice"]` plantado para ver si lo encuentra. Agente `probe` con
`permission: {edit: deny, bash: deny, webfetch: deny, …}`, prompt de ~150
tokens con formato de salida fijo. Pregunta: "Where is formatPrice used in
this repo?".

## Las tres corridas

| # | Config | Tiempo | Tool calls | Resultado |
|---|---|---|---|---|
| 1 | ollama por defecto (`num_ctx` 4096) | 223 s | 0 | "No tengo herramientas de acceso a archivos" |
| 2 | `num_ctx` 16384 | 586 s | 2 | Correcto, encontró el acceso dinámico |
| 3 | 16384 + `agent.title.disable` | **35 s** | 1 | Correcto, encontró el acceso dinámico |
| 4 | igual que 3, **modelo actualizado** (digest `dfaf2605162e`, 3,1 GB), caché frío | 70 s | 1 | Correcto, con un error: `src/report.ts` en vez de `src/lib/report.ts` |

La corrida 4 es la que vale como referencia de ahora en más: modelo nuevo y
sin caché de prefijo (los ~27 s de procesar los 11K en frío están incluidos).
El path mal escrito es un modo de falla a esperar de un modelo chico: el
harness tiene que verificar que cada path reportado existe, no solo que el
juez lo encuentre razonable.

Lo que explica cada salto, con la evidencia:

1. **ollama truncó el prompt.** Log de ollama: `truncating input prompt
   limit=2050 prompt=11037`. opencode mandó 11.037 tokens; la ventana por
   defecto de ollama es 4096 y se quedó con los primeros 2.050. El modelo
   nunca vio las herramientas. Llamado directo a `/v1/chat/completions` con un
   solo tool `grep` (314 tokens), el mismo modelo hizo el tool call en 5 s.
2. **El agente interno `title` de opencode se comió el 87 % del tiempo.**
   Corre antes que el agente del usuario (`small=true agent=title` en el log
   de opencode) con un prompt de 470 tokens, y el 2B generó 11.622 tokens
   (510 s a 22,7 tok/s) antes de parar. Con `agent.title.disable: true` en
   `opencode.json` desaparece.

## Los números que condicionan el diseño

- **Piso de contexto de opencode: ~11.000 tokens** con el agente cargado y
  las herramientas de escritura negadas. Nuestro prompt son 150 de esos
  11.000. Qué hay adentro y cómo bajarlo a 1.310 está en "Los 11K abiertos",
  más abajo.
- **Velocidad del 2B acá:** ~22 tok/s de generación, ~400 tok/s de prompt
  eval. Procesar los 11K en frío son ~27 s; ollama cachea el prefijo entre
  sesiones (la corrida 3 reprocesó 4 tokens), así que corridas repetidas con
  el mismo agente no lo pagan. La corrida 3 se benefició de ese caché: en frío
  sería ~60 s.
- Cada resultado de `grep` que vuelve al modelo cuesta lo que pesa: el de la
  corrida 3 fueron 2.858 tokens por 14 coincidencias.
- **El formato de salida no se respetó en ninguna corrida** (pidió
  `USES OF … / TOTAL: n`, devolvió markdown propio). El contenido fue
  correcto; la forma, no. Es el primer problema de diseño de agente real que
  tiene este repo.

## Lo que esto decide

- `num_ctx` 16384 (mínimo) es requisito, no opción. Va como alias de modelo
  por `Modelfile` (ver `setup/`), no como env global del servidor, para que
  quede versionado y `MODELOS.md` registre con qué ventana se midió.
- `agent.title.disable: true` va en el `opencode.json` del harness.
- El harness mide **tokens de prompt reportados por ollama**, no los del
  agente: el piso del host es parte de lo que se mide.
- `tools:` en el frontmatter está deprecado en el esquema de opencode; usar
  `permission:` (lo que install.py de local-agents ya hace).
- El modelo con `tool_call: true` en el provider es necesario para que
  opencode le ofrezca herramientas.

## Los 11K abiertos (corridas 5-7, misma tarde)

Con `tools/log-proxy.py` entre opencode y ollama se capturó el request
exacto y se midió cada pieza en tokens pidiéndoselos a ollama por separado
(la suma dio 11.046 contra 11.047 reportados: la medición cierra).

| Pieza del request | Tokens | % |
|---|---:|---:|
| Nuestro prompt (`probe.md`) | 99 | 0,9 |
| `# Your Model` + entorno (`<env>`, fecha, cwd) | ~90 | 0,8 |
| **Catálogo "Code Mode"** — firmas TypeScript de 7 herramientas internas de opencode (`session_rename`, `worktree_create`, `models`, recursos MCP…) para llamar vía `execute` | **9.148** | **82,8** |
| Schemas JSON de las 7 herramientas ofrecidas (`glob`, `grep`, `read`, `question`, `skill`, `websearch`, `execute`) | 1.682 | 15,2 |
| Mensaje del usuario | 15 | 0,1 |

**El 83 % del piso es un catálogo que un sidekick nunca va a usar, y se
apaga desde el agente.** Negando `execute` (más `question`, `skill` y
`websearch`) en `permission:`, el mismo request bajó a:

| | Tokens |
|---|---:|
| system (nuestro prompt + modelo + entorno) | 428 |
| tools (`glob`, `grep`, `read`) | 867 |
| usuario | 15 |
| **Total** | **1.310** (antes 11.047) |

Corrida 7 con esa configuración, fixture limpio, caché frío: **53 s**, un
`grep`, 10 coincidencias, respuesta correcta. El `codemode: boolean` del
esquema de config es por servidor MCP; para el grupo interno de opencode no
hay toggle — el deny de `execute` es la vía.

Tres hallazgos laterales de estas corridas, todos para el harness:

- **`opencode run` se cuelga a veces al arrancar** cuando usa el servicio de
  fondo (`opencode serve --service`): hace `GET /api/tags` en loop y nunca
  manda el chat. Con `--standalone` (servidor privado por corrida) no pasó.
  El harness corre siempre con `--standalone`.
- **Las salidas del harness no pueden vivir dentro del fixture.** En la
  corrida 6, `dumps/` y `run*.jsonl` estaban en la carpeta del fixture y el
  `grep` del modelo devolvió 31 KB de JSON ajeno; el 2B entró en un loop de
  generación, opencode cortó la request (`BrokenPipe`) y la reintentó cuatro
  veces, 18 minutos cada una, sin tope. Con el fixture limpio (corrida 7) no
  se repitió. Una muestra: hipótesis, no prueba. Dos reglas salen igual:
  salidas fuera del fixture, y tope de tiempo por corrida con `timeout -s
  KILL` (opencode ignora el SIGTERM de `timeout`).
- La actualización de la app de ollama trajo ollama **0.40.12** y un runner
  `mlx` en Apple Silicon (antes llama.cpp). El log de ollama ya no muestra
  los conteos de tokens por request; el proxy es la forma de medir ahora.

## Pendiente que abre

1. ~~Ver qué hay en los 11K del host y si se puede recortar por agente.~~
   Hecho: 1.310 tokens con `execute: deny`.
2. Hacer que el formato de salida se respete (¿regla al final del prompt?
   ¿ejemplo completo? ¿validar en el harness y reintentar?).
3. ~~Repetir la tanda con el `qwen3.5:2b` nuevo y anotar el digest.~~ Hecho:
   corrida 4.
