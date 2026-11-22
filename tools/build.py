#!/usr/bin/env python3
"""Tuk Or Walk — static site builder (no dependencies, Python 3.8+).

Run from anywhere:   python3 tools/build.py
Reads  : data/trips.json, data/galleries.json, data/site.json
Updates: home "Recent trips", trips archive, gallery archive, country tabs + counts,
         countries page stats, JSON-LD lists, sitemap.xml (+images), llms.txt, humans.txt,
         language switcher on every page, Maps profile link, CSP header.
It is idempotent: running it twice gives the same result. Existing trip/gallery pages are never rewritten.
"""
import json, re, os, sys, math, html, datetime, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
TODAY = datetime.date.today().isoformat()
SITE = json.load(open('data/site.json', encoding='utf-8'))
TRIPS = json.load(open('data/trips.json', encoding='utf-8'))
GALS = json.load(open('data/galleries.json', encoding='utf-8'))
DOM = SITE['domain']
esc = lambda s: html.escape(s, quote=True)
def rd(p): return open(p, encoding='utf-8').read()
def wr(p, s):
    open(p, 'w', encoding='utf-8', newline='\n').write(s)

live_trips = sorted([t for t in TRIPS if t['status'] == 'live'], key=lambda t: t['date'], reverse=True)
soon_trips = [t for t in TRIPS if t['status'] != 'live']
live_gals = sorted([g for g in GALS if g['status'] == 'live'], key=lambda g: g['date'], reverse=True)
soon_gals = [g for g in GALS if g['status'] != 'live']
trips_ordered = live_trips + soon_trips
gals_ordered = live_gals + soon_gals

# ---------------------------------------------------------------- markers
def put(h, name, inner, open_re=None, close_re=None):
    """Replace content between <!--BUILD:name--> ... <!--/BUILD:name-->. First run: create markers."""
    a, b = '<!--BUILD:%s-->' % name, '<!--/BUILD:%s-->' % name
    if a in h:
        i, j = h.index(a) + len(a), h.index(b)
        return h[:i] + '\n' + inner + '\n' + h[j:]
    m = re.search(open_re, h, re.S)
    if not m: raise SystemExit('anchor not found for ' + name)
    start = m.end()
    c = re.search(close_re, h[start:], re.S)
    if not c: raise SystemExit('close anchor not found for ' + name)
    end = start + c.start()
    end = h.rfind('</div>', start, end)       # keep the container's own closing tag
    return h[:start] + '\n' + a + '\n' + inner + '\n' + b + '\n' + h[end:]

def tab_html(label, items, kind):
    out = ['<button class="country-tab active" type="button" data-country="all" aria-pressed="true">\n          %s <span class="ct-count" id="countAll" data-c="all">%d</span>\n        </button>' % (label, len(items))]
    for c in SITE['countries']:
        n = sum(1 for i in items if i['country'] == c['slug'])
        if n:
            out.append('<button class="country-tab" type="button" data-country="%s" aria-pressed="false">\n          <span class="flag" aria-hidden="true">%s</span> %s <span class="ct-count" data-c="%s">%d</span>\n        </button>' % (c['slug'], c['flag'], c['name'], c['slug'], n))
    return '\n        '.join(out)

def trip_card(t):
    rel = t['url'][len('trips/'):] if t['url'] else ''
    inner = ('<span class="trip-image-wrap">\n            <span class="trip-card-kicker">%s %s%s</span>\n'
             '            <img src="%s" alt="%s" width="900" height="600" loading="lazy" decoding="async">\n'
             '            <span class="trip-card-label">%s</span>\n          </span>\n'
             '          <span class="trip-body">\n            <span class="trip-desc">%s</span>\n'
             '            <span class="trip-meta-line">%s</span>\n          </span>') % (
        t['flag'], t['countryName'], ('' if t['status'] == 'live' else ' · Coming soon'), t['image'], esc(t['alt']),
        esc(t['label']), esc(t['desc']), ''.join('<span>%s</span>' % s for s in t['stats']))
    attrs = 'data-country="%s" data-city="%s" data-city-label="%s"' % (t['country'], t['city'], esc(t['cityLabel']))
    if t['status'] == 'live':
        return '<a class="trip-card" href="%s"\n           %s\n           aria-label="Read the %s guide, %s, %s">\n          %s\n        </a>' % (rel, attrs, esc(t['label']), esc(t['cityLabel']), t['countryName'], inner)
    return '<div class="trip-card soon"\n             %s\n             aria-label="%s, coming soon">\n          %s\n        </div>' % (attrs, esc(t['label']), inner)

