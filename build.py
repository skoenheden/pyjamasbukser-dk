#!/usr/bin/env python3
"""
build.py - statisk site-generator for pyjamasbukser.dk

Læser content/site.json, content/brands.json og content/articles/*.html
og skriver et komplet statisk site til docs/ (GitHub Pages-rod, virker også på cPanel/LiteSpeed).

Brug:
    python3 build.py            # byg alt
    python3 build.py --check    # valider indhold, skriv intet

En artikel er en .html-fil i content/articles/ der starter med en HTML-kommentar
med JSON-front-matter, efterfulgt af brødteksten:

    <!--
    { "slug": "pyjamasbukser-herre", "title": "...", "description": "...", ... }
    -->
    <h2>...</h2>

Pladsholdere i brødtekst, intro og quick_answer:
    {{SHOP}}                          -> boombutik.dk/products/bomuldsbukser med UTM
    {{SHOP:/collections/x}}           -> dyb URL på boombutik.dk med UTM
    {{CTA|Leadtekst|Knaptekst}}       -> CTA-boks til Bomuldsbukserne
    {{CTA:/sti|Leadtekst|Knaptekst}}  -> CTA-boks til en anden sti
    {{LINK:slug|Ankertekst}}          -> intern link (valideres)
    {{PRODUCT}}                       -> produktkort for Boom Butiks Bomuldsbukser
    {{FACTS}}                         -> faktaboks: fragt, retur, reparation, anmeldelser
    {{COMPARE}}                       -> fuld sammenligningstabel fra brands.json
    {{COMPARE:tag}}                   -> tabel filtreret på tag (fx herre, dame, bomuld)
    {{ARTICLES}}                      -> kortgitter med alle listede artikler

Husregel: ingen lange tankestreger (U+2014 / U+2013) i synlig tekst. Build fejler hvis de findes.
"""
import datetime
import html
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(ROOT, "content")
ASSETS = os.path.join(ROOT, "assets")
OUT = os.path.join(ROOT, "docs")
CHECK_ONLY = "--check" in sys.argv

MONTHS = ["januar", "februar", "marts", "april", "maj", "juni", "juli",
          "august", "september", "oktober", "november", "december"]

errors, warnings = [], []


# ---------------------------------------------------------------- helpers
def read_json(path):
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            sys.exit(f"JSON-fejl i {path}: {e}")


def esc(s):
    return html.escape(str(s), quote=True)


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def jsonld(obj):
    return ('<script type="application/ld+json">'
            + json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            + "</script>")


def da_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {MONTHS[d.month - 1]} {d.year}"


SITE = read_json(os.path.join(CONTENT, "site.json"))
BRANDS = read_json(os.path.join(CONTENT, "brands.json"))
DOMAIN = SITE["domain"].rstrip("/")
SHOP = SITE["shop"].rstrip("/")
BOOM = SITE["boom"]


def shop_url(path=None, content="inline", slug="home"):
    path = path or BOOM["product_path"]
    path = path if path.startswith("/") else "/" + path
    sep = "&" if "?" in path else "?"
    return (f"{SHOP}{path}{sep}utm_source=pyjamasbukser.dk&utm_medium=referral"
            f"&utm_campaign=seo&utm_content={slug}-{content}")


def page_url(slug):
    return f"{DOMAIN}/" if slug == "index" else f"{DOMAIN}/{slug}"


def href(slug):
    return "/" if slug == "index" else f"/{slug}"


