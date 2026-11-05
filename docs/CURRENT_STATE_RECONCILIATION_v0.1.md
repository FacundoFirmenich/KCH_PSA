# Reconciliación del estado KCH/Jarvis v0.1 — 2026-11-05

## Resultado

El estado posterior a agosto no forma una única línea de releases. Existen al menos tres genealogías que deben conservarse separadas hasta que sus contratos y evidencia puedan reconciliarse:

1. **KCH nativo y AIO**: R21/R33, AIO2 y el candidato AIO3.
2. **Jarvis / Superagente**: sidecar, adapters de hosts, Telegram, escritorio, voz y continuidad.
3. **Superficies de producto**: KCH Playpad, GWD/WTJ, capa RPG/cartas, NNF y experiencia amigable.

La reconstrucción no debe convertir títulos de chats, reportes de una sesión o paquetes locales en autoridad presente.

## Línea pública verificada

El árbol público `FacundoFirmenich/KCH` leído el 5 de noviembre de 2026 tiene SHA Git `76c52fea0180cc61bfee4318d1734d67f3873ec2`, 2.529 rutas y respuesta no truncada.

- La distribución documentada como operativa es AIO2, basada en R21/R33.
- AIO2 registra 1.382/1.382 pruebas de paquete y 156/156 de Studio dentro de su jurisdicción histórica.
- Su cierre separa fuente instalada de caché realmente servida y mantiene un gate de recarga del host.
- AIO3 es un sucesor incremental construido sobre AIO2; no afirma instalación viva ni promoción.
- El repositorio público no contiene una línea R34/R35 operativa posterior que deba tomarse como base de `KCH_PSA`.

Estos números son evidencia histórica del repositorio, no fueron reejecutados en esta auditoría.

## Línea nativa actual

- R21 y R33 0.11.33 están instaladas y habilitadas.
- R34 deprecada continúa habilitada hasta completar la autorización constitucional exacta para retirarla.
- La presencia en caché o configuración no demuestra que cada capacidad se interponga realmente en cada inferencia.
- PHL sigue autorizado arquitectónicamente, no entrenado ni ejecutado con feedback real.

## Línea Jarvis recuperada hasta ahora

Las tareas nativas posteriores a agosto muestran trabajo sobre:

- integración con Cline y OpenCode;
- sidecar Python y continuidad de sesiones;
- Telegram y escritorio;
- voz/ElevenLabs con gates de activación;
- exportación, reconciliación y recuperación tras interrupciones;
- una familia de paquetes Jarvis v0.5.x y reportes posteriores de v0.7.0.

El reporte de v0.7.0 y sus conteos de tests se conservan como `HISTORICAL_SESSION_REPORT_NOT_YET_REEXECUTED`. No se importarán como release canónica hasta localizar artefactos, manifiestos, hashes, código y recibos host-reales.

## Fuentes nativas identificadas

### Codex

- `01a077b6-f814-7b92-ae6d-18fc6e0bed7a` — Jarvis: Telegram y desktop.
- `01a0498e-906e-7e52-a1bc-3fcc6b13e353` — Jarvis KCH · Puente nativo GPT.
- `01a05a61-ddf2-7b21-b803-6e59d07e6f81` — KCH Jarvis v0.5.3 — sucesión integral (2).
- `01a03f11-dcfe-7350-8e5a-abcbdf9c4617` — KCH Jarvis v0.5.3 — sucesión integral.
- `01a078be-69d7-7430-8d40-71dbe21bdb20` — KCH Lab: ideas y herramientas operativas (2).
- `01a067ff-2a52-7b41-916e-71de7c893c7e` — Fusionar tres sesiones KCH.
- `01a06ef1-18db-7af3-b55f-ec83bfbeacf5` — KCH Supersesión Sucesora Integral SuperPrime.2.
- `01a08180-5afe-70d0-b295-faf599e9e288` — Jarvis Desktop/data/agent-work.

### ChatGPT

Se identificaron conversaciones sobre evolución, proyección y cierre de KCH, DeepSeek Harness, desarrollo de agentes, Programación Estadística/MIS y arquitectura constitucional. Los títulos no se consideran prueba de contenido vigente: dos lecturas recientes mostraron que chats con títulos pertinentes habían evolucionado hacia líneas diferentes.

## Estado de lectura

La Biblioteca y las tareas fueron inventariadas y varias fuentes recientes fueron leídas parcialmente. Aún no se afirma EOF de todos los chats relevantes. Cada importación posterior deberá registrar cursor, rango temporal, procedencia y estado `EXACT_NATIVE`, `EXACT_RECONSTRUCTED` o `UNRESOLVED_TRUNCATION`.

## Decisión

`KCH_PSA` comienza como repositorio independiente. No es un fork mecánico de R34 ni una copia de Jarvis. Su primera versión deberá extraer contratos verificables y volver a adjudicar cada componente contra el ecosistema 2026 y contra gates host-reales.
