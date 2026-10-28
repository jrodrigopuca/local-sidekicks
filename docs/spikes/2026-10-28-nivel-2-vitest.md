# Spike 3 — ¿Un 2B sostiene una tarea que escribe? (actualizar un test en Vitest)

Fecha: 2026-10-28. `qwen3.5:2b` (digest `dfaf2605162e`) vía `qwen3.5:2b-16k`,
`runner/control.py` con `edit`/`write`/`run_tests`, `think: false`,
`temperature: 0.2`. Fixture: el proyecto del spike 1 más `formatPercent(ratio)`
en `src/lib/format.ts` sin test; Vitest instalado; línea de base 1 test verde.

**Tarea** (prompt del usuario): "formatPercent(ratio) was added to
src/lib/format.ts. Add a test in src/lib/format.test.ts checking that
formatPercent(0.125) returns '12,5 %'. Run the tests."

**Verificación externa, después de cada corrida y desde afuera del modelo:**
`git checkout` antes de empezar; al terminar, `npx vitest run` debe dar
**2 tests en verde** (base + 1) y el diff debe contener `formatPercent(0.125)`.
Las tres condiciones, o la corrida no cuenta.

## Tally: 18 corridas, 6 tandas de 3

| Tanda | Qué cambió respecto de la anterior | Correctas | Cómo fallaron las otras |
|---|---|:---:|---|
| 1 | runner con `edit`, `write`, `run_tests` | 0/3 | 2× tocó el módulo (`format.ts`) y lo rompió; 1× borró el test existente (suite "verde" con 1 test) |
| 2 | **guardas**: `writable:` por glob, no borrar tests, `--expect-tests 2` | 1/3 | 1× bug del runner (rechazó re-correr tests tras un edit); 1× ídem |
| 3 | bug del runner corregido | 1/3 | 1× borró el test existente (la guarda contaba `it(`, no nombres); 1× **test trampa**: verde sin llamar a `formatPercent` |
| 4 | guarda por **identidad** de test, `--expect-diff` | 0/3 | 3× sin el import, `not defined`, se agotaron los 8 pasos |
| 5 | **regla de prompt**: "un test solo puede llamar lo que el archivo importa; agregá el nombre al import existente" | **2/3** | 1× reemplazó el import en vez de extenderlo |

(La tanda 2→3 son 18 corridas en total contando la de diagnóstico.) Las dos
correctas de la tanda 5: 6 pasos, 33-37 s, ~10K tokens de entrada
acumulados, ~500 generados, mensaje final que dice qué hizo y dónde.

## Lo que cada falla enseñó, y dónde quedó la lección

Control primero, prompt después. En ese orden porque una guarda es
determinista y una regla de prompt es una probabilidad.

1. **El modelo toca lo que no debe → `writable:` en el agente.** Lista de
   globs; `edit`/`write` fuera de ella se rechazan con el motivo. En la
   tanda 4 se ve funcionando: tres intentos sobre `format.ts`, tres
   rechazos, el modelo vuelve al archivo de test. Es la misma idea que
   `permission` por ruta en opencode, pero del lado del runner.
2. **"Verde" no es "correcto", dos veces.** Reemplazar el único test por el
   nuevo deja el suite verde con la misma cantidad → `--expect-tests` (base
   + 1) y guarda por **identidad** (cada nombre de test que existía al
   empezar debe seguir). Y un test que calcula el resultado sin llamar a la
   función también queda verde → `--expect-diff` con una regex sobre el
   diff. Es la lección de `interaction/build2` ("el entregable es el
   archivo; la regresión se cuenta") más una nueva: **el criterio de
   contenido no es opcional** con un modelo chico.
3. **Mi propia guarda anti-loop le negó `run_tests` después de un `edit`**
   y costó dos corridas que iban bien. Regla: una escritura exitosa vuelve a
   habilitar lecturas y corridas de tests; solo se rechaza la repetición
   cuando nada cambió.
4. **La falla dominante (10 de 18) es olvidar el import** y leer
   `formatPercent is not defined` como "la función no existe". Ninguna
   guarda la arregla; la arregló una regla de prompt **específica de la
   clase de tarea** (nivel 2 con Vitest): 0/3 → 2/3. Para un 2B, una regla
   concreta sobre el error que va a cometer vale más que diez principios.
5. **`max_steps: 8` es el techo correcto.** Las correctas usaron 6; las que
   llegaron a 8 no iban a arreglarse con 12 — estaban en loop.

## Lo que esto decide

- **El 2B sostiene el nivel 2 a 2/3 con guardas + una regla específica,**
  con ~35 s por corrida y sin tocar nunca lo que no debe. No es confiable
  para dejarlo solo; sí es usable con la verificación externa como red, que
  es exactamente lo que el runner hace.
- **El veredicto de nivel 2 es del 8B** (ADR-0003): la regla "si aguanta en
  2B aguanta en 8B" dice que el 8B debería dar ≥ 2/3; lo que no sabemos es
  si llega a 3/3 sin la regla del import. `runner/control.py` ya lee
  `OLLAMA_URL`, así que la misma tanda corre contra la otra máquina sin
  cambiar nada.
- Las guardas y las verificaciones son **del runner, no del modelo**: valen
  igual para un 8B, y son lo que un host tiene que ofrecer para que valga
  la pena usarlo. Esa es ahora la vara del bake-off (ADR-0004 pendiente):
  ¿deja negar por ruta? ¿deja verificar desde afuera?

## Pendiente que abre

1. Misma tanda (find-usages + update-vitest-test) contra el 8B remoto.
2. Segunda tarea de escritura ("hacer un cambio en un componente React")
   con el mismo método: fixture, verificación externa, 3 corridas.
3. El caso "reemplazó el import en vez de extenderlo" (tanda 5, corrida 3):
   ¿regla de prompt o guarda sobre imports? Medir antes de elegir.
