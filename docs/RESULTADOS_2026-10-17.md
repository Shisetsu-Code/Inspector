# Primer análisis remoto: Big Bass Vegas 1000

**Fecha:** 2026-10-17. **Repositorio:** Inspector.
**Workflow:** Inspector CI y captura demo.
**Run:** https://github.com/Shisetsu-Code/Inspector/actions/runs/39034795739
**Commit analizado:** 4af739cf8117513a671001c5cfd9c1963bcda318

## Resultado verificado de GitHub Actions

- Pruebas sintéticas: PASS.
- Captura Playwright: PASS.
- Juego: vs10bbveg1000 (Big Bass Vegas 1000).
- doInit recibido: 1.
- Recursos estáticos observados: 45.
- build.js recuperado durante la captura: sí.
- reel_sets publicados: 2.
- Tiras individuales publicadas: 10.
- Geometría declarada: 5 carretes x 3 filas, rectángulo.
- Símbolos con pago declarado: 12.
- Solicitudes de giro enviadas por Inspector: 0.
- Tiradas históricas de esta captura: 0.
- Matemática completa del servidor: desconocida.
- Resultados finales globalmente prohibidos demostrados: ninguno.

La prueba comprueba que se puede recuperar la inicialización desde GitHub Actions sin jugar manualmente. El HAR crudo se generó en el runner, se analizó y se eliminó; el artifact contiene solo el subconjunto de inicialización y reportes depurados.

## Qué falta

Los conjuntos de tiras permiten verificar compatibilidad con paradas circulares directas, pero existen reglas de transformación y generación server-side no publicadas. No se declara que una tirada sea imposible por no estar en la tira. Para reconstruir el universo matemático completo se necesitarían más especificaciones del backend.

## Evidencia descargable

El artifact del run se llama inspector-resultados-depurados. GitHub lo conserva 7 días desde la corrida. Los archivos principales incluyen summary.json, reel_rules.json, paytable.json, assets_index.json y sanitized-init.har. Este documento mantiene un resumen aunque expire el artifact.
