# Animación versus motor matemático — Inspección estática

## Pregunta

¿Se pueden utilizar las animaciones para reconstruir las tiradas permitidas e imposibles?

**Se pueden identificar reglas de representación, transiciones y transformaciones que efectivamente existen en el cliente.** Pero la animación puede consumir resultados ya decididos por el backend. Sin demostrar que el código de animación participa en la elección de resultados, no se puede atribuirle la matemática comercial del proveedor.

## Canal de datos

El código de la plataforma Pragmatic puede contener las siguientes rutas:

    Respuesta HTTP -> parser del protocolo -> datos del resultado
        -> selección de elementos de pantalla -> manager de carretes -> animación

En otros casos el motor gráfico puede producir símbolos temporales usando tiras visuales o selecciones pseudoaleatorias, mientras espera el resultado. Esos símbolos transitorios no son necesariamente el estado final validado por el servidor.

Inspector NO envía giros en esta investigación. Por eso los campos que solo aparecen en el código se registran como capacidades declaradas y no como campos observados en una respuesta real de giro.

## Señales que Inspector inspecciona

| Señal | Significado posible | Límite |
|---|---|---|
| `Vars.ResultScreenSymbols` | Ruta de lectura del resultado para visualización | No prueba el origen del RNG |
| `VS_Reel.prototype.GetNextSymbol` | Obtención del próximo símbolo para animación | Puede elegir símbolos meramente visuales |
| `this.symbolList` | Secuencia de símbolos del carrete gráfico | No equivale necesariamente a la tira matemática |
| `Math.random()` | Aleatoriedad de animación o simulación local | No es prueba de RNG comercial |
| `reel_set` | Identificador del conjunto actual del protocolo | El cliente puede conocerlo sin que esté presente en la captura |
| `n_reel_set` | Identificador del conjunto siguiente del protocolo | Su presencia en código no prueba que se use en ese juego |
| `srf` | Datos de sustitución de símbolos | Deben confirmarse las reglas que los consumen |
| `tmb` | Datos de cascadas | No implica todas las combinaciones posibles |
| `n_rsl` | Lista de símbolos siguientes | Requiere evidencia de su interpretación específica |

## Niveles de evidencia

- **OBSERVED_IN_CAPTURE:** el campo estaba presente en una respuesta `doInit` o `doSpin` del HAR proporcionado; no significa que conozcamos todos los valores válidos ni las transiciones.
- **CLIENT_KNOWS_FIELD_ONLY:** el diccionario y el parser del cliente conocen el campo; la captura no demostró que llegase en una respuesta.
- **NOT_CONFIRMED:** no se encontró la vinculación sintáctica completa.
- **UNKNOWN:** no conocemos las restricciones generativas del servidor.

Un método puede estar compilado y no ejecutarse en la modalidad analizada. Un componente puede estar habilitado inicialmente pero cambiar de estado durante la ronda, o estar deshabilitado inicialmente pero ser habilitado después. El análisis estático no observa estos cambios.

## Procedimiento autónomo

1. Playwright abre la demo y deja que llegue `doInit`; no pulsa Spin.
2. El HAR se analiza localmente para recuperar las declaraciones de `reel_setN` y los assets.
3. El contenido de `build.js` se analiza *solo en memoria* buscando funciones del parser, rutas de símbolos, selectores y operaciones de animación.
4. Los componentes de la escena se usan para distinguir capacidades compiladas de configuraciones iniciales, sin asumir activaciones futuras.
5. `animation_origin_trace.json` almacena exclusivamente nombres de métodos, marcadores, booleanos y estados de evidencia.
6. No se publica el código propietario, HAR crudo, sesión, tokens ni solicitudes de apuesta.

## Qué permitiría resolver el problema completamente

Para demostrar qué tiradas finales son alcanzables hay que tener una especificación de cómo el servidor selecciona y transforma resultados. La animación ayuda a identificar una parte de la composición final, pero no prueba por sí sola cuáles son los estados que el backend puede generar. Sin la información ausente, la única conclusión responsable es `UNKNOWN`.
