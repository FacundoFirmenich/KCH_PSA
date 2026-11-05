# Evaluación de importación Jarvis 0.9.0 — 2026-11-05

## Dictamen

Jarvis 0.9.0 es el primer antecedente material de una arquitectura multiharness que KCH_PSA debe reutilizar conceptualmente. No está listo para importación directa ni promoción: el repositorio es privado, la instalación viva quedó en 0.8.0, el adapter usa un SDK embebido anterior a la frontera actual y no atravesó el gate de inferencia/efecto end-to-end.

Estado:

```text
SOURCE_PRESENT
REMOTE_COMMIT_VERIFIED
HISTORICAL_TEST_REPORT_PRESENT
ACTIVE_INSTALL_NOT_PROMOTED
MODEL_INFERENCE_NOT_EXECUTED
TOOL_EFFECT_NOT_EXECUTED
LICENSE_TRANSFER_NOT_ADJUDICATED
```

## Evidencia remota exacta

- Repositorio: `FacundoFirmenich/Jarvis` (privado).
- `main`: `8b14850b735ff76244cda6cf903135fb1012e836`.
- Commit: `feat: add governed Cline engine adapter`, 438 adiciones y 21 eliminaciones.
- Versión fuente: 0.9.0.
- Lock observado: Cline CLI 3.0.61; `@cline/sdk`, core, agents, shared y llms 0.0.82.
- Suite registrada en el cierre: 176/176; no reejecutada por esta auditoría.

## Qué ya está bien resuelto

1. Separación de identidad: Jarvis conserva misión/autoridad y Cline es engine subordinado.
2. `providerId` y `modelId` son obligatorios; no hay selección silenciosa.
3. Los tools usan default deny y aprobación visible de un solo uso con expiración.
4. La aprobación no está disponible al propio agente mediante la allowlist conversacional.
5. El adapter registra intentos, eventos, resultados y fallos en el ledger.
6. Las credenciales no se aceptan como campos de comando y se aplica redacción básica.
7. Un cambio en versiones o artefactos bloquea la conexión hasta revalidación.
8. La sesión iniciada por Jarvis puede cancelarse o detenerse explícitamente.

## Defectos y deuda material

### Lifecycle y continuidad

- `persistedSessionReattach=false` y `engine.cline.send` falla cerrado tras reinicio.
- `checkpoint.enabled=false` al iniciar una sesión.
- no existe settlement robusto de efectos inciertos después de crash;
- `history.coverage.complete` se infiere sólo de `rows.length < limit`, sin cursor/provider receipt.

### Versionado y supply chain

- el SDK interno 0.0.82 está detrás de la frontera pública 0.2.0 auditada;
- el lock cubre manifests y entrypoints directos, no el cierre transitivo;
- la localización por `%APPDATA%\\npm\\node_modules\\cline` es host-específica;
- no se separan todavía versiones de CLI, IDE/Desktop, SDK y backend como matriz dinámica.

### Seguridad

- la redacción por expresiones regulares reduce exposición, pero no prueba ausencia de secretos;
- `clean()` no constituye serializador de seguridad ni análisis de objetos cíclicos;
- todos los tools quedan `enabled:true` y la contención descansa en el callback de aprobación;
- falta un policy compiler por capacidad, recurso, duración, destino y efecto;
- no existe red-team de prompt/tool injection ni de eventos maliciosos del engine.

### Portabilidad

- el runtime actual es Node y depende de una instalación global Cline;
- KCH_PSA necesita que el sidecar Python supervise engines Node, no que la UI ni Node posean el estado constitucional;
- no hay adapter equivalente OpenCode/Codex/OpenClaw ni reconciliación cross-engine.

### Evidencia

- el test real cargó el SDK y leyó historial, pero no ejecutó una inferencia terminal;
- no hubo aprobación con efecto reversible verificado;
- la fuente 0.9.0 no fue instalada en el residente diario;
- no hay benchmark comparativo ni claim de superioridad.

## Estrategia de rescate

No copiar `src/cline-engine.mjs` al repositorio público. Extraer un contrato independiente y versionado:

```text
probe
create
resume-or-reattach
events
approval-request/decision
steer/wait/cancel
checkpoint
settlement
export
reconcile
close
```

Después implementar dos adapters contra el mismo contrato:

1. adapter de compatibilidad para la instalación Cline 3.0.61 / SDK 0.0.82, si todavía se necesita;
2. adapter principal para el SDK público actual, con reattach y health observer.

La importación de código privado sólo podrá ocurrir tras decidir licencia, visibilidad y custodia. La importación conceptual de contratos sí puede realizarse sin copiar código.

## Primer gate KCH_PSA

1. Definir schemas vendor-neutral para engine, sesión, evento, approval y receipt.
2. Implementar un conformance harness sin modelo ni tools.
3. Ejecutar `probe → create → cancel → close` contra el SDK actual.
4. Reiniciar el sidecar y demostrar reattach o declarar la brecha exacta.
5. Ejecutar una misión textual sin tools.
6. Ejecutar una única herramienta reversible con aprobación de un uso.
7. Verificar efecto, ledger, export/reconcile y rollback.

Sólo los pasos 1-3 pueden comenzar sin nueva autoridad material.
