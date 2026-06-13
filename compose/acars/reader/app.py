#!/usr/bin/env python3
"""
VA3YMX ACARS Reader — a clean, readable view of ACARS traffic for multipart messages.

ACARSHub's own UI stores and shows each ACARS *block* as a separate card, which
scatters multi-block exchanges. This page reads ACARSHub's SQLite DB **read-only**
and re-renders it the way it's actually readable:

  • messages are grouped by aircraft into one card (consecutive blocks within a time
    gap), newest aircraft activity first;
  • each card shows the **full decoded text** (ACARSHub's stored libacars decode,
    rendered as readable indented text) at the top;
  • then every **raw block** below it, stacked, each tagged with its label, message
    part (MSN) and block id.

It re-uses ACARSHub's decoding (the `libacars` column) — it doesn't re-decode. The DB
is opened read-only (WAL heap-index), so this never writes. Port 8095.
"""
import glob
import json
import sqlite3
from collections import defaultdict
from flask import Flask, jsonify, request

app = Flask(__name__)

DB_GLOB = "/data/*.db"
LIMIT = 400          # most recent messages to consider (live feed)
SEARCH_LIMIT = 2500  # most recent matches to consider when searching a tail/flight
GROUP_GAP = 90       # secs: gap between same-aircraft blocks that splits a card
MAX_CARDS = 60       # cards returned to the page
SKIP_FALSE = {"err", "crc_ok"}   # noisy boolean keys to drop when false/true-uninteresting


def _db():
    f = sorted(glob.glob(DB_GLOB))
    if not f:
        return None
    return sqlite3.connect(f"file:{f[0]}?mode=ro", uri=True)


def prettify(k):
    return str(k).replace("_", " ").replace("-", " ").strip().capitalize()


