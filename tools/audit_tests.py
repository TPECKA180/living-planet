"""Run the suite and record successful dispatch for all registered actions."""
from pathlib import Path
from collections import defaultdict,Counter
import json,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from planet.engine import World,PRICES

def run():
    counts=defaultdict(Counter);original=World.execute
    def tracked(self,state,action):
        name=action.get('type',action.get('action')) if isinstance(action,dict) else None
        try:result=original(self,state,action)
        except Exception:counts[str(name)]['rejected']+=1;raise
        counts[str(name)]['success']+=1;return result
    World.execute=tracked
    try:result=unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.discover(str(ROOT/'tests')))
    finally:World.execute=original
    report=dict(tests=result.testsRun,passed=result.wasSuccessful(),registered_actions=len(PRICES),
        missing_success=[name for name in PRICES if not counts[name]['success']],actions={name:dict(counts[name]) for name in sorted(PRICES)})
    print(json.dumps(report));return report

if __name__=='__main__':
    result=run();sys.exit(not result['passed'] or bool(result['missing_success']))
