"""The built-in module boundary. Existing algorithms remain in their old files."""
from types import MappingProxyType
from .core import Component, LegacyInterface, SystemRegistry, CommandDispatcher


def create_systems(world):
    from .engine import PRICES
    registry = SystemRegistry(CommandDispatcher(world, PRICES))
    definitions = (
        ('state', 'Мир', (), ('cells', 'states', 'units'),
         {'state': 'state', 'positions': 'positions', 'context': 'context', 'snapshot': 'data'}),
        ('economy', 'Экономика', ('state',), ('stocks', 'daily_income'),
         {'forecast': 'economic_forecast', 'income': 'income', 'production': 'production_for_cell'}),
        ('population', 'Население', ('state', 'economy'), ('population', 'modern.growth_remainder_tenths'),
         {'status': 'population_status', 'capacity': 'population_capacity', 'place': 'place_people', 'orders': 'population_actions'}),
        ('industry', 'Промышленность', ('population', 'economy'), ('modern', 'factory_enabled', 'factory_priority'),
         {'plan': 'industrial_plan', 'forecast': 'modern_forecast', 'context': 'modern_context'}),
        ('construction', 'Строительство', ('economy', 'population'), ('building', 'building_level', 'wall_hp'),
         {'projects': 'construction_context', 'cost': 'construction_cost', 'repair_wall': 'repair_wall'}),
        ('technology', 'Технологии', ('state', 'economy'), ('tech', 'era'),
         {'catalog': 'research_catalog', 'research': 'modern_research'}),
        ('diplomacy', 'Дипломатия', ('state',), ('relations', 'wars', 'messages'),
         {'relations': 'relations_context', 'at_war': 'at_war', 'action': 'diplomatic_action', 'message': 'send_message'}),
        ('trade', 'Торговля', ('economy', 'diplomacy'), ('trade_offers', 'exchanges', 'settlements', 'supply_pacts'),
         {'context': 'commerce_context', 'assess': 'assess_trade', 'action': 'financial_action', 'supply': 'supply_action'}),
        ('military', 'Армия и флот', ('state', 'diplomacy', 'economy'), ('units', 'movement_log', 'fortification'),
         {'context': 'military_context', 'naval': 'naval_context', 'route': 'find_route', 'move': 'movement_action'}),
        ('politics', 'Политика', ('diplomacy', 'economy'), ('vassal_treaties', 'pledges'),
         {'context': 'political_context', 'action': 'politics_action'}),
        ('events', 'Хронология', ('state',), ('events',), {'record': 'log'}),
    )
    for name, title, dependencies, owns, operations in definitions:
        registry.register(Component(name, title, LegacyInterface(world, operations), dependencies, owns))
    return registry


def catalogs():
    """Live views of the original catalogs, not competing definitions."""
    from .engine import PRICES
    from .technology import TECHNOLOGIES as base_technologies
    from .modern_catalog import BUILDINGS, UNITS, TECHNOLOGIES, RESOURCE_NAMES
    return MappingProxyType(dict(actions=MappingProxyType(PRICES),
        resources=MappingProxyType(RESOURCE_NAMES), buildings=MappingProxyType(BUILDINGS),
        units=MappingProxyType(UNITS), technologies=MappingProxyType(TECHNOLOGIES),
        base_technologies=MappingProxyType(base_technologies)))