# ---------------------------------------------------------------- articles
def load_articles():
    arts = []
    d = os.path.join(CONTENT, "articles")
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".html"):
            continue
        raw = open(os.path.join(d, fn), encoding="utf-8").read()
        m = re.match(r"\s*<!--(.*?)-->(.*)", raw, re.S)
        if not m:
            errors.append(f"{fn}: mangler front-matter-kommentar")
            continue
        try:
            meta = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            errors.append(f"{fn}: front-matter er ikke gyldig JSON ({e})")
            continue
        meta["body"] = m.group(2).strip()
        meta["_file"] = fn
        for k in ("slug", "title", "description", "h1", "date_published", "date_modified"):
            if not meta.get(k):
                errors.append(f"{fn}: mangler felt '{k}'")
        if meta.get("slug") and meta["slug"] + ".html" != fn and not (meta["slug"] == "index" and fn == "index.html"):
            errors.append(f"{fn}: slug '{meta.get('slug')}' matcher ikke filnavnet")
        meta.setdefault("layout", "article")
        meta.setdefault("listed", meta["layout"] == "article")
        meta.setdefault("faq", [])
        meta.setdefault("related", [])
        meta.setdefault("category", "Guide")
        arts.append(meta)
    return arts


ARTICLES = load_articles()
BY_SLUG = {a["slug"]: a for a in ARTICLES if a.get("slug")}


# ---------------------------------------------------------------- components
def cta_box(path, lead, btn, slug):
    return (f'<div class="cta-box"><p>{lead}</p>'
            f'<a class="btn" href="{esc(shop_url(path, "cta", slug))}">{btn} →</a></div>')


def stars(score):
    return f'<span class="stars" aria-hidden="true">★</span> {score}'


def product_card(slug):
    b = BOOM
    img = b["images"][0]
    colors = ", ".join(b["colors"])
    return f'''<div class="product-card">
  <a class="product-img" href="{esc(shop_url(None, "product-card", slug))}"><img src="{esc(img["src"])}" alt="{esc(img["alt"])}" loading="lazy" width="600" height="750"></a>
  <div class="product-body">
    <span class="pill">Vores anbefaling</span>
    <h3>{esc(b["product_name"])} fra Boom Butik</h3>
    <div class="product-price">{b["price"]} kr.</div>
    <p class="product-rating">{stars(str(b["rating"]).replace(".", ","))} / 5 fra {b["reviews"]} anmeldelser på boombutik.dk</p>
    <ul class="spec">
      <li><b>Materiale</b> {esc(b["material"])}, {b["gsm"]} g/m²</li>
      <li><b>Pasform</b> {esc(b["fit"])}</li>
      <li><b>Størrelser</b> {esc(b["sizes"])}</li>
      <li><b>Farver</b> {esc(colors)}</li>
      <li><b>Fragt</b> {esc(b["shipping_short"])}</li>
      <li><b>Retur</b> {esc(b["returns_short"])}</li>
    </ul>
    <a class="btn" href="{esc(shop_url(None, "product-card", slug))}">Se Bomuldsbukserne →</a>
    <p class="own">{esc(SITE["disclosure_short"])}</p>
  </div>
</div>'''


def facts_box():
    b = BOOM
    return f'''<div class="facts">
  <div><b>{b["price"]} kr.</b><span>pris pr. par</span></div>
  <div><b>{b["free_shipping_from"]} kr.</b><span>gratis fragt fra</span></div>
  <div><b>{b["return_days"]} dage</b><span>returret</span></div>
  <div><b>Hele livet</b><span>gratis reparation</span></div>
  <div><b>{str(b["rating"]).replace(".", ",")} / 5</b><span>{b["reviews"]} produktanmeldelser</span></div>
</div>'''


