"""Build an offline HTML handbook with no network/CDN/runtime dependency."""
from pathlib import Path
import html,re
ROOT=Path(__file__).resolve().parents[1]
DOCUMENTS=['README.md','docs/SETUP.md','docs/GAME_GUIDE.md','docs/ACTIONS.md','docs/CATALOGS.md','docs/CONFIGURATION.md','docs/LIMITS.md','docs/AI.md','docs/HISTORY.md','docs/SAVES.md','docs/TROUBLESHOOTING.md','docs/ARCHITECTURE.md','docs/DEVELOPMENT.md','docs/VALIDATION.md','CHANGELOG.md','CONTRIBUTING.md']

def inline(text):
    text=html.escape(text)
    def link(match):
        image,label,url=match.groups();url=html.unescape(url)
        if image:
            if url.startswith('docs/'):url=url[5:]
            return f'<img alt="{label}" src="{html.escape(url,quote=True)}">'
        if url.endswith('.md'):url='#doc-'+Path(url).stem
        return f'<a href="{html.escape(url,quote=True)}">{label}</a>'
    text=re.sub(r'(!?)\[([^\]]+)\]\(([^)]+)\)',link,text)
    text=re.sub(r'`([^`]+)`',r'<code>\1</code>',text)
    return re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',text)

def render(source):
    result=[];paragraph=[];code=None;table=[];listing=False
    def flush():
        nonlocal listing
        if paragraph:result.append('<p>'+inline(' '.join(paragraph))+'</p>');paragraph.clear()
        if table:
            rows=[x for x in table if not re.match(r'^\|[\s:|-]+\|$',x)]
            result.append('<div class="table"><table>')
            for i,row in enumerate(rows):
                tag='th' if i==0 else 'td';result.append('<tr>'+''.join(f'<{tag}>{inline(c.strip())}</{tag}>' for c in row.strip('|').split('|'))+'</tr>')
            result.append('</table></div>');table.clear()
        if listing:result.append('</ul>');listing=False
    for line in source.splitlines():
        if line.startswith('```'):
            if code is None:flush();code=[]
            else:result.append('<pre><code>'+html.escape('\n'.join(code))+'</code></pre>');code=None
            continue
        if code is not None:code.append(line);continue
        if line.startswith('|'):
            if paragraph:result.append('<p>'+inline(' '.join(paragraph))+'</p>');paragraph.clear()
            table.append(line);continue
        if table:flush()
        if not line.strip():flush();continue
        if line.startswith('#'):
            flush();level=len(line)-len(line.lstrip('#'));result.append(f'<h{min(6,level)}>'+inline(line.lstrip('# '))+f'</h{min(6,level)}>');continue
        match=re.match(r'^(?:- |\d+\. )(.*)',line)
        if match:
            if paragraph:result.append('<p>'+inline(' '.join(paragraph))+'</p>');paragraph.clear()
            if not listing:result.append('<ul>');listing=True
            result.append('<li>'+inline(match[1])+'</li>');continue
        paragraph.append(line)
    flush();return '\n'.join(result)

def generate():
    links=[];sections=[]
    for rel in DOCUMENTS:
        source=(ROOT/rel).read_text(encoding='utf-8');stem=Path(rel).stem
        title=source.splitlines()[0].lstrip('# ')
        links.append(f'<a href="#doc-{stem}">{html.escape(title)}</a>')
        sections.append(f'<section id="doc-{stem}">{render(source)}</section>')
    css='''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#10171d;color:#dce6e8;font:16px/1.7 system-ui,Segoe UI,sans-serif}aside{position:fixed;width:256px;height:100vh;overflow:auto;padding:28px 22px;border-right:1px solid #2a3b44;background:#131e26}aside b{color:#65d6b3;letter-spacing:.08em}aside a{display:block;margin:15px 0;color:#a9bfc6;font-size:14px;text-decoration:none}aside a:hover,a{color:#72dbc0}main{margin-left:256px;padding:35px 45px;max-width:1340px}section{scroll-margin:24px;margin:0 0 50px;padding:26px 32px;background:#17232c;border:1px solid #2b3c46;border-radius:16px}h1{font-size:32px;line-height:1.25;color:#eef8f5}h2{margin-top:40px;color:#7addc0}h3{margin-top:26px}p,li{max-width:90ch}li{margin:8px 0}code{font:14px/1.7 Consolas,monospace;background:#0e1921;padding:2px 5px;border-radius:4px;color:#b9e9df}pre{padding:18px;overflow:auto;background:#0e1921;border-radius:9px}pre code{padding:0;white-space:pre}img{max-width:100%;border-radius:12px;border:1px solid #344c57}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:11px 13px;border:1px solid #31444e;text-align:left;vertical-align:top}th{background:#21343e;color:#a6ead7}.hint{color:#8fa9b1;font-size:13px}@media(max-width:850px){aside{position:relative;width:auto;height:auto}main{margin:0;padding:15px}section{padding:18px}}@media print{aside{display:none}main{margin:0;padding:0;max-width:none}body,section{background:white;color:black}section{border:0;break-after:page}h1,h2,h3,a{color:black}pre,code{white-space:pre-wrap;background:#eee;color:black}table{font-size:10px}}'''
    page='<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Живая планета7.5.4 · Полная справка</title><style>'+css+'</style><aside><b>ЖИВАЯ ПЛАНЕТА /7.5.4</b><p class="hint">Полная локальная справка<br>Поиск: Ctrl+F · без интернета</p>'+''.join(links)+'</aside><main>'+''.join(sections)+'</main></html>'
    (ROOT/'docs/index.html').write_text(page,encoding='utf-8')
    return len(page.encode('utf-8'))

if __name__=='__main__':print('Offline manual bytes:',generate())
