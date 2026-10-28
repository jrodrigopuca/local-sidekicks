# ADR-0001: La unidad de diseño es la tarea, no el rol

- Estado: aceptada (2026-10-28)
- Drivers: (1) contexto — un agente de `local-agents` carga 5-6K tokens antes
  de la primera skill (el generalist solo pesa 12 KB) y un 8B tiene 8-32K de
  ventana útil; (2) lo medido en `interaction/MODELOS.md`: las reglas duras
  aportaron +37 %/+25 % (Sonnet/Haiku) y las de juicio +12 %/+13 % — con un
  modelo chico la brecha se agranda; (3) tool-calling errático en modelos
  chicos: cuantas menos herramientas vea, menos se equivoca.
- Decisión: un sidekick = una tarea (`agents/<tarea>/`), con una salida de
  formato fijo, tres o cuatro reglas duras, un ejemplo y una allowlist de
  herramientas mínima declarada en su frontmatter. Sin persona, sin creencias,
  sin herencia. `core/base.md` arranca vacío y una línea sube solo si se midió
  que aporta en tres agentes.
- Tradeoff aceptado: se pierde la capacidad de juicio transversal que da un rol;
  las tareas abiertas (cambiar un componente, encontrar un error sin pista) no
  son un sidekick sino una cadena de sidekicks, o un modelo más grande.
- Revisar si: un sidekick con reglas de juicio le gana a su versión de solo
  reglas duras en la misma tanda, tres corridas, en el modelo piso.
