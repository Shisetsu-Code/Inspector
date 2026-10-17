# Verificación de Inspector con Deep Sea Frenzy — V2

**Fecha:** 17 de octubre de 2026.  
**Juego:** `vs50frenzy`, Deep Sea Frenzy (Pragmatic Play).  
**Run final:** https://github.com/Shisetsu-Code/Inspector/actions/runs/39036859850  
**Commit probado:** `a405a45de55eae145474f1ed3244234a1d23be7e`  
**Artifact:** https://github.com/Shisetsu-Code/Inspector/actions/runs/39036859850/artifacts/12102920531

## Resultado obtenido automáticamente

| Comprobación | Resultado |
| --- | --- |
| Tests unitarios | PASS |
| Captura pasiva con Playwright | PASS |
| doInit | 1 |
| Giros enviados | 0 |
| Recursos estáticos indexados | 69 |
| build.js presente | sí |
| Conjuntos de tiras | 5 |
| Tiras individuales | 25 |
| Pantalla declarada | 5×4 |
| Unión exacta de pantallas directas | 6.399.810.846 |
| Suma de conjuntos antes de descontar duplicados | 6.399.812.926 |
| Duplicados descontados por inclusión-exclusión | 2.080 |
| Prueba sobre muestra de pantalla directa | PASS |
| Conocimiento completo de RNG server-side | NO |

El testigo `943bb39531a1S7452883` fue construido tomando cuatro símbolos consecutivos de cada una de las cinco tiras del primer conjunto y serializándolos por filas. El mismo algoritmo de validación consumido por la GUI devolvió `direct_model_compatible=true` y `server_outcome_validity=UNKNOWN`.

El histograma de cantidad de símbolos `S` está en `direct_model.json`. No es una frecuencia de RNG ni una estimación de probabilidades.

## Corrección de robustez

Una corrida intermedia falló porque el capturador accedía a `request.post_data` de POST binarios de terceros, generando un `UnicodeDecodeError` en Playwright. La captura ahora verifica primero el método, host y ruta; solo decodifica POST pertenecientes a `gameService`. Se incorporó un test con un POST binario simulado. La corrida final completa verifica la corrección.

## Límites

Los resultados clasificados describen el **modelo de paradas circulares directas**. No se han recuperado ni probado las reglas completas de sustitución, cascadas o generación del servidor. Por tanto, no hay base para declarar exhaustivamente qué tiradas finales del backend son posibles o prohibidas.