def num(v):
    """ACARSHub stores freq/level as TEXT — coerce to float (or None) for the page."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def render_libacars(obj, indent=0):
    """Recursively turn a libacars decode dict into readable indented text."""
    pad = "  " * indent
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in SKIP_FALSE and v in (False, True, None):
                continue
            if isinstance(v, (dict, list)) and v:
                inner = render_libacars(v, indent + 1)
                if inner.strip():
                    out.append(f"{pad}{prettify(k)}:")
                    out.append(inner)
            elif v not in (None, "", {}, []):
                out.append(f"{pad}{prettify(k)}: {v}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                inner = render_libacars(item, indent)
                if inner.strip():
                    out.append(inner)
            elif item not in (None, ""):
                out.append(f"{pad}- {item}")
    else:
        out.append(f"{pad}{obj}")
    return "\n".join(l for l in out if l.strip())


def build_card(key, msgs):
    decoded, blocks = [], []
    for r in msgs:
        blocks.append({
            "t": r["msg_time"], "label": r["label"] or "",
            "msgno": r["msgno"] or "", "block_id": r["block_id"] or "",
            "level": num(r["level"]), "raw": (r["msg_text"] or "").rstrip("\n"),
        })
        if r["libacars"]:
            try:
                txt = render_libacars(json.loads(r["libacars"]))
                if txt.strip():
                    decoded.append({"label": r["label"] or "",
                                    "msgno": r["msgno"] or "", "text": txt})
            except Exception:
                pass
    pick = lambda f: next((m[f] for m in msgs if m[f]), "")
    return {
        "key": key, "flight": pick("flight"), "icao": pick("icao"),
        "freq": num(pick("freq")),
        "t0": min(m["msg_time"] for m in msgs),
        "t1": max(m["msg_time"] for m in msgs),
        "n": len(msgs), "decoded": decoded, "blocks": blocks,
        "level": max([x for x in (num(m["level"]) for m in msgs) if x is not None], default=None),
        "id": max(m["id"] for m in msgs),
    }


@app.get("/api/cards")
def api_cards():
    c = _db()
    if c is None:
        return jsonify(cards=[], latest=0, error="no database yet")
    c.row_factory = sqlite3.Row
    q = (request.args.get("q") or "").strip()
    sel = ("select id,msg_time,tail,flight,icao,fromaddr,freq,label,block_id,msgno,"
           "level,msg_text,libacars from messages ")
    if q:                                  # search tail OR flight, full history (case-insensitive)
        like = "%" + q + "%"
        cur = c.execute(sel + "where tail like ? or flight like ? order by id desc limit ?",
                        (like, like, SEARCH_LIMIT))
    else:                                  # live feed: most recent messages
        cur = c.execute(sel + "order by id desc limit ?", (LIMIT,))
    rows = [dict(r) for r in cur]
    c.close()
    by = defaultdict(list)
    for r in rows:
        by[r["tail"] or r["flight"] or r["icao"] or r["fromaddr"] or "?"].append(r)
    cards = []
    for key, msgs in by.items():
        msgs.sort(key=lambda r: r["msg_time"] or 0)
        cluster = []
        for r in msgs:
            if cluster and (r["msg_time"] - cluster[-1]["msg_time"]) > GROUP_GAP:
                cards.append(build_card(key, cluster))
                cluster = []
            cluster.append(r)
        if cluster:
            cards.append(build_card(key, cluster))
    cards.sort(key=lambda x: x["t1"], reverse=True)
    cards = cards[:MAX_CARDS]
    latest = max((c["id"] for c in cards), default=0)
    return jsonify(cards=cards, latest=latest)


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>VA3YMX · ACARS Reader</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body{background:#0e1116;color:#d7dde4;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0}
 header{position:sticky;top:0;background:#0e1116cc;backdrop-filter:blur(6px);border-bottom:1px solid #2a313c;padding:.5rem .8rem;display:flex;align-items:center;gap:.6rem;z-index:5}
 header b{color:#7ee787} .sub{color:#9aa6b2;font-size:.74rem}
 #q{background:#0e1116;color:#d7dde4;border:1px solid #2a313c;border-radius:6px;padding:.28rem .55rem;font-size:.82rem;width:13rem;max-width:42vw}
 #q:focus{outline:none;border-color:#1f6feb}
 #qclear{background:none;border:0;color:#9aa6b2;cursor:pointer;font-size:1rem;display:none;padding:0 .2rem}
 #wrap{max-width:980px;margin:0 auto;padding:.6rem .8rem 3rem}
 .card{border:1px solid #2a313c;border-radius:10px;background:#161b22;margin:.55rem 0;overflow:hidden}
 .chdr{display:flex;align-items:baseline;gap:.55rem;flex-wrap:wrap;padding:.45rem .6rem;background:#1b222c;border-bottom:1px solid #2a313c}
 .tail{font-weight:700;color:#e6edf3;font-size:.95rem} .flight{color:#58a6ff;font-weight:600}
 .cmeta{margin-left:auto;color:#9aa6b2;font-size:.72rem;white-space:nowrap}
 .decoded{padding:.45rem .6rem;border-bottom:1px solid #22272e;background:#13241a}
 .dec{margin:.15rem 0}
 .dtag{display:inline-block;font-size:.66rem;color:#7ee787;border:1px solid #2ea04366;border-radius:5px;padding:0 .3rem;margin-bottom:.2rem}
 .decoded pre{margin:.1rem 0 .3rem;white-space:pre-wrap;word-break:break-word;font:12.5px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;color:#c9e7d2}
 .blocks{padding:.35rem .6rem}
 .blk{margin:.3rem 0;padding-left:.5rem;border-left:2px solid #30363d}
 .btag{font-size:.68rem;color:#9aa6b2;margin-bottom:.12rem}
 .btag .k{color:#d29922} .btag .b{color:#58a6ff}
 .raw{margin:.05rem 0;white-space:pre-wrap;word-break:break-word;font:12.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:#d7dde4}
 .raw.empty{color:#6e7681;font-style:italic}
 #pill{position:fixed;left:50%;transform:translateX(-50%);bottom:1rem;background:#1f6feb;color:#fff;border:0;border-radius:20px;padding:.4rem .9rem;font-weight:600;cursor:pointer;display:none;box-shadow:0 4px 14px #0008;z-index:9}
 .empty-state{color:#6e7681;text-align:center;padding:2rem}
</style></head><body>
<header><b>ACARS</b> <span class="sub">Reader</span>
 <input id="q" placeholder="search tail / flight…" autocomplete="off" autocapitalize="characters" spellcheck="false">
 <button id="qclear" title="clear">✕</button>
 <span class="sub" id="upd" style="margin-left:auto"></span></header>
<div id="wrap"><div class="empty-state" id="list">loading…</div></div>
<button id="pill" onclick="goTop()">▲ new messages</button>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const hhmmss=t=>new Date(t*1000).toLocaleTimeString('en-CA',{hour12:false});
let renderedLatest=0, pendingNew=0;
function card(c){
 const range = c.t0===c.t1 ? hhmmss(c.t1) : `${hhmmss(c.t0)}–${hhmmss(c.t1)}`;
 const fq=Number(c.freq), lv=Number(c.level);
 const meta = [isFinite(fq)?fq.toFixed(3)+' MHz':'', range, c.n+(c.n>1?' msgs':' msg'),
   (isFinite(lv)?lv.toFixed(1)+' dBFS':'')].filter(Boolean).join(' · ');
 let dec='';
 if(c.decoded.length){
  dec='<div class="decoded">'+c.decoded.map(d=>
    `<div class="dec"><span class="dtag">decoded${d.label?' · '+esc(d.label):''}${d.msgno?' · '+esc(d.msgno):''}</span>`+
    `<pre>${esc(d.text)}</pre></div>`).join('')+'</div>';
 }
 const blks=c.blocks.map(b=>{
  const tag=[b.label?`<span class="k">${esc(b.label)}</span>`:'', b.msgno?`part <span class="k">${esc(b.msgno)}</span>`:'',
    `block <span class="b">${esc(b.block_id||'–')}</span>`, hhmmss(b.t)].filter(Boolean).join(' · ');
  const raw = b.raw ? `<div class="raw">${esc(b.raw)}</div>` : `<div class="raw empty">— (no text / link control)</div>`;
  return `<div class="blk"><div class="btag">${tag}</div>${raw}</div>`;
 }).join('');
 return `<div class="card"><div class="chdr"><span class="tail">${esc(c.key)}</span>`+
  `${c.flight?`<span class="flight">${esc(c.flight)}</span>`:''}`+
  `<span class="cmeta">${esc(meta)}</span></div>${dec}<div class="blocks">${blks}</div></div>`;
}
let query='';
function render(cards){
 $('list').className=''; $('wrap').firstElementChild.id='list';
 const empty = query ? `No ACARS messages for “${esc(query)}”` : 'No ACARS yet — activate ACARS mode in the control panel.';
 $('list').innerHTML = cards.length ? cards.map(c=>{try{return card(c)}catch(e){return ''}}).join('') : `<div class="empty-state">${empty}</div>`;
}
function goTop(){ window.scrollTo({top:0,behavior:'smooth'}); $('pill').style.display='none'; pendingNew=0; pull(true); }
async function pull(force){
 let d; const url='api/cards'+(query?('?q='+encodeURIComponent(query)):'');
 try{ d=await fetch(url).then(r=>r.json()); }catch(e){ return; }
 $('upd').textContent='updated '+new Date().toLocaleTimeString('en-CA',{hour12:false});
 if(!force && d.latest===renderedLatest) return;
 if(force || window.scrollY<60){
  try{ render(d.cards); }catch(e){ $('list').innerHTML='<div class="empty-state">render error: '+esc(e.message)+'</div>'; }
  renderedLatest=d.latest; $('pill').style.display='none'; pendingNew=0;
 } else if(d.latest!==renderedLatest){
  pendingNew++; $('pill').textContent=`▲ ${pendingNew} new`; $('pill').style.display='block';
 }
}
let qtimer;
function applyQuery(v){
 query=v.trim(); $('qclear').style.display=query?'inline':'none';
 renderedLatest=0; pendingNew=0; $('pill').style.display='none';
 window.scrollTo({top:0}); pull(true);
}
$('q').addEventListener('input',e=>{ clearTimeout(qtimer); qtimer=setTimeout(()=>applyQuery(e.target.value),300); });
$('qclear').addEventListener('click',()=>{ $('q').value=''; applyQuery(''); $('q').focus(); });
pull(true); setInterval(pull,9000);
</script></body></html>"""


@app.get("/")
def index():
    return PAGE


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8095)
