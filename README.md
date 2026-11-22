# Tuk Or Walk — static site (tukorwalk.com)

Plain HTML/CSS/JS, hosted on Cloudflare Pages from GitHub. Photos live on your R2 bucket.
Cards, counts, sitemap, llms.txt and the SEO lists are generated from two small data files, so a new trip
never means editing the older pages.

## Folder map

    index.html, about.html, contact.html, privacy.html ...   root pages
    trips/                      archive page + one folder per trip   trips/<country>/<city>/<slug>/index.html
    gallery/                    archive page + one folder per gallery gallery/<country>/<city>/<slug>/index.html
    countries/                  countries page
    data/trips.json             one entry per trip   (feeds home "Recent trips", trips archive, sitemap, llms.txt)
    data/galleries.json         one entry per gallery (feeds gallery archive, counts, sitemap, llms.txt)
    data/site.json              domain, Maps profile link, country list, page sizes
    data/seo.json               optional per-page title / meta description overrides
    tools/build.py              the generator (Python 3 only, no packages)
    tools/audit.py              checks every internal link, duplicate ids, JSON-LD, titles, H1, canonical
    assets/js/lang.js           language switcher (21 languages)
    assets/css/site.css         language selector + breadcrumb styles
    _headers _redirects robots.txt sitemap.xml llms.txt humans.txt manifest.webmanifest

## Add a new trip (about 5 minutes)

1. Copy an existing trip folder (e.g. trips/thailand/bangkok/vijit-chao-phraya-2026/) to the new path and edit the text,
   canonical URL, JSON-LD and images. Same for the gallery folder if the trip has one.
2. Add one object to data/trips.json (and data/galleries.json if there is a gallery):

       {"id":"my-trip","status":"live","country":"thailand","countryName":"Thailand","flag":"🇹🇭",
        "city":"chiang-mai","cityLabel":"Chiang Mai","date":"2026-12-05",
        "url":"trips/thailand/chiang-mai/my-trip/","label":"My trip title",
        "desc":"One or two sentences for the card.",
        "image":"https://pub-....r2.dev/.../cover.webp","alt":"Describe the photo",
        "stats":["<strong>Free</strong> entry","<strong>2</strong> hrs","<strong>Chiang Mai</strong>"],
        "home":["1 day","Free show","Chiang Mai"],"homeTitle":"Title shown on the home card",
        "gallery":"gallery/thailand/chiang-mai/my-trip/"}

   Newest `date` shows first. Use "status":"soon" for a coming-soon card (url can be empty).
   A new country: add it to data/site.json "countries" and its tab appears by itself.
3. Run `python3 tools/build.py` then `python3 tools/audit.py` (both optional on Cloudflare, see below).
4. Commit and push. Cloudflare publishes it.

What updates automatically: home Recent trips, trips archive cards and counts, gallery archive cards and counts,
country tabs, countries page numbers, JSON-LD lists, sitemap.xml (+ cover images), llms.txt, last-update date,
breadcrumbs and the language switcher on every page. Older trip pages are never rewritten.
What stays hand-written: the FAQ sentences on archive pages (e.g. "Five Thailand guides are live").

## Cloudflare Pages settings

- Framework preset: None
- Build command: `python3 tools/build.py`  (or leave empty — the committed files are already built)
- Build output directory: `/`  (the repo root)

## Language switcher

English is the default and is what Google indexes. Picking another language loads Google Website Translator and
translates the page in the browser. The choice is kept in sessionStorage plus a session cookie, so it follows the visitor
to every page until the browser session ends. Nothing is loaded for English.

## Before you promote the site

- Replace the Stripe TEST donate links (buy.stripe.com/test_...) with live links.
- Photos load from R2 (pub-073bb9ec0405497288c023970f27deee.r2.dev); keep that bucket public.
- The balloon images in the donate modal come from myimgs.org; host them on R2 when you can.
