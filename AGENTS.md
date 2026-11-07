# Living Planet development rules

- Treat existing gameplay algorithms and balance as the baseline. Change behavior only for an explicit user request.
- Preserve LLM prompts, schemas, context packing, settings and call order. A requested bug fix is a narrow, documented exception.
- Keep World as the single state authority. Preserve SQLite format 6 and legacy imports.
- Use World.systems interfaces for new cross-system calls. Keep legacy methods available.
- Register components in planet/systems.py. This bootstrap runs for restored worlds too. Do not rely on a registry attached only to one temporary clone.
- Add new content to the existing catalogs. Do not duplicate resource, building or technology definitions.
- New commands use systems.commands and must validate all prerequisites before mutation. Registration must happen in the bootstrap for restored worlds.
- Preserve command order, day phases, RNG order, error behavior and paid costs unless the user explicitly requests a change.
- Legacy mixins still share internal data. Keep internal algorithms intact during architectural work. Ownership metadata describes the boundary, not a security sandbox.
- Prefer small modules and thin adapters. Avoid heavy frameworks, duplicate state, event queues and cosmetic rewrites.
- Do not remove existing tests or overwrite user changes. Use focused existing checks. Do not create new large test suites or run long simulations without a request.
- Keep private saves, local config and logs out of publications.
- Record architecture changes briefly in docs/MODULAR_ARCHITECTURE.md.
