# Operación en Windows y GitHub Actions

## Windows 10/11

Instalar Python 3.11 o superior. Clonar el repositorio. Doble clic en Abrir_Inspector.cmd para elegir un HAR y pulsar Analizar HAR.

También se admite línea de comandos:

    py -3 -m inspector.cli analyze "C:\Capturas\juego.har" --out resultado

Para capturar automáticamente sin usar la interfaz gráfica:

    py -3 -m pip install -r requirements-online.txt
    py -3 -m playwright install chromium
    py -3 -m inspector.cli capture "https://www.pragmaticplay.com/en/games/big-bass-vegas-1000/" --out resultado --require-init

No se envían giros. El HAR temporal se elimina al terminar. Quien necesite guardar su propio HAR original localmente puede utilizar --keep-raw-har, pero ese archivo contiene potenciales tokens de sesión y debe mantenerse privado.

## GitHub Actions

Abrir la pestaña Actions del repositorio y localizar Inspector CI y captura de demo. La primera ejecución también se solicita automáticamente al crear la configuración por un commit en main.

El workflow_dispatch permite ejecutar una URL de ficha oficial diferente. La validación de URL rechaza dominios externos y destinos no permitidos. Cada captura usa un contexto Chromium nuevo, sin importar cookies ni sesiones externas.

La ejecución tiene dos trabajos:
- tests: Python unittest sin navegador.
- capture: instala Chromium con dependencias, abre la demo, espera doInit, analiza el HAR privado dentro del runner y publica resultados depurados.

Se pueden descargar los archivos generados desde Artifacts del run correspondiente. El HAR original nunca se incluye en el artifact, porque podría contener sesión, saldo u otros datos personales. El archivo sanitized-init.har no es una grabación completa: sirve para reproducir y auditar solo la configuración extraída.

Si el proveedor bloquea la navegación, no publica el iframe o no se observa doInit, el trabajo informa falla de captura con salida explícita. GitHub Actions no garantiza disponibilidad de sitios de terceros ni corrige las reglas RNG faltantes.

## Pruebas locales

    py -3 -m unittest discover -s tests -v

Revisar report.md y summary.json antes de considerar suficientes las evidencias.
