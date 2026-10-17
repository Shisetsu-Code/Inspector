# Arquitectura del Inspector

## Objetivo y límites

Inspector transforma archivos HAR de la demo pública oficial de Pragmatic Play en un contrato estático con trazabilidad. Su captura remota usa Playwright exclusivamente para cargar el juego y obtener las respuestas que la propia inicialización genera; ningún módulo envía giros, compras o decisiones.

## Componentes

- inspector.capture: navega a la ficha oficial, encuentra el iframe data-game-src sin hacer clics, abre el launcher demo y registra un HAR temporal. Permite GET/HEAD y únicamente POST action=doInit en el gameService oficial; bloquea todo otro método mutador.
- inspector.core: lee el HAR local, comprueba host/rutas, extrae las respuestas doInit con reel_set*, tabla de pagos, geometría sw/sh y recursos estáticos. Calcula ventanas circulares para cada tira. No ejecuta JavaScript descargado.
- inspector.cli: interfaz automatizable para local o Actions. El HAR crudo de captura se destruye automáticamente salvo opción explícita keep-raw-har.
- inspector.gui: ventana Tkinter para seleccionar y analizar HAR desde Windows.
- GitHub Actions: ejecuta pruebas unitarias, captura una demo oficial y publica exclusivamente resultados depurados.

## Modelo de resultados

1. Observado en HAR: resultado retornado durante una sesión previa.
2. Compatible con parada circular directa: todas las columnas existen como ventana en un conjunto, para alguna orientación probada.
3. Incompatible con parada circular directa: no coincide con las ventanas conocidas de ese modelo.
4. Posibilidad global del servidor: UNKNOWN, hasta disponer de especificación completa del generador, de transformaciones, de las transiciones y de la selección efectiva de conjuntos.

No inferir tiradas prohibidas por ausencia de muestras. Las probabilidades tampoco se infieren de frecuencias observadas ni de las longitudes de las tiras.

## Datos y formato

- summary.json: recuentos, identidad, capacidad, límites y auditoría histórica.
- reel_rules.json: secuencias publicadas, alfabetos y ventanas circulares de longitud 1–4.
- paytable.json: declaración de pagos inicial.
- historical_audit.json: contraste de tiradas históricas con el modelo directo, NO con el RNG real.
- assets_index.json: hashes SHA256, tamaños e indicadores léxicos del JavaScript, sin contenido propietario.
- sanitized-init.har: HAR sintético reducido que contiene solo doInit con claves públicas permitidas, sin sesiones ni cookies.
- report.md: conclusión legible, advertencias y alcance.

## Verificación

La batería tests/test_inspector.py crea HAR falsos con un secreto deliberado y verifica que sanitized-init.har no lo exponga. No incluye credenciales ni HAR comerciales en el repositorio.
