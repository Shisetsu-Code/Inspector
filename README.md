# Inspector — Pragmatic Play HAR Analyzer

Herramienta de escritorio y línea de comandos para capturar pasivamente la inicialización de **demos oficiales** de Pragmatic Play, analizar archivos HAR y extraer restricciones documentables: tiras de carretes, alfabetos, ventanas circulares, tablas de pago y metadatos de cliente.

**Principio de seguridad:** se permiten solicitudes de inicialización `doInit` y descargas GET de recursos; no se envían giros, compras ni elecciones. En GitHub Actions no se publica el HAR sin depurar (puede contener sesiones). El artefacto es un informe y un HAR reducido con campos públicos de configuración.

**Límite científico:** las ventanas de las tiras describen el modelo de parada directa sin transformaciones. Su ausencia NO prueba que una pantalla final sea matemáticamente imposible. La clasificación global permanece «desconocida» salvo prueba del generador del servidor.

## Uso

Consulta el workflow **Inspector CI / captura demo** en Actions. También existe interfaz gráfica local con Tkinter para Windows 10/11. Los archivos fuente y la documentación operativa se incorporan en el siguiente commit.
