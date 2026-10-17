# Captura autónoma: Deep Sea Frenzy

**Fecha:** 17 de octubre de 2026  
**Proveedor:** Pragmatic Play (demo oficial)  
**Juego:** Deep Sea Frenzy — `vs50frenzy`  
**URL:** https://www.pragmaticplay.com/en/games/deep-sea-frenzy/?gamelang=en&cur=USD  
**Workflow:** [Inspector CI y captura demo — run 39035599166](https://github.com/Shisetsu-Code/Inspector/actions/runs/39035599166)  
**Commit probado:** `067f6fa5ecfef66b27444dda3c7e48b895568984`

## Resultado de ejecución real

La corrida GitHub Actions terminó correctamente, con los trabajos `tests` y `capture` en `success`. El analizador produjo `status=OK_INIT`, lo que acredita la inicialización y **no** la reconstrucción del motor matemático del servidor.

| Magnitud | Resultado |
| --- | --- |
| doInit | 1 |
| Giros enviados por Inspector | 0 |
| Giros históricos en esta captura | 0 |
| Recursos estáticos indexados | 69 |
| build.js | Detectado |
| Conjuntos reel_set | 5 |
| Tiras individuales | 25 |
| Pantalla declarada | 5 × 4 (rect) |
| Símbolos con pagos en paytable | 11 |
| Matemática completa del servidor | No conocida |
| Todas las tiradas finales permitidas/prohibidas | No conocidas |

La captura bloqueó 20 solicitudes mutadoras de terceros o distintas de `doInit` (ver `capture_status.json`), y no registró advertencias de navegación.

## Restricciones de símbolos observadas en reel_set

El alfabeto estático de los cinco conjuntos presenta este patrón por carrete:

| Carrete | Símbolos declarados en al menos uno de los cinco conjuntos |
| --- | --- |
| 1 | `123456789Sab` |
| 2 | `123456789SWab` |
| 3 | `123456789SWab` |
| 4 | `123456789SWab` |
| 5 | `123456789TUVWXYab` |

Por lo tanto, `S` no está en la tira directa del quinto carrete; `T`, `U`, `V`, `X` e `Y` se observan solo en tiras del quinto carrete. Esto **no demuestra imposibilidad global**: una transformación, modo distinto o lógica remota puede introducir resultados no explicados por esas tiras.

El modelo de paradas circulares directas, de altura 4, devuelve cantidades por conjunto que se pueden calcular como producto de ventanas distintas. Ese modelo es un conjunto hipotético, no el universo final de resultados.

## Evidencia

[Descargar el artifact depurado de GitHub Actions](https://github.com/Shisetsu-Code/Inspector/actions/runs/39035599166/artifacts/12101953213)

Incluye `reel_rules.json`, `paytable.json`, `summary.json`, `assets_index.json`, `capture_status.json`, `sanitized-init.har` y `report.md`. No publica cookies, HAR bruto ni el JavaScript propietario original.

**Conclusión:** validada la captura autónoma de inicialización del juego `vs50frenzy` desde GitHub Actions, sin participación humana ni giros. Faltan los contratos del generador server-side para clasificar exhaustivamente tiradas finales.
