# Deep Sea Frenzy — evidencia del cliente y límites del generador

**Fecha:** 17 de octubre de 2026  
**Juego:** Deep Sea Frenzy — Pragmatic Play — `vs50frenzy`  
**Run verificado:** https://github.com/Shisetsu-Code/Inspector/actions/runs/39037659121  
**Artefacto:** https://github.com/Shisetsu-Code/Inspector/actions/runs/39037659121/artifacts/12102244532

## Alcance

Esta inspección se efectuó **sin enviar giros**. El workflow capturó una respuesta `doInit`, 69 recursos estáticos, `build.js` y los tres fragmentos de escena `game000.json`, `game001.json` y `game002.json`. Los fragmentos se combinaron antes de interpretarlos. El resultado fue `scene.status=PARSED`, con 142 tipos diferentes de componentes de escena.

La inspección solo compara firmas de funciones estáticas con las declaraciones de componentes. No ejecuta el código capturado, no extrae tokens y no publica el JavaScript original.

## Hallazgos confirmados

| Señal observada | Resultado | Alcance |
| --- | --- | --- |
| `VS_Reel.prototype.GetNextSymbol` | Encontrado en `build.js` | Código disponible en el cliente |
| Rama con `Vars.ResultScreenSymbols` | Encontrada | Existe ruta para mostrar símbolos de resultado |
| Rama con `this.symbolList` | Encontrada | Existe ruta que usa lista de símbolos para parada visual |
| `RequestProvider.prototype.NewRequest` con `ServerOptions.isOnline` | Encontrada | Código cliente distingue transporte online |
| Clase `OfflineServer` | Presente en bundle | Su presencia NO demuestra uso en producción |
| `RequestProvider.offlineServer` | `null` en la escena | No está conectada la instancia genérica offline en esa escena |
| `VS_ReelsManager.stopOnScreenSymbols` | `false` en la escena | La bandera no activa por defecto esa rama |
| `VSProtocolParser` | Presente | Cliente dispone de parser de protocolo |
| Generador matemático completo del backend | NO recuperado | No podemos demostrar todo el universo de tiradas |
| Resultados finales globalmente prohibidos | Ninguno demostrado | No confundir con incompatibilidad del modelo de carretes |

La coincidencia de símbolos de los carretes con un resultado tampoco prueba que el backend lo genere. A la inversa, una pantalla no presente entre ventanas directas podría producirse por otras rutas o transformaciones. **La capacidad del código no implica que esté habilitada por la escena**, y los valores en la escena pueden depender de más condiciones no capturadas.

## Modelo directo separado

Los archivos `reel_rules.json` y `direct_model.json` identifican 5 conjuntos, 25 tiras y una unión de 6.399.810.846 pantallas distintas de paradas circulares independientes, descontando 2.080 duplicados entre conjuntos. Esas cifras describen la hipótesis de tiras directas, **no** las tiradas comerciales autorizadas por el servidor. En el HAR automático no se registraron giros.

## Archivos del análisis

- `client_evidence.json`: componentes, firmas y conclusiones con alcance explícito.
- `direct_model.json`: combinaciones de ventanas directas y número de símbolos `S`.
- `summary.json`: resumen de la captura y clasificación.
- `assets_index.json`: rutas de recursos estáticos, tamaños y hashes; no código propietario.
- `sanitized-init.har`: solo configuración de doInit con claves admitidas, no HAR de sesión.

## Próximos límites técnicos

Para clasificar todos los resultados finales se necesitan las reglas que el servidor aplica al escoger, transformar y devolver un estado. Si dichas reglas no se publican en el cliente ni en su inicialización, Inspector no puede establecerlas con certeza solo mediante análisis estático. La conclusión correcta sigue siendo `UNKNOWN`.
