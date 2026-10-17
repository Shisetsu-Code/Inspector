# Parser de premios y animación: servidor frente a cliente

Inspector puede analizar los métodos compilados de `build.js` sin efectuar giradas.

`VSProtocolParser.ParseWinLines` reconoce estructuras de ganancias por línea, número de línea, importe y posiciones. `VSProtocolParser.ParseWinGroups` reconoce pagos por grupos/vías, número de formas, longitud y posición. La interfaz puede leer las posiciones comunicadas para resaltar símbolos, mediante `WinLineVisual.OnWinLineShow` y `VS_LinesDefinitions.symbolSquares`.

### Lo que demuestra
- El cliente **acepta mensajes con importes y posiciones premiadas**.
- El código gráfico tiene una ruta para destacar esas posiciones.
- La pantalla final puede mostrar premios decididos por el servidor sin recalcularlos.

### Lo que no demuestra
- Que el cliente vuelva a calcular y validar los importes económicos.
- Que el método esté activo en Deep Sea Frenzy cuando se ejecuta una tirada.
- Que el motor generativo del backend resida en el navegador.
- Que todos los resultados posibles estén representados por las tiras directas.

`win_delivery_trace.json` conserva exclusivamente nombres y marcadores de métodos, nunca el código completo de Pragmatic. Los campos `server_may_send_winning_amount_and_positions` y `client_can_visualize_received_win_positions` se basan en evidencia estática, no en respuestas de ronda porque la captura automática solo permite `doInit`.

Para validar una liquidación real se necesita evidencia de una ronda efectivamente ejecutada o documentación formal del backend. Inspector no envía apuestas para obtenerla.
