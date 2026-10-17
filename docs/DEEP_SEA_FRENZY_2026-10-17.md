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


## Ampliación verificada: unión exacta del modelo directo

La siguiente cifra fue calculada con las tiras de los cinco reel_set de la captura. Cada carrete aporta las ventanas circulares **distintas** de cuatro símbolos. El número de pantallas distintas de un conjunto es el producto de las opciones de sus cinco carretes. Las duplicadas entre reel_set se descuentan mediante inclusión-exclusión de intersecciones.

| Conjunto | Ventanas distintas por carrete | Pantallas distintas |
| --- | --- | ---: |
| reel_set0 | 85, 51, 74, 73, 53 | 1.241.136.510 |
| reel_set1 | 84, 75, 70, 52, 53 | 1.215.396.000 |
| reel_set2 | 94, 58, 83, 44, 64 | 1.274.285.056 |
| reel_set3 | 76, 75, 73, 40, 54 | 898.776.000 |
| reel_set4 | 90, 79, 63, 52, 76 | 1.770.219.360 |
| **Suma con duplicados** | — | **6.399.812.926** |
| **Duplicados entre conjuntos** | — | **2.080** |
| **Unión sin duplicados** | — | **6.399.810.846** |

Un testigo sintético reproducible del conjunto 0, ordenado por filas: `943bb39531a1S7452883`. Su compatibilidad con ventanas directas no implica que sea una tirada autorizada por el backend.

El histograma exacto de cantidad de `S` se exporta en `direct_model.json`, sin pesos ni frecuencias. Las ventanas extraídas de las tiras no contienen `S` en el quinto carrete. Estas restricciones son válidas **dentro del modelo directo sin transformaciones**; no constituyen prohibiciones globales para los resultados del servidor.

La nueva herramienta permite comprobar una pantalla de 20 símbolos desde la GUI o con el comando `python -m inspector.cli check <carpeta> <pantalla>`.