def gal_card(g):
    cname = next(c['name'] for c in SITE['countries'] if c['slug'] == g['country'])
    inner = ('<span class="trip-image-wrap">\n            <span class="trip-card-kicker">%s %s%s</span>\n'
             '            <img src="%s" alt="%s" width="900" height="600" loading="lazy" decoding="async">\n'
             '            <span class="trip-card-label">%s</span>\n          </span>\n'
             '          <span class="trip-body">\n            <span class="trip-desc">%s</span>\n'
             '            <span class="trip-meta-line">%s</span>\n          </span>') % (
        g['flag'], cname, ('' if g['status'] == 'live' else ' · Coming soon'), g['image'], esc(g['alt']),
        esc(g['label']).replace('&amp;amp;', '&amp;'), esc(g['desc']), ''.join('<span>%s</span>' % s for s in g['stats']))
    href = g['url'][len('gallery/'):] if g['status'] == 'live' else '../countries/index.html?country=' + g['country']
    lab = ('Open the %s photo gallery' % g['label']) if g['status'] == 'live' else ('%s photo gallery, coming soon' % cname)
    return '<a class="trip-card" href="%s"\n           data-country="%s" data-city="%s" data-city-label="%s"\n           aria-label="%s">\n          %s\n        </a>' % (
        href, g['country'], g['city'], esc(g['cityLabel']), esc(lab), inner)

def home_card(t):
    if t['status'] == 'live':
        href = t['url']; kick = '%s %s · %s' % (t['flag'], t['countryName'], t['cityLabel'])
        meta = t.get('home', ['', '', t['cityLabel']]); title = t.get('homeTitle', t['label']); read = 'Read trip →'
    else:
        href = 'trips/index.html?country=' + t['country']; kick = '%s %s · %s' % (t['flag'], t['countryName'], t['cityLabel'])
        meta = ['Coming soon', t['stats'][1].replace('<strong>', '').replace('</strong>', ''), t['cityLabel']]; title = t['label']; read = 'See country →'
    return ('<a href="%s" class="trip-card">\n          <figure class="trip-media">\n'
            '            <img src="%s" alt="%s" width="800" height="500" loading="lazy" decoding="async">\n'
            '            <span class="trip-country">%s</span>\n            <div class="trip-days">\n'
            '              <span>%s</span>\n              <span class="ghost">%s</span>\n'
            '              <span class="maps"><span aria-hidden="true">📍</span> <b>%s</b></span>\n            </div>\n          </figure>\n'
            '          <div class="trip-body">\n            <h4>%s</h4>\n            <p>%s</p>\n'
            '            <div class="trip-meta">\n              <span class="trip-read">%s</span>\n            </div>\n          </div>\n        </a>') % (
        href, t['image'], esc(t['alt']), kick, esc(meta[0]), esc(meta[1]), esc(meta[2]), esc(title), esc(t['desc']), read)

GENERIC_COUNT_JS = re.compile(r"document\.getElementById\('countAll'\)\.textContent = countCountry\('all'\);.*?getElementById\('countIndia'\)\.textContent = countCountry\('india'\);", re.S)
GENERIC_COUNT_NEW = "document.querySelectorAll('.ct-count[data-c]').forEach(function(el){ el.textContent = countCountry(el.dataset.c); });"

def jsonld_replace(h, fn):
    m = re.search(r'(<script type="application/ld\+json">)(.*?)(</script>)', h, re.S)
    if not m: return h
    data = json.loads(m.group(2)); fn(data)
    return h[:m.start(2)] + json.dumps(data, ensure_ascii=False) + h[m.end(2):]

