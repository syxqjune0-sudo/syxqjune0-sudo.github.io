#!/usr/bin/env python3
"""
网站构建脚本 — 模板拼装 + 博客 Markdown 转 HTML + 渠道分发
用法: python build.py

模板系统:
  _templates/header.html  — 页面头部 + 导航 (含 {{NAV_ITEMS}} 占位符)
  _templates/footer.html  — 页脚 + 免责声明 + 浮动按钮

页面源文件:
  _src/{page}.html — 包含 {{HEAD}} 和 {{BODY}} 占位符

博客源文件:
  blog/src/{date}_{slug}.md — Markdown + YAML front matter
  构建后输出:
    1. blog/{date}_{slug}.html        — 官网博客页 (带导航/页脚/外部 CSS)
    2. 市场内容/{date}_{slug}.html     — 渠道分发版 (自包含 HTML，适配公众号/知乎)

运行后自动生成官网页面、博客文章和渠道分发 HTML。
"""

import os
import re
import glob
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, '_templates')
SRC_DIR = os.path.join(BASE_DIR, '_src')
BLOG_SRC_DIR = os.path.join(BASE_DIR, 'blog', 'src')
BLOG_DIR = os.path.join(BASE_DIR, 'blog')
CHANNEL_DIR = os.path.join(os.path.dirname(BASE_DIR), '市场内容')

SITE_BASE = 'https://syxqjune0-sudo.github.io/'

# 导航配置: (文件名, 显示文字)
NAV_ITEMS = [
    ('index.html',    '首页'),
    ('services.html', '服务'),
    ('iso.html',      '标准体系'),
    ('videos.html',   '视频'),
    ('why.html',      '为什么需要'),
    ('cases.html',    '场景'),
    ('industry.html', '行业'),
    ('subsidy.html',  '补贴'),
    ('blog.html',     '博客'),
    ('contact.html',  '联系'),
]

# ============================================================
# 工具函数
# ============================================================

def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def load_template(name):
    return read(os.path.join(TEMPLATE_DIR, name))

# ============================================================
# 模板渲染
# ============================================================

def build_nav(active_page):
    """生成导航 HTML，自动标记 active"""
    items = []
    for href, label in NAV_ITEMS:
        cls = ' class="active"' if href == active_page else ''
        items.append(f'    <a href="{href}"{cls}>{label}</a>')
    return '\n'.join(items)

def render_page(page_file, content_html):
    """用模板渲染一个完整页面"""
    header_tpl = load_template('header.html')
    footer_tpl = load_template('footer.html')
    src = read(os.path.join(SRC_DIR, page_file))

    # 从源文件提取 <head> 内容
    head_match = re.search(r'\{\{HEAD\}\}\s*\n(.*?)\n\{\{HEAD_END\}\}', src, re.DOTALL)
    if not head_match:
        # 兼容: 直接取 {{HEAD}} 后到文件末尾之外的内容
        # 新格式: 源文件第一行是 {{HEAD}}, 最后一行是 {{BODY_END}}
        head_start = src.index('{{HEAD}}') + len('{{HEAD}}') + 1
        body_marker = '\n{{BODY}}'
        body_start = src.index(body_marker)
        head_content = src[head_start:body_start].strip()
        body_content = src[body_start + len(body_marker):].strip()
    else:
        head_content = head_match.group(1).strip()
        body_content = src[head_match.end():].replace('{{BODY}}', '').strip()

    # 渲染 header
    header = header_tpl
    header = header.replace('{{HEAD}}', head_content)
    header = header.replace('{{NAV_ITEMS}}', build_nav(page_file))

    # 替换动态内容占位符
    if '{{BLOG_LIST}}' in body_content:
        body_content = body_content.replace('{{BLOG_LIST}}', build_homepage_blog_section())

    header = header.replace('{{BODY}}', body_content)

    return header + '\n' + footer_tpl

# ============================================================
# 博客系统
# ============================================================

def parse_frontmatter(text):
    """解析 YAML front matter (简易实现)"""
    if not text.startswith('---'):
        return {}, text
    parts = text.split('---', 2)
    if len(parts) < 3:
        return {}, text

    meta = {}
    for line in parts[1].strip().split('\n'):
        if ':' in line:
            key, val = line.split(':', 1)
            key = key.strip()
            val = val.strip()
            # 只去掉成对的外层引号，保留内容中的引号
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            meta[key] = val
    return meta, parts[2].strip()

def md_to_html(md_text):
    """Markdown 转 HTML"""
    try:
        import markdown
        return markdown.markdown(md_text, extensions=['extra', 'sane_lists', 'toc'])
    except ImportError:
        return _basic_md(md_text)

