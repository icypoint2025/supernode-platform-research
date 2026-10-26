"""严格导出公开阅读版；不改动项目原件。"""
import argparse, hashlib, html, json, re, subprocess, os
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

MAIN='output/超节点平台竞争分析.html'
SEEDS=[MAIN,'output/产品定位-产品介绍更新版.html','output/全场景旅程与角色协作V15.html','output/产品框架-双门户角色侧边栏V12.html','output/竞品结论与设计洞察V2.html','output/竞品侧边栏分析V3/index.html']
EXT=r'(?:png|jpe?g|webp|gif|svg|ico|pdf|csv|json|md|html|css|js|woff2?|ttf|mp4|xlsx|pptx|xls|ppt|docx|doc|zip)'
FILE=re.compile(r'^[^<>\n\r\x00{}$*|]+\.'+EXT+r'(?:[?#].*)?$',re.I)
BLOCKED=('个人智能报告','AI普惠调查','备份','__pycache__','.git','GitHubPages-本地资料留存')
# 用户仅授权公开阅读内容；源文档与逐行原始提取保持本地。
PRIVATE_NAMES={
 'AIStation人工智能平台_V5.0_普通用户手册 1.pdf',
 'H3C灵犀使能平台-基础（Base）组件 用户手册-E0601-5W100-整本手册.pdf',
 'SothisAI人工智能管理平台V3.2介绍.pptx',
 '超节点集群操作系统MRD-需求清单 v0.5.xlsx',
 'MRD-V0.5核对索引.json',
}
SOURCE_SUFFIXES={'.pdf','.xlsx','.pptx','.xls','.docx','.doc','.ppt'}
def private_reference(value):
    if not isinstance(value,str):return False
    u=urlsplit(html.unescape(value))
    if u.hostname=='lenovo.sharepoint.com' and 'MRD-' in unquote(u.query) and 'v0.5.xlsx' in unquote(u.query):return True
    if u.scheme or u.netloc:return False
    name=Path(unquote(u.path)).name
    if name in PRIVATE_NAMES:return True
    if Path(name).suffix.lower() in SOURCE_SUFFIXES:
        raise ValueError('遇未知本地源文档，必须核对公开范围：'+value)
    return False

def private_note(value):
    u=urlsplit(html.unescape(value));name=Path(unquote(u.path)).name
    if u.hostname=='lenovo.sharepoint.com':name='超节点集群操作系统MRD-需求清单 v0.5.xlsx'
    page=u.fragment.removeprefix('page=') if u.fragment.startswith('page=') else ''
    return '来源：'+name+('，第'+page+'页' if page else '')+'（源文件未公开）'

def clean_json(value):
    if isinstance(value,list):return [clean_json(x) for x in value]
    if isinstance(value,dict):
        out={}
        for key,item in value.items():
            if isinstance(item,str) and key in {'source','source_url','url','href','path','file'} and private_reference(item):
                if key=='source':out[key]=None
                out['source_note']=private_note(item)
            else:out[key]=clean_json(item)
        return out
    return value

def public_text(text,suffix,is_main=False):
    if suffix=='.json':return json.dumps(clean_json(json.loads(text)),ensure_ascii=False,indent=2)
    if suffix=='.md':
        def md_link(m):
            value=m.group(2).strip('<>')
            return m.group(1)+' — '+private_note(value) if private_reference(value) else m.group(0)
        return re.sub(r'\[([^\]]*)\]\((<?[^)]+>?)\)',md_link,text)
    if suffix!='.html':return text
    def anchor(m):
        opening,inner=m.group(1),m.group(2)
        h=re.search(r'\bhref=["\x27]([^"\x27]+)["\x27]',opening)
        if h and private_reference(h.group(1)):
            label=html.escape(private_note(h.group(1)))
            return '<span class="source-unpublished">'+inner+' · '+label+'</span>'
        return m.group(0)
    # 仅处理HTML静态区域，避免把JS模板中的锚点当作实际元素。
    chunks=re.split(r'(<script\b[^>]*>[\s\S]*?</script>)',text,flags=re.I)
    for i,chunk in enumerate(chunks):
        if not chunk.lower().startswith('<script'):
            chunks[i]=re.sub(r'(<a\b[^>]*>)([\s\S]*?)</a>',anchor,chunk,flags=re.I)
    text=''.join(chunks)
    def evidence(m):
        data=clean_json(json.loads(m.group(2)))
        return m.group(1)+json.dumps(data,ensure_ascii=False).replace('<','\\u003c')+m.group(3)
    text=re.sub(r'(<script\b[^>]*id="evidence-sources"[^>]*>)([\s\S]*?)(</script>)',evidence,text)
    match=re.search(r'const data=(\[[\s\S]*?\]);const esc=',text)
    if match:
        data=clean_json(json.loads(match.group(1)))
        text=text[:match.start(1)]+json.dumps(data,ensure_ascii=False).replace('<','\\u003c')+text[match.end(1):]
    if is_main:
        helper="""function setPublicViewerSource(url,note){const link=document.getElementById('viewer-source');let label=document.getElementById('viewer-source-private-note');if(!label){label=document.createElement('span');label.id='viewer-source-private-note';link.after(label)}link.hidden=!url;label.hidden=!!url;label.textContent=url?'':(note||'来源未公开');if(url)link.href=url;else link.removeAttribute('href');}\n"""
        marker="document.querySelectorAll('.image-button').forEach"
        if text.count(marker)!=1:raise ValueError('图片查看器入口不唯一')
        text=text.replace(marker,helper+marker,1)
        old="document.getElementById('viewer-source').href=source.source;"
        if text.count(old)!=1:raise ValueError('动态来源绑定入口不唯一')
        text=text.replace(old,'setPublicViewerSource(source.source,source.source_note);')
        text=text.replace("document.getElementById('viewer-source').href=image.src;","setPublicViewerSource(image.src);")
        text=text.replace("document.getElementById('viewer-source').href='业务关系示例图.png';","setPublicViewerSource('业务关系示例图.png');")
        text=text.replace("document.getElementById('viewer-source').removeAttribute('href');","setPublicViewerSource(null,'未提供原始来源');")
    return text

