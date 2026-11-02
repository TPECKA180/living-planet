"""Recover repeated learning prose without replaying it or changing token budgets."""
import copy
import json


class GenerationStalled(Exception):
    """Terminal generation failure; deliberately not an automatic retry error."""


def unfinished_field(text):
    decoder=json.JSONDecoder()
    pos=0
    def skip(index):
        while index<len(text) and text[index].isspace():index+=1
        return index
    pos=skip(pos)
    if pos>=len(text) or text[pos]!='{':return None
    pos+=1
    while True:
        pos=skip(pos)
        if pos<len(text) and text[pos]==',':pos=skip(pos+1)
        try:key,end=decoder.raw_decode(text,pos)
        except ValueError:return None
        if not isinstance(key,str):return None
        pos=skip(end)
        if pos>=len(text) or text[pos]!=':':return None
        pos=skip(pos+1)
        try:_,pos=decoder.raw_decode(text,pos)
        except ValueError:return key
        pos=skip(pos)
        if pos>=len(text) or text[pos]=='}':return None


def preserve_learning(schema,context,field):
    # null already means keep the existing learning state in the game protocol.
    if field not in ('learning_notes','learning_review'):return schema,False
    if field=='learning_notes' and not context.get('learning',{}).get('notes'):return schema,False
    result=copy.deepcopy(schema)
    props=(result or {}).get('json_schema',{}).get('schema',{}).get('properties',{})
    if field not in props:return schema,False
    props[field]={'type':'null'}
    return result,True