def _basic_md(text):
    """极简 Markdown 转换 (无第三方依赖)"""
    lines = text.split('\n')
    html = []
    in_list = False
    in_p = False

    for line in lines:
        stripped = line.strip()

        # 空行
        if not stripped:
            if in_list:
                html.append('</ul>')
                in_list = False
            if in_p:
                html.append('</p>')
                in_p = False
            continue

        # 水平线
        if re.match(r'^-{3,}$', stripped) or re.match(r'^\*{3,}$', stripped) or re.match(r'^_{3,}$', stripped):
            if in_list: html.append('</ul>'); in_list = False
            if in_p: html.append('</p>'); in_p = False
            html.append('<hr>')
            continue

        # 标题
        h_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if h_match:
            if in_list: html.append('</ul>'); in_list = False
            if in_p: html.append('</p>'); in_p = False
            level = len(h_match.group(1))
            html.append(f'<h{level}>{_inline(h_match.group(2))}</h{level}>')
            continue

        # 列表
        if stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                html.append('<ul>')
                in_list = True
            html.append(f'<li>{_inline(stripped[2:])}</li>')
            continue

        # 段落
        if not in_p:
            html.append('<p>')
            in_p = True
        else:
            html.append('<br>')
        html.append(_inline(stripped))

    if in_list: html.append('</ul>')
    if in_p: html.append('</p>')
    return '\n'.join(html)

def _inline(text):
    """处理行内 Markdown 语法"""
    # 粗体+斜体
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    # 粗体
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # 斜体
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # 链接
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text

def build_blog_post(md_file):
    """构建单篇博客文章"""
    text = read(md_file)
    meta, content = parse_frontmatter(text)

    title = meta.get('title', '博客')
    date = meta.get('date', '')
    desc = meta.get('description', '')
    slug = os.path.basename(md_file).replace('.md', '')
    out_file = os.path.join(BLOG_DIR, slug + '.html')

    body_html = md_to_html(content)

    head = f'''<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="../common.css">'''

    body = f'''<section class="page-hero"><div class="wrap">
  <h1>{title}</h1>
  <p>体系咨询团队 · {date}</p>
</div></section>

<section><div class="wrap" style="max-width:720px">
  <div class="blog-article">
    {body_html}
  </div>
  <div style="margin-top:40px;text-align:center">
    <a href="../blog.html" class="btn t">返回博客列表</a>
  </div>
</div></section>'''

    header_tpl = load_template('header.html')
    footer_tpl = load_template('footer.html')

    header = header_tpl.replace('{{HEAD}}', head)
    header = header.replace('{{NAV_ITEMS}}', build_nav('blog.html'))
    header = header.replace('{{BODY}}', body)

    result = header + '\n' + footer_tpl
    write(out_file, result)
    print(f'  博客: {slug}.html')
    return {'slug': slug, 'title': title, 'date': date, 'description': desc}

# ---------------------------------------------------------------- 渠道分发
CHANNEL_CSS = '''
body{margin:0;padding:0;background:#f4f6f9;color:#1f2329;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  line-height:1.85;font-size:15px}
.wrap{max-width:720px;margin:28px auto;background:#fff;
  border:1px solid #e6ebf1;border-radius:12px;overflow:hidden;
  box-shadow:0 2px 14px rgba(0,0,0,.05)}
.banner{background:linear-gradient(135deg,#1f6feb,#3b82f6);padding:30px 34px;color:#fff}
.banner .tag{font-size:13px;letter-spacing:1px;opacity:.9}
.banner h1{margin:12px 0 6px;font-size:25px;line-height:1.4;font-weight:700}
.banner .date{font-size:13px;opacity:.85}
.body{padding:30px 34px 36px}
.body h2{font-size:19px;margin:30px 0 14px;padding-left:12px;
  border-left:4px solid #1f6feb;color:#1f3a5f}
.body p{margin:0 0 16px;font-size:15.5px;color:#475569}
.body strong{color:#2c3e50}
.body ul{margin:0 0 16px;padding-left:22px}
.body li{margin:9px 0;font-size:15px;color:#2c333d}
.body hr{border:none;border-top:1px solid #eef0f3;margin:28px 0}
.body blockquote{margin:16px 0;padding:12px 18px;background:#f0f6ff;
  border-left:4px solid #2f6fed;border-radius:6px;color:#34415c;font-size:15px}
.body em{color:#6b7280;font-size:14px}
.cta{background:#eef4ff;border:1px solid #cfe0ff;border-radius:10px;
  padding:20px 22px;margin:8px 0 6px}
.cta p{margin:0 0 8px;font-size:16px;font-weight:700;color:#1f3a5f}
.cta .sub{margin:0;font-size:15px;color:#475569;font-weight:400}
.cta .kw{color:#1f6feb;font-size:16px;letter-spacing:1px}
.foot{margin:26px 0 0;font-size:13px;color:#94a3b8;text-align:center;
  padding:0 34px 28px}
'''