class References(HTMLParser):
    def __init__(self,s):
        super().__init__();self.refs=[];self.feed(s)
    def handle_starttag(self,tag,attrs):
        for k,v in attrs:
            if v and k in ('src','href','data-original','poster'):self.refs.append(v)

def remove_editor_parts(source, parts):
    for part in parts:
        if not part or source.count(part)!=1:raise ValueError("编辑器原始区块不唯一，拒绝猜测删除")
        source=source.replace(part,"",1)
    if "/api/report-text" in source or "/api/attachment-text" in source:raise ValueError("残留后台接口")
    return source

def remove_editors(source, root):
    code="import * as a from './scripts/report_text_editor.mjs';import * as b from './scripts/attachment_text_editor.mjs';console.log(JSON.stringify([a.reportTextEditorMarkup,b.attachmentTextEditorMarkup,a.reportTextEditorScript,b.attachmentTextEditorScript]));"
    parts=json.loads(subprocess.check_output(['node','--input-type=module','-e',code],cwd=root,text=True))
    return remove_editor_parts(source, parts)

def references(text,suffix):
    if suffix=='.json':
        refs=[]
        def walk(v):
            if isinstance(v,dict):
                for k,x in v.items():
                    if k in {'file','preview','local','href','src','path','source_url','url'} and isinstance(x,str) and FILE.fullmatch(x):refs.append(x)
                    elif isinstance(x,(dict,list)):walk(x)
            elif isinstance(v,list):
                for x in v:walk(x)
        walk(json.loads(text));return set(refs)
    refs=References(text).refs if suffix=='.html' else []
    # 侧栏显式data schema优先解析，避免HTML模板字符串吞掉相邻JSON字符串。
    if suffix=='.html' and 'const data=' in text and 'const esc=' in text:
        match=re.search(r'const data=(\[[\s\S]*?\]);const esc=',text)
        if match:
            products=json.loads(match.group(1))
            for product in products:
                if not isinstance(product.get('shots'),list):raise ValueError('侧栏shots结构无效')
                for shot in product['shots']:
                    local=shot.get('local')
                    if not isinstance(local,str) or not local:raise ValueError('侧栏截图缺少local')
                    refs.append(local)
    if suffix=='.html' and 'const PAIN_POINTS=' in text:
        start=text.index('const PAIN_POINTS=')+len('const PAIN_POINTS=')
        points,_=json.JSONDecoder().raw_decode(text,start)
        for rows in points.values():
            for point in rows:
                for source in point['sources']:refs.append(source['file'])
    # 内嵌JSON和JS的完整路径字符串；不解析拼接表达式，不猜测缺失资源。
    for m in re.finditer(r'"([^"\\]*(?:\\.[^"\\]*)*)"|\x27([^\x27\\]*(?:\\.[^\x27\\]*)*)\x27',text):
        raw=m.group(0)
        try:v=json.loads(raw) if raw[0]=='"' else raw[1:-1].replace('\\/','/')
        except json.JSONDecodeError:continue
        if FILE.fullmatch(v):refs.append(v)
    refs += re.findall(r'url\(["\x27]?([^\)"\x27]+)',text)
    return set(refs)