def compare_table(tag, slug):
    rows = [x for x in BRANDS["rows"] if not tag or tag in x.get("tags", []) or x.get("boom")]
    out = ['<div class="compare-wrap"><table class="compare">',
           "<thead><tr><th>Brand og model</th><th>Materiale</th><th>Pris</th>"
           "<th>Fragt</th><th>Retur</th><th>Trustpilot</th><th></th></tr></thead><tbody>"]
    for r in rows:
        boom = r.get("boom")
        link = shop_url(r["path"], "compare", slug) if boom else r["url"]
        rel = "" if boom else ' rel="nofollow noopener" target="_blank"'
        badge = '<span class="pill">Vores anbefaling</span>' if boom else ""
        tp = r.get("trustpilot") or "ikke oplyst"
        out.append(
            f'<tr class="{"is-boom" if boom else ""}">'
            f'<td data-label="Brand">{badge}<b>{esc(r["brand"])}</b><span class="sub">{esc(r["model"])}</span></td>'
            f'<td data-label="Materiale">{esc(r["material"])}</td>'
            f'<td data-label="Pris"><b>{esc(r["price"])}</b></td>'
            f'<td data-label="Fragt">{esc(r["shipping"])}</td>'
            f'<td data-label="Retur">{esc(r["returns"])}</td>'
            f'<td data-label="Trustpilot">{esc(tp)}</td>'
            f'<td><a class="{"btn btn-sm" if boom else "out"}" href="{esc(link)}"{rel}>{"Se bukserne" if boom else "Se hos " + esc(r["shop"])} →</a></td>'
            "</tr>")
    out.append("</tbody></table></div>")
    out.append(f'<p class="source">Priser, fragt og returvilkår er tjekket på brandenes egne sider og Trustpilot {da_date(BRANDS["checked"])}. '
               "Priser skifter, så tjek altid den aktuelle pris hos forhandleren. "
               + esc(SITE["disclosure_short"]) + " Se {{LINK:om|hvordan vi sammenligner}}.</p>")
    return "\n".join(out)


def article_cards(exclude=None):
    items = [a for a in ARTICLES if a["listed"] and a["slug"] != exclude]
    items.sort(key=lambda a: (a.get("order", 999), a["title"]))
    cards = "".join(
        f'<a class="card" href="{href(a["slug"])}"><span class="card-tag">{esc(a["category"])}</span>'
        f'<strong>{esc(a.get("card_title") or a["h1"])}</strong></a>' for a in items)
    return f'<div class="cards">{cards}</div>'


def expand(text, slug):
    if not isinstance(text, str):
        return text
    text = re.sub(r"\{\{COMPARE(?::([a-z\-]+))?\}\}", lambda m: compare_table(m.group(1), slug), text)
    text = text.replace("{{PRODUCT}}", product_card(slug)).replace("{{FACTS}}", facts_box())
    text = text.replace("{{ARTICLES}}", article_cards(exclude=slug))
    text = re.sub(r"\{\{CTA(?::([^|}]+))?\|([^|}]+)\|([^}]+)\}\}",
                  lambda m: cta_box(m.group(1), m.group(2), m.group(3), slug), text)
    text = re.sub(r"\{\{SHOP(?::([^}]+))?\}\}", lambda m: shop_url(m.group(1), "inline", slug), text)

    def link(m):
        target, anchor = m.group(1), m.group(2)
        if target not in BY_SLUG:
            errors.append(f"{slug}: {{{{LINK:{target}}}}} peger på en artikel der ikke findes")
        return f'<a href="{href(target)}">{anchor}</a>'
    text = re.sub(r"\{\{LINK:([a-z0-9\-]+)\|([^}]+)\}\}", link, text)
    if "{{" in text:
        errors.append(f"{slug}: ukendt pladsholder: {text[text.index('{{'):text.index('{{') + 40]}")
    return text


# ---------------------------------------------------------------- page shell
CSS = open(os.path.join(ROOT, "assets", "site.css"), encoding="utf-8").read()


def head(a, canonical):
    title = a["title"]
    desc = a["description"]
    og_type = "website" if a["slug"] == "index" else "article"
    return f'''<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="geo.region" content="DK">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" href="/favicon.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta property="og:site_name" content="pyjamasbukser.dk">
<meta property="og:locale" content="da_DK">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{DOMAIN}/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap" rel="stylesheet">
<style>{CSS}</style>
'''