def build_trips_page():
    p = 'trips/index.html'; h = rd(p)
    h = put(h, 'trip-cards', '\n\n        '.join(trip_card(t) for t in trips_ordered),
            r'<div class="trip-grid fade-in" id="tripGrid">', r'<!-- FAQ moved above credit line -->')
    h = put(h, 'tabs', tab_html('All trips', TRIPS, 'trip'), r'<div class="country-tabs fade-in"[^>]*>', r'<div class="result-line')
    h = GENERIC_COUNT_JS.sub(GENERIC_COUNT_NEW, h)
    n, nl, ns = len(TRIPS), len(live_trips), len(soon_trips)
    h = re.sub(r'(id="resultCount"[^>]*>)[^<]*', r'\g<1>Showing %d trips' % n, h)
    h = re.sub(r'(<span class="rl-hint">)[^<]*', r'\g<1>%d guides live · %d coming soon' % (nl, ns), h)
    pages = max(1, math.ceil(n / SITE['perPage']))
    h = re.sub(r'(id="pageInfo">)[^<]*', r'\g<1>Page 1 of %d · %d trips' % (pages, n), h)
    def jl(d):
        for node in d['@graph']:
            ty = node.get('@type'); ty = ty if isinstance(ty, list) else [ty]
            if 'CollectionPage' in ty:
                node['mainEntity'] = {"@type": "ItemList", "name": "Walking trip guides", "numberOfItems": nl,
                    "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": DOM + '/' + t['url'], "name": t['label']} for i, t in enumerate(live_trips)]}
                node['dateModified'] = TODAY
    h = jsonld_replace(h, jl)
    wr(p, h)

def build_gallery_page():
    p = 'gallery/index.html'; h = rd(p)
    h = put(h, 'gallery-cards', '\n\n        '.join(gal_card(g) for g in gals_ordered),
            r'<div class="trip-grid fade-in" id="tripGrid">', r'<!-- =+\s*\n\s*📝 CREDIT LINE')
    h = put(h, 'tabs', tab_html('All places', GALS, 'gal'), r'<div class="country-tabs fade-in"[^>]*>', r'<div class="result-line')
    h = GENERIC_COUNT_JS.sub(GENERIC_COUNT_NEW, h)
    n, nl, ns = len(GALS), len(live_gals), len(soon_gals)
    photos = sum(g.get('photos', 0) for g in live_gals)
    h = re.sub(r'(id="resultCount"[^>]*>)[^<]*', r'\g<1>Showing %d galleries' % n, h)
    h = re.sub(r'(<span class="rl-hint">)[^<]*', r'\g<1>%d galleries live · %d coming soon' % (nl, ns), h)
    pages = max(1, math.ceil(n / SITE['perPage']))
    h = re.sub(r'(id="pageInfo">)[^<]*', r'\g<1>Page 1 of %d · %d galleries' % (pages, n), h)
    def jl(d):
        for node in d['@graph']:
            ty = node.get('@type'); ty = ty if isinstance(ty, list) else [ty]
            if 'ImageGallery' in ty and node.get('mainEntity'):
                node['mainEntity'] = {"@type": "ItemList", "name": "Photo galleries", "numberOfItems": nl,
                    "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": {"@type": "ImageGallery", "name": g['label'], "url": DOM + '/' + g['url'],
                        "numberOfItems": g.get('photos', 0), "image": g['image']}} for i, g in enumerate(live_gals)]}
                node['dateModified'] = TODAY
    h = jsonld_replace(h, jl)
    wr(p, h)

def build_home():
    p = 'index.html'; h = rd(p)
    shown = (live_trips + soon_trips)[:SITE['homeRecentMax']]
    h = put(h, 'recent-trips', '\n\n        '.join(home_card(t) for t in shown),
            r'<div class="trips-track" id="tripsTrack">', r'<div class="trips-controls"')
    h = re.sub(r'(<span class="count">)\d+ featured', r'\g<1>5 featured', h)
    wr(p, h)

