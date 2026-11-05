# Checkpoint de implementación KCH_PSA 0.1 — 2026-11-05

## Posición

El proyecto está materialmente mejor posicionado: pasó de arquitectura documentada a un núcleo Python instalable que puede adjudicar engines mediante un contrato común, registrar recibos y detectar alteraciones del ledger. Todavía no está conectado a Cline, OpenCode o Codex; esa frontera permanece explícita.

## Implementación

- contratos inmutables para probe, sesión, approvals y recibos;
- nueve ejes de despliegue obligatorios;
- serialización JSON canónica y SHA-256;
- ledger SQLite WAL append-only con `BEGIN IMMEDIATE` y hash chain;
- replay que detecta cambios de payload, JSON inválido, orden, enlace y hash;
- protocolo async de engine;
- harness `probe → create sin modelo/tools → cancel → close → replay`;
- JSON Schemas para probe y recibo;
- CLI instalable `kch-psa-conformance`.

## Revisión adversarial

La primera suite terminó 9/9, pero la revisión de código pidió cambios por tres defectos materiales:

1. un adapter podía devolver un receipt PASS perteneciente a otra misión o engine;
2. un payload convertido en JSON inválido podía romper la verificación en vez de producir evidencia FAIL;
3. la serialización convertía claves no textuales y podía colisionar representaciones.

Los tres fueron corregidos. También se validó el schema del ledger, se evitó que un rollback inexistente enmascare el error original y se habilitó uso multihilo bajo lock.

## Gates ejecutados

| Gate | Resultado | Alcance |
|---|---|---|
| Suite fuente | 12/12 PASS | contratos, ledger, fallos y conformidad con test double |
| Wheel | PASS | `kch_psa-0.1.0.dev0-py3-none-any.whl` |
| SHA-256 wheel | `f680ed32318ca5138d062b502a377a75f86fc1aa879a1078b4bf3db9ef52f7fc` | 10.610 bytes |
| Instalación aislada | PASS | sin dependencias externas |
| Smoke instalado | PASS | import, append y replay de un evento |

El warning de pip sobre consulta de versión no afectó el build ni implicó descarga; se usó `--no-build-isolation --no-deps`.

## Evidencia adversa de host

La escritura inicial del parche quedó varios minutos esperando la cadena de hooks activa, aunque los archivos sí se habían aplicado. Esto no prueba por sí solo qué plugin consumió el tiempo, pero refuerza la necesidad del A/B host-real tras deshabilitar R34.

## Límites

- No hay adapter productivo incluido.
- El test double vive sólo en `tests/` y no se distribuye como capacidad.
- La hash chain no es firma digital, notarización ni observación externa.
- No hay modelo, tool, red, cuenta, permiso externo ni efecto ejecutado.
- No se demuestra reattach, operación continua, seguridad completa ni superioridad.
- El wheel local está ignorado por Git; GitHub custodiará la fuente, no ese binario.

## Próxima acción decisiva

Implementar un adapter Cline actual contra este contrato y ejecutar únicamente el gate cero sin modelo ni tools. Debe registrar por separado CLI, SDK, IDE/Desktop y backend, y fallar cerrado si no puede crear/cancelar/cerrar una sesión vacía sin efectos.
