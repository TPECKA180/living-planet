"""Bounded layout cache; only visible lines need surfaces on each frame."""
from collections import OrderedDict

class TextLayout:
    def __init__(self,budget=8*1024*1024):
        self.cache=OrderedDict();self.used=0;self.budget=budget

    def clear(self):self.cache.clear();self.used=0

    def lines(self,text,width,font):
        key=(text,width,font)
        if key in self.cache:
            self.cache.move_to_end(key);return self.cache[key][0]
        lines=[];line=''
        for paragraph in text.split('\n'):
            for word in paragraph.split():
                candidate=(line+' '+word).strip()
                if font.size(candidate)[0]>width and line:lines.append(line);line=''
                if font.size(word)[0]>width:
                    # Fit long tokens in chunks, avoiding a gigantic rendered line.
                    offset=0
                    while offset<len(word):
                        remaining=len(word)-offset
                        lo,hi=1,min(64,remaining)
                        while hi<remaining and font.size(word[offset:offset+hi])[0]<=width:hi=min(remaining,hi*2)
                        while lo<hi:
                            mid=(lo+hi+1)//2
                            if font.size(word[offset:offset+mid])[0]<=width:lo=mid
                            else:hi=mid-1
                        part=word[offset:offset+lo];offset+=lo
                        if offset<len(word):lines.append(part)
                        else:line=part
                else:line=(line+' '+word).strip()
            lines.append(line);line=''
        result=tuple(lines)
        # Include Python's per-line/container overhead and Unicode worst case.
        cost=4*(len(text)+sum(map(len,result)))+128*len(result)+256
        while self.cache and (self.used+cost>self.budget or len(self.cache)>=32):
            _,(_,old)=self.cache.popitem(last=False);self.used-=old
        if cost<=self.budget:self.cache[key]=(result,cost);self.used+=cost
        return result