def build_channel_post(md_file):
    """构建渠道分发版本 — 自包含 HTML，<style> 在 head 中，适配公众号/知乎等。"""
    text = read(md_file)
    meta, content = parse_frontmatter(text)

    title = meta.get('title', '博客')
    date = meta.get('date', '')
    slug = os.path.basename(md_file).replace('.md', '')

    body_html = md_to_html(content)

    # 从 Markdown 正文末尾提取 CTA 和署名 (--- 分隔后的部分)
    cta_html = ''
    footer_text = ''
    if '<hr>' in body_html:
        parts = body_html.rsplit('<hr>', 1)
        body_html = parts[0].rstrip()
        tail = parts[1].strip()

        # 最后一段 <em>...</em> 作为署名
        em_match = re.search(r'<p>\s*<em>(.+?)</em>\s*</p>', tail, re.DOTALL)
        if em_match:
            footer_text = em_match.group(1)
            tail = tail[:em_match.start()] + tail[em_match.end():]

        # 剩余内容作为 CTA
        tail = tail.strip()
        if tail:
            # 把关键词「XXX」高亮
            tail = re.sub(
                r'「(.+?)」',
                r'<span class="kw">「\1」</span>',
                tail,
            )
            # 去掉所有 <p> 标签，提取纯文本行
            lines = []
            for chunk in re.split(r'</?p>', tail):
                chunk = chunk.strip()
                if chunk:
                    # 去掉 <strong> 标签但保留内容
                    chunk = re.sub(r'</?strong>', '', chunk).strip()
                    if chunk:
                        lines.append(chunk)

            if lines:
                # 第一行作为 CTA 标题，其余作为副文本
                cta_title = lines[0]
                cta_html = f'<div class="cta"><p>{cta_title}</p>'
                if len(lines) > 1:
                    sub_text = '<br>'.join(lines[1:])
                    cta_html += f'<p class="sub">{sub_text}</p>'
                cta_html += '</div>'

    # 生成输出文件名: YYYYMMDD_中文短标题.html
    date_compact = date.replace('-', '')
    # 从 title 提取短标题 (取第一个？或！前的部分，或前 30 字)
    short = re.split(r'[？?！!]', title)[0] if re.search(r'[？?！!]', title) else title[:30]
    short = short.strip().replace('"', '').replace("'", '').replace('/', '与').replace('\\', '')
    short = short.replace(':', '：').replace('|', '-').replace('<', '').replace('>', '')
    short = short.replace('*', '').replace('?', '').replace('"', '')
    out_name = f'{date_compact}_{short}.html'
    out_file = os.path.join(CHANNEL_DIR, out_name)

    result = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>{CHANNEL_CSS}</style>
</head>
<body>
<div class="wrap">
  <div class="banner">
    <div class="tag">体系文件开发团队 · 中小企业 ISO 实务</div>
    <h1>{title}</h1>
    <div class="date">{date} · 面向中小企业老板 / 管理者</div>
  </div>
  <div class="body">
    {body_html}
    {cta_html}
  </div>
  <div class="foot">{footer_text}</div>
</div>
</body>
</html>'''

    write(out_file, result)
    print(f'  渠道: {out_name}')


def get_all_posts():
    """获取所有博客文章元数据"""
    posts = []
    for md_file in glob.glob(os.path.join(BLOG_SRC_DIR, '*.md')):
        text = read(md_file)
        meta, _ = parse_frontmatter(text)
        slug = os.path.basename(md_file).replace('.md', '')
        posts.append({
            'slug': slug,
            'title': meta.get('title', ''),
            'date': meta.get('date', ''),
            'description': meta.get('description', ''),
        })
    posts.sort(key=lambda p: p['date'], reverse=True)
    return posts

def build_blog_listing():
    """构建博客列表页"""
    posts = get_all_posts()

    head = '''<title>博客_资讯_ISO体系认证实操干货</title>
<meta name="description" content="ISO体系认证的实操干货：中小企业为什么需要ISO体系、9001和27001怎么选、TISAX是什么。帮你少走弯路。">
<link rel="stylesheet" href="common.css">'''

    links = []
    for p in posts:
        links.append(
            f'    <a href="blog/{p["slug"]}.html">\n'
            f'      <div style="font-weight:600;margin-bottom:4px">{p["title"]}</div>\n'
            f'      <div style="font-size:13px;color:var(--mut)">{p["description"]}</div>\n'
            f'    </a>'
        )
    blog_list = '\n'.join(links)

    body = f'''<section class="page-hero"><div class="wrap">
  <h1>博客 / 资讯</h1>
  <p>体系认证的实操干货，帮你少走弯路</p>
