# Deep Sea Frenzy: trazado de animación y selección inicial de carretes

**Fecha:** 17 de octubre de 2026
**Juego:** Deep Sea Frenzy, código `vs50frenzy`
**Run confirmado:** https://github.com/Shisetsu-Code/Inspector/actions/runs/39044859917
**Artifact depurado:** https://github.com/Shisetsu-Code/Inspector/actions/runs/39044859917/artifacts/12105203299
**Commit verificado:** `4886b68342aad6c3ada8764ae4777766099b3885`

## Resultado verificado automáticamente

- Tests unitarios: correctos.
- Captura Playwright demo oficial: correcta.
- `doInit`: 1; giros emitidos por Inspector: 0.
- `build.js`: presente; escena: PARSED.
- Recursos estáticos catalogados: 69.
- Geometría: 5×4.
- Conjuntos: 5, con 25 tiras individuales.
- Conjunto actual declarado en `doInit`: **`reel_set=0`**.
- Ventanas combinadas únicas para ese conjunto, **solo bajo el modelo circular directo**: **1.241.136.510**.
- Unión hipotética de los cinco conjuntos, mismo modelo: **6.399.810.846**.
- Tiradas finales admisibles/prohibidas por el generador server-side: **UNKNOWN**.

## Verificación del código de animación

`animation_origin_trace.json` identifica 77 métodos relevantes de parser y carretes según firmas estáticas.

| Elemento | Evidencia |
| --- | --- |
| `VS_Reel.prototype.GetNextSymbol` | Encontrado, función balanceada y analizada |
| Rama `Vars.ResultScreenSymbols` | Encontrada dentro del método |
| Rama `this.symbolList` | Encontrada dentro del método |
| `Math.random()` y `emptySymbolReplacements` | Coexistentes en la ruta de sustitución visual |
| `stopOnScreenSymbols` | `false` en configuración inicial de la escena |
| `RequestProvider.offlineServer` | `null` en escena |
| Activación dinámica de la rama durante un giro | No observada (sin `doSpin`) |
| Motor matemático del servidor incluido en bundle | No demostrado |

## Campos que el cliente puede interpretar

| Campo | Estado |
| --- | --- |
| `reel_set` | Observado en `doInit`; valor numérico `0` |
| `reel_set_size` | Observado en `doInit` |
| `n_reel_set` | CLIENT_KNOWS_FIELD_ONLY |
| `srf` (sustitución) | CLIENT_KNOWS_FIELD_ONLY |
| `tmb` (cascadas) | CLIENT_KNOWS_FIELD_ONLY |
| `n_rsl` (símbolos siguientes) | CLIENT_KNOWS_FIELD_ONLY |
| `msr` (mystery symbol) | CLIENT_KNOWS_FIELD_ONLY |

`CLIENT_KNOWS_FIELD_ONLY` significa que aparece en el diccionario y parser del JavaScript, no que haya sido recibido en la captura. La captura no ejecuta giros por diseño.

## Respuesta a la hipótesis de las animaciones

Hay código de selección visual de símbolos y una ruta de `Math.random()` vinculada con sustituciones de símbolos vacíos. **Esto demuestra aleatoriedad en la interfaz, no una función de elección de premios o tiradas comerciales.**

Sí es útil para reconstruir restricciones de representación y distinguir símbolos transitorios de resultados recibidos. No permite por sí solo demostrar qué pantallas genera realmente el servidor.

## Salida y privacidad

La captura genera `animation_origin_trace.json`, `client_evidence.json`, `reel_set_selector_evidence.json`, `direct_model.json`, `summary.json` y otros informes. No incluye código JavaScript propietario original ni HAR con tokens en el artifact público.
