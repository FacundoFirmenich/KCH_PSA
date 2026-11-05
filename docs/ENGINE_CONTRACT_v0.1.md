# Contrato de engines KCH_PSA v0.1

## Resultado implementado

KCH_PSA ya dispone de un plano común ejecutable para integrar engines sin convertirlos en autoridad. El contrato separa probe, creación de sesión, eventos, cancelación, cierre, recibos, efectos y estado de despliegue. El ledger SQLite conserva una cadena hash reproducible y detecta alteraciones de payload, orden o enlace.

## Lifecycle mínimo

```text
probe
→ create(no model, no tools, no effects)
→ cancel
→ close
→ replay ledger
```

Este recorrido es el gate cero. No acredita inferencia, herramientas, reattach, seguridad completa ni operación continua.

## Ejes obligatorios

Cada probe debe declarar exactamente:

- specification;
- code;
- tests;
- package;
- install;
- host_activation;
- continuous_operation;
- causal_validation;
- external_authority.

Los estados permitidos son `PRESENT`, `ABSENT`, `NOT_ESTIMABLE` y `NOT_APPLICABLE`. Un adapter no puede omitir ejes para producir una apariencia de madurez.

## Recibos

Cada operación devuelve un `ExecutionReceipt` con:

- UUID;
- misión, engine y operación;
- tiempos con zona;
- hash del request y del resultado;
- estado PASS/FAIL/ABSTAIN/NOT_ESTIMABLE;
- efecto NONE/CONFIRMED/UNCERTAIN;
- head del ledger cuando exista;
- fronteras de evidencia;
- error obligatorio para FAIL.

## Integridad

El ledger usa SQLite WAL, `BEGIN IMMEDIATE`, serialización JSON canónica y una cadena SHA-256. Esta cadena detecta modificaciones relativas al head conservado; no es firma digital, timestamp de tercero ni prueba de observación externa completa.

## Ejecución

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m kch_psa.conformance `
  --adapter paquete.adapter:factory `
  --mission-id MISION `
  --ledger runtime/conformance.sqlite3 `
  --receipt runtime/conformance-receipt.json
```

No se incluye un adapter simulado en producción. La suite usa un test double confinado a `tests/support.py` para verificar contratos y fallos sin afirmar integración host-real.

## Gate local 2026-11-05

- suite fuente: 12/12 PASS;
- revisión adversarial: tres defectos de integridad hallados y corregidos;
- wheel: build PASS;
- instalación aislada: PASS;
- smoke desde el wheel instalado: PASS;
- adapter host-real: no ejecutado.
