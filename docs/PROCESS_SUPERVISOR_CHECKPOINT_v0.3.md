# Checkpoint de implementación 0.3 — supervisor host-real acotado

Fecha: 2026-11-06

## Resultado sustantivo

`KCH_PSA` queda mejor posicionado que en el checkpoint 0.2. El ciclo durable ya no se limita a modelar estados: un adapter Windows/POSIX inicia un proceso inocuo sólo después de una autorización exacta, captura su identidad fuerte, conserva logs y registro de estado, aplica un lease finito, solicita la parada y verifica terminalidad antes de declarar `STOPPED`.

La ejecución canónica única `process-supervisor-witness-20261106-r1` produjo `PASS`. No hubo reintento ni reemplazo.

## Qué se implementó

- lanzamiento sin shell con ejecutable y directorio de trabajo absolutos;
- autorización de arranque exacta y finita antes de cualquier efecto;
- identidad compuesta por PID, ruta/hash SHA-256 del ejecutable y token de creación del proceso;
- hash canónico de argv sin persistir argumentos sensibles en el registro;
- stdout y stderr separados;
- registro atómico de estado por operación;
- solicitud durable de parada antes del efecto;
- negativa a terminar un PID cuya identidad ya no coincide;
- verificación post-stop para distinguir ausencia de proceso y reutilización de PID;
- reconciliación de un proceso desaparecido después de una salida inesperada;
- aplicación explícita del vencimiento del lease mediante `enforce_run_lease`;
- revocación y cierre durable ante fallo de arranque después de crear el proceso;
- escalado `terminate` → `kill` sólo tras verificar la identidad exacta;
- preservación en ledger de fallos e incompatibilidades de identidad.

## Evidencia host-real R1

Entorno observado:

- Windows `10.0.19045`;
- Python `3.14.0` en `C:\Python314\python.exe`;
- PID observado: `17920`;
- token de creación: `filetime:134383972921808352`;
- SHA-256 del ejecutable: `467014615a5255aca450ae88100dd2caf887da87657f00e3c2171ec44a685aec`;
- lease de ejecución: aproximadamente 2 segundos;
- fase terminal: `STOPPED`;
- PID ausente en verificación externa posterior;
- stdout: 0 bytes; stderr: 0 bytes;
- ledger: 4 eventos, cadena válida;
- head: `efd0b9e9bd4de9294ea650242e9121adf87b7c73aabbe30f8c12418d3b304fca`.

Secuencia factual del ledger:

1. `resident.start.authorized.v0.1`;
2. `resident.running.observed.v0.1`;
3. `resident.stop.requested.v0.1`, actor `kch-psa:lease-supervisor`;
4. `resident.stopped.observed.v0.1`.

Los cuatro artefactos referenciados por el recibo fueron recalculados después de la ejecución y coincidieron byte por byte con sus hashes declarados. El recibo canónico tiene SHA-256 `8eb8444f4ec4ef99408fabe4e911984674493ff35e8defe2ee00aedb0cee9fd4`.

El `exit_code=1` es el código observado por Windows al terminar deliberadamente el intérprete dormido mediante `terminate`; no es el código del testigo. El testigo concluyó con código 0 y `status=PASS`.

## Validación de código

- `python -m compileall -q src scripts`: PASS;
- `git diff --check`: PASS;
- suite local Windows/Python 3.14: 30/30 PASS;
- validación Draft 2020-12 local con `jsonschema`: schemas y recibo PASS;
- casos del supervisor: arranque/parada real, rechazo pre-efecto sin autorización, negativa ante identidad divergente, reconciliación de salida inesperada y vencimiento de lease real.

## Frontera de evidencia

Este checkpoint demuestra una única ejecución local inocua y acotada. No demuestra todavía:

- enforcement continuo sin que un scheduler llame al supervisor;
- recuperación de un proceso aún vivo después de reiniciar el proceso controlador;
- integración con Windows Task Scheduler, service manager o daemon de usuario;
- adapters funcionales para Codex CLI, Cline, OpenCode, OpenClaw o Telegram;
- ejecución de herramientas, modelos, prompts, MCP, credenciales o acciones externas;
- operación permanente, seguridad de producción, superioridad causal o promoción.

No se ejecutaron PHL, K3, campañas científicas ni promoción. No se usó R34 como base.

## Significado técnico y próximo gate

La separación `permission != authority != execution != observation` ya tiene un correlato host-real mínimo y reproducible. El siguiente salto crítico es la recuperación crash-safe de un residente vivo: reabrir desde el registro durable sin depender del objeto `Popen`, reconciliar identidad exacta y aplicar leases mediante un loop/scheduler supervisado. Sólo después corresponde conectar un engine real bajo un protocolo sin prompt, herramientas ni credenciales.

## Artefactos

- recibo versionado: `docs/receipts/PROCESS_SUPERVISOR_WITNESS_20261106_R1.json`;
- recibo y bytes locales completos: `.artifacts/process-supervisor-witness-20261106-r1/`;
- supervisor: `src/kch_psa/process_supervisor.py`;
- tests: `tests/test_process_supervisor.py`;
- testigo: `scripts/run_process_supervisor_witness.py`;
- schemas: `schemas/managed-process-record.schema.json` y `schemas/process-supervisor-witness.schema.json`.
