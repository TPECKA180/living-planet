"""Small explicit contracts around the existing engine, with no game state copies."""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol


class SystemInterface(Protocol):
    def call(self, operation, *args, **kwargs): ...


class LegacyInterface:
    def __init__(self, target, operations):
        self._target = target
        self.operations = MappingProxyType(dict(operations))

    def call(self, operation, *args, **kwargs):
        # Resolve at call time to retain legacy overrides and instrumentation.
        return getattr(self._target, self.operations[operation])(*args, **kwargs)


@dataclass(frozen=True)
class Component:
    id: str
    name: str
    interface: SystemInterface
    dependencies: tuple = ()
    owns: tuple = ()


class CommandDispatcher:
    def __init__(self, world, reserved):
        self._world = world
        self._reserved = frozenset(reserved)
        self._extensions = {}

    def register(self, name, handler):
        if name in self._reserved or name in self._extensions:
            raise ValueError('Command already registered: ' + name)
        if not callable(handler):
            raise TypeError('Command handler must be callable')
        self._extensions[name] = handler

    def execute(self, state, action):
        kind = action.get('type', action.get('action')) if isinstance(action, dict) else None
        handler = self._extensions.get(kind)
        if handler is not None:
            # Extension handlers must validate before changing the shared world.
            return handler(self._world, state, action)
        return self._world.execute(state, action)


class SystemRegistry:
    def __init__(self, commands):
        self.commands = commands
        self._components = {}

    def register(self, component):
        if component.id in self._components:
            raise ValueError('Component already registered: ' + component.id)
        self._components[component.id] = component
        try:
            self.validate()
        except Exception:
            del self._components[component.id]
            raise

    def validate(self):
        visiting, complete = set(), set()

        def visit(name):
            if name in visiting:
                raise ValueError('Cyclic component dependency: ' + name)
            if name in complete:
                return
            if name not in self._components:
                raise ValueError('Missing component: ' + name)
            visiting.add(name)
            for dependency in self._components[name].dependencies:
                visit(dependency)
            visiting.remove(name)
            complete.add(name)

        for name in self._components:
            visit(name)

    def __getitem__(self, name):
        return self._components[name].interface

    @property
    def components(self):
        return MappingProxyType(self._components)
