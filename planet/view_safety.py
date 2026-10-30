"""Shape check for model prose shown before local order preparation finishes."""
import math

def readable_assessment(value):
    if not isinstance(value,dict): return False
    if not all(isinstance(value.get(k),str) for k in ('objective','chosen','success_metric')): return False
    if type(value.get('horizon_days')) is not int: return False
    options=value.get('alternatives')
    if not isinstance(options,list) or not all(isinstance(o,dict) and all(isinstance(o.get(k),str) for k in ('mode','gain','risk','opponent_response')) for o in options): return False
    plan=value.get('rival_plan'); limits=value.get('risk_limits')
    if not isinstance(plan,dict) or not all(isinstance(plan.get(k),str) for k in ('leverage','public_position','private_intent','trigger','fallback')): return False
    if not isinstance(limits,dict) or not isinstance(limits.get('stop_condition'),str): return False
    return all(type(limits.get(k)) in (int,float) and math.isfinite(limits[k]) for k in ('min_food_days','money_reserve'))
