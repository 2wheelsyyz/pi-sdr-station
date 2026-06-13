#!/usr/bin/env python3
"""
VA3YMX station control panel — start/stop the SDR service containers, and tune /
stream HD Radio, from a web page. Embedded in Homepage via an iframe widget so the
buttons live right in the portal.

The page is AJAX-driven (it polls /api/state ~5 s and patches the DOM in place) so
the embedded HD Radio **audio player isn't interrupted** by full-page reloads.
Control is via the Docker socket.

The discone dongle has ONE consumer at a time, so the "discone modes" behave like
radio buttons: choosing one stops the others. **HD Radio** (nrsc5 → Icecast) is one
of those modes — the panel launches its container with a chosen frequency/program,
shows now-playing metadata (station / title / artist) parsed from the decoder log,
and embeds an audio player for the Icecast stream (the same one `hdradio.sh` uses).

Config: /app/config.yaml (mounted). Icecast source password: /icecast.env (mounted
read-only from /opt/icecast/.env). Port 8093.
"""
import os
import re
import yaml
import docker
from flask import Flask, jsonify, request

app = Flask(__name__)
dock = docker.from_env()
CFG = yaml.safe_load(open(os.environ.get("CONTROL_CONFIG", "/app/config.yaml")))
MODES = CFG.get("discone_modes", [])
SERVICES = CFG.get("services", [])

NRSC5_IMAGE = "va3ymx/nrsc5:latest"
ICECAST_HOST = "192.168.1.230"
STREAM_URL = "https://hd.example.org/hd.mp3"   # https → embeds clean in the https portal
DISCONE_INDEX = "1"                               # discone dongle = RTL-SDR device index 1


def state(name):
    try:
        return dock.containers.get(name).status        # running / exited / ...
    except docker.errors.NotFound:
        return "absent"
    except Exception:
        return "error"


def act(action, name):
    try:
        getattr(dock.containers.get(name), action)()
    except Exception:
        pass


