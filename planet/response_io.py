"""Bound server responses before JSON parsing or accumulation of SSE tokens."""
import json

class ResponseTooLarge(RuntimeError):pass

def response_limit(config):
    return max(1024,int(config.get('response_max_bytes',32*1024*1024)))

def read_json(response,limit):
    data=response.read(limit+1)
    if len(data)>limit:raise ResponseTooLarge('Ответ сервера превысил безопасный размер; неполное решение не применено')
    return json.loads(data)

def stream_lines(response,limit):
    used=0;line_limit=min(limit,4*1024*1024)
    while True:
        line=response.readline(min(line_limit,limit-used)+1)
        if not line:return
        used+=len(line)
        if used>limit or len(line)>line_limit:
            raise ResponseTooLarge('Поток сервера превысил безопасный размер; неполное решение не применено')
        yield line
