"""Caches live only inside one read-only calculation, never across game mutations."""
from contextlib import contextmanager
from functools import wraps
import copy


def read_analysis(function):
    @wraps(function)
    def wrapped(self,*args,**kwargs):
        with self.analysis_scope(): return function(self,*args,**kwargs)
    return wrapped


def memo_analysis(function):
    @wraps(function)
    def wrapped(self,state,*args,**kwargs):
        with self.analysis_scope():
            memo=self._analysis_index.setdefault('results',{})
            key=(function.__name__,state.id,tuple(id(value) for value in args),tuple((key,id(value)) for key,value in kwargs.items()))
            if key not in memo: memo[key]=function(self,state,*args,**kwargs)
            return copy.deepcopy(memo[key])
    return wrapped


def cached_route(function):
    @wraps(function)
    def wrapped(self,unit,target=None,explore=False,assume_war_with=None):
        cache=getattr(self,'_analysis_index',None)
        if cache is None: return function(self,unit,target,explore,assume_war_with)
        key=(unit['id'],tuple(unit['cell']),tuple(target) if target is not None else None,explore,assume_war_with)
        routes=cache['routes']
        if key not in routes: routes[key]=function(self,unit,target,explore,assume_war_with)
        return copy.deepcopy(routes[key])
    return wrapped


def mutation(function):
    @wraps(function)
    def wrapped(self,*args,**kwargs):
        self._analysis_index=None
        return function(self,*args,**kwargs)
    return wrapped


class AnalysisCache:
    @contextmanager
    def analysis_scope(self):
        if getattr(self,'_analysis_index',None) is not None:
            yield; return
        positions={state.id:[] for state in self.states}
        for i,cell in enumerate(self.cells):
            if cell.owner in positions: positions[cell.owner].append([i%self.size,i//self.size])
        self._analysis_index=dict(positions=positions,occupied={tuple(u['cell']):u for u in self.units if not u.get('embarked_on')},routes={})
        try: yield
        finally: self._analysis_index=None
