# Checkpoint de implementación 0.2 — ciclo de vida durable

Fecha: 2026-11-05  
HEAD validado: `1285331147e2323ef1b9945b93734c70ad7ac30c`

## Resultado sustantivo

`KCH_PSA` queda mejor posicionado: el kernel neutral de engines incorpora ahora un ciclo de vida durable para residentes Jarvis/KCH. El componente no inicia ni detiene procesos; gobierna la autorización y registra observaciones del host sin colapsarlas.

La secuencia implementada es:

```text
STOPPED
  -> START_AUTHORIZED (gesto exacto + lease finito)
  -> RUNNING (proceso observado + referencia a la autorización)
  -> stop requested (deseo durable, proceso puede seguir vivo)
  -> STOPPED (terminación/no-proceso observada)
```

Una autorización que vence antes del arranque se convierte explícitamente en trabajo de parada. No queda activa por silencio ni permite un arranque tardío.

## Propiedades verificadas

- autorización, efecto y observación son estados distintos;
- no existe arranque implícito;
- el proceso observado debe citar la autorización exacta;
- el lease es finito y su borde temporal es excluyente;
- la parada solicitada permanece durable mientras el host aún informa `RUNNING`;
- volver a `STOPPED` exige una observación host-real enlazada a la solicitud;
- los tiempos no pueden retroceder;
- los operation IDs son idempotentes y un payload distinto bajo el mismo ID falla cerrado;
- varios residentes comparten ledger sin fusionar sus estados;
- las transiciones usan compare-and-swap sobre el head del ledger;
- un escritor con head obsoleto no puede anexar una historia competidora;
- las lecturas SQLite compartidas quedan serializadas y materializadas antes de liberar el lock;
- el hash-chain sigue verificable después de conflictos rechazados.

## Gate remoto

Workflow: [ci run 42120411529](https://github.com/FacundoFirmenich/KCH_PSA/actions/runs/42120411529)

| Entorno | Instalación | compileall | tests |
|---|---:|---:|---:|
| Python 3.11 | PASS | PASS | PASS |
| Python 3.12 | PASS | PASS | PASS |
| Python 3.13 | PASS | PASS | PASS |

El gate anterior de concurrencia también pasó: [ci run 42119994308](https://github.com/FacundoFirmenich/KCH_PSA/actions/runs/42119994308). El primer gate secuencial fue [ci run 42119514573](https://github.com/FacundoFirmenich/KCH_PSA/actions/runs/42119514573).

## Revisión adversa preservada

La primera implementación secuencial pasó CI, pero una revisión posterior encontró que dos controladores podían derivar transiciones desde el mismo head. Se añadió una precondición atómica de head en la misma transacción `BEGIN IMMEDIATE`; la prueba de escritor obsoleto confirma que sólo la primera transición se conserva.

La segunda implementación impedía ejecutar después del vencimiento, pero no cerraba durablemente la autorización expirada. Se añadió `EXPIRE_START_AUTHORIZATION` y la transición supervisada a parada pendiente.

Estos defectos no se borran de la genealogía: los commits previos permanecen como candidatos superados.

## Frontera de evidencia

Este checkpoint demuestra código, compilación, instalación editable y tests en runners Linux de GitHub. No demuestra:

- control de un proceso real;
- host activation en Windows;
- continuidad después de reiniciar el equipo;
- integración con Scheduled Tasks, Telegram, Cline u OpenCode;
- ausencia de todos los fallos concurrentes posibles;
- autoridad externa, operación continua, superioridad causal o promoción.

La validación local Windows está bloqueada por saturación de C:. La auditoría read-only clasificó los rollouts grandes como `RETAIN`; no se borró material para forzar el gate.

## Próximo gate

Construir un adapter de supervisor sin efectos por defecto que:

1. lea un proceso por identidad fuerte (PID + executable hash + start time);
2. produzca observaciones, no conclusiones implícitas;
3. aplique start/stop sólo después de la transición durable pertinente;
4. sobreviva a crash entre solicitud y efecto;
5. reconcilie el host al reabrir;
6. se valide primero con un proceso de prueba inocuo y lease corto.

Hasta ese gate, `host_activation=ABSENT` y `continuous_operation=NOT_ESTIMABLE`.
