# Ecosistema de arneses y agentes — corte 2026-11-05

## Conclusión arquitectónica

El salto reciente del ecosistema valida la conveniencia de `KCH_PSA`, pero también vuelve obsoleta una arquitectura que trate cada agente como terminal estanca conectada por MCP. Los sistemas actuales exponen harnesses embebibles, procesos persistentes, sesiones recuperables, hooks, subagentes y protocolos interoperables. KCH_PSA debe gobernarlos como una mancomunidad confederada: núcleo constitucional común, hosts soberanos en su ejecución local y adapters con traducción semántica verificable.

## Fuentes primarias y valor integrable

### OpenClaw 2

- OpenClaw v2026.8.1 fue presentado oficialmente como OpenClaw 2.0; la documentación actual muestra una línea posterior v2026.10.10.
- Aporta patrones de asistente persistente, skills, automatización, interfaces nativas, plugins, memoria y computer use.
- KCH_PSA debe rescatar su operabilidad y superficie de asistente, no importar implícitamente su modelo de confianza o seguridad.
- Fuentes: <https://docs.openclaw.ai/releases/2026.8.1> y <https://docs.openclaw.ai/>.

### Cline 2 / Cline SDK

- `ClineCore` expone el harness completo con herramientas, sesiones, aprobaciones, scheduling, backends y plugins; `Agent` es una primitiva inferior y más acotada.
- Cline ofrece CLI, VS Code, JetBrains, SDK, equipos, programación y conectores de mensajería.
- Valor para KCH_PSA: primer adapter rico embebido, con lifecycle y approvals observables; no mero shell o MCP.
- Fuentes: <https://docs.cline.bot/cline-sdk/sessions> y <https://github.com/cline/cline>.

### OpenCode 2

- Su SDK puede alojar el host completo en proceso; también conserva una superficie servidor/OpenAPI.
- Valor: adapter embebido con propiedad explícita del lifecycle y alternativa servidor para aislamiento.
- Fuentes: <https://dev.opencode.ai/v2/docs> y <https://dev.opencode.ai/v2/docs/build/sdk>.

### Codex

- App Server expone un proceso persistente JSON-RPC con threads, autenticación, herramientas y estado; el SDK y el modo exec cubren jurisdicciones distintas.
- Valor: integración de primera clase, evitando reducir Codex a una terminal externa.
- Fuentes: <https://openai.com/index/unlocking-the-codex-harness/> y <https://developers.openai.com/blog/codex-as-a-platform>.

### Qwen Code

- Integra subagentes especializados, aislamiento de contexto, herramientas controladas, background/resume y un sistema extenso de hooks.
- Valor: taxonomía de lifecycle y ejecución federada; sus executors externos no transfieren autoridad automáticamente.
- Fuentes: <https://qwenlm.github.io/qwen-code-docs/en/users/features/sub-agents/> y la documentación oficial de hooks.

### DeepSeek Harness

- Su API pública permite crear y reanudar agentes vivos, orientar, cancelar, esperar y consumir eventos; conserva atribución del iniciador a través de workers/reinicios.
- Valor: protocolo explícito de agencia persistente y trazabilidad causal de quién inició cada acción.
- Fuente: <https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/core/agent>.

### LangGraph

- Aporta grafos de estado, checkpoints durables, interrupts y tratamiento explícito de errores.
- Valor: ejecución durable y recuperable, pero no debe convertirse en constitución de KCH ni en dependencia obligatoria del núcleo.
- Fuente: <https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph>.

### VS Code / Copilot Agents

- VS Code ya trata Copilot, Claude y Codex como harnesses seleccionables y expone sesiones locales, background/cloud, skills y plugins.
- Valor: superficie IDE federada donde KCH_PSA puede proyectar contratos comunes sin suponer que el IDE es el núcleo.
- Fuente: <https://code.visualstudio.com/docs/agents/overview>.

### Claude y Gemini/Antigravity

- Claude Platform documenta agentes gestionados con tools, skills, memory stores, policies, sessions y multiagente.
- Gemini CLI evoluciona hacia un harness compartido con Antigravity 2.0, subagentes, hooks, plugins y ejecución asíncrona.
- Valor: adapters futuros basados en capacidades observadas, no compatibilidad nominal.

## Protocolos que deben convivir

- **Agent Client Protocol (ACP)**: JSON-RPC para editor↔agente, con initialize, sesiones, prompt/cancel, permisos, filesystem y terminal.
- **MCP**: recursos y herramientas externas; útil como borde, no como plano constitucional interno.
- **A2A**: interoperabilidad entre agentes remotos y organizaciones.
- **Agent Skills**: unidad portable de capacidad/instrucción.

No debe confundirse Agent Client Protocol con otros proyectos llamados Agent Control Protocol.

## Decisión para KCH_PSA

La prioridad de integración será:

```text
SDK o App Server nativo
→ lifecycle/hooks nativos
→ ACP/A2A cuando corresponda
→ CLI gobernada
→ MCP sólo para brechas externas
```

La comparación tecnológica es `CAPABILITY_DISCOVERY`, no certificación de seguridad, superioridad ni soporte productivo.
