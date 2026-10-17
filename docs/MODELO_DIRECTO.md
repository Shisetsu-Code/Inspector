# Modelo exacto de paradas directas

## Alcance

Inspector no afirma haber recuperado el generador del servidor. Esta capa examina **únicamente** las tiras de \`reel_setN\` publicadas por \`doInit\` y evalúa la hipótesis delimitada:

- Una pantalla de un \`reel_set\` se compone de una ventana circular consecutiva por carrete.
- Todos los carretes del mismo conjunto se detienen independientemente y sus ventanas pueden combinarse.
- Las ventanas tienen exactamente \`sh\` símbolos, con \`sw\` carretes.
- No intervienen cascadas, sustituciones, símbolos adicionales, control de estados ni generación remota distinta.

**No se conocen las probabilidades de parada ni se necesitan para este cálculo.** Tampoco conocemos si todas esas combinaciones pueden ocurrir en el juego real.

## Conteo y duplicados

Para cada conjunto \`s\` y carrete \`r\`, definimos \`W[s,r]\` como el conjunto de ventanas circulares *distintas* de altura \`sh\`. El conjunto de pantallas directas es el producto cartesiano de \`W[s,0] × ... × W[s,sw-1]\`.

Su cardinalidad es \`product_r |W[s,r]|\`.

Para la unión sobre conjuntos, Inspector aplica inclusión-exclusión:

\`|∪_s A_s| = Σ_{∅≠T⊆S} (-1)^(|T|+1) × product_r |∩_{s∈T} W[s,r]|\`.

Así se obtiene el resultado sin enumerar miles de millones de pantallas. Por defecto la cuenta exacta se limita a 12 conjuntos, para evitar la explosión exponencial de subconjuntos. Por encima de ese número devuelve cotas sin afirmar exactitud.

El histograma del símbolo \`S\` se calcula de la misma manera, convolucionando por carrete las cantidades de ventanas que contienen 0, 1, 2... símbolos S. Es una **distribución de pantallas distintas**, no una distribución probabilística del RNG.

## Qué demuestra y qué no

**MATCH**: la pantalla candidata coincide con un conjunto completo para alguna orientación serializada (por filas o columnas).  
**NOT_IN_DIRECT_MODEL**: no existe tal coincidencia dentro de las tiras y condiciones de esta hipótesis.  
**UNKNOWN**: es siempre la conclusión respecto de la validez matemática real del backend, incluso cuando el candidato coincide.

Una pantalla incompatible con la hipótesis no puede declararse prohibida por el proveedor. Es posible que el servidor seleccione o componga resultados sin recorrer estas tiras literalmente.

No ejecutar código JavaScript descargado como parte de la validación. No reproducir resultados a partir de frecuencias observadas.

## Interfaz y comandos

En Windows: \`Abrir_Inspector.cmd\` → seleccionar HAR → \`Analizar HAR\` → escribir pantalla → \`Comprobar pantalla\`.

En CLI:

    py -3 -m inspector.cli analyze "juego.har" --out resultado
    py -3 -m inspector.cli check "resultado" "943bb39531a1S7452883"

La cadena de ejemplo pertenece al modelo directo de Deep Sea Frenzy, tiene 20 símbolos y está ordenada por filas. No procede de un giro real.

## Evidencia y auditoría

Los reportes \`direct_model.json\`, \`summary.json\` y \`sample_screen_check.json\` no incluyen cookies ni identificadores de sesión. El ejemplo automático de Actions se genera determinísticamente tomando cuatro símbolos consecutivos de cada tira del primer conjunto completo disponible, y se somete al mismo comprobador que utiliza la GUI.

Los ensayos unitarios comprueban un caso de conjuntos parcialmente solapados, un histograma simple y una pantalla presente/ausente. En todos se exige \`server_outcome_validity=UNKNOWN\`.
