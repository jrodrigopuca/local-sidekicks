# Preparar una máquina

Lo mínimo para que opencode le hable a un modelo de ollama con herramientas.
Medido en el [spike 1](../docs/spikes/2026-10-28-tool-calls-2b.md): sin los
dos primeros puntos el modelo no ve las herramientas y una corrida tarda
minutos en vez de segundos.

## 1. ollama: ventana de contexto

La ventana por defecto de ollama es 4096 tokens y opencode manda ~11.000 solo
de arranque: ollama trunca y el modelo nunca ve las herramientas. Hay dos
formas de subirla; las dos están verificadas en esta máquina.

**a) Desde la app de ollama (macOS):** Settings → *Context length* → 16k. Eso
pone `OLLAMA_CONTEXT_LENGTH=16384` en el entorno del servidor (se ve en la
primera línea de `~/.ollama/logs/server.log`, `server config env=…`) y vale
para **todos** los modelos de esa máquina. Es lo más rápido y no requiere
terminal. Lo que no da: queda fuera del repo, así que anotarlo en
`MODELOS.md` cuando se mida.

**b) Alias por Modelfile:** un alias del modelo con `num_ctx` propio, a partir
del Modelfile de esta carpeta. Sirve para una máquina sin la app (Linux,
servidor) y deja la ventana versionada:

```bash
ollama pull qwen3.5:2b                       # o el modelo que corresponda
ollama create qwen3.5:2b-16k -f setup/Modelfile.qwen3.5-2b-16k
ollama show qwen3.5:2b-16k | grep num_ctx    # debe decir 16384
```

Después de un `ollama pull` que actualice el modelo base hay que **volver a
correr `ollama create`**: el alias apunta a las capas del momento en que se
creó, no al tag (verificado el 2026-10-28: tras actualizar `qwen3.5:2b` de
2,7 a 3,1 GB, el alias seguía en el digest viejo hasta recrearlo).

Para el 8B la forma es la misma (`Modelfile.qwen3.5-8b-16k`, cuando exista).
Con la app configurada en 16k el alias es redundante en esa máquina, pero no
molesta; el harness usa el nombre del alias para que `MODELOS.md` diga con
qué ventana se midió sin depender de cómo esté la app.

## 2. opencode: provider y agente `title`

En el `opencode.json` del proyecto donde corre el harness:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "title": { "disable": true }
  },
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (local)",
      "options": { "baseURL": "http://localhost:11434/v1" },
      "models": {
        "qwen3.5:2b-16k": { "name": "Qwen 3.5 2B (16k ctx)", "tool_call": true }
      }
    }
  }
}
```

- `agent.title.disable`: opencode genera un título de sesión con una llamada
  extra antes de la del agente; con un 2B esa llamada tardó 510 s de 586.
- `tool_call: true`: sin eso opencode no le ofrece herramientas al modelo.
- Verificar con `opencode models | grep ollama` que el modelo aparece.

## 3. En cada agente: negar `execute`

El 83 % del prompt que opencode manda (9.148 de 11.047 tokens) es el
catálogo "Code Mode": firmas de herramientas internas que se llaman vía
`execute`. Se apaga por agente, en el frontmatter:

```yaml
permission:
  edit: deny
  bash: deny
  execute: deny      # apaga el catálogo Code Mode: 11.047 → 1.310 tokens
  question: deny
  skill: deny
  websearch: deny
```

Para un sidekick de solo lectura quedan `read`, `grep` y `glob` (867 tokens de
schemas). Medido en el spike 1, corridas 5-7.

## 4. Correr desde un script

- Siempre `opencode run --standalone …`: el servicio de fondo se colgó dos
  veces al arrancar (loop de `GET /api/tags` sin mandar el chat).
- Tope duro por corrida: `timeout -s KILL <seg> opencode run …`. opencode
  ignora el SIGTERM que manda `timeout` sin `-s`.
- Las salidas (dumps, jsonl, logs) van **fuera** de la carpeta del fixture:
  el `grep` del modelo las encuentra y le ensucian el contexto.
- Para ver los bytes exactos que opencode manda: `tools/log-proxy.py`.

## 5. La máquina que sirve el 8B por red

En la máquina que sirve: `OLLAMA_HOST=0.0.0.0` en el entorno del servidor de
ollama y el puerto 11434 abierto en la red local. Con la app de macOS, el
servidor arranca con `OLLAMA_HOST:http://127.0.0.1:11434` (visto en el log de
esta máquina); la app tiene un ajuste para exponerlo a la red — a verificar
que es ese el que cambia ese valor. En la que corre el harness,
el `baseURL` del provider pasa a `http://<ip-de-la-otra>:11434/v1`. Pendiente
de verificar en la práctica (ADR-0003).
