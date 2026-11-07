"""Compatibility interfaces for the existing LLM and SQLite implementations."""


class LLMAdapter:
    def __init__(self, brain):
        self.brain = brain

    def think(self, state, context):
        return self.brain.think(state, context)

    def manager(self, world):
        return self.brain.manager(world)

    def review_construction(self, state, context, decision):
        return self.brain.review_construction(state, context, decision)

    def review_economy(self, state, context, decision):
        return self.brain.review_economy(state, context, decision)

    def review_strategy(self, state, context, decision):
        return self.brain.review_strategy(state, context, decision)

    def review_relationships(self, state, context, decision):
        return self.brain.review_relationships(state, context, decision)


class PersistenceAdapter:
    def __init__(self, store):
        self.store = store

    def save(self, world):
        return self.store.save(world)

    def load(self):
        return self.store.load()