def build_countries():
    p = 'countries/index.html'; h = rd(p)
    for c in SITE['countries']:
        nt = sum(1 for t in live_trips if t['country'] == c['slug'])
        ng = sum(1 for g in live_gals if g['country'] == c['slug'])
        if not nt: continue
        stats = '<span class="country-stats"><span><strong>%d</strong> %s live</span><span><strong>%d</strong> %s</span></span>' % (
            nt, 'trip' if nt == 1 else 'trips', ng, 'photo gallery' if ng == 1 else 'photo galleries')
        h = re.sub(r'(data-country="%s"[^>]*>.*?)<span class="country-stats">.*?</span></span>' % c['slug'], lambda m: m.group(1) + stats, h, count=1, flags=re.S)
    nc = len(SITE['countries']); live_c = len({t['country'] for t in live_trips})
    h = re.sub(r'(id="countriesCount">)[^<]*', r'\g<1>%d countries · %d live, %d coming soon' % (nc, live_c, nc - live_c), h)
    wr(p, h)


def home_head():
    p = 'index.html'; h = rd(p)
    title = re.search(r'<title>(.*?)</title>', h, re.S).group(1)
    desc = re.search(r'name="description" content="(.*?)"', h).group(1)
    img = re.search(r'<header class="hero".*?<img src="([^"]+)" alt="([^"]*)"', h, re.S)
    imgsrc, imgalt = img.group(1), img.group(2)
    faqs = [(re.sub(r'<[^>]+>', '', q), re.sub(r'<[^>]+>', '', a)) for q, a in re.findall(r'<details[^>]*><summary>(.*?)</summary><p>(.*?)</p></details>', h, re.S)]
    graph = [
      {"@type": "Organization", "@id": DOM + "/#org", "name": SITE['name'], "url": DOM + "/", "email": SITE['email'],
       "description": "A one-person, sponsor-free budget travel site with free solo walking guides for Asia: real prices, real walking times and honest notes.",
       "sameAs": [SITE['mapsProfile']], "knowsAbout": ["Budget travel", "Solo travel", "Walking routes", "Thailand travel", "Sri Lanka travel", "Laos travel", "India travel"],
       "contactPoint": {"@type": "ContactPoint", "contactType": "customer support", "email": SITE['email'], "availableLanguage": "English"}},
      {"@type": "WebSite", "@id": DOM + "/#website", "url": DOM + "/", "name": SITE['name'], "description": "Free solo budget travel guides, walked on foot, with real costs.", "publisher": {"@id": DOM + "/#org"}, "inLanguage": "en"},
      {"@type": "WebPage", "@id": DOM + "/#webpage", "url": DOM + "/", "name": title, "description": desc, "isPartOf": {"@id": DOM + "/#website"}, "about": {"@id": DOM + "/#org"},
       "primaryImageOfPage": {"@type": "ImageObject", "url": imgsrc, "caption": imgalt}, "dateModified": TODAY, "inLanguage": "en", "audience": {"@type": "Audience", "audienceType": "Solo budget travelers"}},
      {"@type": "ItemList", "name": "Latest trips", "numberOfItems": len(live_trips),
       "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": DOM + "/" + t['url'], "name": t['label']} for i, t in enumerate(live_trips)]},
      {"@type": "ItemList", "name": "Countries covered by Tuk Or Walk",
       "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": c['name'], "url": DOM + "/countries/index.html?country=" + c['slug']} for i, c in enumerate(SITE['countries'])]},
    ]
    if faqs: graph.append({"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]})
    block = """<meta name="keywords" content="budget travel, solo budget travel, free travel guides, walking guides, backpacking Asia, cheap travel, real travel costs, Thailand budget travel, Sri Lanka budget travel, Laos budget travel, India budget travel, Bangkok on foot, tuk or walk">
  <link rel="alternate" hreflang="en" href="%(d)s/">
  <link rel="alternate" hreflang="x-default" href="%(d)s/">
  <link rel="preload" as="image" href="%(i)s" fetchpriority="high">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Tuk Or Walk">
  <meta property="og:locale" content="en_US">
  <meta property="og:title" content="%(t)s">
  <meta property="og:description" content="%(s)s">
  <meta property="og:url" content="%(d)s/">
  <meta property="og:image" content="%(i)s">
  <meta property="og:image:alt" content="%(a)s">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="%(t)s">
  <meta name="twitter:description" content="%(s)s">
  <meta name="twitter:image" content="%(i)s">
  <meta name="twitter:image:alt" content="%(a)s">
  <link rel="manifest" href="/manifest.webmanifest">
  <link rel="sitemap" type="application/xml" href="/sitemap.xml">
  <script type="application/ld+json">%(j)s</script>""" % dict(d=DOM, i=imgsrc, a=esc(imgalt), t=title, s=desc, j=json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False))
    a, b = '<!--BUILD:seo-head-->', '<!--/BUILD:seo-head-->'
    if a in h:
        i, j = h.index(a) + len(a), h.index(b); h = h[:i] + '\n  ' + block + '\n  ' + h[j:]
    else:
        h = h.replace('<link rel="canonical" href="https://tukorwalk.com/">', '<link rel="canonical" href="https://tukorwalk.com/">\n  ' + a + '\n  ' + block + '\n  ' + b, 1)
    wr(p, h)

# ---------------------------------------------------------------- site-wide
LANG_ITEMS = [('English','en'),('中文','zh-CN'),('हिन्दी','hi'),('Español','es'),('Français','fr'),('العربية','ar'),('Português','pt'),('Русский','ru'),('Deutsch','de'),('日本語','ja'),('Türkçe','tr'),('한국어','ko'),('தமிழ்','ta'),('Italiano','it'),('Polski','pl'),('Nederlands','nl'),('සිංහල','si'),('Svenska','sv'),('Čeština','cs'),('Dansk','da'),('Eesti','et')]
def lang_links(): return ''.join('<a href="#lang-%s"%s>%s</a>' % (c, ' class="active"' if c == 'en' else '', n) for n, c in LANG_ITEMS)
LANG_TOP = ('<div class="lang-selector-wrap notranslate" translate="no"><button class="lang-btn" id="langBtn" type="button" aria-label="Select language" aria-haspopup="true" aria-expanded="false" aria-controls="langDropdown">🌐 <span>EN</span></button>'
            '<div class="lang-dropdown" id="langDropdown">' + lang_links() + '</div></div>')
LANG_BOTTOM = '<div class="bottom-languages notranslate" translate="no"><span class="lang-label">Language</span>' + lang_links() + '</div>'

def all_pages():
    out = []
    for dp, dn, fn in os.walk('.'):
        dn[:] = [d for d in dn if d not in ('.git', 'node_modules', 'tools', 'data', 'assets')]
        for f in fn:
            if f.endswith('.html'): out.append(os.path.join(dp, f)[2:])
    return sorted(out)

def depth_prefix(path):
    d = path.count('/')
    return '../' * d if d else ''

def sitewide(path):
    h = rd(path); o = h
    # 1. Maps profile link (both old short links -> the one profile)
    for old in ('https://maps.app.goo.gl/8AdPkKa7Vuog1gF4A?g_st=aw', 'https://maps.app.goo.gl/8AdPkKa7Vuog1gF4A', 'https://maps.app.goo.gl/SoAGrskscJ8Nycmn6'):
        h = h.replace(old, SITE['mapsProfile'])
    # 1b. clamp over-deep relative prefixes (e.g. ../../../../../ on a 4-deep page) to the real depth
    dd = path.count('/')
    def _clamp(m):
        n = len(m.group(2)) // 3
        return m.group(1) + '../' * min(n, dd) if n > dd else m.group(0)
    h = re.sub(r'((?:href|src|action)=")((?:\.\./)+)', _clamp, h)
    # 1c. exactly one <h1> per URL: later in-page 'stop' headings become <h2 class="stop-title"> (same look)
    if len(re.findall(r'<h1[\s>]', h)) > 1:
        first = h.index('<h1')
        head, tail = h[:first + 3], h[first + 3:]
        tail = re.sub(r'<h1(\s[^>]*)?>(.*?)</h1>', lambda m: '<h2%s>%s</h2>' % ((m.group(1) or '').replace('class="', 'class="stop-title ', 1) if 'class="' in (m.group(1) or '') else ' class="stop-title"' + (m.group(1) or ''), m.group(2)), tail, flags=re.S)
        h = head + tail
        h = h.replace('.hero h1{', '.hero h1,.hero h2.stop-title{').replace('.hero h1 em{', '.hero h1 em,.hero h2.stop-title em{')
    # 2. language UI present on every page
    if 'id="langBtn"' not in h:
        h = re.sub(r'(<button class="nav-toggle")', lambda m: LANG_TOP + m.group(1), h, count=1)
    if 'class="bottom-languages' not in h:
        for anchor in ('<div class="subscribe-footer-wrap"', '<footer class="site-footer"', '</body>'):
            if anchor in h:
                h = h.replace(anchor, LANG_BOTTOM + '\n' + anchor, 1); break
    pre = depth_prefix(path)
    if 'assets/css/site.css' not in h:
        h = h.replace('</head>', '  <link rel="stylesheet" href="%sassets/css/site.css">\n</head>' % pre, 1)
    if 'assets/js/lang.js' not in h:
        h = h.replace('</body>', '<script src="%sassets/js/lang.js" defer></script>\n</body>' % pre, 1)
    # 3. a11y/perf niceties
    h = h.replace('<a href="https://maps.app.goo.gl/77Y5Mqe3ptirzjRb6" target="_blank">', '<a href="https://maps.app.goo.gl/77Y5Mqe3ptirzjRb6" target="_blank" rel="noopener">')
    if h != o: wr(path, h)


SEO = json.load(open('data/seo.json', encoding='utf-8')) if os.path.exists('data/seo.json') else {}
CRUMB_NAMES = {'trips': 'Trips', 'gallery': 'Gallery', 'countries': 'Countries'}
DEFAULT_IMG = None

def seo_pass(path):
    global DEFAULT_IMG
    h = rd(path); o = h
    url = path[:-10] if path.endswith('index.html') else path
    canon = DOM + '/' + url
    # overrides
    ov = SEO.get(path, {})
    if 'title' in ov:
        h = re.sub(r'<title>.*?</title>', '<title>%s</title>' % esc(ov['title']), h, count=1, flags=re.S)
    if 'description' in ov:
        h = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + esc(ov['description']), h, count=1)
    title = html.unescape(re.search(r'<title>(.*?)</title>', h, re.S).group(1))
    desc = html.unescape(re.search(r'name="description" content="(.*?)"', h).group(1))
    # keep og/twitter in step with title/description
    for pr in ('og:title', 'twitter:title'):
        h = re.sub(r'(<meta (?:property|name)="%s" content=")[^"]*' % pr, lambda m: m.group(1) + esc(title), h)
    for pr in ('og:description', 'twitter:description'):
        h = re.sub(r'(<meta (?:property|name)="%s" content=")[^"]*' % pr, lambda m: m.group(1) + esc(desc), h)
    add = []
    if 'hreflang="en"' not in h and '<link rel="canonical"' in h:
        add.append('<link rel="alternate" hreflang="en" href="%s">\n  <link rel="alternate" hreflang="x-default" href="%s">' % (canon, canon))
    if 'rel="manifest"' not in h: add.append('<link rel="manifest" href="/manifest.webmanifest">')
    if 'property="og:title"' not in h:
        img = live_trips[-1]['image']; ialt = live_trips[-1]['alt']
        add.append('\n  '.join(['<meta property="og:type" content="website">', '<meta property="og:site_name" content="Tuk Or Walk">', '<meta property="og:locale" content="en_US">',
            '<meta property="og:title" content="%s">' % esc(title), '<meta property="og:description" content="%s">' % esc(desc), '<meta property="og:url" content="%s">' % canon,
            '<meta property="og:image" content="%s">' % img, '<meta property="og:image:alt" content="%s">' % esc(ialt),
            '<meta name="twitter:card" content="summary_large_image">', '<meta name="twitter:title" content="%s">' % esc(title), '<meta name="twitter:description" content="%s">' % esc(desc),
            '<meta name="twitter:image" content="%s">' % img, '<meta name="twitter:image:alt" content="%s">' % esc(ialt)]))
    elif 'name="twitter:card"' not in h:
        add.append('<meta name="twitter:card" content="summary_large_image">')
    # structured data: breadcrumb + page node when the page has none
    segs = [x for x in url.split('/') if x]
    crumbs = [('Home', DOM + '/')]
    top = segs[0] if segs else ''
    if top in CRUMB_NAMES and len(segs) > 1: crumbs.append((CRUMB_NAMES[top], DOM + '/' + top + '/'))
    leaf = re.sub(r'\s*[·|]\s*Tuk Or Walk\s*$', '', title)
    if segs: crumbs.append((CRUMB_NAMES.get(top, leaf) if len(segs) == 1 and top in CRUMB_NAMES else leaf, canon))
    if 'application/ld+json' not in h and path != '404.html':
        ptype = 'AboutPage' if path == 'about.html' else 'ContactPage' if path == 'contact.html' else 'CollectionPage' if path.endswith('index.html') else 'WebPage'
        g = [{"@type": "Organization", "@id": DOM + "/#org", "name": SITE['name'], "url": DOM + "/", "email": SITE['email'], "sameAs": [SITE['mapsProfile']]},
             {"@type": "WebSite", "@id": DOM + "/#website", "url": DOM + "/", "name": SITE['name'], "publisher": {"@id": DOM + "/#org"}, "inLanguage": "en"},
             {"@type": ptype, "@id": canon + "#page", "url": canon, "name": title, "description": desc, "isPartOf": {"@id": DOM + "/#website"}, "about": {"@id": DOM + "/#org"}, "inLanguage": "en", "dateModified": TODAY},
             {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(crumbs)]}]
        add.append('<script type="application/ld+json">%s</script>' % json.dumps({"@context": "https://schema.org", "@graph": g}, ensure_ascii=False))
    if add and '</head>' in h:
        h = h.replace('</head>', '  ' + '\n  '.join(add) + '\n</head>', 1)
    # visible breadcrumb navigation (not on home / 404)
    if segs and path != '404.html' and 'class="crumbs"' not in h:
        lis = ''.join('<li><a href="%s">%s</a></li>' % (depth_prefix(path) + ('' if u == DOM + '/' else u[len(DOM) + 1:]) if u != DOM + '/' else depth_prefix(path) + 'index.html', esc(n)) for n, u in crumbs[:-1])
        lis += '<li><span aria-current="page">%s</span></li>' % esc(crumbs[-1][0])
        nav = '<nav class="crumbs" aria-label="Breadcrumb"><ol>%s</ol></nav>' % lis
        m = re.search(r'<main[^>]*>', h)
        if m: h = h[:m.end()] + '\n' + nav + h[m.end():]
    if h != o: wr(path, h)