def header():
    nav = "".join(f'<a href="{esc(u)}">{esc(t)}</a>' for t, u in SITE["nav"])
    return f'''<header class="site-header">
  <div class="wrap header-inner">
    <a class="logo" href="/" aria-label="pyjamasbukser.dk forside">
      <svg class="logo-mark" viewBox="0 0 34 34" width="34" height="34" aria-hidden="true"><rect width="34" height="34" rx="8" fill="#1d2340"/><circle cx="17" cy="17" r="10" fill="#f7f5f0"/><circle cx="22.5" cy="13.5" r="10" fill="#1d2340"/></svg>
      <span class="logo-text"><b>pyjamasbukser.dk</b><small>Guide og sammenligning</small></span>
    </a>
    <nav class="main-nav" id="nav">{nav}</nav>
    <button class="nav-toggle" aria-label="Menu" aria-expanded="false" onclick="var n=document.getElementById('nav');n.classList.toggle('open');this.setAttribute('aria-expanded',n.classList.contains('open'))">☰</button>
  </div>
</header>'''


def footer(slug):
    links = "".join(f'<a href="{esc(u)}">{esc(t)}</a>' for t, u in SITE["nav"])
    return f'''<footer class="site-footer">
  <div class="wrap">
    <div class="footer-top">
      <div><b>pyjamasbukser.dk</b><p>{esc(SITE["disclosure_short"])}</p></div>
      <nav>{links}<a href="/om">Om siden</a></nav>
    </div>
    <p class="footer-copy">© {datetime.date.today().year} pyjamasbukser.dk. Varemærker tilhører deres respektive ejere.</p>
  </div>
</footer>
<div class="mobile-cta"><a href="{esc(shop_url(None, "mobile-sticky", slug))}">Se Bomuldsbukserne · {BOOM["price"]} kr. →</a></div>'''


def breadcrumb(a):
    if a["slug"] == "index":
        return "", None
    trail = [("Forside", "/")]
    if a["layout"] == "article":
        trail.append(("Artikler", "/artikler"))
    trail.append((a.get("card_title") or a["h1"], None))
    items = []
    for t, u in trail:
        items.append(f'<a href="{u}">{esc(t)}</a>' if u else f"<span>{esc(t)}</span>")
    schema = {"@context": "https://schema.org", "@type": "BreadcrumbList",
              "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": t,
                                   "item": (DOMAIN + u) if u else page_url(a["slug"])}
                                  for i, (t, u) in enumerate(trail)]}
    return f'<nav class="crumbs" aria-label="Brødkrumme">{" / ".join(items)}</nav>', schema


def faq_html(faq, slug):
    if not faq:
        return ""
    items = "".join(f'<details class="faq-item"><summary>{esc(q["q"])}</summary><div>{expand(q["a"], slug)}</div></details>'
                    for q in faq)
    return f'<section class="faq" id="faq"><h2>Ofte stillede spørgsmål</h2>{items}</section>'


def related_html(a):
    rel = [BY_SLUG[s] for s in a["related"] if s in BY_SLUG]
    for s in a["related"]:
        if s not in BY_SLUG:
            errors.append(f"{a['slug']}: related '{s}' findes ikke")
    if not rel:
        return ""
    lis = "".join(f'<li><a href="{href(r["slug"])}">{esc(r.get("card_title") or r["h1"])}</a></li>' for r in rel)
    return f'<aside class="related"><h2>Læs også</h2><ul>{lis}</ul></aside>'


