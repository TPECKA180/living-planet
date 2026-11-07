# Architecture 8.0.0

## Entry points and state
main.py → Runner.work → World. Planning, preparing, resolution, manager and idle retain their existing order.
World.data/restore remain the save contract. Store and WorldLibrary own SQLite and exports.
Registry objects are transient and omitted from saves.

## Boundaries
World.systems is a lazy per-world SystemRegistry from planet/systems.py.
A Component declares its ID, dependencies, ownership and a LegacyInterface with explicit operation names.
Example: world.systems['population'].call('status', state).
Registration rejects duplicate IDs, missing dependencies and cycles. It never schedules a game phase.

| ID | Implementation | Main operations / owned data |
| --- | --- | --- |
| state | engine.py | context, positions, snapshot / cells, states, units |
| economy | economy.py, engine.income | forecast, income, production / stocks, income ledger |
| population | modern_economy.py | status, capacity, place, orders / population, fractional growth |
| industry | modern.py, modern_economy.py | plan, forecast, context / factories and industrial status |
| construction | infrastructure.py | projects, cost, repair_wall / buildings and walls |
| technology | technology.py, modern.py | catalog, research / technology and era |
| diplomacy | diplomacy.py, engine.send_message | relations, action, message / relations, wars, letters |
| trade | commerce.py, modern_trade.py | context, assess, action, supply / offers, payments and contracts |
| military | mobility.py, naval.py, military_ai.py | context, naval, route, move / units and movement |
| politics | politics.py | context, action / vassals and pledges |
| events | engine.log | record / existing event chronology |

Runner uses the state boundary for context, LLMAdapter for think/manager and PersistenceAdapter for saves.
Actual execution and preview use the same CommandDispatcher. Existing actions delegate unchanged to World.execute.
Old Brain, Store, World methods and imports remain valid.
No extra model calls or world copies are introduced by the adapter layer.

## Extension procedure
Add a component in a separate module and register it in create_systems. Dependencies must already exist.
Register new commands there through registry.commands.register. Existing command names cannot be replaced.
Keep validation/payment/mutation inside the owning operation. Expose new AI actions only after a separately authorized schema/catalog update.
Catalog views come from systems.catalogs and reference existing definitions. Nested records remain legacy objects and must be treated as read-only until an authorized catalog edit.
Use the existing log contract for events. No new event dispatcher is needed.

## Remaining coupling
Legacy mixins still call one another and access shared World fields. Ownership is logical and the public operation whitelist is explicit, but internal data isolation is not complete.
The UI and most internal calls retain legacy entry points. Future work can migrate one caller at a time without changing algorithms.
The next small step is to migrate one external economy consumer to the forecast operation.

## Requested generation fix
The only behavior change beyond architecture concerns the reported truncated LLM response.
The stream now checks a bounded rolling tail of server reasoning with the existing repetition detector.
An incomplete length response gets at most one clean recovery within the existing attempt budget. Complete JSON still passes the existing validators.
Normal prompts, schemas, request settings and response ceilings are preserved. Recovery clarification applies only after a failure.
Persistent failure still stops safely with the current day and completed decisions retained.
