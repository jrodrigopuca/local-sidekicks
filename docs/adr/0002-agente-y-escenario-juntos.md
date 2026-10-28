# ADR-0002: Agente, fixture y escenarios viven en la misma carpeta

- Estado: aceptada (2026-10-28)
- Drivers: (1) un solo host (opencode) — la separación catálogo/harness de
  `local-agents` + `interaction` existía para probar la salida de un instalador
  en cinco hosts, y acá no hay cinco; (2) el escenario no es "una prueba del
  agente", es la especificación de la tarea: sin él no se sabe qué promete el
  sidekick; (3) `interaction/run.py` (2.700 líneas) está acoplado a `claude -p`,
  `~/.claude/agents` y costo en USD — portarlo es reescribirlo.
- Decisión: `agents/<tarea>/` contiene `agent.md`, `fixtures/` y
  `scenarios.yaml`; `validate` rechaza un agente sin escenarios. El harness es
  nuevo y chico, alrededor de `opencode run`, con rama con/sin agente, juez
  Sonnet vía `claude -p` (el único punto pago, ya calibrado en interaction
  B-039) y métricas de tokens, segundos y cantidad de tool calls — no USD.
  `budget.py` cuenta tokens de `agent.md` más los schemas de sus herramientas
  y falla el CI si pasan el techo.
- Tradeoff aceptado: un repo que mezcla catálogo y harness; se renuncia a
  reusar el runner existente y a la multi-host.
- Revisar si: aparece un segundo host con modelos locales que valga la pena
  medir; entonces el harness se separa, no antes.
