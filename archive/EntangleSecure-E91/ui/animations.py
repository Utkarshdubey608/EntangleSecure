"""Animated scientific visualisations rendered in sandboxed iframes.

Each animation receives a JSON payload extracted from the *current* experiment
result (settings, outcomes, roles, Eve interceptions, Bell statistics, keys), so
what moves on screen is the simulated data, not a canned loop.
"""

from __future__ import annotations

import json
import math

import numpy as np
import streamlit as st

from entanglesecure.protocol import ExperimentResult
from entanglesecure.protocol.postprocessing import bits_to_hex
from entanglesecure.quantum import singlet_circuit_trace

from . import theme


def _num(x: float) -> float | None:
    return None if x is None or not math.isfinite(x) else float(x)


def payload(res: ExperimentResult, n_rounds: int = 300) -> dict:
    cfg = res.config
    r = res.rounds.head(n_rounds)
    k = res.keys
    m = res.metrics()
    sift_a = k.sifted.alice[:64].tolist()
    sift_b = k.sifted.bob[:64].tolist()
    trace = [{"label": lab, "amps": np.real(psi).round(4).tolist()} for lab, psi in singlet_circuit_trace()]
    return {
        "cfg": {
            "alice": list(cfg.alice_angles_deg), "bob": list(cfg.bob_angles_deg), "n": cfg.n_pairs,
            "noise": cfg.depolarizing_noise, "eta": cfg.detection_efficiency, "eve": cfg.eve.enabled,
            "q": cfg.eve.intercept_fraction, "eveAngles": list(cfg.eve.basis_angles_deg), "seed": cfg.seed,
        },
        "rounds": {
            "a": r.alice_setting.tolist(), "b": r.bob_setting.tolist(), "x": r.alice_outcome.tolist(),
            "y": r.bob_outcome.tolist(), "role": r.role.tolist(), "hit": r.intercepted.astype(int).tolist(),
            "ea": r.eve_angle_index.tolist(), "eo": r.eve_outcome.tolist(),
        },
        "trace": trace,
        "counts": res.role_counts(),
        "concurrence": _num(res.model.concurrence_channel),
        "bell": {
            "S": _num(res.bell.s_value), "err": _num(res.bell.s_stderr), "low": _num(res.bell.s_lower),
            "sig": _num(res.bell.significance), "theory": _num(res.bell.s_theory),
            "violated": res.bell.violates_classical, "confirmed": res.bell.violation_confirmed,
            "z": cfg.bell_confidence_sigma,
            "terms": [
                {"sym": sym, "lab": f"A{c.alice_idx}B{c.bob_idx}", "E": _num(c.expectation), "err": _num(c.stderr),
                 "th": _num(c.theory), "sign": sign, "n": c.n}
                for sym, c, sign in res.bell.chsh_terms()
            ],
        },
        "keys": {
            "siftA": sift_a, "siftB": sift_b, "sifted": len(k.sifted), "qber": _num(k.sifted_qber),
            "qberEst": _num(k.qber_estimate), "estN": k.estimation_size,
            "leak": k.cascade.leaked_bits if k.cascade else None,
            "residual": k.cascade.residual_errors if k.cascade else None,
            "final": k.final_length, "hex": bits_to_hex(k.final_alice)[:48], "stages": k.stages,
            "eveAgree": _num(k.eve_agreement), "chi": _num(k.eve_info_bound), "aborted": k.aborted, "reason": k.abort_reason,
        },
        "status": m["security_status"],
    }


_COMMON_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:transparent;color:%(ink)s;font-family:'IBM Plex Sans',system-ui,sans-serif;overflow:hidden}
canvas{display:block;width:100%%}
.mono{font-family:'IBM Plex Mono',ui-monospace,monospace}
button{font:inherit;color:%(ink)s;background:%(raised)s;border:1px solid %(line_strong)s;border-radius:8px;padding:6px 12px;cursor:pointer;transition:border-color .15s}
button:hover{border-color:%(cyan)s} button:focus-visible{outline:2px solid %(cyan)s;outline-offset:2px}
""" % {"ink": theme.INK, "raised": theme.RAISED, "line_strong": theme.LINE_STRONG, "cyan": theme.CYAN}

_FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">'

_JS_COMMON = r"""
const C = {bg:'#0B1220', ink:'#E7EDF7', ink2:'#A3B0C7', muted:'#6B7A96', line:'#1C2740', lineS:'#2A3856',
  cyan:'#22D3EE', violet:'#A78BFA', blue:'#4C8DFF', eve:'#E0A23A', good:'#34D399', warn:'#FBBF24', bad:'#F87171'};
const REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function fitCanvas(cv, S, h){ return (cv.parentElement.clientWidth && cv.parentElement.clientWidth !== S.w) ? setupCanvas(cv, h) : S; }
function setupCanvas(cv, h){
  const dpr = window.devicePixelRatio || 1; const w = cv.parentElement.clientWidth;
  cv.width = w*dpr; cv.height = h*dpr; cv.style.height = h+'px';
  const ctx = cv.getContext('2d'); ctx.setTransform(dpr,0,0,dpr,0,0); return {ctx, w, h};
}
const ease = t => t<0?0:t>1?1:1-Math.pow(1-t,3);
const lerp = (a,b,t)=>a+(b-a)*t;
function glow(ctx,x,y,r,color,alpha){ const g=ctx.createRadialGradient(x,y,0,x,y,r); g.addColorStop(0,hexA(color,alpha)); g.addColorStop(1,hexA(color,0)); ctx.fillStyle=g; ctx.beginPath(); ctx.arc(x,y,r,0,7); ctx.fill(); }
function hexA(h,a){ const n=parseInt(h.slice(1),16); return `rgba(${n>>16&255},${n>>8&255},${n&255},${a})`; }
function dot(ctx,x,y,r,color){ ctx.fillStyle=color; ctx.beginPath(); ctx.arc(x,y,r,0,7); ctx.fill(); }
function text(ctx,s,x,y,o={}){ ctx.font=`${o.weight||400} ${o.size||12}px ${o.mono?"'IBM Plex Mono',monospace":"'IBM Plex Sans',sans-serif"}`;
  ctx.fillStyle=o.color||C.ink; ctx.textAlign=o.align||'center'; ctx.textBaseline=o.base||'middle'; ctx.fillText(s,x,y); }