</div></section>

<section><div class="wrap">
  <div class="blog">
{blog_list}
  </div>
</div></section>

<section class="cta-section"><div class="wrap">
  <h2>还有问题？</h2>
  <p class="sub">博客没覆盖到的问题，顾问直接帮你解答</p>
  <a href="contact.html" class="btn btn-lg">免费咨询</a>
</div></section>'''

    header_tpl = load_template('header.html')
    footer_tpl = load_template('footer.html')

    header = header_tpl.replace('{{HEAD}}', head)
    header = header.replace('{{NAV_ITEMS}}', build_nav('blog.html'))
    header = header.replace('{{BODY}}', body)

    result = header + '\n' + footer_tpl
    write(os.path.join(BASE_DIR, 'blog.html'), result)
    print('  博客列表: blog.html')

def build_homepage_blog_section():
    """生成首页的博客摘要 (供 index.html 引用)"""
    posts = get_all_posts()[:4]
    lines = []
    for p in posts:
        lines.append(
            f'    <a href="blog/{p["slug"]}.html">{p["title"]}</a>'
        )
    return '\n'.join(lines)

def build_sitemap():
    """自动生成 sitemap.xml"""
    urls = []

    # 首页
    urls.append(('https://syxqjune0-sudo.github.io/', 'weekly', '1.0'))

    # 页面 (按优先级)
    page_priority = {
        'services.html': '0.9',
        'iso.html': '0.9',
        'contact.html': '0.9',
        'videos.html': '0.8',
        'why.html': '0.8',
        'cases.html': '0.8',
        'industry.html': '0.8',
        'subsidy.html': '0.8',
        'blog.html': '0.8',
    }
    for page_file, priority in page_priority.items():
        if os.path.exists(os.path.join(SRC_DIR, page_file)):
            urls.append((f'https://syxqjune0-sudo.github.io/{page_file}', 'weekly', priority))

    # 博客文章
    posts = get_all_posts()
    for p in posts:
        urls.append((f'https://syxqjune0-sudo.github.io/blog/{p["slug"]}.html', 'monthly', '0.7'))

    # 生成 XML
    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for loc, freq, pri in urls:
        xml_lines.append('  <url>')
        xml_lines.append(f'    <loc>{loc}</loc>')
        xml_lines.append(f'    <changefreq>{freq}</changefreq>')
        xml_lines.append(f'    <priority>{pri}</priority>')
        xml_lines.append('  </url>')
    xml_lines.append('</urlset>')

    write(os.path.join(BASE_DIR, 'sitemap.xml'), '\n'.join(xml_lines) + '\n')
    print(f'  Sitemap: {len(urls)} 条 URL')

# ============================================================
# 主构建流程
# ============================================================

def build_all():
    print('=' * 50)
    print('开始构建网站...')
    print('=' * 50)

    # 1. 构建所有页面
    print('\n[1/5] 构建页面...')
    for src_file in sorted(glob.glob(os.path.join(SRC_DIR, '*.html'))):
        page_file = os.path.basename(src_file)
        result = render_page(page_file, '')
        out_path = os.path.join(BASE_DIR, page_file)
        write(out_path, result)
        print(f'  页面: {page_file}')

    # 2. 构建博客文章
    print('\n[2/5] 构建博客...')
    if os.path.exists(BLOG_SRC_DIR):
        for md_file in sorted(glob.glob(os.path.join(BLOG_SRC_DIR, '*.md'))):
            build_blog_post(md_file)
    else:
        print('  (无博客源文件，跳过)')

    # 3. 构建渠道分发版本 (同一份 Markdown → 自包含 HTML → 市场内容/)
    print('\n[3/5] 构建渠道分发...')
    if os.path.exists(BLOG_SRC_DIR):
        md_files = glob.glob(os.path.join(BLOG_SRC_DIR, '*.md'))
        if md_files:
            os.makedirs(CHANNEL_DIR, exist_ok=True)
            for md_file in sorted(md_files):
                build_channel_post(md_file)
        else:
            print('  (无博客源文件，跳过)')
    else:
        print('  (无博客源文件，跳过)')

    # 4. 重新构建博客列表和首页博客区 (依赖博客元数据)
    print('\n[4/5] 更新博客列表...')
    if os.path.exists(BLOG_SRC_DIR) and glob.glob(os.path.join(BLOG_SRC_DIR, '*.md')):
        build_blog_listing()

    # 5. 更新 sitemap
    print('\n[5/5] 更新 Sitemap...')
    build_sitemap()

    print('\n' + '=' * 50)
    print('构建完成!')
    print(f'  官网: {BASE_DIR}')
    print(f'  渠道: {CHANNEL_DIR}')
    print('=' * 50)

if __name__ == '__main__':
    build_all()