def sitemap():
    pages = all_pages()
    meta = {}
    for t in TRIPS:
        if t['status'] == 'live': meta[t['url']] = (t['date'], t['image'], t['alt'])
    for g in GALS:
        if g['status'] == 'live': meta[g['url']] = (g['date'], g['image'], g['alt'])
    rows = []
    for p in pages:
        if p == '404.html': continue
        if p.endswith('index.html'):
            url = p[:-10]
        else: url = p
        loc = DOM + '/' + url
        base = url
        lm, img, alt = meta.get(url, (TODAY, None, None))
        if url in ('', 'trips/', 'gallery/', 'countries/'): lm = TODAY; freq, pr = 'weekly', '1.0' if url == '' else '0.9'
        elif url.startswith('trips/') or url.startswith('gallery/'): freq, pr = 'monthly', '0.8' if url.count('/') <= 5 else '0.7'
        else: freq, pr = 'yearly', '0.5' if url in ('about.html', 'contact.html') else '0.4'
        if url == 'about.html': freq = 'monthly'
        x = '  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n    <changefreq>%s</changefreq>\n    <priority>%s</priority>\n' % (loc, lm, freq, pr)
        if img: x += '    <image:image>\n      <image:loc>%s</image:loc>\n      <image:caption>%s</image:caption>\n    </image:image>\n' % (esc(img), esc(alt))
        rows.append((pr, loc, x + '  </url>\n'))
    rows.sort(key=lambda r: (-float(r[0]), r[1]))
    wr('sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n' + ''.join(r[2] for r in rows) + '</urlset>\n')
    return len(rows)

