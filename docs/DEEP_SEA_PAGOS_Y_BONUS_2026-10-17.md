# Deep Sea Frenzy: pagos por símbolos, premios y free spins

**Fecha:** 17 de octubre de 2026.  
**Juego:** `vs50frenzy` — Deep Sea Frenzy, Pragmatic Play.  
**Run verificado:** https://github.com/Shisetsu-Code/Inspector/actions/runs/39046120427  
**Resultados:** https://github.com/Shisetsu-Code/Inspector/actions/runs/39046120427/artifacts/12106096541

## Resumen confirmado por evidencia

Inspector procesó la inicialización de la demo oficial sin enviar ningún giro. Extrajo la `paytable` de `doInit` y la condición pública de bonus de la ficha del proveedor; son **dos fuentes distintas**.

- `doInit`: la tabla de premios declara algunas combinaciones de **2 símbolos** y otras desde **3 símbolos**.
- Descripción pública oficial: **8 o más símbolos de dinero** en carretes 1–4, simultáneamente con **Collect** en carrete 5, activan la funcionalidad y otorgan inicialmente **5 free spins**. Collect +1 añade un giro.
- `doInit` no publicó la tabla `scatters` convencional en esta captura. No se presume que exista una condición de tres scatters.
- El parser cliente sabe interpretar `WinAmount`, `WinPositions`, premios agrupados, multiplicadores y contadores de free spins, pero no demuestra que valide independientemente cada pago desde el resultado final.
- El motor matemático de producción del servidor no fue recuperado.

## Paytable extraída de doInit

| Símbolo | 2 coincidencias | 3 | 4 | 5 |
| --- | ---: | ---: | ---: | ---: |
| 1 | 3× | 10× | 60× | 200× |
| 2–3 | 2× | 10× | 50× | 160× |
| 4–5 | — | 10× | 40× | 100× |
| 6–7 | — | 5× | 40× | 80× |
| 8–9 | — | 5× | 10× | 50× |
| a–b | — | 5× | 10× | 40× |

**Importante:** estos son coeficientes declarados por cantidad. Dos símbolos iguales colocados en lugares arbitrarios de la pantalla no implican un premio. Hace falta confirmar la línea o modalidad válida, símbolos sustitutos, dirección de pago y denominación. La ausencia de un pago por dos símbolos en una fila no descarta otros premios de la misma pantalla.

## Condición pública del bonus

El extractor de la descripción publicada produce:

    minimum_money_symbols=8
    money_symbol_reels=[1,2,3,4]
    collect_symbol_reel=5
    awarded_free_spins=5
    collect_plus_one_can_add_one_spin=true

El evaluador comprueba escenarios sintéticos:

| Money symbols | Collect en carrete 5 | Collect +1 | Resultado según regla publicada |
| ---: | --- | --- | --- |
| 7 | Sí | No | No reúne la condición |
| 8 | No | No | No reúne la condición |
| 8 | Sí | No | Cumple; 5 free spins declarados |
| 8 | Sí | Sí | Cumple; 6 free spins declarados |

No se identificó aún una relación certificada entre los IDs gráficos del protocolo (`S`, `T`, etc.) y cada componente semántico money/Collect. Tampoco se conoce el valor individual de los money symbols ni el multiplicador efectivo, por lo que no se calcula la ganancia monetaria real de una pantalla arbitraria.

## Cómo usar la interfaz gráfica

1. En Windows, ejecutar `Abrir_Inspector.cmd`.
2. Seleccionar el HAR y pulsar `Analizar HAR`.
3. En el panel de tabla de pagos, indicar símbolo y número de coincidencias y pulsar `Evaluar condición`.
4. En el panel de bonus, indicar cantidad de money symbols, presencia de Collect en el carrete 5 y el indicador +1 y pulsar `Evaluar bonus`.

Todo esto se ejecuta localmente sobre los informes; **no se envían apuestas, compras, bonus ni giros**.

## Línea de comandos

    py -3 -m inspector.cli analyze "juego.har" --out resultado
    py -3 -m inspector.cli pay-count resultado 1 2
    py -3 -m inspector.cli pay-count resultado 4 2
    py -3 -m inspector.cli pay-count resultado 4 3
    py -3 -m inspector.cli pay-line resultado 11142
    py -3 -m inspector.cli bonus-check resultado 7 --collect-reel5
    py -3 -m inspector.cli bonus-check resultado 8 --collect-reel5
    py -3 -m inspector.cli bonus-check resultado 8 --collect-reel5 --plus-one

`pay-line` es un ejemplo de prefijo consecutivo de símbolos desde la izquierda; **no valida el pago comercial** de una pantalla ni infiere los paylines efectivos.

## Archivos

- `payment_contract.json`: mínimos, multiplicadores, capacidades parser y límites.
- `official_feature_rules.json`: reglas detectadas en la ficha oficial, con atribución y advertencias.
- `paytable.json`: tabla de `doInit`.
- `client_evidence.json`: señales de los parsers y animaciones.
- `summary.json`: resultados e indicadores de evidencia.

## Qué falta para verificar los premios exactos

1. Geometría y dirección **efectiva** de las líneas o vías de pago.
2. Condiciones completas de Wild, money symbols, Collect y cualquier transformación.
3. Denominación y factores monetarios para traducir los coeficientes en efectivo.
4. Información de transición de estado y liquidación del servidor para bonus/free spins.
5. Confirmar el tratamiento de las estructuras de premios en las respuestas reales de una ronda.

**El cliente no tiene por qué aceptar o rechazar los premios.** El código puede limitarse a interpretar el `WinAmount` recibido y mostrarlo. La validez del resultado económico corresponde al contrato aplicado por el servidor.