function rrect(ctx,x,y,w,h,r){ ctx.beginPath(); ctx.moveTo(x+r,y); ctx.arcTo(x+w,y,x+w,y+h,r); ctx.arcTo(x+w,y+h,x,y+h,r); ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath(); }
// Measurement station: dial with the party's three directions, the active one highlighted (θ from +z, clockwise toward +x).
function station(ctx,x,y,r,angles,active,color,label,outcome,flash){
  ctx.strokeStyle=C.lineS; ctx.lineWidth=1; ctx.beginPath(); ctx.arc(x,y,r,0,7); ctx.stroke();
  angles.forEach((a,i)=>{ const t=a*Math.PI/180; const ex=x+Math.sin(t)*r, ey=y-Math.cos(t)*r;
    ctx.strokeStyle = i===active? color : hexA(C.ink2,0.25); ctx.lineWidth = i===active?2.5:1.2;
    ctx.beginPath(); ctx.moveTo(x-Math.sin(t)*r*0.15,y+Math.cos(t)*r*0.15); ctx.lineTo(ex,ey); ctx.stroke();
    if(i===active) dot(ctx,ex,ey,3.5,color); });
  dot(ctx,x,y,3,C.ink2);
  text(ctx,label,x,y+r+16,{size:13,weight:500});
  if(outcome){ const a=flash; glow(ctx,x,y,r*1.25,outcome>0?C.cyan:C.violet,0.28*a);
    text(ctx,outcome>0?'+1':'−1',x,y-r-14,{size:15,weight:600,mono:true,color:hexA(outcome>0?C.cyan:C.violet,Math.max(a,0.35))}); }
}
"""


def channel_hero(res: ExperimentResult, height: int = 330) -> None:
    """Live Alice ← source → Bob channel replaying the first rounds of the current run."""
    data = json.dumps(payload(res, 400))
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>" + _FONTS + "<style>" + _COMMON_CSS + r"""
.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:12px;color:#A3B0C7;padding:2px 4px 0}
.legend span{display:inline-flex;align-items:center;gap:6px}.legend i{width:9px;height:9px;border-radius:50%;display:inline-block}
</style></head><body><canvas id="cv"></canvas>
<div class="legend"><span><i style="background:#22D3EE"></i>outcome +1</span><span><i style="background:#A78BFA"></i>outcome −1</span>
<span><i style="background:#34D399"></i>key round</span><span><i style="background:#4C8DFF"></i>CHSH round</span><span><i style="background:#6B7A96"></i>discarded</span>
<span id="evelg" style="display:none"><i style="background:#E0A23A"></i>intercepted by Eve</span></div>
<script>""" + _JS_COMMON + r"""
const D = __DATA__; const R = D.rounds; const N = R.a.length; const H = __H__;
if (D.cfg.eve) document.getElementById('evelg').style.display='inline-flex';
const cv = document.getElementById('cv'); let S = setupCanvas(cv,H); window.addEventListener('resize',()=>S=setupCanvas(cv,H));
const ROLE_COL = [C.good, C.blue, C.muted, '#3a4560']; const ROLE_TXT=['key','CHSH','discard','lost'];
const PERIOD = 520, FLIGHT = 1250; let keyA='', keyB='', nK=0, nC=0, nD=0, nL=0, lastIdx=-1; const t0 = performance.now();
function frame(now){
  S = fitCanvas(cv, S, H); const {ctx,w,h} = S; ctx.clearRect(0,0,w,h);
  const compact = w < 560; const midY = h*0.36, ax = compact? 40 : Math.max(70,w*0.1), bx = w-ax, sx = w/2, ex = lerp(sx,bx,0.55);
  // channels
  ctx.setLineDash([2,6]); ctx.strokeStyle=C.lineS; ctx.lineWidth=1; ctx.beginPath(); ctx.moveTo(ax,midY); ctx.lineTo(bx,midY); ctx.stroke(); ctx.setLineDash([]);
  if(!compact){ text(ctx,'quantum channel',lerp(ax,sx,0.5),midY+16,{size:11,color:C.muted}); text(ctx,'quantum channel',lerp(sx,bx,0.5)-(D.cfg.eve?60:0),midY+16,{size:11,color:C.muted}); }
  // source
  const pulse = (Math.sin(now/300)+1)/2; glow(ctx,sx,midY,34+6*pulse,C.blue,0.35); dot(ctx,sx,midY,7,C.ink);
  text(ctx,'Entangled source',sx,midY-40,{size:13,weight:500}); if(!compact) text(ctx,'|ψ⁻⟩ = (|01⟩ − |10⟩)/√2',sx,midY+42,{size:12,mono:true,color:C.ink2});
  if (D.cfg.eve){ ctx.strokeStyle=C.eve; ctx.lineWidth=1.5; rrect(ctx,ex-15,midY-15,30,30,7); ctx.stroke(); text(ctx,'Eve',ex,midY-28,{size:12,weight:500,color:C.eve}); text(ctx,'q = '+D.cfg.q.toFixed(2),ex,midY+28,{size:10.5,color:C.eve}); }
  const tt = REDUCED ? 3*PERIOD+FLIGHT : now - t0; const latest = Math.floor(tt/PERIOD);
  // emit / fly pairs
  let stA=null, stB=null;
  const arrived = Math.floor((tt-FLIGHT)/PERIOD);
  for (let k=lastIdx+1; k<=arrived; k++){ const i=k%N; const role=R.role[i]; lastIdx=k;
    if(role===0){ nK++; keyA += R.x[i]>0?'0':'1'; keyB += R.y[i]>0?'1':'0'; keyA=keyA.slice(-60); keyB=keyB.slice(-60);} // Bob flips (anti-correlation)
    else if(role===1) nC++; else if(role===2) nD++; else nL++; }
  if (arrived>=0){ const f = Math.max(0, 1-((tt-FLIGHT)-arrived*PERIOD)/PERIOD); stA={i:arrived%N,f}; stB=stA; }
  for (let k=Math.max(0,latest-4); k<=latest; k++){
    const i = k % N; const age = tt - k*PERIOD; if (age<0) continue; const p = ease(age/FLIGHT);
    const hit = D.cfg.eve && R.hit[i]===1;
    const xa = lerp(sx,ax,p), xb = lerp(sx,bx,p);
    if (age<FLIGHT){
      // entanglement link (broken once Eve has measured Bob's particle)
      const evePassed = hit && xb>=ex;
      if (!evePassed){ ctx.strokeStyle=hexA(C.blue,0.35*(1-p)+0.1); ctx.lineWidth=1; ctx.beginPath(); ctx.moveTo(xa,midY); ctx.quadraticCurveTo(sx,midY-50*(1-p)-8,xb,midY); ctx.stroke(); }
      glow(ctx,xa,midY,10,C.cyan,0.5); dot(ctx,xa,midY,3.2,C.ink);
      glow(ctx,xb,midY,10,evePassed?C.eve:C.violet,0.5); dot(ctx,xb,midY,3.2,evePassed?C.eve:C.ink);
    }
  }
  const ia = stA? stA.i : 0;
  const rad = compact? 20 : 28;
  station(ctx,ax,midY,rad,D.cfg.alice, stA? R.a[ia] : -1, C.cyan,'Alice', stA? R.x[ia]:0, stA?stA.f:0);
  station(ctx,bx,midY,rad,D.cfg.bob, stB? R.b[ia] : -1, C.violet,'Bob', stB? R.y[ia]:0, stB?stB.f:0);
  if (stA){ const role=R.role[ia]; const lbl = 'pair '+(ia+1)+': '+ROLE_TXT[role]+' round, A'+R.a[ia]+'B'+R.b[ia];
    ctx.fillStyle=hexA(ROLE_COL[role],0.12); rrect(ctx,sx-92,midY+62,184,24,12); ctx.fill(); text(ctx,lbl,sx,midY+74,{size:11.5,color:ROLE_COL[role]}); }
  // key tapes
  const ty = h-34, kx0 = compact? 8 : ax-40, kx1 = compact? w-8 : bx+40, nChars = Math.floor((compact? w*0.44 : w*0.3)/8.2);
  text(ctx,'Alice key',kx0,ty-11,{size:11,color:C.muted,align:'left'}); text(ctx,'Bob key',kx1,ty-11,{size:11,color:C.muted,align:'right'});
  text(ctx,keyA.slice(-nChars),kx0,ty+7,{size:12.5,mono:true,color:C.cyan,align:'left'});
  text(ctx,keyB.slice(-nChars),kx1,ty+7,{size:12.5,mono:true,color:C.violet,align:'right'});
  const tally = `${nK} key, ${nC} CHSH, ${nD} discarded`+(nL?`, ${nL} lost`:'');
  text(ctx, compact? tally : 'pairs replayed so far: '+tally, sx, compact? ty-34 : ty+7,{size:11,color:C.ink2});
  if(!REDUCED) requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
</script></body></html>"""
    ).replace("__DATA__", data).replace("__H__", str(height - 28))
    st.iframe(html, height=height)


def protocol_stepper(res: ExperimentResult, height: int = 660) -> None:
    """Eight-step animated E91 walkthrough driven by the current experiment."""
    data = json.dumps(payload(res, 64))
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>" + _FONTS + "<style>" + _COMMON_CSS + r"""
.wrap{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(260px,1fr);gap:16px;height:100%}
@media(max-width:820px){.wrap{grid-template-columns:1fr}}
.rail{display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap}
.rail button{padding:5px 10px;font-size:12px;color:#A3B0C7;border-radius:999px;background:transparent}
.rail button.on{color:#03121a;background:#22D3EE;border-color:#22D3EE;font-weight:600}
.rail button.done{color:#E7EDF7;border-color:#2A3856}
.stage{background:#0B1220;border:1px solid #1C2740;border-radius:12px;overflow:hidden}
.side{background:#0B1220;border:1px solid #1C2740;border-radius:12px;padding:16px 18px;display:flex;flex-direction:column;gap:10px;overflow:auto}
.side h2{font-size:17px;font-weight:600;letter-spacing:-.01em}
.side p{font-size:13.5px;line-height:1.6;color:#A3B0C7}
.facts{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:12.5px;border-top:1px solid #1C2740;padding-top:10px}
.facts dt{color:#6B7A96}.facts dd{color:#E7EDF7;font-variant-numeric:tabular-nums;text-align:right}
.ctrl{display:flex;gap:8px;align-items:center;margin-top:10px}.ctrl button{font-size:13px;padding:5px 12px}
.ctrl .sp{flex:1}.ctrl small{color:#6B7A96;font-size:12px}
.tag{font-size:11.5px;color:#6B7A96}
</style></head><body>
<div class="rail" id="rail"></div>
<div class="wrap"><div><div class="stage"><canvas id="cv"></canvas></div>
<div class="ctrl"><button id="prev">Previous</button><button id="play">Pause</button><button id="next">Next step</button><span class="sp"></span><small id="prog"></small></div></div>
<div class="side"><span class="tag" id="tag"></span><h2 id="title"></h2><p id="body"></p><dl class="facts" id="facts"></dl></div></div>
<script>""" + _JS_COMMON + r"""
const D = __DATA__; const R = D.rounds; const K = D.keys; const B = D.bell; const H = __H__;
const fmt=(v,d=3)=> v===null||v===undefined? '—' : (typeof v==='number'? v.toFixed(d): v);
const pct=(v,d=2)=> v===null||v===undefined? '—' : (v*100).toFixed(d)+' %';
const nf = v => (v===null||v===undefined)?'—':v.toLocaleString('en-US');
const cv=document.getElementById('cv'); let S=setupCanvas(cv,H); window.addEventListener('resize',()=>S=setupCanvas(cv,H));
const SHOW = 12; // rounds shown in the measurement tapes
const ROLE_COL=[C.good,C.blue,C.muted,'#3a4560'], ROLE_TXT=['key','CHSH','discard','lost'];
const eveTxt = D.cfg.eve ? `Eve intercepts ${Math.round(D.cfg.q*100)} % of Bob's particles (intercept-resend).` : 'No eavesdropper on the channel.';
const STEPS = [
 {t:'Entangled pair generation', b:'The source prepares the Bell singlet from |00⟩ with the circuit X⊗X → H⊗I → CNOT. The bars show the real state-vector amplitudes after each gate, computed by the simulator. Neither particle has a definite spin on its own; only their joint state is defined.',
  f:()=>[['State','|ψ⁻⟩'],['Amplitudes |01⟩, |10⟩','+0.7071, −0.7071'],['Pairs generated',nf(D.cfg.n)],['Concurrence after channel',fmt(D.concurrence,4)]], dur:6400},
 {t:'Particle distribution', b:`One particle of every pair travels to Alice, the other to Bob. Depolarizing noise p = ${D.cfg.noise.toFixed(3)} acts on each particle. ${eveTxt} Intercepted pairs lose their entanglement link.`,
  f:()=>[['Depolarizing noise p',fmt(D.cfg.noise,3)],['Detection efficiency',fmt(D.cfg.eta,2)],['Eve',D.cfg.eve?'on, q = '+D.cfg.q.toFixed(2):'off'],['Entanglement (concurrence)',fmt(D.concurrence,4)]], dur:5200},
 {t:"Alice's measurement", b:`For each particle Alice picks one of her directions A0, A1, A2 = ${D.cfg.alice.map(a=>a+'°').join(', ')} at random and records +1 or −1. Each of her outcomes on its own is a fair coin flip; no information is in her data alone.`,
  f:()=>[['Directions',D.cfg.alice.map(a=>a+'°').join(', ')],['Shown',`first ${SHOW} pairs`],['+1 among shown',R.x.slice(0,SHOW).filter(v=>v>0).length+' / '+SHOW]], dur:5600},
 {t:"Bob's measurement", b:`Bob independently picks B0, B1, B2 = ${D.cfg.bob.map(a=>a+'°').join(', ')}. When both happen to choose the same direction the outcomes are always opposite: that is the singlet's perfect anti-correlation, E = −cos(a − b).`,
  f:()=>{ let same=0, anti=0; for(let i=0;i<SHOW;i++){ if(D.cfg.alice[R.a[i]]===D.cfg.bob[R.b[i]]){ same++; if(R.x[i]===-R.y[i]) anti++; } } return [['Directions',D.cfg.bob.map(a=>a+'°').join(', ')],['Same direction (shown)',String(same)],['…of which anti-correlated',String(anti)]]; }, dur:5600},
 {t:'Public basis discussion', b:'Over an authenticated public channel Alice and Bob announce which directions they used, never their outcomes. Each pair is labelled: equal directions become key rounds, the four CHSH combinations feed the Bell test, the rest are discarded.',
  f:()=>[['Key rounds',nf(D.counts.key)],['CHSH rounds',nf(D.counts.chsh)],['Discarded',nf(D.counts.discard)],['Lost (no detection)',nf(D.counts.lost)]], dur:5200},
 {t:'Bell inequality test', b:`From the CHSH rounds they estimate the four correlators and S = |E(a,b) + E(a,b′) + E(a′,b) − E(a′,b′)|. Any local-realistic model gives S ≤ 2; quantum mechanics reaches 2√2 ≈ 2.828. Measured S = ${fmt(B.S)} ± ${fmt(B.err)}.`,
  f:()=>[['S measured',fmt(B.S,4)+' ± '+fmt(B.err,4)],['S theory',fmt(B.theory,4)],['Above 2 by',fmt(B.sig,1)+' σ'],['S − '+B.z+'σ',fmt(B.low,4)]], dur:6400},
 {t:'Key extraction', b:`Bob flips his key bits because the singlet is anti-correlated. ${K.estN} bits are revealed to estimate the QBER and discarded; Cascade corrects the remaining errors; Toeplitz hashing removes what Eve could know, χ(S) = ${fmt(K.chi,3)} per bit.`,
  f:()=>[['Sifted key',nf(K.sifted)+' bits'],['QBER (estimated)',pct(K.qberEst)],['Bits leaked by Cascade',nf(K.leak)],['Final secret key',nf(K.final)+' bits']], dur:6400},
 {t:'Security assessment', b: K.aborted ? K.reason : `The Bell inequality is violated by ${fmt(B.sig,1)} σ, so the correlations cannot come from a local (intercepted) source. Alice and Bob keep a ${nf(K.final)}-bit secret key.`,
  f:()=>[['Verdict',D.status],['S',fmt(B.S,4)],['QBER',pct(K.qber)],['Eve agreement with Bob',pct(K.eveAgree,1)],['Final key (hex)',K.hex? K.hex.slice(0,16)+'…':'—']], dur:7000},
];
let step=0, t0=performance.now(), playing=!REDUCED;
const rail=document.getElementById('rail');
STEPS.forEach((s,i)=>{ const b=document.createElement('button'); b.textContent=(i+1)+'. '+s.t; b.onclick=()=>go(i); rail.appendChild(b); });
function go(i){ step=(i+STEPS.length)%STEPS.length; t0=performance.now(); render(); }
document.getElementById('prev').onclick=()=>go(step-1); document.getElementById('next').onclick=()=>go(step+1);
const pb=document.getElementById('play'); pb.textContent=playing?'Pause':'Play'; pb.onclick=()=>{ playing=!playing; pb.textContent=playing?'Pause':'Play'; t0=performance.now()-0; };
function render(){ const s=STEPS[step]; document.getElementById('tag').textContent=`Step ${step+1} of ${STEPS.length}`;
  document.getElementById('title').textContent=s.t; document.getElementById('body').textContent=s.b;
  document.getElementById('facts').innerHTML=s.f().map(([k,v])=>`<dt>${k}</dt><dd>${v}</dd>`).join('');
  [...rail.children].forEach((b,i)=>{ b.className = i===step?'on':(i<step?'done':''); }); document.getElementById('prog').textContent=playing?'auto-advancing':'paused'; }
render();

function layout(w,h){ return {ax:Math.max(64,w*0.12), bx:w-Math.max(64,w*0.12), sx:w/2, y:h*0.30}; }
function stations(ctx,L,ai,bi,xo,yo,f){ station(ctx,L.ax,L.y,26,D.cfg.alice,ai,C.cyan,'Alice',xo,f); station(ctx,L.bx,L.y,26,D.cfg.bob,bi,C.violet,'Bob',yo,f); }
function tape(ctx,w,top,upto,opts){ // rows of rounds: settings + outcomes (+ role colouring)
  const n=SHOW, cw=Math.min(46,(w-110)/n), x0=(w-cw*n)/2+30; const rows=opts.rows;
  rows.forEach((row,ri)=>{ const y=top+ri*24; text(ctx,row.label,x0-12,y,{size:11,color:C.muted,align:'right'});
    for(let i=0;i<Math.min(n,upto);i++){ const v=row.val(i); const col=row.col?row.col(i):C.ink2; text(ctx,v,x0+cw*i+cw/2,y,{size:12,mono:true,color:col}); } });
  if(opts.roles){ for(let i=0;i<Math.min(n,upto);i++){ const r=R.role[i]; ctx.fillStyle=hexA(ROLE_COL[r],0.16); rrect(ctx,x0+cw*i+2,top-12,cw-4,rows.length*24,6); ctx.fill();
     text(ctx,ROLE_TXT[r],x0+cw*i+cw/2,top+rows.length*24+2,{size:10,color:ROLE_COL[r]}); } }
  for(let i=0;i<Math.min(n,upto);i++) text(ctx,String(i+1),x0+cw*i+cw/2,top-22,{size:10,color:C.muted});
}
const outTxt=v=>v>0?'+1':(v<0?'−1':'·'); const outCol=v=>v>0?C.cyan:(v<0?C.violet:C.muted);

const SCENES=[
 // 1. generation: circuit + amplitude bars
 (ctx,w,h,t)=>{ const L=layout(w,h); const T=D.trace; const per=1500; const k=Math.min(T.length-1,Math.floor(t/per)); const f=ease((t%per)/700);
   const prev=T[Math.max(0,k-1)].amps, cur=T[k].amps; const amps=cur.map((a,i)=>k===0?a:lerp(prev[i],a,f));
   const gx0=w*0.12, gw=w*0.76, gy=h*0.16; text(ctx,'|00⟩',gx0-6,gy,{size:13,mono:true,align:'right',color:C.ink2});
   T.slice(1).forEach((s,i)=>{ const x=gx0+gw*(i+0.5)/(T.length-1); const on=i+1<=k; ctx.strokeStyle=on?C.cyan:C.lineS; ctx.lineWidth=1.5; rrect(ctx,x-48,gy-15,96,30,8); ctx.stroke();
     text(ctx,s.label,x,gy,{size:12,mono:true,color:on?C.ink:C.muted}); });
   ctx.strokeStyle=C.lineS; ctx.beginPath(); ctx.moveTo(gx0,gy); ctx.lineTo(gx0+gw,gy); ctx.stroke();
   const labels=['|00⟩','|01⟩','|10⟩','|11⟩']; const base=h*0.66, bh=h*0.25, bw=Math.min(70,w*0.09);
   ctx.strokeStyle=C.lineS; ctx.beginPath(); ctx.moveTo(w*0.2,base); ctx.lineTo(w*0.8,base); ctx.stroke();
   amps.forEach((a,i)=>{ const x=w*0.2+(w*0.6)*(i+0.5)/4; const hh=a*bh; ctx.fillStyle=a>=0?C.cyan:C.violet; rrect(ctx,x-bw/2,Math.min(base,base-hh),bw,Math.max(Math.abs(hh),1),4); ctx.fill();
     text(ctx,labels[i],x,base+bh+16,{size:13,mono:true,color:C.ink2}); text(ctx,(a>=0?'+':'')+a.toFixed(3),x,a>=0?base-hh-12:base-hh+12,{size:11.5,mono:true}); });
   text(ctx,'after '+(k===0?'initialisation':T[k].label),w/2,h*0.30,{size:12,color:C.muted}); },
 // 2. distribution
 (ctx,w,h,t)=>{ const L=layout(w,h); const ex=lerp(L.sx,L.bx,0.55); const y=h*0.42;
   ctx.setLineDash([2,6]); ctx.strokeStyle=C.lineS; ctx.beginPath(); ctx.moveTo(L.ax,y); ctx.lineTo(L.bx,y); ctx.stroke(); ctx.setLineDash([]);
   glow(ctx,L.sx,y,30,C.blue,0.4); dot(ctx,L.sx,y,6,C.ink); text(ctx,'source',L.sx,y-36,{size:12,color:C.ink2});
   text(ctx,'Alice',L.ax,y+40,{size:13,weight:500}); text(ctx,'Bob',L.bx,y+40,{size:13,weight:500}); dot(ctx,L.ax,y,5,C.cyan); dot(ctx,L.bx,y,5,C.violet);
   if(D.cfg.eve){ ctx.strokeStyle=C.eve; ctx.lineWidth=1.5; rrect(ctx,ex-14,y-14,28,28,7); ctx.stroke(); text(ctx,'Eve',ex,y-28,{size:12,color:C.eve}); }
   const per=650, fl=1600; const latest=Math.floor(t/per);
   for(let k=Math.max(0,latest-3);k<=latest;k++){ const i=k%R.a.length; const p=ease((t-k*per)/fl); if(p>=1) continue; const hit=D.cfg.eve&&R.hit[i]===1;
     const xa=lerp(L.sx,L.ax,p), xb=lerp(L.sx,L.bx,p); const broken=hit&&xb>=ex;
     if(!broken){ ctx.strokeStyle=hexA(C.blue,0.5); ctx.lineWidth=1.2; ctx.beginPath(); ctx.moveTo(xa,y); ctx.quadraticCurveTo(L.sx,y-60*(1-p)-10,xb,y); ctx.stroke(); }
     glow(ctx,xa,y,11,C.cyan,0.55); dot(ctx,xa,y,3.5,C.ink); glow(ctx,xb,y,11,broken?C.eve:C.violet,0.55); dot(ctx,xb,y,3.5,broken?C.eve:C.ink);
     if(broken) text(ctx,'measured & resent',xb,y+22,{size:10.5,color:C.eve}); }
   text(ctx,'curves = entanglement link between the two particles of a pair',w/2,h*0.86,{size:11.5,color:C.muted}); },
 // 3. Alice measures
 (ctx,w,h,t)=>{ const L=layout(w,h); const per=420; const upto=Math.min(SHOW,Math.floor(t/per)+1); const i=upto-1; const f=1-((t%per)/per)*0.6;
   stations(ctx,L,R.a[i],-1,R.x[i],0,f); text(ctx,'pair '+(i+1),L.sx,L.y,{size:12,color:C.muted});
   tape(ctx,w,h*0.66,upto,{rows:[{label:'Alice',val:k=>'A'+R.a[k],col:()=>C.cyan},{label:'outcome',val:k=>outTxt(R.x[k]),col:k=>outCol(R.x[k])}]}); },
 // 4. Bob measures
 (ctx,w,h,t)=>{ const L=layout(w,h); const per=420; const upto=Math.min(SHOW,Math.floor(t/per)+1); const i=upto-1; const f=1-((t%per)/per)*0.6;
   stations(ctx,L,R.a[i],R.b[i],R.x[i],R.y[i],f); const same=D.cfg.alice[R.a[i]]===D.cfg.bob[R.b[i]];
   text(ctx,same?'same direction → opposite outcomes':'pair '+(i+1),L.sx,L.y,{size:12,color:same?C.good:C.muted});
   tape(ctx,w,h*0.62,upto,{rows:[{label:'Alice',val:k=>'A'+R.a[k],col:()=>C.cyan},{label:'',val:k=>outTxt(R.x[k]),col:k=>outCol(R.x[k])},
     {label:'Bob',val:k=>'B'+R.b[k],col:()=>C.violet},{label:'',val:k=>outTxt(R.y[k]),col:k=>outCol(R.y[k])}]}); },
 // 5. public discussion
 (ctx,w,h,t)=>{ const L=layout(w,h); const y=h*0.2; ctx.setLineDash([6,5]); ctx.strokeStyle=C.ink2; ctx.beginPath(); ctx.moveTo(L.ax,y); ctx.lineTo(L.bx,y); ctx.stroke(); ctx.setLineDash([]);
   text(ctx,'public classical channel: settings only',L.sx,y-16,{size:12,color:C.ink2}); text(ctx,'Alice',L.ax,y+20,{size:13,weight:500}); text(ctx,'Bob',L.bx,y+20,{size:13,weight:500});
   const p=(t%1400)/1400; text(ctx,'A'+R.a[Math.floor(t/1400)%SHOW],lerp(L.ax,L.bx,p),y,{size:12,mono:true,color:C.cyan}); text(ctx,'B'+R.b[Math.floor(t/1400)%SHOW],lerp(L.bx,L.ax,p),y,{size:12,mono:true,color:C.violet});
   const upto=Math.min(SHOW,Math.floor(t/300)+1);
   tape(ctx,w,h*0.5,upto,{roles:true,rows:[{label:'Alice',val:k=>'A'+R.a[k],col:()=>C.cyan},{label:'Bob',val:k=>'B'+R.b[k],col:()=>C.violet}]}); },
 // 6. Bell test
 (ctx,w,h,t)=>{ const g=ease(t/1800); const x0=w*0.16, x1=w*0.84, base=h*0.42, sc=h*0.26; const n=B.terms.length; const bw=Math.min(64,(x1-x0)/n*0.45);
   ctx.strokeStyle=C.lineS; ctx.beginPath(); ctx.moveTo(x0,base); ctx.lineTo(x1,base); ctx.stroke();
   B.terms.forEach((tm,i)=>{ const x=x0+(x1-x0)*(i+0.5)/n; const e=(tm.E||0)*g; ctx.fillStyle=tm.sign>0?C.cyan:C.violet; rrect(ctx,x-bw/2,Math.min(base,base-e*sc),bw,Math.max(Math.abs(e*sc),1),4); ctx.fill();
     ctx.strokeStyle=C.ink; ctx.lineWidth=2; ctx.beginPath(); ctx.moveTo(x-bw/2-6,base-(tm.th||0)*sc); ctx.lineTo(x+bw/2+6,base-(tm.th||0)*sc); ctx.stroke();
     text(ctx,(tm.sign>0?'+ ':'− ')+tm.sym,x,base+sc+18,{size:12,mono:true}); text(ctx,tm.lab+'  '+fmt(tm.E,3),x,base+sc+36,{size:11,color:C.ink2}); });
   text(ctx,'bars: measured E · white ticks: theory',w/2,h*0.08,{size:11,color:C.muted});
   // S scale
   const sy=h*0.9, s0=w*0.12, s1=w*0.88, X=v=>s0+(s1-s0)*v/3; ctx.fillStyle=hexA(C.bad,0.10); ctx.fillRect(s0,sy-8,X(2)-s0,16); ctx.fillStyle=hexA(C.violet,0.14); ctx.fillRect(X(2),sy-8,X(2.828)-X(2),16);
   [[2,'2',C.bad],[2.828,'2√2',C.violet]].forEach(([v,l,c])=>{ ctx.strokeStyle=c; ctx.beginPath(); ctx.moveTo(X(v),sy-12); ctx.lineTo(X(v),sy+12); ctx.stroke(); text(ctx,l,X(v),sy+22,{size:11,color:c}); });
   if(B.S!==null){ const sv=lerp(0,B.S,g); glow(ctx,X(Math.min(sv,3)),sy,16,B.confirmed?C.cyan:C.bad,0.6); dot(ctx,X(Math.min(sv,3)),sy,5,C.ink); text(ctx,'S = '+sv.toFixed(3),X(Math.min(sv,3)),sy-20,{size:12.5,weight:600}); } },
 // 7. key extraction
 (ctx,w,h,t)=>{ const nb=Math.min(K.siftA.length, Math.floor((w-120)/13)); const show=Math.min(nb,Math.floor(t/60)); const x0=(w-nb*13)/2+30;
   const rows=[['Alice',K.siftA,C.cyan],['Bob',K.siftB,C.violet]]; rows.forEach(([lab,bits,col],ri)=>{ const y=h*0.16+ri*26; text(ctx,lab,x0-12,y,{size:11,color:C.muted,align:'right'});
     for(let i=0;i<show;i++){ const err=K.siftA[i]!==K.siftB[i]; text(ctx,String(bits[i]),x0+13*i+6,y,{size:12.5,mono:true,color:err?C.bad:col}); } });
   text(ctx,'sifted bits after Bob\'s flip; red = disagreement',w/2,h*0.16+56,{size:11,color:C.muted});
   const st=K.stages; const top=st.length? Math.max(...st.map(s=>s[1])):1; const fy=h*0.42; const g=ease((t-600)/1600);
   st.forEach((s,i)=>{ const y=fy+i*Math.min(30,(h*0.55)/st.length); const bwid=(w*0.5)*Math.max(s[1]/top,0.004)*g; text(ctx,s[0],w*0.32,y,{size:12,color:C.ink2,align:'right'});
     const grd=ctx.createLinearGradient(w*0.34,0,w*0.84,0); grd.addColorStop(0,'#0ea5c6'); grd.addColorStop(1,'#8b6cf0'); ctx.fillStyle=grd; rrect(ctx,w*0.34,y-5,Math.max(bwid,2),10,4); ctx.fill();
     text(ctx,nf(s[1]),w*0.34+bwid+8,y,{size:12,align:'left',color:C.ink}); }); },
 // 8. verdict
 (ctx,w,h,t)=>{ const col=D.status==='SECURE'?C.good:(D.status==='COMPROMISED'?C.bad:C.warn); const g=ease(t/900); const cx=w/2, cy=h*0.36;
   glow(ctx,cx,cy,90*g,col,0.25); ctx.strokeStyle=col; ctx.lineWidth=3; ctx.beginPath(); ctx.arc(cx,cy,44,-Math.PI/2,-Math.PI/2+Math.PI*2*g); ctx.stroke();
   text(ctx,D.status==='SECURE'?'✓':(D.status==='COMPROMISED'?'!':'?'),cx,cy+1,{size:34,weight:600,color:col});
   text(ctx,{SECURE:'Secure key established',COMPROMISED:'Eavesdropping detected, key discarded',INCONCLUSIVE:'Inconclusive'}[D.status],cx,cy+76,{size:17,weight:600});
   const items=[['S',fmt(B.S,3)],['QBER',pct(K.qber,1)],['final key',nf(K.final)+' bits']]; items.forEach(([k,v],i)=>{ const x=w*(0.28+0.22*i); text(ctx,v,x,h*0.82,{size:18,weight:500}); text(ctx,k,x,h*0.82+22,{size:11.5,color:C.muted}); });
   if(K.hex) text(ctx,K.hex.slice(0,32)+'…',cx,cy+102,{size:12,mono:true,color:C.ink2}); },
];
function frame(now){ S=fitCanvas(cv,S,H); const {ctx,w,h}=S; ctx.clearRect(0,0,w,h); let t=REDUCED? 1e5 : now-t0;
  if(playing && t>STEPS[step].dur+1200){ go(step+1); t=0; }
  SCENES[step](ctx,w,h,t); requestAnimationFrame(frame); }
requestAnimationFrame(frame);
</script></body></html>"""
    ).replace("__DATA__", data).replace("__H__", str(height - 160))
    st.iframe(html, height=height)