def icecast_pw():
    try:
        with open("/icecast.env") as f:
            for line in f:
                if line.startswith("ICECAST_SOURCE_PASSWORD="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return os.environ.get("ICECAST_SOURCE_PASSWORD", "")


def hd_meta():
    """Now-playing for the hdradio stream, parsed from the decoder's log."""
    try:
        c = dock.containers.get("hdradio")
    except docker.errors.NotFound:
        return {"live": False}
    except Exception as e:
        return {"live": False, "error": str(e)}
    if c.status != "running":
        return {"live": False}
    try:
        logs = c.logs(tail=200).decode("utf-8", "replace")
    except Exception:
        logs = ""
    station = title = artist = None
    for line in logs.splitlines():                      # latest line of each kind wins
        m = re.search(r"Station name:\s*(.+)", line)
        if m: station = m.group(1).strip()
        m = re.search(r"Title:\s*(.+)", line)
        if m: title = m.group(1).strip()
        m = re.search(r"Artist:\s*(.+)", line)
        if m: artist = m.group(1).strip()
    args = c.attrs.get("Args", [])                      # [freq, program]
    # "Synchronized" scrolls out of the log tail after a few minutes, but live
    # metadata means it's still decoding — treat either as locked.
    synced = ("Synchronized" in logs) or bool(title or artist or station)
    return {"live": True, "synced": synced,
            "station": station, "title": title, "artist": artist,
            "freq": args[0] if len(args) >= 1 else None,
            "program": args[1] if len(args) >= 2 else "0",
            "stream": STREAM_URL}


# ---- actions ----------------------------------------------------------------

def mode_containers(m):                                 # a mode = its container + helpers
    return [m["container"]] + (m.get("with") or [])


@app.post("/mode/<cid>")
def mode(cid):
    target = next((m for m in MODES if m["container"] == cid), None)
    for m in MODES:                                     # exclusive: free the dongle
        if m["container"] != cid:
            for c in mode_containers(m):
                act("stop", c)
    for c in (target.get("with") or []):                # start helpers (rsp_tcp bridge) first
        act("start", c)
    act("start", cid)
    return jsonify(ok=True)


@app.post("/modestop/<cid>")
def modestop(cid):                                      # release an active mode + its helpers
    m = next((x for x in MODES if x["container"] == cid), None)
    for c in (mode_containers(m) if m else [cid]):
        act("stop", c)
    return jsonify(ok=True)


@app.post("/hdradio/tune")
def hd_tune():
    freq = (request.form.get("freq") or "").strip()
    prog = (request.form.get("program") or "0").strip()
    try:                                                # validate before it reaches docker
        float(freq)
        prog_i = int(prog)
        if not 0 <= prog_i <= 7:
            raise ValueError
    except Exception:
        return jsonify(ok=False, error="bad frequency/program"), 400
    for m in MODES:                                     # free the dongle (web SDR / decoders)
        if m["container"] != "hdradio":
            act("stop", m["container"])
    try:                                                # clear any prior stream container
        dock.containers.get("hdradio").remove(force=True)
    except Exception:
        pass
    try:
        dock.containers.run(
            NRSC5_IMAGE, [freq, str(prog_i)],
            name="hdradio", detach=True, remove=True,
            entrypoint="/usr/local/bin/hdstream",
            volumes={"/dev/bus/usb": {"bind": "/dev/bus/usb", "mode": "rw"}},
            device_cgroup_rules=["c 189:* rwm"],
            environment={"ICECAST_SOURCE_PASSWORD": icecast_pw(),
                         "ICECAST_HOST": ICECAST_HOST,
                         "NRSC5_DEVICE": DISCONE_INDEX},
        )
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500
    return jsonify(ok=True)


@app.post("/hdradio/stop")
def hd_stop():
    try:
        dock.containers.get("hdradio").remove(force=True)   # auto-frees the dongle
    except Exception:
        pass
    return jsonify(ok=True)


@app.post("/<action>/<name>")
def control(action, name):
    if action in ("start", "stop", "restart"):
        act(action, name)
        return jsonify(ok=True)
    return jsonify(ok=False, error="bad action"), 400


@app.get("/api/state")
def api_state():
    modes = [{"label": m["label"], "container": m["container"],
              "status": state(m["container"])}
             for m in MODES if not m.get("cli")]        # hdradio rendered by its own block
    svcs = [{"label": s["label"], "container": s["container"],
             "status": state(s["container"])} for s in SERVICES]
    return jsonify(modes=modes, services=svcs, hdradio=hd_meta())


# ---- page (AJAX-driven; braces are JS/CSS, so this is a plain string) --------

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body{background:#0e1116;color:#d7dde4;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:.6rem}
 .cols{display:flex;gap:.8rem;align-items:flex-start;flex-wrap:wrap}
 .col{flex:1;min-width:230px}
 .grp{color:#9aa6b2;font-size:.7rem;letter-spacing:.08em;margin:.2rem 0 .3rem}
 .row{display:flex;align-items:center;gap:.5rem;padding:.3rem .4rem;border:1px solid #2a313c;border-radius:8px;margin:.25rem 0;background:#161b22}
 .dot{width:10px;height:10px;border-radius:50%;flex:none}
 .lbl{flex:1;font-weight:600} .st{color:#9aa6b2;font-size:.72rem;text-align:right;white-space:nowrap}
 button{border:0;border-radius:6px;padding:.3rem .6rem;font-weight:600;cursor:pointer;font-size:.8rem}
 .go{background:#238636;color:#fff} .act{background:#1f6feb;color:#fff}
 button:disabled{background:#30363d;color:#6e7681;cursor:not-allowed}
 .hd{border:1px solid #2a313c;border-radius:8px;margin:.25rem 0;background:#161b22;padding:.4rem}
 .hdform{display:flex;gap:.35rem;align-items:center;flex-wrap:wrap;margin-top:.35rem}
 .hdform input,.hdform select{background:#0e1116;color:#d7dde4;border:1px solid #2a313c;border-radius:6px;padding:.25rem .4rem;font-size:.8rem}
 .hdform input{width:4rem}
 .hdnow{font-size:.78rem;color:#cdd6e0;margin-top:.4rem;min-height:1em} .hdnow b{color:#7ee787}
 #hdplayer audio{width:100%;margin-top:.4rem;height:34px}
 .muted{color:#6e7681}
</style></head><body>
 <div class="cols">
  <div class="col">
   <div class="grp">DISCONE — one at a time</div>
   <div id="modes"></div>
   <div class="hd">
    <div class="row" style="border:0;background:none;padding:.1rem .2rem;margin:0">
     <span class="dot" id="hddot" style="background:#6e7681"></span>
     <span class="lbl">HD Radio (nrsc5)</span><span class="st" id="hdst">off</span>
    </div>
    <form id="hdform" class="hdform">
     <input name="freq" id="hdfreq" value="98.1" inputmode="decimal" aria-label="frequency MHz">
     <span class="muted">MHz</span>
     <select name="program" id="hdprog" aria-label="program">
      <option value="0">HD1</option><option value="1">HD2</option>
      <option value="2">HD3</option><option value="3">HD4</option>
     </select>
     <button type="submit" class="go">▶ Tune</button>
     <button type="button" id="hdstop" class="act">■ Stop</button>
    </form>
    <div id="hdnow" class="hdnow"></div>
    <div id="hdplayer"></div>
   </div>
  </div>
  <div class="col">
   <div class="grp">SERVICES</div>
   <div id="services"></div>
  </div>
 </div>
<script>
const DOT={running:'#7ee787',exited:'#f85149',absent:'#6e7681',created:'#d29922',error:'#f85149'};
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const api=(p,o)=>fetch(p,o).then(r=>r.json()).catch(()=>({}));
function row(label,status,txt,cls,action,disabled){
 return `<div class="row"><span class="dot" style="background:${DOT[status]||'#6e7681'}"></span>`+
  `<span class="lbl">${esc(label)}</span><span class="st">${esc(status)}</span>`+
  `<button class="${cls}" data-action="${action}" ${disabled?'disabled':''}>${txt}</button></div>`;
}
function renderModes(modes){
 $('modes').innerHTML=modes.map(m=>{
  const on=m.status==='running', absent=m.status==='absent';
  return on ? row(m.label,m.status,'■ release','act',`modestop/${m.container}`,false)
            : row(m.label,m.status,'▶ activate','go',`mode/${m.container}`,absent);
 }).join('');
}
function renderServices(svcs){
 $('services').innerHTML=svcs.map(s=>{
  const on=s.status==='running', absent=s.status==='absent';
  return on ? row(s.label,s.status,'■ stop','act',`stop/${s.container}`,false)
            : row(s.label,s.status,'▶ start','go',`start/${s.container}`,absent);
 }).join('');
}
function renderHd(hd){
 const live=hd&&hd.live, synced=live&&hd.synced;
 $('hddot').style.background=live?(synced?'#7ee787':'#d29922'):'#6e7681';
 $('hdst').textContent=live?(synced?`HD${(+hd.program||0)+1} · ${hd.freq} MHz`:'tuning…'):'off';
 if(live){
  const p=[]; if(hd.station)p.push(`<b>${esc(hd.station)}</b>`);
  if(hd.title)p.push(esc(hd.title)); if(hd.artist)p.push('— '+esc(hd.artist));
  $('hdnow').innerHTML=p.length?p.join(' '):'<span class="muted">syncing…</span>';
 } else $('hdnow').innerHTML='';
 const pl=$('hdplayer');
 if(live){
  const key=`${hd.freq}|${hd.program}`;
  let a=pl.querySelector('audio');
  if(!a){                                   // first time: create the player (paused)
   pl.innerHTML=`<audio controls preload="none" data-key="${esc(key)}" src="${hd.stream}?s=${encodeURIComponent(key)}"></audio>`;
  } else if(synced && (window.__hdReattach || a.dataset.key!==key)){
   // station changed (or a fresh Tune) and the new stream is locked → reconnect.
   // Icecast drops listeners when the source flips, so the element must reload or
   // it stays stuck buffering the old (now-dead) stream.
   window.__hdReattach=false;
   const playing=!a.paused && !a.ended;
   a.dataset.key=key;
   a.src=`${hd.stream}?s=${encodeURIComponent(key)}.${Date.now()}`;
   a.load();
   if(playing) a.play().catch(()=>{});
  }
 } else if(pl.querySelector('audio')){ pl.innerHTML=''; }
}
async function poll(){
 const s=await api('api/state');
 if(s.modes)renderModes(s.modes); if(s.services)renderServices(s.services); renderHd(s.hdradio);
}
document.addEventListener('click',async e=>{
 const b=e.target.closest('button[data-action]'); if(!b||b.disabled)return;
 b.disabled=true; await api(b.dataset.action,{method:'POST'}); poll();
});
$('hdform').addEventListener('submit',async e=>{
 e.preventDefault(); $('hdst').textContent='starting…';
 window.__hdReattach=true;                  // reconnect the player once the new stream locks
 await api('hdradio/tune',{method:'POST',body:new URLSearchParams(new FormData($('hdform')))});
 setTimeout(poll,800);
});
$('hdstop').addEventListener('click',async()=>{await api('hdradio/stop',{method:'POST'}); poll();});
poll(); setInterval(poll,5000);
</script></body></html>"""


@app.get("/")
def index():
    return PAGE


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8093)
