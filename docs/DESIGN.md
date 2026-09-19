# Design choices and course implementation

## Alternatives to Grafana

- **Native SVG/CSS/JavaScript — implemented here.** A small, inspectable static application with explicit mapping from observed values to animation. Python owns ingestion and data projection. No chart library is needed.
- **[Three.js](https://threejs.org/).** A useful next step for an interactive, rotatable 3D heart or terrain. It adds model creation, rendering, and performance work that this lightweight replay does not require.
- **[Rive](https://rive.app/docs/runtimes/web/web-js).** Suitable for designed character and anatomical animation driven through state machines. It introduces a dedicated animation asset workflow.
- **[Canvas](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API).** Suitable for denser particles or larger interactive landscapes. Native controls and an accessible textual counterpart still matter.

The heart and burro illustrations were generated for this project and optimized as JPEGs. Their prompts are recorded in `ASSET_PROVENANCE.txt`. CSS drives the heart's scale and the burro's subtle movement; functional SVG paths visualize normalized workout positions. Illustrations are decorative, not anatomical or diagnostic evidence.

## What the visual encoding means

- Heart: sample BPM controls pulse frequency during replay. Fast-forward advances the recording without multiplying visible pulse frequency. Pausing, reduced motion, or missing observations stops pulsation.
- Trail: the burro follows the latest valid normalized GPS position; recorded distance and speed provide context. Gaps are not connected. A low-speed segment is labeled cautiously.
- Recovery: each night is selectable, and orb area scales with hours asleep. Stage durations remain available as text. There is no invented readiness score.
- Agents: a star is one persisted evaluation case. Color distinguishes passing, failing, and safely blocked outcomes. Blocking can be the correct passing result. The experiment's overall percentage stays visible even under a filter.

## Course concepts carried forward

The supplied Week 1–5 handouts informed the original backend. This project reuses those implementation modules behind a new visual client:

| Concept | Implementation | Status and limit |
| --- | --- | --- |
| Prompting and structured model routing | `observatory/investigator/provider.py`, `agent.py`, `evals/cases.json` | Local routing works without a model; saved Nebius experiment is included. |
| RAG and grounded explanations | `rag.py`, `knowledge/measurement-guide.md`, `retrieval_eval.py` | Measurement guidance retrieval and evidence citations; not medical advice. |
| Tool use, state, and graph orchestration | `tools.py`, `graph.py`, `agent.py` | Bounded, read-only tools; optional LangGraph adapter. |
| Evaluation and observability | `evaluate.py`, `braintrust_sync.py`, `langsmith_sync.py` | Braintrust report contains 120 persisted and read-back cases. LangSmith is an optional adapter, not a newly successful run here. |
| Dataset preparation and model adaptation | `training/prepare.py`, `train_lora.py`, LLaMA-Factory configurations | Synthetic semantic-family split and LoRA recipes supplied. No completed Qwen/LoRA training is claimed. |
| Safety and routing boundaries | `investigator/safety.py`, `safety/` | Local safety gates tested; optional Guardrails and NeMo adapters require their own setup. |

**A Week 6 handout was not supplied.** The above maps implemented concepts rather than claiming completion of an unseen assignment. The new experience adds accessible visual replay, deterministic public data generation, screenshot provenance, and reproducible CI.

## Further creative extensions

1. A Three.js terrain replay with a split-screen “runner observation / missing observation” lens.
2. A Rive burro with animation states tied only to recorded movement, never inferred emotion.
3. A breathing interaction used as a timer, clearly separated from measured respiration.
4. An agent flight recorder that animates tool spans from real trace exports and lets failures interrupt the scene.
5. A side-by-side experiment constellation where matching case IDs connect across versions, exposing regressions as well as improvements.