def llms():
    L = ['# Tuk Or Walk', '',
         '> Tuk Or Walk is a one-person, sponsor-free budget travel site. It publishes free solo walking guides and event guides for Asia (Thailand live; Sri Lanka, Laos and India being written) with real prices in local currency, real walking times, toilets, water, food nearby and honest notes. All routes are walked first-hand and all photos are original.', '',
         '## Trips (newest first)']
    for t in live_trips: L.append('- [%s](%s/%s): %s' % (t['label'], DOM, t['url'], t['desc']))
    L += ['', '## Photo galleries']
    for g in live_gals: L.append('- [%s gallery](%s/%s): %s' % (g['label'], DOM, g['url'], g['desc']))
    L += ['', '## Key pages',
          '- [About](%s/about.html): who runs the site, the promise, how guides are made' % DOM,
          '- [All trips](%s/trips/): every walking route and event guide' % DOM,
          '- [Countries](%s/countries/): Thailand, Sri Lanka, Laos, India' % DOM,
          '- [Gallery](%s/gallery/): original photos from every trip' % DOM,
          '- [Editorial policy](%s/editorial-policy.html): how prices are recorded and corrections handled' % DOM,
          '- [Affiliate disclosure](%s/affiliate-disclosure.html): how the site earns; no sponsored posts' % DOM,
          '- [Copyright](%s/copyright.html) and [Image rights](%s/image-rights.html): reuse and credit rules' % (DOM, DOM),
          '- [Contact](%s/contact.html): %s' % (DOM, SITE['email']), '',
          '## Citing this site', 'Please credit "Tuk Or Walk (tukorwalk.com)" and link to the specific page. Prices are what the author paid on the date shown on each page.', '']
    wr('llms.txt', '\n'.join(L))