def schemas(a, canonical):
    out = []
    publisher = {"@type": "Organization", "name": "pyjamasbukser.dk", "url": DOMAIN + "/",
                 "logo": f"{DOMAIN}/apple-touch-icon.png",
                 "parentOrganization": {"@type": "Organization", "name": "Boom Butik", "url": SHOP + "/"}}
    if a["slug"] == "index":
        out.append({"@context": "https://schema.org", "@type": "WebSite", "name": "pyjamasbukser.dk",
                    "url": DOMAIN + "/", "inLanguage": "da", "description": SITE["description"],
                    "publisher": publisher})
        out.append({"@context": "https://schema.org", "@type": "ItemList",
                    "name": "Pyjamasbukser sammenlignet i Danmark",
                    "itemListElement": [
                        {"@type": "ListItem", "position": i + 1,
                         "name": f'{r["brand"]} {r["model"]}',
                         "url": (SHOP + r["path"]) if r.get("boom") else r["url"]}
                        for i, r in enumerate(BRANDS["rows"])]})
        out.append({"@context": "https://schema.org", "@type": "Product",
                    "name": f'Boom Butik {BOOM["product_name"]}', "brand": {"@type": "Brand", "name": "Boom Butik"},
                    "description": BOOM["summary"], "image": [i["src"] for i in BOOM["images"]],
                    "material": BOOM["material"], "url": SHOP + BOOM["product_path"],
                    "offers": {"@type": "Offer", "price": str(BOOM["price"]), "priceCurrency": "DKK",
                               "availability": "https://schema.org/InStock",
                               "url": SHOP + BOOM["product_path"],
                               "seller": {"@type": "Organization", "name": "Boom Butik"}}})
    else:
        typ = "Article" if a["layout"] == "article" else "WebPage"
        out.append({"@context": "https://schema.org", "@type": typ, "headline": a["h1"],
                    "description": a["description"], "url": canonical, "inLanguage": "da",
                    "datePublished": a["date_published"], "dateModified": a["date_modified"],
                    "image": f"{DOMAIN}/og-image.png",
                    "author": {"@type": "Organization", "name": "pyjamasbukser.dk", "url": DOMAIN + "/"},
                    "publisher": publisher,
                    "mainEntityOfPage": canonical})
    if a["faq"]:
        out.append({"@context": "https://schema.org", "@type": "FAQPage",
                    "mainEntity": [{"@type": "Question", "name": q["q"],
                                    "acceptedAnswer": {"@type": "Answer", "text": strip_tags(expand(q["a"], a["slug"]))}}
                                   for q in a["faq"]]})
    return out


def render(a):
    slug = a["slug"]
    canonical = page_url(slug)
    crumbs, crumb_schema = breadcrumb(a)
    body = expand(a["body"], slug)
    qa = a.get("quick_answer")
    qa_html = f'<div class="quick-answer"><span>Kort svar</span><p>{expand(qa, slug)}</p></div>' if qa else ""
    intro = f'<p class="lede">{expand(a["intro"], slug)}</p>' if a.get("intro") else ""
    updated = f'<p class="meta">Opdateret {da_date(a["date_modified"])} · Af redaktionen</p>'

    if a["layout"] == "home":
        top = f'''<section class="hero">
  <div class="wrap">
    <p class="eyebrow">{esc(a.get("eyebrow", ""))}</p>
    <h1>{a["h1"]}</h1>
    {intro}
    {updated}
  </div>
</section>
<div class="wrap narrow">{qa_html}</div>'''
        main = f'<main class="home">{body}</main>'
    else:
        top = ""
        main = f'''<main class="wrap narrow article">
  {crumbs}
  <p class="eyebrow">{esc(a.get("eyebrow") or a["category"])}</p>
  <h1>{a["h1"]}</h1>
  {updated}
  {intro}
  {qa_html}
  <div class="prose">{body}</div>
  {faq_html(a["faq"], slug)}
  {related_html(a)}
</main>'''
    if a["layout"] == "home" and a["faq"]:
        main += f'<div class="wrap narrow">{faq_html(a["faq"], slug)}</div>'

    sch = schemas(a, canonical)
    if crumb_schema:
        sch.append(crumb_schema)
    doc = (head(a, canonical) + "".join(jsonld(s) for s in sch) + "\n</head>\n<body>\n"
           + header() + "\n" + top + "\n" + main + "\n" + footer(slug) + "\n</body>\n</html>\n")
    return doc


# ---------------------------------------------------------------- site files
def sitemap():
    urls = []
    for a in sorted(ARTICLES, key=lambda x: (x["slug"] != "index", x["slug"])):
        pr = "1.0" if a["slug"] == "index" else ("0.8" if a["layout"] == "article" else "0.5")
        urls.append(f"  <url><loc>{page_url(a['slug'])}</loc><lastmod>{a['date_modified']}</lastmod>"
                    f"<changefreq>weekly</changefreq><priority>{pr}</priority></url>")
    urls.append(f"  <url><loc>{DOMAIN}/artikler</loc><lastmod>{max(a['date_modified'] for a in ARTICLES)}</lastmod>"
                f"<changefreq>weekly</changefreq><priority>0.7</priority></url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n")


