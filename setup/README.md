# Preparar una máquina

Lo mínimo para que opencode le hable a un modelo de ollama con herramientas.
Medido en el [spike 1](../docs/spikes/2026-10-28-tool-calls-2b.md): sin los
dos primeros puntos el modelo no ve las herramientas y una corrida tarda
minutos en vez de segundos.

## 1. ollama: ventana de contexto

La ventana por defecto de ollama es 4096 tokens y opencode manda ~11.000 solo
de arranque: ollama trunca y el modelo nunca ve las herramientas. Se crea un
alias del modelo con `num_ctx` mayor, a partir del Modelfile de esta carpeta:

```bash
ollama pull qwen3.5:2b                       # o el modelo que corresponda
ollama create qwen3.5:2b-16k -f setup/Modelfile.qwen3.5-2b-16k
ollama show qwen3.5:2b-16k | grep num_ctx    # debe decir 16384
```

Después de un `ollama pull` que actualice el modelo base hay que **volver a
correr `ollama create`**: el alias apunta a las capas del momento en que se
creó, no al tag.

Para el 8B la forma es la misma (`Modelfile.qwen3.5-8b-16k`, cuando exista).
La alternativa global es `OLLAMA_CONTEXT_LENGTH=16384` en el entorno del
servidor; no la usamos porque no queda versionada y afecta a todos los
modelos de la máquina.

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

## 3. La máquina que sirve el 8B por red

En la máquina que sirve: `OLLAMA_HOST=0.0.0.0` en el entorno del servidor de
ollama y el puerto 11434 abierto en la red local. En la que corre el harness,
el `baseURL` del provider pasa a `http://<ip-de-la-otra>:11434/v1`. Pendiente
de verificar en la práctica (ADR-0003).
