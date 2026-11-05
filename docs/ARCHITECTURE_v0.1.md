# Arquitectura KCH_PSA v0.1 — mancomunidad confederada

## Tesis

`KCH_PSA` no será un agregador de CLIs ni un reemplazo monolítico de Cline, Codex, OpenCode u OpenClaw. Será un superagente soberano que gobierna una mancomunidad confederada de harnesses y agentes: cada miembro conserva capacidades locales; el núcleo KCH conserva misión, evidencia, permisos, autoridad, continuidad, recibos y recuperación.

## Capas

```text
KCH Playpad / Telegram / IDE / voz
                │
        Experience Gateway
                │
  Mission + Authority + Evidence Core
                │
  Event ledger / state graph / recovery
                │
 Python sidecar + runtime supervisor
                │
 Native host adapters / ACP / A2A / CLI / MCP
                │
 Codex · Cline · OpenCode · OpenClaw · Qwen · otros
```

## 1. Núcleo constitucional

Objetos comunes mínimos:

- `Mission`: objetivo, jurisdicción, invariantes, criterio de cierre.
- `EvidenceClaim`: observación, derivación, inferencia, procedencia y límites.
- `AuthorityConformation`: capacidad, soporte, permiso, autoridad, ejecución y entrenamiento separados.
- `ManeuverNode`: decisión ramificadora y gesto humano requerido.
- `PermissionLease`: alcance, expiración, revocación y sujeto.
- `ExecutionPlan`: acciones, dependencias, reversibilidad y reglas de parada.
- `ExecutionReceipt`: qué ocurrió realmente en qué host.
- `Outcome`: resultado separado de la mera ejecución.
- `RecoveryPoint`: estado reconstruible y hashes.
- `FutureOnlyUpdate`: aprendizaje que no reescribe el pasado.

El núcleo no invoca proveedores directamente. Adjudica contratos y valida recibos.

## 2. Plano de ejecución

El sidecar Python es vital porque puede operar de forma portable en Windows, Linux/VPS y macOS, supervisar procesos y mantener estado sin acoplar el núcleo a React o a un IDE.

Responsabilidades:

- dispatcher con backpressure;
- supervisor de PID, terminalidad, logs y recuperación;
- leases y revocación;
- event ledger append-only con replay;
- reconciliación de sesiones multi-host;
- health checks y circuit breakers;
- vault references sin almacenar secretos en el ledger;
- autosave y checkpoints;
- scheduler local explícitamente distinguido de daemon OS.

## 3. Adapters de hosts

Cada adapter publica una matriz real de capacidades y traduce sin degradación silenciosa:

```text
common contract → host plan → host events → common receipt
```

Un adapter no puede declarar soportada una propiedad sólo porque el host tenga una función de nombre parecido. Debe demostrar create/resume/cancel/close, permisos, tools, hooks, recovery y semántica de errores en su propia jurisdicción.

Primera prioridad propuesta:

1. Cline 2 mediante SDK/harness completo.
2. OpenCode 2 mediante SDK embebido y alternativa servidor.
3. Codex mediante App Server/SDK.
4. OpenClaw como peer operativo aislado y sometido a policy gateway.

## 4. Superficies

### KCH Playpad

React/TypeScript será una superficie rica, no el runtime. Debe mostrar misiones, agentes, nodos de maniobra, evidencia, leases, procesos vivos y recovery sin esconder su estado real.

### Telegram

El fork propio funcionará como interfaz remota sobre el mismo gateway; no alojará la lógica constitucional en el bot ni dependerá de un backend propietario único.

### IDE

VS Code/Cline/OpenCode exponen trabajo, diffs, terminales y aprobaciones. KCH_PSA conserva la continuidad transversal y no transforma al IDE en soberano.

### GWD/WTJ y NNF

La pareja de nahuales agentivos y la Pokéball/NNF forman una capa de acceso, aprendizaje y despliegue gamificado. La capa RPG/cartas representa capacidades, estados, sinergias, costes y progresión, pero nunca falsea evidencia ni concede autoridad por puntuación lúdica.

## 5. Seguridad de nueva generación

Dos dominios coexistentes:

- **ciberseguridad defensiva clásica**: secretos, sandbox, red, filesystem, supply chain, aislamiento y actualización;
- **ciberseguridad interna agentiva**: coherencia de misión, escalada de autoridad, prompt/tool injection, delegación espuria, colusión de agentes, deriva de memoria, reanudación adulterada y receipts falsos.

Toda acción material requiere sujeto, alcance, lease, política, host, recibo y ruta de recuperación.

## 6. Funciones KCH transversales

- `RECAP`: hiperloop helicoidal de recapitulación crítica y reinformación future-only.
- `Agentic Coherence`: detecta cambios bruscos, abre rama/confirmación y obedece la decisión final del usuario sin fingir que la contradicción nunca ocurrió.
- ecualizadores de relevancia longitudinal: candidatos experimentales, nunca modificación invisible del modelo base.
- prevención de microsegmentación disolutoria: gates de salto material y cierre por objetivo.
- routers bayesianos jerárquicos sobre información estructurada.
- Hot Keys: activadores explícitos/fuzzy con scope y efecto visibles.
- continuidad informacional que trata 20k como límite de transporte y pagina/reconstruye hasta EOF.

## 7. Primer vertical verificable

El primer vertical no será una pantalla. Será:

```text
KCH mission
→ Cline 2 initialize/session
→ eventos normalizados
→ aprobación KCH cuando corresponda
→ cancel/close/recovery
→ recibo reconciliado
→ exportación exacta
```

Se ejecutará primero sin prompts sustantivos, modelos, herramientas ni permisos externos; después se ampliará por gates. Sólo entonces se conectará a Playpad/Telegram.

## No-claims actuales

- No hay todavía runtime `KCH_PSA` implementado.
- No hay adapter Cline/OpenCode validado en este repositorio.
- No hay daemon VPS desplegado.
- No hay seguridad inexpugnable demostrada.
- No hay promoción R34/R35 ni PHL real.