def robots():
    bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "Perplexity-User",
            "ClaudeBot", "Claude-User", "Claude-SearchBot", "Google-Extended", "Applebot",
            "Applebot-Extended", "Bingbot", "CCBot"]
    s = "# robots.txt - pyjamasbukser.dk\nUser-agent: *\nAllow: /\n\n# AI-søgemaskiner (GEO) - eksplicit tilladt\n"
    s += "".join(f"User-agent: {b}\nAllow: /\n\n" for b in bots)
    return s + f"Sitemap: {DOMAIN}/sitemap.xml\n"


def llms():
    b = BOOM
    lines = [f"# pyjamasbukser.dk", "", f"> {SITE['description']}", "",
             "## Kerneoplysninger", ""]
    lines += [f"- {x}" for x in SITE["llms_facts"]]
    lines += ["", "## Sammenligning (tjekket " + BRANDS["checked"] + ")", ""]
    for r in BRANDS["rows"]:
        lines.append(f'- {r["brand"]} {r["model"]}: {r["material"]}, {r["price"]}, fragt: {r["shipping"]}, '
                     f'retur: {r["returns"]}, Trustpilot: {r.get("trustpilot") or "ikke oplyst"}')
    groups = {}
    for a in ARTICLES:
        if a["listed"]:
            groups.setdefault(a["category"], []).append(a)
    for cat in sorted(groups):
        lines += ["", f"## {cat}", ""]
        for a in sorted(groups[cat], key=lambda x: x["slug"]):
            lines.append(f"- [{a['h1']}]({page_url(a['slug'])}): {a['description']}")
    lines += ["", "## Om siden", "", f"- [Om pyjamasbukser.dk og metode]({DOMAIN}/om): {SITE['disclosure_short']}"]
    return "\n".join(lines) + "\n"


def artikler_page():
    groups = {}
    for a in ARTICLES:
        if a["listed"]:
            groups.setdefault(a["category"], []).append(a)
    order = SITE.get("category_order", [])
    cats = sorted(groups, key=lambda c: (order.index(c) if c in order else 99, c))
    body = ""
    for c in cats:
        items = sorted(groups[c], key=lambda a: (a.get("order", 999), a["title"]))
        cards = "".join(f'<a class="card" href="{href(a["slug"])}"><span class="card-tag">{esc(c)}</span>'
                        f'<strong>{esc(a.get("card_title") or a["h1"])}</strong><em>{esc(a["description"])}</em></a>'
                        for a in items)
        body += f"<h2>{esc(c)}</h2><div class='cards cards-lg'>{cards}</div>"
    newest = max(a["date_modified"] for a in ARTICLES)
    page = {"slug": "artikler", "layout": "page", "title": "Artikler om pyjamasbukser: guides og sammenligninger",
            "description": "Alle guides om pyjamasbukser: materialer, størrelser, pasform, priser og sammenligninger af brands i Danmark.",
            "h1": "Artikler og guides om pyjamasbukser", "card_title": "Artikler", "category": "Oversigt",
            "intro": "Her finder du alle vores guides. Vi skriver løbende nye, og de gamle bliver opdateret, når priser og udvalg ændrer sig.",
            "date_published": "2026-09-11", "date_modified": newest, "faq": [], "related": [], "body": body,
            "listed": False}
    return page


def htaccess():
    return """# pyjamasbukser.dk - LiteSpeed/Apache (cPanel). GitHub Pages ignorerer filen.
Options -Indexes
DirectoryIndex index.html
ErrorDocument 404 /404.html
RewriteEngine On
RewriteCond %{HTTPS} off [OR]
RewriteCond %{HTTP_HOST} ^www\\. [NC]
RewriteRule ^ https://pyjamasbukser.dk%{REQUEST_URI} [L,R=301]
RewriteCond %{THE_REQUEST} \\s/+(.+?)\\.html[\\s?] [NC]
RewriteRule ^ /%1 [L,R=301]
RewriteCond %{THE_REQUEST} \\s/+index(\\.html)?[\\s?] [NC]
RewriteRule ^ / [L,R=301]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME}.html -f
RewriteRule ^(.+?)/?$ $1.html [L]
<IfModule mod_expires.c>
  ExpiresActive On
  ExpiresByType image/png "access plus 30 days"
  ExpiresByType image/x-icon "access plus 30 days"
  ExpiresByType text/html "access plus 1 hour"
</IfModule>
"""


