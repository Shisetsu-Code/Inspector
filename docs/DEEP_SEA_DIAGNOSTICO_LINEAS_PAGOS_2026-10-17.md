# Deep Sea Frenzy — líneas, símbolos especiales, apuestas y premios recibidos

**Investigación:** 17 de octubre de 2026  
**Juego:** Pragmatic Play / Deep Sea Frenzy (`vs50frenzy`)  
**Captura y pruebas verificadas:** https://github.com/Shisetsu-Code/Inspector/actions/runs/39049200830  
**Análisis numérico y de campos de línea:** https://github.com/Shisetsu-Code/Inspector/actions/runs/39049055963  
**Alcance:** recursos públicos de inicialización (doInit) y código/escenas descargados por el navegador, sin enviar giros.

## Resultado y distinción fundamental

Inspector confirmó tres capas diferentes:

1. **Condiciones publicadas:** `paytable` en `doInit` contiene coeficientes desde 2/3 coincidencias según símbolo; la ficha pública especifica un bonus al reunir 8 símbolos de dinero y Collect en el quinto carrete.
2. **Presentación de premios:** `VSProtocolParser.ParseWinLines` y `ParseWinGroups` interpretan `WinAmount`, `WinPositions` y campos de grupos; `WinLineVisual.OnWinLineShow` puede resaltar posiciones que recibió, utilizando `Vars.ReceivedWinLines` y `symbolSquares`.
3. **Motor de premios del backend:** no se ha recuperado ninguna especificación completa que convierta arbitrariamente una pantalla 5×4 en el cobro y los giros gratis efectivos, ni todas las reglas de generación del RNG.

La existencia de métodos de parser es **evidencia estática**, no prueba de que ese método específico haya sido ejecutado durante una tirada en este juego.

## Hallazgo sobre los 50 LineInfo

La escena contiene un componente `VS_LinesDefinitions`. El campo `symbolSquares` aloja 50 registros `LineInfo`:

- Cantidad de registros: **50**.
- Vectores de `symbolIndices` distintos: **1**.
- Los 50 contienen **`[0,1,2,3,4]`**.
- Las direcciones publicadas en esos registros son `LEFT_TO_RIGHT`.
- Los 50 vectores pasan una comprobación geométrica por filas, pero **son iguales**.
- Estado de validación estricta: **`NO_EXPLICIT_LINE_PATHS`**.
- `explicit_paths_ready=0`; no existen 50 recorridos diferentes recuperados de ese campo.

Conclusión: **no son evidencia de 50 paylines independientes**. Podrían ser plantillas o estructuras usadas para resaltar posiciones premiadas; el código gráfico consume `symbolSquares` y `WinPositions`, pero no confirma aquí todas las coordenadas pagadoras. La interfaz y la CLI se niegan a calcular el cobro de una pantalla completa si la geometría no está acreditada.

Los datos están en `line_candidates.json`, `line_geometry.json` y `win_delivery_trace.json`. Estos archivos no contienen código propietario completo ni identificadores de sesión.

## Wild y símbolos especiales

De las tiras de `reel_set0`–`reel_set4`, el identificador `W` aparece en los carretes **2, 3, 4 y 5**, pero no en el primero. Esto demuestra su presencia literal en las tiras; **no demuestra** qué símbolos sustituye, qué multiplica, ni si interviene en todos los modos. Su semántica de Wild comercial queda `UNKNOWN`.

Tampoco existe vinculación completa verificada entre `S`, `T`, `U`, `V`, `W`, `X`, `Y` y cada función de dinero/Collect. La descripción oficial utiliza nombres semánticos, mientras que las tiras incluyen identificadores internos.

## Escala monetaria observada

Datos extraídos de `doInit`:

| Parámetro | Declarado |
| --- | --- |
| `sc` | 22 valores, de `0.01` a `10.00` |
| `bls` | `25,40` |
| `c` | `0.08` |
| `l` | `25` |
| `total_bet_min` | `0.25` |
| `total_bet_max` | `42500.00` |

El cálculo hipotético `sc × bls` obtiene un mínimo de `0.25` y un máximo de `400.00`. La coincidencia del mínimo aporta una pista, **pero no prueba** que esa fórmula determine el importe monetario real: el máximo no coincide con el límite publicado y no se ha verificado la modalidad o los multiplicadores efectivos.

La conversión del coeficiente de `paytable` a cobro en dinero permanece indeterminada.

## Tabla de pagos y free spins

`doInit` anuncia pagos desde **2 coincidencias** para `1`, `2` y `3`; otros símbolos de la tabla empiezan en 3. Son condiciones de la tabla, no premios por cualquier par/tercia de símbolos ubicados arbitrariamente.

La descripción oficial de Deep Sea Frenzy permite identificar un disparador: al menos **8 money symbols** en carretes 1–4 y **Collect** en carrete 5, con **5 free spins** iniciales; el Collect `+1 Spin` puede agregar otro giro. Esa regla procede de la descripción pública, **no** de una traza de bonus ejecutado.

## Uso de Inspector

1. En Windows: `Abrir_Inspector.cmd` → seleccionar HAR → `Analizar HAR`.
2. En la sección de tabla de pagos, consultar símbolos y coincidencias.
3. En la sección de bonus, evaluar el recuento semántico de money symbols y Collect.
4. En pantalla completa, pulsar `Evaluar pagos de pantalla`. Para este juego y esta captura debe indicar que **no existen rutas de líneas explícitas suficientes** para certificar un premio.
5. Por consola, usar `py -3 -m inspector.cli evaluate-screen resultado <pantalla_de_20_simbolos>` o `screen-pay` (alias), que aplican la misma validación estricta.

No se envían apuestas ni giros. La clasificación `UNKNOWN` de cobro o validez del RNG no es un error de la herramienta: refleja los límites de los archivos disponibles.

## Verificación de GitHub Actions

En la corrida final verificada se observaron `doInit=1`, **69 recursos**, **5 conjuntos**, **25 tiras**, presencia de `build.js` y **0 giros enviados**. Las pruebas unitarias y el trabajo de captura terminaron correctamente. El reporte mantiene `payment_line_cash_validation_possible=false` y `complete_server_math_known=false`.

**Siguiente fuente necesaria:** un contrato verificable de posiciones ganadoras y liquidación, procedente de una especificación matemática o de evidencia de rondas autorizadas. El JavaScript de animaciones por sí solo no determina cuáles resultados puede generar ni cuánto debe pagar el servidor.
