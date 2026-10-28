# ADR-0003: Dos modelos: 2B para desarrollar, 8B remoto como puerta de salida

- Estado: aceptada (2026-10-28)
- Drivers: (1) la máquina de desarrollo tiene 8 GB de RAM (M1): un 8B
  cuantizado son ~5 GB de pesos más KV cache y entra en swap — minutos por
  corrida, inútil para iterar; (2) `qwen3.5:2b` ya está bajado y declara la
  capacidad `tools`; (3) el objetivo del proyecto es prompts chicos y precisos,
  y un piso más bajo lo fuerza.
- Decisión: el loop de desarrollo corre en `qwen3.5:2b` en esta máquina; el
  veredicto que va a `MODELOS.md` se toma en `qwen3.5:8b` servido desde otra
  máquina por red (`ollama serve` en 11434, provider de opencode apuntado por
  `baseURL`), con el repo, los fixtures y `runs/` quedándose en una sola
  máquina. `run.py --model` es obligatorio y cada corrida registra con cuál se
  midió. Regla de piso: un sidekick que aguanta en 2B aguanta en 8B; al revés
  no, así que "listo" se declara solo con el 8B.
- Tradeoff aceptado: depende de que las dos máquinas compartan red; una
  diferencia 2B/8B en un escenario obliga a correr dos veces para entender cuál
  de los dos miente.
- Revisar si: la máquina de desarrollo pasa a tener 16 GB o más, o el `baseURL`
  remoto de opencode resulta no funcionar (entonces el harness se clona en la
  otra máquina y `runs/` se sincroniza por git).
