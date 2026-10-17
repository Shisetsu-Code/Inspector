# Inspector — Pragmatic Play HAR

**Inspector** es una herramienta local de Windows y un workflow de GitHub Actions para recuperar **automáticamente** los recursos de inicialización de demos oficiales Pragmatic Play. No requiere operar el juego y nunca envía giros o compras.

El usuario puede seleccionar cualquier HAR ya capturado en la interfaz gráfica, o utilizar Actions para crear un HAR **en el runner de GitHub**: Playwright abre la ficha oficial, localiza la URL de la demo, registra el tráfico del navegador y procesa la respuesta de inicialización doInit. El HAR de red completo es temporal; el artefacto publicable está depurado.

## Estado real de la investigación

En las capturas de Big Bass Vegas 1000 (vs10bbveg1000) y Forever Split Megaways (vswaysmgrmgw) detectamos que doInit incluye conjuntos de tiras y tablas de pago. Algunos resultados reales NO son ventanas consecutivas del conjunto publicado: el cliente puede mostrar símbolos devueltos por el servidor independientemente de sus tiras de animación.

**Por lo tanto, estos datos NO permiten conocer todas las tiradas permitidas y prohibidas por el RNG real.** Inspector diferencia la compatibilidad con paradas directas de la validez global del servidor, que queda en UNKNOWN. No interpreta palabras como random o transform en el JavaScript como prueba de que exista un RNG local.

## Windows (interfaz gráfica)

Instalar Python 3.11 o posterior, clonar o descargar el código del repositorio y ejecutar:

    Abrir_Inspector.cmd

Elegir el archivo HAR, la carpeta de resultados y pulsar **Analizar HAR**. La herramienta funciona offline, no usa navegador y no modifica el HAR.

## Línea de comandos

Analizar una captura local:

    py -3 -m inspector.cli analyze "C:\Capturas\juego.har" --out resultado

Capturar y analizar una demo oficial automáticamente, sin clics ni giros:

    py -3 -m pip install -r requirements-online.txt
    py -3 -m playwright install chromium
    py -3 -m inspector.cli capture "https://www.pragmaticplay.com/en/games/big-bass-vegas-1000/" --out resultado --require-init

Por defecto el HAR original de captura se borra. Para conservarlo **solo en tu PC** se puede utilizar la opción --keep-raw-har con una ruta; podría contener credenciales efímeras.

Pruebas unitarias:

    py -3 -m unittest discover -s tests -v

## GitHub Actions

Ir a **Actions → Inspector CI y captura demo**. El workflow corre al subir código a main y también manualmente mediante **Run workflow**, donde admite otra URL de ficha oficial.

El job tests comprueba extracción, ventanas circulares y ocultación de credenciales. El job capture instala Chromium, abre la demo y procesa su inicialización. No pulsa Spin y bloquea métodos mutadores salvo POST action=doInit del proveedor. La captura requiere que el proveedor permita acceso desde la infraestructura de GitHub.

En cada ejecución, descargar el artefacto inspector-resultados-depurados. No se publica un HAR de sesión: se genera sanitized-init.har, un subconjunto reproducible de doInit con las claves reel_set*, paytable y geometría. Los activos JavaScript propietarios no se cargan como artefactos, pero su existencia y hashes quedan registrados.

### Clasificación exacta del modelo de paradas directas

Después de la captura, Inspector calcula la unión de pantallas de todos los reel_set completos sin generar combinaciones una por una. Se publica como `direct_model.json` (conteos, duplicados y distribución de cantidad de símbolos `S`); el modelo **no es el RNG real**.

Para comprobar una pantalla desde Windows, abrí la GUI, analizá un HAR, introducí una cadena de símbolos de longitud `sw × sh` y pulsá **Comprobar pantalla**. El mensaje diferencia `MATCH` de `NOT_IN_DIRECT_MODEL` y siempre conserva `server_outcome_validity=UNKNOWN`.

Desde consola:

    py -3 -m inspector.cli check "resultado" "943bb39531a1S7452883"

El ejemplo corresponde a Deep Sea Frenzy (5×4) y a una pantalla de parada directa reconstruida de `reel_set0`. No es una tirada real registrada.

Detalles matemáticos y verificación: [Modelo de paradas directas](docs/MODELO_DIRECTO.md).


### Archivos de resultados

| Archivo | Significado |
| --- | --- |
| summary.json | Identidad, cantidad de inicializaciones, tiras, activos y límites |
| reel_rules.json | Tiras, alfabetos y ventanas circulares exactas (longitud 1–4) |
| paytable.json | Tabla de pagos declarada por el juego |
| historical_audit.json | Comparación de giros capturados con el modelo directo |
| direct_model.json | Unión exacta de pantallas de paradas directas y distribución por cantidad de símbolos S |
| client_evidence.json | Firmas estáticas de `build.js`, componentes de escena y sus límites; no se extrae el RNG del servidor |
| sample_screen_check.json | Pantalla testigo generada desde las tiras y validación del contrato en Actions |
| assets_index.json | SHA256, tamaño e indicadores de scripts, sin código propietario |
| sanitized-init.har | HAR reducido solo a parámetros públicos de inicialización |
| report.md | Diagnóstico resumido |
| capture_status.json | Evidencia de carga, doInit y solicitudes bloqueadas (solo en modo captura) |

### Advertencias técnicas

- El HTML de la página y el formato de la API pueden cambiar.
- No se eluden bloqueos, desafíos ni controles de sesión.
- El servidor puede producir resultados que no se reconstruyen a partir de las tiras locales.
- La ausencia de una ventana en las tiras **NO significa** que una pantalla final esté prohibida.
- La captura HAR es generada por Chromium; no es un archivo HAR que el proveedor entregue para descargar.
- No colocar HAR originales, tokens o bundles propietarios en un repositorio público.

Más detalles: [Arquitectura](docs/ARCHITECTURA.md) · [Operación](docs/OPERACION.md).

[Inspección del cliente de Deep Sea Frenzy](docs/DEEP_SEA_CLIENTE_EVIDENCIA_2026-10-17.md): analiza `GetNextSymbol`, `stopOnScreenSymbols`, el simulador offline y la diferencia entre renderizado y generación de resultados.


## Investigar las animaciones y el origen del resultado

Inspector también inspecciona estáticamente `build.js` y los componentes de la escena para separar **paradas visuales**, **parsing del protocolo** y **generación del servidor**. El archivo `animation_origin_trace.json` contiene un inventario acotado de funciones y campos encontrados sin publicar código propietario.

Se comprueba la existencia de los campos `reel_set` (conjunto actual), `n_reel_set` (selector siguiente), `srf` (sustituciones), `tmb` (cascadas) y `n_rsl` (símbolos siguientes). Cada uno se clasifica por separado como `OBSERVED_IN_CAPTURE`, `CLIENT_KNOWS_FIELD_ONLY` o `NOT_CONFIRMED`. La mera presencia en el JavaScript no prueba que la función se active en el juego.

Un uso de `Math.random()` en animaciones o simulaciones offline **no demuestra** que el cliente decida los resultados reales. La conclusión global es `UNKNOWN` si no se dispone de la matemática completa del servidor.

Detalles técnicos: [Animaciones, protocolo y origen de los resultados](docs/ANIMACION_Y_MATEMATICA.md).

## Organización del proyecto

- inspector/core.py — lectura y normalización offline.
- inspector/capture.py — navegación pasiva de demo con Playwright.
- inspector/cli.py — ejecución automatizada.
- inspector/gui.py — interfaz Tkinter.
- tests/ — regresiones sintéticas offline.
- .github/workflows/inspector.yml — CI y captura remota.
