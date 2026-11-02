"""Lossless representations for the request only; stored game data stays intact."""
from collections import Counter
import json

def encoded(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'))

def shared_schema(schema):
    if not isinstance(schema,dict) or '$defs' in schema:return schema
    counts=Counter();objects={}
    def visit(value):
        if isinstance(value,dict):
            key=encoded(value)
            if len(key)>72:counts[key]+=1;objects[key]=value
            for child in value.values():visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    visit(schema)
    names={key:'d'+str(i) for i,key in enumerate(k for k,n in counts.items() if n>1)}
    if not names:return schema
    def pack(value,root=False):
        if isinstance(value,dict):
            key=encoded(value)
            if not root and key in names:return {'$ref':'#/$defs/'+names[key]}
            return {k:pack(v) for k,v in value.items()}
        if isinstance(value,list):return [pack(v) for v in value]
        return value
    result=pack(schema,True)
    result['$defs']={names[key]:pack(objects[key],True) for key in names}
    return result if len(encoded(result))<len(encoded(schema)) else schema

def grouped_map(rows,size):
    if not isinstance(rows,list) or not rows or type(size) is not int or size<1:return rows
    if not all(isinstance(row,list) and len(row)==8 for row in rows):return rows
    groups={}
    for x,y,*values in rows:
        if type(x) is not int or type(y) is not int:return rows
        key=encoded(values)
        groups.setdefault(key,[*values,[]])[-1].append(y*size+x)
    packed=dict(format='cell_groups',size=size,
        columns=['terrain','level','owner','building','building_level','population','indices'],
        decode='Для каждого index: x=index%size, y=index//size. Все клетки группы имеют указанные свойства. Порядок клеток незначим.',
        groups=list(groups.values()))
    return packed if len(encoded(packed))<len(encoded(rows)) else rows
