#!/usr/bin/env bash
# Build a styled, self-contained .html next to every .md in the repo.
# Re-run any time docs change.  Requires: pandoc.
#
#   ./scripts/build-html.sh
#
# - Self-contained output (--embed-resources): CSS + logo are inlined, so each
#   .html works on its own, even copied off the Pi or opened over the link.
# - Inter-doc links written as *.md are rewritten to *.html so navigation works
#   in the HTML build too.
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root
ROOT="$(pwd)"

command -v pandoc >/dev/null || { echo "pandoc not found. brew install pandoc"; exit 1; }

STYLE="$(mktemp)"
trap 'rm -f "$STYLE"' EXIT
cat > "$STYLE" <<'CSS'
<style>
  :root{
    --bg:#0e1116; --panel:#161b22; --fg:#d7dde4; --muted:#9aa6b2;
    --accent:#3fb6ff; --accent2:#7ee787; --border:#2a313c; --code:#1b2027;
  }
  *{box-sizing:border-box}
  /* override pandoc's default standalone stylesheet (white html bg + body max-width:36em) */
  html{scroll-behavior:smooth; background:var(--bg); color:var(--fg);
       max-width:none; width:auto; margin:0; padding:0}
  body{
    background:var(--bg); color:var(--fg);
    font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    margin:0; padding:0; max-width:none; width:auto;
  }
  .wrap{max-width:860px; margin:0 auto; padding:2.2rem 1.3rem 5rem}
  a{color:var(--accent); text-decoration:none}
  a:visited{color:#c8a6ff}            /* readable lavender on the dark theme */
  a:hover{text-decoration:underline}
  h1,h2,h3,h4{line-height:1.25; font-weight:650; margin:1.8em 0 .6em}
  h1{font-size:2rem; border-bottom:2px solid var(--border); padding-bottom:.3em; margin-top:.2em}
  h2{font-size:1.45rem; border-bottom:1px solid var(--border); padding-bottom:.25em}
  h3{font-size:1.15rem; color:var(--accent2)}
  code{background:var(--code); padding:.15em .4em; border-radius:5px; font-size:.88em;
       font-family:"SF Mono",ui-monospace,Menlo,Consolas,monospace}
  pre{background:var(--code); border:1px solid var(--border); border-radius:9px;
      padding:1rem 1.1rem; overflow-x:auto}
  pre code{background:none; padding:0; font-size:.85rem; line-height:1.55}
  blockquote{margin:1.2em 0; padding:.4em 1.1em; border-left:4px solid var(--accent);
             background:rgba(63,182,255,.07); color:var(--muted); border-radius:0 8px 8px 0}
  blockquote p{margin:.4em 0}
  table{border-collapse:collapse; width:100%; margin:1.3em 0; font-size:.94rem}
  th,td{border:1px solid var(--border); padding:.55em .8em; text-align:left; vertical-align:top}
  th{background:var(--panel)}
  tr:nth-child(even) td{background:rgba(255,255,255,.02)}
  hr{border:none; border-top:1px solid var(--border); margin:2.4em 0}
  img{max-width:100%; height:auto}
  .wrap > p:first-of-type img{display:block; margin:0 auto}
  ul,ol{padding-left:1.4em}
  li{margin:.25em 0}
  .topbar{position:sticky; top:0; z-index:9; background:rgba(14,17,22,.92);
          backdrop-filter:saturate(140%) blur(8px); border-bottom:1px solid var(--border)}
  .topbar .wrap{padding:.6rem 1.3rem; display:flex; gap:1rem; align-items:center}
  .topbar a, .topbar a:visited{color:var(--muted); font-size:.9rem}
  .topbar .brand{color:var(--fg); font-weight:700; letter-spacing:.04em}
  .topbar .sp{flex:1}
  /* logo sits on a light chip so the black vinyl artwork shows on the dark theme */
  div[align="center"]{text-align:center}
  div[align="center"] img{background:#eef2f7; padding:14px 18px; border-radius:14px;
    box-shadow:0 2px 12px rgba(0,0,0,.45); margin:.4rem auto}
</style>
CSS

# Nav template with two path placeholders, substituted per page:
#   {ROOT} → prefix to reach root-level files (index/README)
#   {DOCS} → prefix to reach docs/* files
NAV_TMPL='<div class="topbar"><div class="wrap"><a class="brand" href="{ROOT}index.html">VA3YMX&nbsp;SDR</a><a href="{ROOT}README.html">⌂ README</a><span class="sp"></span><a href="{DOCS}01-hardware-and-rf.html">1 HW</a><a href="{DOCS}02-os-base-setup.html">2 OS</a><a href="{DOCS}03-rtl-sdr-v4-drivers.html">3 Drivers</a><a href="{DOCS}04-adsb-feeder.html">4 ADS-B</a><a href="{DOCS}05-openwebrx-discone.html">5 WebSDR</a><a href="{DOCS}06-decoders-and-trunking.html">6 Decoders</a><a href="{DOCS}07-operations.html">7 Ops</a><a href="{DOCS}08-migration-from-adsb-box.html">8 Migrate</a><a href="{DOCS}09-integration-and-dashboards.html">9 Dash</a><a href="{DOCS}10-system-diagram.html">10 Diagram</a><a href="{DOCS}11-https-caddy.html">11 HTTPS</a><a href="{DOCS}12-receiver-evolution.html">12 Receivers</a></div></div>'

count=0
while IFS= read -r -d '' md; do
  html="${md%.md}.html"
  title="$(grep -m1 '^# ' "$md" | sed 's/^# *//' || true)"
  [ -z "$title" ] && title="VA3YMX SDR"

  # Root-level page (index.html / README.html) vs a docs/* page.
  # find yields absolute paths, so compare the file's dir to repo root.
  if [ "$(cd "$(dirname "$md")" && pwd)" = "$ROOT" ]; then
    nav="${NAV_TMPL//\{ROOT\}/}"; nav="${nav//\{DOCS\}/docs/}"
  else
    nav="${NAV_TMPL//\{ROOT\}/../}"; nav="${nav//\{DOCS\}/}"
  fi

  pandoc "$md" -f gfm -t html5 \
    --embed-resources --standalone \
    --resource-path "$(dirname "$md"):$ROOT" \
    --metadata title="$title — VA3YMX SDR" \
    --include-in-header "$STYLE" \
    --include-before-body <(echo "$nav"; echo '<div class="wrap">') \
    --include-after-body <(echo '</div>') \
    -o "$html"

  # rewrite intra-repo .md links to .html
  perl -0pi -e 's/href="([^":]*?)\.md(#[^"]*)?"/href="$1.html$2"/g' "$html"

  echo "  ✓ $(basename "$md") → $(basename "$html")"
  count=$((count+1))
done < <(find "$ROOT" -name '*.md' -not -path '*/.git/*' \
          -not -name 'CLAUDE.md' -not -name 'MEMORY.md' -print0)

echo "Built $count HTML file(s)."
