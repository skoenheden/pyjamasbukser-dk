# pyjamasbukser.dk

SEO/GEO-side der sammenligner pyjamasbukser og sender trafik videre til Boom Butiks Bomuldsbukser
(boombutik.dk/products/bomuldsbukser, UTM `utm_source=pyjamasbukser.dk`). Siden er åben om, at Boom Butik står bag.

- `content/site.json` - Boom-fakta (pris, fragt, retur, anmeldelser)
- `content/brands.json` - sammenligningstabellen. Kun verificerede tal, ellers "ikke oplyst"
- `content/articles/*.html` - én fil pr. side, JSON-front-matter i første HTML-kommentar
- `content/backlog.json` - kø af kommende artikler, som den ugentlige opgave tager fra
- `python3 build.py` bygger til `docs/`, `--check` validerer kun

Regler: ingen lange tankestreger i copy, aldrig "fri retur" (skriv "100 dages returret"), ingen opdigtede tal.
Deploy: `docs/` (GitHub Pages med CNAME, eller upload til cPanel-mappen /pyjamasbukser.dk - `.htaccess` er med).