def source_file(path, root):
    # 迁移后的两处资料挂载是明确的来源；其他软链接不进入公开包。
    path=Path(os.path.abspath(path))
    if not path.is_relative_to(root):raise ValueError('来源目录越界：'+str(path))
    current=root;allowed=root
    for index, part in enumerate(path.relative_to(root).parts):
        current=current/part
        if current.is_symlink():
            expected=root.parent/part
            if index!=0 or part not in {'参考资料','需求文档'} or os.readlink(current)!='../'+part or expected.is_symlink():
                raise ValueError('未授权的来源软链接：'+str(current))
            allowed=expected.resolve(strict=True)
    actual=path.resolve(strict=True)
    if not actual.is_relative_to(allowed):raise ValueError('真实来源目录越界：'+str(path))
    if not actual.is_file():raise FileNotFoundError(path)
    return path

def resolve(owner,ref,root):
    ref=html.unescape(ref)
    if private_reference(ref):raise ValueError("私有源文档仍可访问："+ref)
    u=urlsplit(ref)
    if u.scheme or u.netloc or not u.path:return None
    if u.path.startswith('/'):raise ValueError(f'不支持项目子路径的绝对引用：{owner}: {ref}')
    p=Path(os.path.abspath((root/owner).parent.joinpath(unquote(u.path))))
    if not p.is_relative_to(root):raise ValueError(f'引用越界：{owner}: {ref}')
    rel=p.relative_to(root)
    if any(any(x in part for x in BLOCKED) for part in rel.parts) or rel.suffix.lower() in ('.py','.zip') or '修改.json' in rel.name:raise ValueError(f'禁止发布依赖：{rel}')
    source_file(p,root)
    return rel.as_posix()

def validate_paths(root,dest):
    root=root.resolve();dest=dest.resolve()
    if not root.is_dir():raise NotADirectoryError(root)
    if dest==root or dest.is_relative_to(root) or root.is_relative_to(dest):
        raise ValueError('源目录与目标目录必须隔离，不能互相包含')
    if dest.exists():raise FileExistsError(dest)
    return root,dest

def build(root,dest):
    ROOT,DEST=validate_paths(root,dest)
    if DEST.exists():raise FileExistsError(f'输出已存在，拒绝混入旧文件：{DEST}')
    pending=list(SEEDS);assets={};edges={}
    while pending:
        name=pending.pop()
        if name in assets:continue
        path=source_file(ROOT/name,ROOT)
        data=path.read_bytes();deps=[]
        if path.suffix.lower() in ('.html','.css','.js','.json','.md'):
            text=data.decode('utf-8')
            if name==MAIN:text=remove_editors(text,ROOT)
            text=public_text(text,path.suffix.lower(),name==MAIN)
            for ref in sorted(references(text,path.suffix.lower())):
                target=resolve(name,ref,ROOT)
                if target:deps.append(target);pending.append(target)
            data=text.encode('utf-8')
        assets[name]=data;edges[name]=deps
    for name,data in assets.items():
        target=DEST/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    entry='<!doctype html><meta charset="utf-8"><title>超节点产品研究</title><script>const target=new URL("output/超节点平台竞争分析.html",location.href);target.search=location.search;target.hash=location.hash;location.replace(target.href)</script><a href="output/超节点平台竞争分析.html">进入完整报告</a>'
    (DEST/'index.html').write_text(entry,encoding='utf-8');(DEST/'.nojekyll').write_text('',encoding='utf-8')
    for owner,targets in edges.items():
        for target in targets:
            if not (DEST/target).is_file():raise FileNotFoundError(target)
    generated={'index.html':entry.encode('utf-8'),'.nojekyll':b''}
    payload={**assets,**generated}
    stats={'asset_files':len(assets),'asset_bytes':sum(map(len,assets.values())),
           'payload_files':len(payload),'payload_bytes':sum(map(len,payload.values())),
           'total_files':len(payload)+2,'metadata_files':['manifest.json','static-validation.json'],
           'bytes_scope':'payload_bytes包含全部页面与资产，不含这两份元数据，避免自引用统计'}
    manifest={'mode':'公开阅读版','publication':{'source_documents':'local-only','raw_mrd_extract':'local-only'},'entry':'index.html','statistics':stats,
              'files':{n:{'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()} for n,d in sorted(payload.items())},'dependencies':edges}
    (DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    result={**stats,'html':sum(n.endswith('.html') for n in payload),'dependency_edges':sum(map(len,edges.values())),'missing':0,'source_unchanged':True}
    (DEST/'static-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    actual=[p for p in DEST.rglob('*') if p.is_file()]
    if len(actual)!=stats['total_files']:raise ValueError('总文件数校验失败')
    for name,data in payload.items():
        if (DEST/name).read_bytes()!=data:raise ValueError('导出内容校验失败：'+name)
    return {**result,'total_bytes':sum(p.stat().st_size for p in actual),'destination':str(DEST)}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--dest',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.source_root,args.dest),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