def humans():
    h = rd('humans.txt')
    h = re.sub(r'Last update: [\d-]+', 'Last update: ' + TODAY, h)
    for old in ('https://maps.app.goo.gl/SoAGrskscJ8Nycmn6', 'https://maps.app.goo.gl/8AdPkKa7Vuog1gF4A'):
        h = h.replace(old, SITE['mapsProfile'])
    h = re.sub(r'    - Khao San Halloween Event Guide \(Khao San Road, Bangkok\)\n', '', h)
    if 'Google Website Translator' not in h: h = h.replace('Leaflet 1.9.4 (Cloudflare CDN) — Sathon walk map only', 'Leaflet 1.9.4 (Cloudflare CDN) — Sathon walk map only\n    - Google Website Translator — loaded only if a visitor picks a language other than English')
    wr('humans.txt', h)

def headers():
    h = rd('_headers')
    csp = ("Content-Security-Policy: default-src 'self'; "
           "img-src 'self' data: https://pub-073bb9ec0405497288c023970f27deee.r2.dev https://myimgs.org https://tile.openstreetmap.org https://www.gstatic.com https://translate.google.com https://translate.googleapis.com https://www.google.com https://fonts.gstatic.com; "
           "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://translate.google.com https://translate.googleapis.com https://www.gstatic.com; "
           "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://translate.googleapis.com https://www.gstatic.com; "
           "font-src 'self' https://fonts.gstatic.com data:; frame-src https://www.google.com; "
           "connect-src 'self' https://translate.googleapis.com https://translate.google.com; base-uri 'self'; form-action 'self' mailto:; frame-ancestors 'self'")
    h = re.sub(r'  Content-Security-Policy:[^\n]*', '  ' + csp, h)
    h = re.sub(r'\n+# ---------- (?:Static assets|Shared CSS/JS).*\Z', '', h, flags=re.S)
    h += '\n\n# ---------- Shared CSS/JS (same file names are reused, so revalidate daily) ----------\n/assets/*\n  Cache-Control: public, max-age=86400, stale-while-revalidate=604800\n'
    wr('_headers', h)

if __name__ == '__main__':
    build_trips_page(); build_gallery_page(); build_home(); home_head(); build_countries()
    for p in all_pages(): sitewide(p); seo_pass(p)
    n = sitemap(); llms(); humans(); headers()
    print('built: %d trips (%d live), %d galleries (%d live), %d sitemap URLs' % (len(TRIPS), len(live_trips), len(GALS), len(live_gals), n))
