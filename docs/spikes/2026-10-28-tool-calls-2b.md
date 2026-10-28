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
  las herramientas de escritura negadas. Es system prompt propio de opencode +
  schemas de las herramientas que quedan + entorno. Nuestro prompt son 150 de
  esos 11.000: **el presupuesto de tokens del agente es irrelevante al lado del
  del host.** Qué hay exactamente en esos 11K y si opencode deja recortarlo
  (reemplazar su system prompt por agente) es la próxima pregunta.
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

## Pendiente que abre

1. Ver qué hay en los 11K del host y si se puede recortar por agente.
2. Hacer que el formato de salida se respete (¿regla al final del prompt?
   ¿ejemplo completo? ¿validar en el harness y reintentar?).
3. Repetir la tanda con el `qwen3.5:2b` nuevo y anotar el digest.