def page_404():
    return {"slug": "404", "layout": "page", "title": "Siden findes ikke | pyjamasbukser.dk",
            "description": "Siden findes ikke. Gå til forsiden og se vores sammenligning af pyjamasbukser.",
            "h1": "Øv, den side findes ikke", "card_title": "404", "category": "Fejl",
            "date_published": "2026-09-11", "date_modified": "2026-09-11", "faq": [], "related": [],
            "body": '<p>Prøv <a href="/">forsiden</a> med vores sammenligning, eller se <a href="/artikler">alle artikler</a>.</p>{{PRODUCT}}',
            "listed": False}


# ---------------------------------------------------------------- validation
DASHES = re.compile("[\u2013\u2014]")


def validate(name, doc):
    visible = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", doc, flags=re.S)
    if DASHES.search(visible):
        i = DASHES.search(visible).start()
        errors.append(f"{name}: lang tankestreg i synlig tekst: ...{strip_tags(visible[max(0, i - 50):i + 20])}...")
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', doc, re.S):
        try:
            json.loads(m.group(1))
        except json.JSONDecodeError as e:
            errors.append(f"{name}: ugyldig JSON-LD ({e})")
    for m in re.finditer(r'href="/([a-z0-9\-]*)(?:#[^"]*)?"', doc):
        s = m.group(1)
        if s and s not in BY_SLUG and s not in ("artikler",):
            errors.append(f"{name}: død intern link /{s}")
    t = re.search(r"<title>(.*?)</title>", doc).group(1)
    d = re.search(r'<meta name="description" content="(.*?)">', doc).group(1)
    if len(html.unescape(t)) > 70:
        warnings.append(f"{name}: title er {len(html.unescape(t))} tegn (> 70)")
    if not 70 <= len(html.unescape(d)) <= 170:
        warnings.append(f"{name}: meta description er {len(html.unescape(d))} tegn")


# ---------------------------------------------------------------- main
def main():
    pages = {}
    for a in ARTICLES:
        pages[a["slug"]] = render(a)
    extra = [artikler_page(), page_404()]
    for p in extra:
        BY_SLUG.setdefault(p["slug"], p)
    for p in extra:
        pages[p["slug"]] = render(p)
    for name, doc in pages.items():
        validate(name, doc)
    for s in ["index", "om"]:
        if s not in BY_SLUG:
            errors.append(f"mangler påkrævet side: {s}")

    for w in warnings:
        print("ADVARSEL:", w)
    if errors:
        for e in errors:
            print("FEJL:", e)
        sys.exit(1)
    print(f"OK: {len(pages)} sider, {sum(1 for a in ARTICLES if a['listed'])} artikler")
    if CHECK_ONLY:
        return

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    for name, doc in pages.items():
        with open(os.path.join(OUT, f"{name}.html"), "w", encoding="utf-8") as f:
            f.write(doc)
    files = {"sitemap.xml": sitemap(), "robots.txt": robots(), "llms.txt": llms(),
             ".htaccess": htaccess(), "CNAME": "pyjamasbukser.dk\n", ".nojekyll": ""}
    for fn, txt in files.items():
        with open(os.path.join(OUT, fn), "w", encoding="utf-8") as f:
            f.write(txt)
    for fn in os.listdir(ASSETS):
        if fn != "site.css" and not fn.startswith("."):
            shutil.copy(os.path.join(ASSETS, fn), os.path.join(OUT, fn))
    print(f"Skrev {OUT}")


if __name__ == "__main__":
    main()
