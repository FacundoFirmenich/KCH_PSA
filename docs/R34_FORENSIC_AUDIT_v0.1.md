# Auditoría forense R34 v0.1 — 2026-11-05

## Veredicto provisional

R34 no debe utilizarse como base operativa de `KCH_PSA`. La evidencia disponible no muestra un único defecto aislado, sino una composición host-real incoherente: un candidato no promovido quedó habilitado junto a dos proyecciones 0.11.33, duplicó hooks globales y añadió servidores MCP ligados a ejecutables inexistentes en rutas absolutas de otro host.

Esto explica razonablemente la experiencia de fricción, interferencia y menor fluidez descrita por el usuario. Aún no constituye atribución causal experimental cerrada: falta observar una sesión fresca con R34 retirada y comparar el mismo protocolo contra la configuración anterior.

## Hechos observados

1. `kch-native-r21` 0.11.33, `kch-native-r33` 0.11.33 y `kch-native-r34` 0.11.34 estaban habilitados simultáneamente.
2. R34 se declara `CANDIDATE_VALIDATED_NOT_PROMOTED`, con `host_activation_observed=false` y sin autoridad heredada.
3. R21 y R33 comparten hooks comunes; R34 introduce una tercera cadena sobre eventos globales como inicio de sesión, prompt, pre/post herramienta, compactación y cierre.
4. Los hooks comunes de R21/R33 resultaron byte-idénticos en la comparación efectuada; por tanto su superposición no aporta diversidad funcional, pero sí trabajo repetido y posibles escrituras concurrentes.
5. Los tres linajes escriben estado SQLite y utilizan transacciones inmediatas; la multiplicación de interceptores aumenta el riesgo de contención y de latencia acumulada.
6. La configuración MCP de R34 referencia ejecutables bajo `D:\KCH_BUILD_R10_20260820\...`; esas rutas no existen en el host auditado.
7. R34 amplía la superficie de descubrimiento, pero su paquete no aporta evidencia de que esa superficie estuviera efectivamente servida en el host actual.
8. La proyección R34 observada carece del tratamiento `Stop` presente en R33, por lo que no conserva paridad completa de ciclo de vida.
9. El repositorio público canónico documenta que AIO2 preservó R21/R33, excluyó R34 y exigió una única proyección Codex activa basada en R33.
10. AIO3 se construyó sobre AIO2 y declara explícitamente que un pass de fuente no equivale a instalación viva ni activación observada.

## Cadena causal más probable

```text
candidato sin promoción habilitado
→ triple interposición global
→ ejecución redundante de hooks y escrituras de estado
→ más latencia, ruido de estado y riesgo de bloqueo SQLite
→ discovery/MCP con rutas muertas
→ intentos o superficies no resolubles
→ experiencia host-real menos fluida y más intrusiva
```

La cadena está apoyada por hechos de configuración y código, pero el último vínculo —cuánto de la degradación percibida proviene de cada mecanismo— permanece `NOT_YET_CAUSALLY_SEPARATED`.

## Qué no debe inferirse

- Que todo el código R34 sea incorrecto.
- Que el número de skills o módulos cause por sí mismo degradación.
- Que una medición rápida de un comando de estado reproduzca la latencia de una sesión completa.
- Que retirar R34 autorice automáticamente una nueva R34.
- Que R33 sea perfecta o que todo su contenido deba heredarse.

## Reparación gobernada pendiente

La mutación exacta propuesta consiste únicamente en cambiar:

```toml
[plugins."kch-native-r34@personal"]
enabled = false
```

El bloqueo constitucional emitió la propuesta `f0e66cab-8f59-47fc-893d-5f88f1fdb9d2`. La autorización debe realizarla el usuario desde un terminal confiable con el comando ya entregado. Después corresponde aplicar exactamente el mismo parche, verificar que ningún otro campo cambió y reiniciar/recargar Codex antes del contraste.

## Gate de causalidad

La auditoría se considerará cerrada sólo si una sesión fresca ejecuta el mismo protocolo con:

1. R21 + R33, R34 deshabilitada;
2. misma tarea, mismo host y mismas superficies permitidas;
3. tiempos de inicio, prompt, pre/post herramienta, compactación y cierre;
4. conteo de hooks realmente disparados;
5. errores/locks SQLite;
6. resolución de servidores y rutas;
7. experiencia cualitativa del usuario registrada sin reemplazar las métricas.

Estado actual: `FORENSIC_MECHANISM_SUPPORTED / HOST_REAL_CAUSAL_GATE_PENDING`.
