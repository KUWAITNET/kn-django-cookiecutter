# Static assets

Theme assets only. Editorial photography, PDFs and video are CMS media, never
tracked files in here: a deploy should not carry the client's annual report, and
an editor should be able to replace it without an engineer.

Everything in this directory is served through `ManifestStaticFilesStorage`
(WhiteNoise's compressed variant), so filenames are content-hashed and cached for
a year. Two consequences worth knowing before you add anything:

- `collectstatic` **fails hard** when a stylesheet references a file that does not
  exist — including inside a CSS comment, because the rewriter is a regular
  expression over the whole file. That is a feature: it catches a broken `url()`
  before visitors do. It also means you must never reference a placeholder asset
  you have not actually committed.
- Hand-stamped `?v=` cache-busting query strings are banned. The hash is the
  version.

Filenames are lowercase, hyphenated ASCII, with no spaces and no parentheses.

```
css/main.css     tokens, typography, forms, the few shell components
css/rtl.css      right-to-left overrides; loaded last, and only on RTL pages
js/forms.js      delegated error clearing + CSRF token refresh
img/favicon.svg  placeholder mark — replace with the client's icon
img/             theme images only, each one optimised before it is committed
```

## The default share image

`og:image` has a fallback chain: the object's own share image, then the page's
hero or listing image, then **one site-wide default**. The fallback is never
nothing — a preview card with no image is the single most common reason a shared
link looks broken.

That site-wide default is a per-project asset and is deliberately **not** shipped
by the template, because a generic placeholder is worse than a deliberate one and
because a missing file referenced from `main.css` or a template would break
`collectstatic` under manifest storage.

To wire it up:

1. Export the client's share image at exactly **1200 x 630 px** (1.91:1 — the one
   size that renders correctly on Facebook, LinkedIn, X, WhatsApp and Slack).
2. JPEG or PNG, never SVG (most platforms will not render it), and keep it under
   **300 KB**. It is fetched by the platform rather than by the visitor, but a
   multi-megabyte file still times out some scrapers.
3. Save it as `img/og-default.jpg` in this directory.
4. Resolve it to an absolute URL in `apps.core.context_processors.site_context`
   and expose it as `DEFAULT_OG_IMAGE_URL`; `templates/includes/meta.html` reads
   that variable and emits `og:image` together with the required
   `og:image:width` and `og:image:height`. Without the dimensions the first scrape
   of a new URL often renders no preview at all while the platform fetches the
   image out of band.

The URL must be absolute `https://`, publicly reachable with no authentication,
and return 200 with the correct `Content-Type`. Social scrapers do not follow
redirects reliably and never get past a staging login — so this is verified
**after** the production DNS cutover, on production URLs, in the Facebook Sharing
Debugger and the LinkedIn Post Inspector.

## Webfonts

Self-hosted, `woff2` only, `font-display: swap`, at most two families and four
weights per language, subset with a `unicode-range` per script so an English page
never downloads the Arabic face. Put the files in `fonts/`, declare the
`@font-face` rules at the top of `css/main.css`, point `--font-sans` (and
`--font-arabic`, which `css/rtl.css` uses) at them, and preload only the one or
two faces used above the fold.

A CDN font is not an option here: there is no CDN host in the Content Security
Policy, it adds a third-party connection on the critical path and an extra round
trip on every Arabic page, and it breaks offline development.
