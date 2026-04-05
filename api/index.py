from flask import Flask, redirect, request, session, render_template_string, Response
import requests
import json
import secrets
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'whoop-dash-secret-dev')

CLIENT_ID     = os.environ.get('WHOOP_CLIENT_ID', '').strip()
CLIENT_SECRET = os.environ.get('WHOOP_CLIENT_SECRET', '').strip()
REDIRECT_URI  = os.environ.get('REDIRECT_URI', 'http://localhost:3000/callback').strip()
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_API_KEY', '').strip()

BASE_URL  = 'https://api.prod.whoop.com/developer'
AUTH_URL  = 'https://api.prod.whoop.com/oauth/oauth2/auth'
TOKEN_URL = 'https://api.prod.whoop.com/oauth/oauth2/token'
SCOPES    = 'read:recovery read:cycles read:workout read:sleep read:profile read:body_measurement'

@app.route('/')
def index():
    return redirect('/dashboard' if 'access_token' in session else '/login')

@app.route('/login')
def login():
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state
    url = f"{AUTH_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope={SCOPES}&state={state}"
    return redirect(url)

@app.route('/callback')
def callback():
    code  = request.args.get('code')
    state = request.args.get('state')
    if not code:
        return '<h2>Error: WHOOP no envió el código. <a href="/login">Intenta de nuevo</a>.</h2>', 400
    if state != session.get('oauth_state'):
        return '<h2>Error de seguridad. <a href="/login">Intenta de nuevo</a>.</h2>', 400
    r = requests.post(TOKEN_URL, data={
        'grant_type':   'authorization_code',
        'code':          code,
        'redirect_uri':  REDIRECT_URI,
        'client_id':     CLIENT_ID,
        'client_secret': CLIENT_SECRET,
    })
    if not r.ok:
        return f'<h2>Error al obtener token: {r.text}</h2>', 400
    session['access_token'] = r.json()['access_token']
    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/dashboard')
def dashboard():
    if 'access_token' not in session:
        return redirect('/login')
    try:
        data = fetch_all_data()
        session['cached_data'] = data
    except Exception:
        session.clear()
        return redirect('/login')
    return render_template_string(HTML, data=json.dumps(data, default=str))

@app.route('/api/chat', methods=['POST'])
def chat():
    if 'access_token' not in session:
        return {'error': 'No autenticado'}, 401
    if not ANTHROPIC_KEY:
        return {'response': 'Chat no disponible: configura ANTHROPIC_API_KEY en Vercel.'}, 200
    body = request.json or {}
    user_msg = body.get('message', '').strip()
    history  = body.get('history', [])
    ctx      = body.get('context', {})
    if not user_msg:
        return {'error': 'Mensaje vacío'}, 400

    system = f"""Eres un coach de salud y rendimiento físico especializado en datos WHOOP. Hablas en español colombiano, de forma cercana, directa y motivadora.

DATOS ACTUALES DEL USUARIO:
{json.dumps(ctx, indent=2, default=str)}

REGLAS:
- Responde máximo en 3 párrafos cortos
- Usa los datos para dar consejos específicos y personalizados  
- Si el dato no está disponible, dilo brevemente y sigue
- Sé como un entrenador de alto rendimiento, no un médico
- No repitas los números exactos en cada respuesta, interprétalos
- Usa emojis con moderación para hacer la respuesta más dinámica"""

    msgs = [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
    msgs.append({"role": "user", "content": user_msg})

    try:
        r = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': ANTHROPIC_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 600,
                'system': system,
                'messages': msgs
            },
            timeout=25
        )
        if r.ok:
            return {'response': r.json()['content'][0]['text']}
        return {'response': f'Error del servidor de IA ({r.status_code}). Intenta de nuevo.'}, 200
    except Exception as e:
        return {'response': 'No pude conectar con la IA. Intenta de nuevo.'}, 200

def h():
    return {'Authorization': f"Bearer {session['access_token']}"}

def get(url, params=None):
    try:
        r = requests.get(f'{BASE_URL}{url}', headers=h(), params=params, timeout=10)
        if r.status_code == 401:
            session.clear()
            raise Exception('Token invalido')
        return r.json() if r.ok else {}
    except Exception as e:
        if 'Token' in str(e): raise
        return {}

def fetch_all_data():
    return {
        'profile':  get('/v2/user/profile/basic'),
        'body':     get('/v2/user/measurement/body'),
        'recovery': get('/v2/recovery',        {'limit': 25}).get('records', []),
        'sleep':    get('/v2/activity/sleep',  {'limit': 25}).get('records', []),
        'workouts': get('/v2/activity/workout',{'limit': 25}).get('records', []),
        'cycles':   get('/v2/cycle',           {'limit': 25}).get('records', []),
    }


HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>WHOOP · Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<style>
:root{
  --bg:#05070e;--s1:#090c18;--s2:#0d1020;--card:#0f1422;
  --border:#18203a;--border2:#202c4a;
  --teal:#00e5c3;--teal2:#00b89c;--tealA:rgba(0,229,195,.1);
  --purple:#7c3aed;--purple2:#a78bfa;
  --amber:#f59e0b;--red:#ef4444;--green:#22c55e;--blue:#3b82f6;
  --text:#e2e8f0;--sub:#4a5568;--sub2:#718096;
  --mono:'JetBrains Mono',monospace;
  --r:18px;--r2:12px;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;-webkit-tap-highlight-color:transparent}
body{font-family:'Space Grotesk',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;overflow-x:hidden;padding-bottom:72px}

/* BACKGROUND */
.bg-orb{position:fixed;border-radius:50%;filter:blur(100px);pointer-events:none;z-index:0}
.orb1{width:600px;height:600px;top:-200px;right:-200px;background:rgba(0,229,195,.03)}
.orb2{width:500px;height:500px;bottom:-150px;left:-150px;background:rgba(124,58,237,.03)}
.bg-grid{position:fixed;inset:0;background-image:linear-gradient(rgba(255,255,255,.015) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.015) 1px,transparent 1px);background-size:48px 48px;pointer-events:none;z-index:0}

/* HEADER */
header{
  position:sticky;top:0;z-index:300;
  display:flex;align-items:center;justify-content:space-between;
  padding:0 24px;height:56px;
  background:rgba(5,7,14,.9);
  border-bottom:1px solid var(--border);
  backdrop-filter:blur(24px);
}
.logo{display:flex;align-items:center;gap:10px;font-size:12px;font-weight:700;letter-spacing:.2em;color:var(--teal);text-transform:uppercase;text-decoration:none}
.pulse-dot{width:7px;height:7px;border-radius:50%;background:var(--teal);box-shadow:0 0 10px var(--teal);animation:pulse 2.5s infinite}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.7)}}
.hdr-right{display:flex;align-items:center;gap:12px}
.hdr-user{font-size:12px;color:var(--sub2);font-weight:500;display:none}
@media(min-width:640px){.hdr-user{display:block}}
.btn-sm{font-family:var(--mono);font-size:10px;letter-spacing:.08em;padding:6px 14px;background:transparent;border:1px solid var(--border2);color:var(--sub2);border-radius:8px;cursor:pointer;text-decoration:none;transition:all .2s}
.btn-sm:hover{border-color:var(--teal);color:var(--teal)}

/* BOTTOM NAV (mobile) */
.bottom-nav{
  position:fixed;bottom:0;left:0;right:0;z-index:300;
  display:flex;
  background:rgba(5,7,14,.95);
  border-top:1px solid var(--border);
  backdrop-filter:blur(24px);
  padding:0 0 env(safe-area-inset-bottom);
}
@media(min-width:768px){.bottom-nav{display:none}}
.bnav-item{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;padding:10px 4px;cursor:pointer;color:var(--sub);transition:color .2s;font-size:9px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;border:none;background:none}
.bnav-item.active{color:var(--teal)}
.bnav-icon{font-size:18px;line-height:1}

/* DESKTOP TABS */
.tabs-bar{
  display:none;
  position:sticky;top:56px;z-index:200;
  background:rgba(5,7,14,.9);border-bottom:1px solid var(--border);
  backdrop-filter:blur(24px);padding:0 24px;
}
@media(min-width:768px){.tabs-bar{display:flex;gap:0}}
.tab{padding:14px 20px;font-size:13px;font-weight:600;color:var(--sub);border-bottom:2px solid transparent;cursor:pointer;transition:all .2s;letter-spacing:.02em;user-select:none}
.tab:hover{color:var(--text)}
.tab.active{color:var(--teal);border-bottom-color:var(--teal)}

/* MAIN */
main{padding:20px;max-width:1400px;margin:0 auto;position:relative;z-index:1}
@media(min-width:768px){main{padding:28px 32px}}
.tab-content{display:none}
.tab-content.active{display:block}

/* CARDS */
.card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:20px;position:relative;overflow:hidden;transition:border-color .3s}
.card:hover{border-color:var(--border2)}
.card-glow::after{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at top left,rgba(0,229,195,.04) 0%,transparent 65%);pointer-events:none}
@media(min-width:768px){.card{padding:24px}}

/* LABELS */
.lbl{font-family:var(--mono);font-size:9px;letter-spacing:.2em;text-transform:uppercase;color:var(--sub);margin-bottom:10px}
.sec-title{font-size:10px;font-weight:700;letter-spacing:.22em;text-transform:uppercase;color:var(--sub);margin-bottom:16px;padding-bottom:10px;border-bottom:1px solid var(--border)}
.section{margin-bottom:32px}

/* GRIDS */
.g2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
.g4{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
@media(min-width:640px){.g4{grid-template-columns:repeat(4,1fr)}}
@media(min-width:768px){.g2{gap:20px}.g3{gap:20px}.g4{gap:16px}}
@media(max-width:639px){.g3{grid-template-columns:1fr 1fr}}

/* ═══════════════════════════════
   3D HERO SECTION
═══════════════════════════════ */
.hero-overview{
  display:grid;
  grid-template-columns:1fr;
  gap:16px;
  margin-bottom:24px;
}
@media(min-width:900px){
  .hero-overview{grid-template-columns:320px 1fr}
  .hero-overview.has-chat{grid-template-columns:280px 1fr 320px}
}

/* 3D FIGURE CARD */
.figure-card{
  background:var(--card);border:1px solid var(--border);
  border-radius:var(--r);overflow:hidden;position:relative;
  display:flex;flex-direction:column;
  min-height:340px;
}
@media(min-width:900px){.figure-card{min-height:420px}}
.figure-card::before{
  content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse at 50% 30%,rgba(0,229,195,.06) 0%,transparent 70%);
  pointer-events:none;z-index:1;
}
#three-canvas{width:100%;height:100%;display:block;position:absolute;inset:0}
.figure-overlay{
  position:absolute;bottom:0;left:0;right:0;z-index:2;
  padding:16px;
  background:linear-gradient(transparent,rgba(5,7,14,.9));
}
.figure-recovery{text-align:center}
.fig-score{font-family:var(--mono);font-size:52px;font-weight:500;line-height:1}
.fig-label{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--sub2);margin-top:2px}
.fig-tag{margin-top:6px;display:flex;justify-content:center}
/* Scan line effect */
.scan-line{position:absolute;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(0,229,195,.4),transparent);animation:scan 4s linear infinite;z-index:2;pointer-events:none}
@keyframes scan{0%{top:0%;opacity:0}10%{opacity:1}90%{opacity:1}100%{top:100%;opacity:0}}
/* Corner brackets */
.corner{position:absolute;width:16px;height:16px;z-index:2;pointer-events:none}
.corner-tl{top:12px;left:12px;border-top:2px solid var(--teal);border-left:2px solid var(--teal)}
.corner-tr{top:12px;right:12px;border-top:2px solid var(--teal);border-right:2px solid var(--teal)}
.corner-bl{bottom:12px;left:12px;border-bottom:2px solid var(--teal);border-left:2px solid var(--teal)}
.corner-br{bottom:12px;right:12px;border-bottom:2px solid var(--teal);border-right:2px solid var(--teal)}

/* METRICS COLUMN */
.metrics-col{display:flex;flex-direction:column;gap:14px}

/* KPI CARDS */
.kpi-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
@media(min-width:500px){.kpi-grid{grid-template-columns:repeat(4,1fr)}}
.kpi{background:var(--card);border:1px solid var(--border);border-radius:var(--r2);padding:14px;text-align:center;position:relative;overflow:hidden}
.kpi::after{content:'';position:absolute;bottom:0;left:0;right:0;height:2px}
.kpi.kpi-teal::after{background:var(--teal)}
.kpi.kpi-purple::after{background:var(--purple2)}
.kpi.kpi-blue::after{background:var(--blue)}
.kpi.kpi-amber::after{background:var(--amber)}
.kpi-val{font-family:var(--mono);font-size:24px;font-weight:500;line-height:1}
.kpi-key{font-size:9px;letter-spacing:.15em;text-transform:uppercase;color:var(--sub);margin-top:5px}
.kpi-delta{font-family:var(--mono);font-size:10px;margin-top:4px}

/* DELTA */
.dlt{display:inline-flex;align-items:center;gap:3px;font-family:var(--mono);font-size:10px;padding:2px 7px;border-radius:5px}
.dlt.up{background:rgba(34,197,94,.12);color:var(--green)}
.dlt.dn{background:rgba(239,68,68,.12);color:var(--red)}
.dlt.fl{background:rgba(100,116,139,.1);color:var(--sub2)}

/* CHART */
.ch{position:relative;height:160px;margin-top:12px}
.ch-tall{position:relative;height:220px;margin-top:12px}
@media(min-width:768px){.ch{height:180px}.ch-tall{height:260px}}

/* INSIGHTS */
.insights{display:flex;flex-direction:column;gap:8px;margin-bottom:20px}
@media(min-width:640px){.insights{flex-direction:row;flex-wrap:wrap}}
.ins{display:flex;align-items:flex-start;gap:10px;padding:12px 14px;border-radius:var(--r2);border:1px solid;font-size:12px;font-weight:500;flex:1;min-width:0}
@media(min-width:640px){.ins{min-width:220px}}
.ins-ico{font-size:16px;flex-shrink:0;margin-top:1px}
.ins.good{background:rgba(34,197,94,.07);border-color:rgba(34,197,94,.2);color:#86efac}
.ins.warn{background:rgba(245,158,11,.07);border-color:rgba(245,158,11,.2);color:#fcd34d}
.ins.info{background:rgba(59,130,246,.07);border-color:rgba(59,130,246,.2);color:#93c5fd}
.ins.bad{background:rgba(239,68,68,.07);border-color:rgba(239,68,68,.2);color:#fca5a5}

/* STAGE BARS */
.stages{display:flex;flex-direction:column;gap:9px;margin-top:14px}
.sr{display:flex;align-items:center;gap:9px}
.sdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.sn{font-size:11px;color:var(--sub2);width:60px;flex-shrink:0}
.sbw{flex:1;background:var(--border);border-radius:3px;height:4px;overflow:hidden}
.sb{height:100%;border-radius:3px;transition:width 1.2s ease}
.sv{font-family:var(--mono);font-size:10px;width:40px;text-align:right;flex-shrink:0}

/* WORKOUT LIST */
.wlist{display:flex;flex-direction:column;gap:8px}
.wi{background:var(--s1);border:1px solid var(--border);border-radius:var(--r2);padding:14px 16px;cursor:pointer;transition:border-color .2s}
.wi:hover,.wi.open{border-color:rgba(0,229,195,.25)}
.wi-h{display:flex;align-items:center;justify-content:space-between;gap:12px}
.wi-l .ws{font-size:13px;font-weight:600;text-transform:capitalize}
.wi-l .wd{font-family:var(--mono);font-size:10px;color:var(--sub);margin-top:2px}
.wi-r{display:flex;gap:16px;align-items:center;flex-shrink:0}
@media(min-width:480px){.wi-r{gap:20px}}
.wst{text-align:right}
.wst-v{font-family:var(--mono);font-size:16px;font-weight:500}
.wst-k{font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--sub);margin-top:1px}
.wi-detail{display:none;margin-top:14px;padding-top:14px;border-top:1px solid var(--border)}
.wi-detail.open{display:block}
.wi-chev{color:var(--sub);transition:transform .3s;font-size:14px;flex-shrink:0}
.wi.open .wi-chev{transform:rotate(180deg)}
.zw{display:flex;gap:4px;align-items:flex-end;height:52px}
.zc{flex:1;display:flex;flex-direction:column;align-items:center;gap:4px}
.zb{width:100%;border-radius:3px 3px 0 0;min-height:4px}
.zl{font-family:var(--mono);font-size:8px;color:var(--sub)}

/* SLEEP LIST */
.slist{display:flex;flex-direction:column;gap:8px}
.sitem{background:var(--s1);border:1px solid var(--border);border-radius:var(--r2);padding:14px 16px}
.sh{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px}
.sd{font-weight:600;font-size:13px}
.sdur{font-family:var(--mono);font-size:10px;color:var(--sub2);margin-top:2px}
.sstats{display:flex;gap:14px;flex-wrap:wrap}
@media(min-width:480px){.sstats{gap:20px}}
.ss-v{font-family:var(--mono);font-size:15px;font-weight:500}
.ss-k{font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--sub);margin-top:1px}
.sbar-row{display:flex;height:6px;border-radius:4px;overflow:hidden;gap:1px;margin-top:10px}
.sbs{border-radius:2px}

/* TAGS */
.tag{display:inline-block;padding:3px 9px;border-radius:5px;font-family:var(--mono);font-size:9px;letter-spacing:.1em;text-transform:uppercase;font-weight:500}
.tg{background:rgba(34,197,94,.15);color:var(--green)}
.ta{background:rgba(245,158,11,.15);color:var(--amber)}
.tr{background:rgba(239,68,68,.15);color:var(--red)}
.tb{background:rgba(59,130,246,.15);color:var(--blue)}

/* COMPARE CARDS */
.cmp-row{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border)}
.cmp-row:last-child{border-bottom:none}
.cmp-label{font-size:12px;color:var(--sub2)}
.cmp-vals{display:flex;align-items:center;gap:16px}
.cmp-now{font-family:var(--mono);font-size:16px;font-weight:500}
.cmp-prev{font-family:var(--mono);font-size:12px;color:var(--sub)}

/* ═══════════════════════════════
   AI CHAT
═══════════════════════════════ */
.chat-fab{
  position:fixed;bottom:80px;right:20px;z-index:400;
  width:52px;height:52px;border-radius:50%;
  background:linear-gradient(135deg,var(--teal2),var(--purple));
  border:none;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  font-size:22px;
  box-shadow:0 4px 20px rgba(0,229,195,.3);
  transition:transform .2s,box-shadow .2s;
}
@media(min-width:768px){.chat-fab{bottom:24px}}
.chat-fab:hover{transform:scale(1.08);box-shadow:0 6px 28px rgba(0,229,195,.4)}
.chat-panel{
  position:fixed;bottom:0;right:0;z-index:500;
  width:100%;max-width:380px;
  height:500px;max-height:80vh;
  background:var(--card);
  border:1px solid var(--border);
  border-radius:20px 20px 0 0;
  display:flex;flex-direction:column;
  transform:translateY(100%);
  transition:transform .35s cubic-bezier(.4,0,.2,1);
  box-shadow:0 -8px 40px rgba(0,0,0,.5);
}
@media(min-width:768px){
  .chat-panel{
    bottom:24px;right:24px;
    border-radius:20px;
    height:480px;
    transform:translateY(20px) scale(.95);
    opacity:0;
    transition:transform .3s cubic-bezier(.4,0,.2,1),opacity .3s;
  }
}
.chat-panel.open{transform:translateY(0);opacity:1}
@media(min-width:768px){.chat-panel.open{transform:translateY(0) scale(1)}}
.chat-head{
  display:flex;align-items:center;justify-content:space-between;
  padding:16px 18px;border-bottom:1px solid var(--border);flex-shrink:0;
}
.chat-head-info{display:flex;align-items:center;gap:10px}
.chat-avatar{
  width:32px;height:32px;border-radius:50%;
  background:linear-gradient(135deg,var(--teal2),var(--purple));
  display:flex;align-items:center;justify-content:center;
  font-size:14px;
}
.chat-title{font-size:14px;font-weight:600}
.chat-sub{font-size:10px;color:var(--teal);font-family:var(--mono);letter-spacing:.08em}
.chat-close{background:none;border:none;color:var(--sub);cursor:pointer;font-size:20px;padding:0;line-height:1;transition:color .2s}
.chat-close:hover{color:var(--text)}
.chat-msgs{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px;scroll-behavior:smooth}
.chat-msgs::-webkit-scrollbar{width:4px}
.chat-msgs::-webkit-scrollbar-track{background:transparent}
.chat-msgs::-webkit-scrollbar-thumb{background:var(--border2);border-radius:2px}
.msg{display:flex;gap:8px;align-items:flex-end}
.msg.user{flex-direction:row-reverse}
.msg-bubble{
  max-width:82%;padding:10px 14px;border-radius:16px;
  font-size:13px;line-height:1.5;
}
.msg.ai .msg-bubble{background:var(--s2);border:1px solid var(--border);border-bottom-left-radius:4px;color:var(--text)}
.msg.user .msg-bubble{background:linear-gradient(135deg,var(--teal2),#00c4a6);color:#000;font-weight:500;border-bottom-right-radius:4px}
.msg-avatar{width:24px;height:24px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:11px}
.msg.ai .msg-avatar{background:linear-gradient(135deg,var(--teal2),var(--purple))}
.msg.user .msg-avatar{background:var(--border2);color:var(--sub2)}
.typing{display:flex;gap:4px;padding:10px 14px}
.td{width:6px;height:6px;border-radius:50%;background:var(--sub);animation:td .8s infinite}
.td:nth-child(2){animation-delay:.2s}
.td:nth-child(3){animation-delay:.4s}
@keyframes td{0%,60%,100%{transform:translateY(0);opacity:.4}30%{transform:translateY(-6px);opacity:1}}
.chat-input-row{
  display:flex;gap:8px;padding:14px 16px;
  border-top:1px solid var(--border);flex-shrink:0;
}
.chat-input{
  flex:1;background:var(--s2);border:1px solid var(--border);
  color:var(--text);border-radius:12px;padding:10px 14px;
  font-family:'Space Grotesk',sans-serif;font-size:13px;
  resize:none;outline:none;transition:border-color .2s;max-height:80px;
}
.chat-input:focus{border-color:var(--teal)}
.chat-send{
  width:40px;height:40px;border-radius:12px;flex-shrink:0;
  background:linear-gradient(135deg,var(--teal2),#00c4a6);
  border:none;cursor:pointer;color:#000;font-size:16px;
  display:flex;align-items:center;justify-content:center;
  transition:opacity .2s;font-weight:700;
}
.chat-send:hover{opacity:.85}
.chat-send:disabled{opacity:.4;cursor:not-allowed}
.chat-suggestions{display:flex;flex-wrap:wrap;gap:6px;padding:0 16px 10px}
.sugg{background:var(--s2);border:1px solid var(--border);color:var(--sub2);border-radius:20px;padding:5px 12px;font-size:11px;cursor:pointer;transition:all .2s;white-space:nowrap}
.sugg:hover{border-color:var(--teal);color:var(--teal)}

/* WEEKLY COMPARE */
.wk-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(min-width:768px){.wk-grid{grid-template-columns:repeat(4,1fr)}}

/* CORRELATION */
.corr-wrap{position:relative;height:220px;margin-top:12px}

/* RECORDS */
.rec-list{display:flex;flex-direction:column;gap:0}
.rec-item{display:flex;align-items:center;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--border)}
.rec-item:last-child{border:none}
.rec-name{font-size:12px;color:var(--sub2)}
.rec-right{display:flex;align-items:center;gap:12px}
.rec-val{font-family:var(--mono);font-size:18px;font-weight:500}
.rec-date{font-family:var(--mono);font-size:10px;color:var(--sub)}

/* PROFILE PILL */
.profile-pill{
  display:flex;align-items:center;gap:14px;
  padding:16px 20px;margin-bottom:20px;
  background:var(--card);border:1px solid var(--border);border-radius:var(--r);
  position:relative;overflow:hidden;
}
.profile-pill::before{content:'';position:absolute;inset:0;background:linear-gradient(90deg,rgba(0,229,195,.04) 0%,transparent 50%);pointer-events:none}
.pav{width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,var(--teal2),var(--purple));display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:800;flex-shrink:0;box-shadow:0 0 20px rgba(0,229,195,.2)}
.pname{font-size:18px;font-weight:700}
.pemail{font-size:11px;color:var(--sub2);margin-top:2px}
.pstats{display:none;margin-left:auto;gap:28px}
@media(min-width:640px){.pstats{display:flex}}
.ps-v{font-family:var(--mono);font-size:18px;font-weight:500}
.ps-k{font-size:9px;letter-spacing:.15em;text-transform:uppercase;color:var(--sub);margin-top:3px}

/* ANIM */
@keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.fu{animation:fadeUp .4s ease forwards;opacity:0}
.fu:nth-child(1){animation-delay:.04s}
.fu:nth-child(2){animation-delay:.08s}
.fu:nth-child(3){animation-delay:.12s}
.fu:nth-child(4){animation-delay:.16s}
.fu:nth-child(5){animation-delay:.2s}
.fu:nth-child(6){animation-delay:.24s}

/* COUNTER ANIM */
.count{display:inline-block}

/* SLEEP DEBT */
.debt-bar{height:8px;background:var(--border);border-radius:4px;overflow:hidden;margin-top:8px}
.debt-fill{height:100%;border-radius:4px;transition:width 1s ease}
</style>
</head>
<body>
<div class="bg-orb orb1"></div>
<div class="bg-orb orb2"></div>
<div class="bg-grid"></div>

<header>
  <a href="#" class="logo"><div class="pulse-dot"></div>WHOOP</a>
  <div class="hdr-right">
    <span class="hdr-user" id="hdr-user"></span>
    <a href="/logout" class="btn-sm">Salir</a>
  </div>
</header>

<nav class="tabs-bar">
  <div class="tab active" data-tab="overview">Resumen</div>
  <div class="tab" data-tab="sleep">Sueño</div>
  <div class="tab" data-tab="training">Entrena</div>
  <div class="tab" data-tab="body">Cuerpo</div>
  <div class="tab" data-tab="analytics">Análisis</div>
</nav>

<main>

<!-- ═══ OVERVIEW ═══ -->
<div class="tab-content active" id="tab-overview">

  <div id="veredicto" class="fu" style="margin-bottom:16px;padding:14px 20px;border-radius:14px;border:1px solid;display:flex;align-items:center;gap:14px;position:relative;overflow:hidden"></div>

  <div class="profile-pill fu">
    <div class="pav" id="pav">?</div>
    <div><div class="pname" id="pname">—</div><div class="pemail" id="pemail">—</div></div>
    <div class="pstats">
      <div><div class="ps-v" id="ps-h">—</div><div class="ps-k">Altura</div></div>
      <div><div class="ps-v" id="ps-w">—</div><div class="ps-k">Peso</div></div>
      <div><div class="ps-v" id="ps-hr">—</div><div class="ps-k">FC Máx</div></div>
    </div>
  </div>

  <div class="insights fu" id="insights"></div>

  <div class="hero-overview fu">
    <!-- 3D PARTICLE BODY -->
    <div class="figure-card" id="figure-card">
      <canvas id="three-canvas"></canvas>
      <div class="scan-line"></div>
      <div class="corner corner-tl"></div>
      <div class="corner corner-tr"></div>
      <div class="corner corner-bl"></div>
      <div class="corner corner-br"></div>
      <div class="figure-overlay">
        <div class="figure-recovery">
          <div class="fig-score count" id="fig-score" style="color:var(--teal)">—</div>
          <div class="fig-label">Recovery Score</div>
          <div class="fig-tag" id="fig-tag"></div>
        </div>
      </div>
    </div>

    <!-- METRICS PANEL -->
    <div class="metrics-col">
      <!-- KPIs -->
      <div class="kpi-grid fu">
        <div class="kpi kpi-teal">
          <div class="kpi-val count" id="kpi-hrv" style="color:var(--teal)">—</div>
          <div class="kpi-key">HRV ms</div>
          <div class="kpi-delta" id="d-hrv"></div>
        </div>
        <div class="kpi kpi-purple">
          <div class="kpi-val count" id="kpi-rhr" style="color:var(--purple2)">—</div>
          <div class="kpi-key">FC Reposo</div>
          <div class="kpi-delta" id="d-rhr"></div>
        </div>
        <div class="kpi kpi-blue">
          <div class="kpi-val" id="kpi-spo2" style="color:var(--blue)">—</div>
          <div class="kpi-key">SpO₂ %</div>
        </div>
        <div class="kpi kpi-amber">
          <div class="kpi-val count" id="kpi-strain" style="color:var(--amber)">—</div>
          <div class="kpi-key">Strain hoy</div>
        </div>
      </div>

      <!-- 7-day trend chart -->
      <div class="card card-glow fu">
        <div class="lbl">Tendencia 7 días — Recovery & HRV</div>
        <div class="ch-tall"><canvas id="chTrend"></canvas></div>
      </div>

      <!-- Sleep summary -->
      <div class="g2 fu">
        <div class="card">
          <div class="lbl">Último sueño</div>
          <div style="display:flex;align-items:baseline;gap:4px">
            <div class="kpi-val count" id="sl-perf" style="color:var(--amber);font-size:40px">—</div>
            <div style="color:var(--sub2)">%</div>
          </div>
          <div style="font-family:var(--mono);font-size:11px;color:var(--sub2);margin-top:4px" id="sl-dur">—</div>
          <div id="sl-perf-d" style="margin-top:6px"></div>
          <div class="stages" id="sl-stages"></div>
        </div>
        <div class="card">
          <div class="lbl">Sueño — Etapas</div>
          <div class="ch"><canvas id="chDonut"></canvas></div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-top:10px;font-size:10px" id="donut-legend"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- Weekly compare -->
  <div class="section fu">
    <div class="sec-title">Esta semana vs semana anterior</div>
    <div class="wk-grid" id="wk-grid"></div>
  </div>

</div><!-- /overview -->


<!-- ═══ SLEEP ═══ -->
<div class="tab-content" id="tab-sleep">
  <div class="section">
    <div class="sec-title">Tendencia de sueño (últimas noches)</div>
    <div class="card card-glow">
      <div class="ch-tall"><canvas id="chSleepTrend"></canvas></div>
    </div>
  </div>
  <div class="section">
    <div class="sec-title">Deuda de sueño acumulada</div>
    <div class="card card-glow" id="sleep-debt-card"></div>
  </div>
  <div class="section">
    <div class="sec-title">Historial detallado</div>
    <div class="slist" id="sleep-list"></div>
  </div>
</div>


<!-- ═══ TRAINING ═══ -->
<div class="tab-content" id="tab-training">
  <div class="section">
    <div class="sec-title">Strain diario (últimas 2 semanas)</div>
    <div class="card card-glow">
      <div class="ch-tall"><canvas id="chStrain"></canvas></div>
    </div>
  </div>
  <div class="section">
    <div class="sec-title">Récords personales</div>
    <div class="card" id="records-card"></div>
  </div>
  <div class="section">
    <div class="sec-title">Workouts recientes</div>
    <div class="wlist" id="workout-list"></div>
  </div>
</div>


<!-- ═══ BODY ═══ -->
<div class="tab-content" id="tab-body">
  <div class="g3 fu" style="margin-bottom:20px">
    <div class="card card-glow" style="text-align:center;padding:28px">
      <div class="lbl">Altura</div>
      <div class="kpi-val count" id="b-h" style="color:var(--teal);font-size:40px">—</div>
      <div style="color:var(--sub2);font-size:14px">cm</div>
    </div>
    <div class="card card-glow" style="text-align:center;padding:28px">
      <div class="lbl">Peso</div>
      <div class="kpi-val count" id="b-w" style="color:var(--purple2);font-size:40px">—</div>
      <div style="color:var(--sub2);font-size:14px">kg</div>
    </div>
    <div class="card card-glow" style="text-align:center;padding:28px">
      <div class="lbl">FC Máxima</div>
      <div class="kpi-val count" id="b-mhr" style="color:var(--red);font-size:40px">—</div>
      <div style="color:var(--sub2);font-size:14px">bpm</div>
    </div>
  </div>
  <div class="g2 fu" style="margin-bottom:20px">
    <div class="card card-glow">
      <div class="lbl">HRV histórico (ms)</div>
      <div class="ch-tall"><canvas id="chHRV"></canvas></div>
    </div>
    <div class="card card-glow">
      <div class="lbl">FC en reposo (bpm)</div>
      <div class="ch-tall"><canvas id="chRHR"></canvas></div>
    </div>
  </div>
  <div class="card card-glow fu">
    <div class="lbl">SpO₂ histórico (%)</div>
    <div class="ch"><canvas id="chSpo2"></canvas></div>
  </div>
</div>


<!-- ═══ ANALYTICS ═══ -->
<div class="tab-content" id="tab-analytics">
  <div class="g2 fu" style="margin-bottom:20px">
    <div class="card card-glow">
      <div class="lbl">Correlación — Sueño vs Recovery</div>
      <div class="corr-wrap"><canvas id="chCorr"></canvas></div>
    </div>
    <div class="card card-glow">
      <div class="lbl">Distribución de Recovery</div>
      <div class="ch-tall"><canvas id="chDist"></canvas></div>
    </div>
  </div>
  <div class="card card-glow fu" style="margin-bottom:20px">
    <div class="lbl">Promedio semanal — Recovery & HRV (últimas 8 semanas)</div>
    <div class="ch-tall"><canvas id="chWeekly"></canvas></div>
  </div>
  <div class="g2 fu">
    <div class="card">
      <div class="lbl">Mejores promedios semanales</div>
      <div class="rec-list" id="best-weeks"></div>
    </div>
    <div class="card">
      <div class="lbl">Estadísticas generales</div>
      <div class="rec-list" id="general-stats"></div>
    </div>
  </div>
</div>

</main><!-- /main -->

<!-- BOTTOM NAV -->
<nav class="bottom-nav">
  <button class="bnav-item active" data-tab="overview"><span class="bnav-icon">⬡</span>Resumen</button>
  <button class="bnav-item" data-tab="sleep"><span class="bnav-icon">🌙</span>Sueño</button>
  <button class="bnav-item" data-tab="training"><span class="bnav-icon">⚡</span>Entrena</button>
  <button class="bnav-item" data-tab="body"><span class="bnav-icon">💪</span>Cuerpo</button>
  <button class="bnav-item" data-tab="analytics"><span class="bnav-icon">📊</span>Análisis</button>
</nav>

<!-- AI CHAT FAB -->
<button class="chat-fab" id="chat-fab" title="Coach IA">🤖</button>

<!-- AI CHAT PANEL -->
<div class="chat-panel" id="chat-panel">
  <div class="chat-head">
    <div class="chat-head-info">
      <div class="chat-avatar">🤖</div>
      <div>
        <div class="chat-title">Coach IA</div>
        <div class="chat-sub">Powered by Claude</div>
      </div>
    </div>
    <button class="chat-close" id="chat-close">×</button>
  </div>
  <div class="chat-msgs" id="chat-msgs">
    <div class="msg ai">
      <div class="msg-avatar">🤖</div>
      <div class="msg-bubble">¡Hola! Soy tu coach de rendimiento. Tengo acceso a todos tus datos WHOOP. ¿Qué quieres saber hoy? 💪</div>
    </div>
  </div>
  <div class="chat-suggestions" id="chat-sugg">
    <span class="sugg">¿Debo entrenar hoy?</span>
    <span class="sugg">¿Cómo estuvo mi semana?</span>
    <span class="sugg">¿Por qué bajó mi HRV?</span>
    <span class="sugg">Análisis de sueño</span>
  </div>
  <div class="chat-input-row">
    <textarea class="chat-input" id="chat-input" placeholder="Pregunta algo sobre tu salud..." rows="1"></textarea>
    <button class="chat-send" id="chat-send">↑</button>
  </div>
</div>

<script>
const RAW = {{ data | safe }};

// ── UTILS ─────────────────────────────────────────────────
const $  = id => document.getElementById(id);
const f1 = v => v!=null?Number(v).toFixed(1):'—';
const f0 = v => v!=null?Math.round(v)+'':'—';
function msH(ms){if(!ms)return'—';const h=Math.floor(ms/3600000),m=Math.floor((ms%3600000)/60000);return`${h}h ${m}m`}
function fDate(s,sh=false){if(!s)return'—';const d=new Date(s);return d.toLocaleDateString('es-CO',sh?{month:'short',day:'numeric'}:{weekday:'short',month:'short',day:'numeric'})}
function rCol(s){return s>=67?'#22c55e':s>=34?'#f59e0b':'#ef4444'}
function rTag(s){const[c,t]=s>=67?['tg','Óptimo']:s>=34?['ta','Moderado']:['tr','Bajo'];return`<span class="tag ${c}">${t}</span>`}
function dlt(c,p,u='',inv=false){
  if(c==null||p==null)return'';
  const d=c-p;
  if(Math.abs(d)<0.4)return'<span class="dlt fl">= Sin cambio</span>';
  const up=inv?d<0:d>0;
  return`<span class="dlt ${up?'up':'dn'}">${up?'↑':'↓'} ${d>0?'+':''}${f1(d)}${u}</span>`;
}
function animCount(el,to,dur=1000,dec=0){
  if(to==null||isNaN(to)){el.textContent='—';return}
  const start=performance.now();
  const from=0;
  function step(now){
    const p=Math.min((now-start)/dur,1);
    const v=from+(to-from)*p;
    el.textContent=dec>0?v.toFixed(dec):Math.round(v);
    if(p<1)requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
const CHART_OPTS={
  responsive:true,maintainAspectRatio:false,
  plugins:{legend:{display:false},tooltip:{backgroundColor:'#0f1422',borderColor:'#18203a',borderWidth:1,titleColor:'#e2e8f0',bodyColor:'#718096',padding:12,cornerRadius:10}},
  scales:{
    x:{grid:{color:'rgba(255,255,255,.03)'},ticks:{color:'#4a5568',font:{size:9}}},
    y:{grid:{color:'rgba(255,255,255,.03)'},ticks:{color:'#4a5568',font:{size:9}}}
  }
};

// ── DATA ──────────────────────────────────────────────────
const prof=RAW.profile||{},body=RAW.body||{};
const recs=RAW.recovery||[],sleeps=RAW.sleep||[],wrks=RAW.workouts||[],cycs=RAW.cycles||[];
const mainSl=sleeps.filter(s=>!s.nap);
const scRecs=recs.filter(r=>r.score_state==='SCORED'&&r.score);
const scSl=mainSl.filter(s=>s.score_state==='SCORED'&&s.score);
const r0=scRecs[0],r1=scRecs[1];
const sl0=scSl[0],sl1=scSl[1];

// ── PROFILE ───────────────────────────────────────────────
const fn=prof.first_name||'',ln=prof.last_name||'';
$('pav').textContent=fn[0]||'?';
$('pname').textContent=[fn,ln].filter(Boolean).join(' ')||'—';
$('pemail').textContent=prof.email||'—';
$('hdr-user').textContent=fn||'';
$('ps-h').textContent=body.height_meter?Math.round(body.height_meter*100)+'cm':'—';
$('ps-w').textContent=body.weight_kilogram?body.weight_kilogram.toFixed(1)+'kg':'—';
$('ps-hr').textContent=body.max_heart_rate?body.max_heart_rate+'bpm':'—';
$('b-h').textContent=body.height_meter?Math.round(body.height_meter*100):'—';
$('b-w').textContent=body.weight_kilogram?body.weight_kilogram.toFixed(1):'—';
$('b-mhr').textContent=body.max_heart_rate||'—';

// ── RECOVERY SCORE ────────────────────────────────────────
let currentScore=0;
if(r0){
  const sc=r0.score;
  currentScore=Math.round(sc.recovery_score);
  animCount($('fig-score'),currentScore,1200);
  $('fig-tag').innerHTML=rTag(currentScore);
  animCount($('kpi-hrv'),sc.hrv_rmssd_milli,1000,1);
  animCount($('kpi-rhr'),sc.resting_heart_rate,1000);
  $('kpi-spo2').textContent=sc.spo2_percentage?f1(sc.spo2_percentage):'—';
  if(r1){
    $('d-hrv').innerHTML=dlt(sc.hrv_rmssd_milli,r1.score.hrv_rmssd_milli,' ms');
    $('d-rhr').innerHTML=dlt(sc.resting_heart_rate,r1.score.resting_heart_rate,' bpm',true);
  }
}
if(cycs.length&&cycs[0].score) animCount($('kpi-strain'),cycs[0].score.strain,1000,1);

// ── SLEEP OVERVIEW ────────────────────────────────────────
if(sl0){
  const ss=sl0.score,st=ss.stage_summary;
  animCount($('sl-perf'),Math.round(ss.sleep_performance_percentage||0),1000);
  const dur=sl0.start&&sl0.end?msH(new Date(sl0.end)-new Date(sl0.start)):'—';
  $('sl-dur').textContent='Duración: '+dur+' · Eficiencia: '+(ss.sleep_efficiency_percentage||0).toFixed(0)+'%';
  if(sl1)$('sl-perf-d').innerHTML=dlt(Math.round(ss.sleep_performance_percentage||0),Math.round(sl1.score.sleep_performance_percentage||0),'%');
  if(st){
    const tot=st.total_in_bed_time_milli||1;
    const stgs=[{n:'Ligero',v:st.total_light_sleep_time_milli,c:'#60a5fa'},{n:'Profundo',v:st.total_slow_wave_sleep_time_milli,c:'#00e5c3'},{n:'REM',v:st.total_rem_sleep_time_milli,c:'#a78bfa'},{n:'Despierto',v:st.total_awake_time_milli,c:'#475569'}];
    $('sl-stages').innerHTML=stgs.map(sg=>{const p=Math.round((sg.v||0)/tot*100);return`<div class="sr"><div class="sdot" style="background:${sg.c}"></div><div class="sn">${sg.n}</div><div class="sbw"><div class="sb" style="width:${p}%;background:${sg.c}"></div></div><div class="sv">${msH(sg.v)}</div></div>`}).join('');
    // Donut
    new Chart($('chDonut'),{type:'doughnut',data:{labels:stgs.map(s=>s.n),datasets:[{data:stgs.map(s=>Math.round((s.v||0)/60000)),backgroundColor:stgs.map(s=>s.c),borderWidth:0,hoverOffset:4}]},options:{responsive:true,maintainAspectRatio:false,cutout:'75%',plugins:{legend:{display:false},tooltip:{backgroundColor:'#0f1422',borderColor:'#18203a',borderWidth:1,bodyColor:'#718096',padding:10,callbacks:{label:c=>' '+msH(c.raw*60000)}}}}});
    $('donut-legend').innerHTML=stgs.map(s=>`<div style="display:flex;align-items:center;gap:4px"><div style="width:6px;height:6px;border-radius:50%;background:${s.c};flex-shrink:0"></div><span style="font-size:9px;color:#718096">${s.n} ${msH(s.v)}</span></div>`).join('');
  }
}

// ── INSIGHTS ──────────────────────────────────────────────
const iEl=$('insights'),iList=[];
if(r0){
  const sc=r0.score,s=currentScore;
  if(s>=80)iList.push({c:'good',i:'💚',t:`Recovery excelente hoy (${s}%) — perfecto para entrenar fuerte`});
  else if(s>=50)iList.push({c:'info',i:'💛',t:`Recovery moderado (${s}%) — entrena con control`});
  else iList.push({c:'bad',i:'🔴',t:`Recovery bajo (${s}%) — prioriza descanso hoy`});
  if(sc.hrv_rmssd_milli&&scRecs.length>=3){
    const avg=scRecs.slice(0,7).reduce((a,r)=>a+(r.score.hrv_rmssd_milli||0),0)/Math.min(scRecs.length,7);
    if(sc.hrv_rmssd_milli>avg*1.1)iList.push({c:'good',i:'📈',t:`HRV de ${f1(sc.hrv_rmssd_milli)}ms — por encima de tu promedio semanal`});
    else if(sc.hrv_rmssd_milli<avg*.85)iList.push({c:'warn',i:'⚠️',t:`HRV bajo respecto a tu promedio — señal de fatiga`});
  }
}
if(sl0&&sl0.score){
  const p=Math.round(sl0.score.sleep_performance_percentage||0);
  if(p<60)iList.push({c:'warn',i:'😴',t:`Sueño insuficiente anoche (${p}%) — intenta acostarte más temprano`});
  if(sl0.score.stage_summary){
    const rem=sl0.score.stage_summary.total_rem_sleep_time_milli||0;
    if(rem>0&&rem<3600000)iList.push({c:'info',i:'🧠',t:`Bajo REM anoche (${msH(rem)}) — el óptimo es 90-120 min`});
  }
}
if(iList.length===0)iList.push({c:'info',i:'📊',t:'Sigue usando WHOOP para ver más insights personalizados'});
iEl.innerHTML=iList.slice(0,3).map(i=>`<div class="ins ${i.c}"><span class="ins-ico">${i.i}</span><span>${i.t}</span></div>`).join('');

// ── VEREDICTO DEL DÍA ─────────────────────────────────
{
  const vEl=$('veredicto');
  let vTitle='',vSub='',vColor='',vBg='',vIcon='';
  if(r0&&sl0){
    const rec=currentScore;
    const slp=Math.round((sl0.score.sleep_performance_percentage||0));
    const combined=(rec+slp)/2;
    if(combined>=75){vTitle='HOY: LISTO PARA ENTRENAR FUERTE';vSub=`Recovery ${rec}% · Sueño ${slp}% — Tu cuerpo está en óptimas condiciones`;vColor='#22c55e';vBg='rgba(34,197,94,.08)';vIcon='🔥'}
    else if(combined>=55){vTitle='HOY: ENTRENA CON CONTROL';vSub=`Recovery ${rec}% · Sueño ${slp}% — Evita máximo esfuerzo, prioriza técnica`;vColor='#f59e0b';vBg='rgba(245,158,11,.08)';vIcon='⚡'}
    else if(combined>=35){vTitle='HOY: ENTRENAMIENTO LIGERO';vSub=`Recovery ${rec}% · Sueño ${slp}% — Solo movilidad o cardio suave`;vColor='#f97316';vBg='rgba(249,115,22,.08)';vIcon='🚶'}
    else{vTitle='HOY: DÍA DE DESCANSO';vSub=`Recovery ${rec}% · Sueño ${slp}% — Tu cuerpo necesita recuperarse`;vColor='#ef4444';vBg='rgba(239,68,68,.08)';vIcon='😴'}
  } else if(r0){
    const rec=currentScore;
    if(rec>=67){vTitle='HOY: LISTO PARA ENTRENAR';vSub=`Recovery ${rec}% — Buen día para esfuerzo moderado-alto`;vColor='#22c55e';vBg='rgba(34,197,94,.08)';vIcon='💪'}
    else if(rec>=34){vTitle='HOY: ENTRENA CON MODERACIÓN';vSub=`Recovery ${rec}% — Escucha tu cuerpo`;vColor='#f59e0b';vBg='rgba(245,158,11,.08)';vIcon='⚡'}
    else{vTitle='HOY: DESCANSA';vSub=`Recovery ${rec}% — Prioriza la recuperación`;vColor='#ef4444';vBg='rgba(239,68,68,.08)';vIcon='😴'}
  }
  if(vTitle){
    vEl.style.background=vBg;
    vEl.style.borderColor=vColor.replace(')',', .3)').replace('rgb','rgba');
    vEl.innerHTML=`
      <div style="font-size:28px;flex-shrink:0">${vIcon}</div>
      <div style="flex:1">
        <div style="font-size:13px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:${vColor}">${vTitle}</div>
        <div style="font-size:12px;color:var(--sub2);margin-top:3px">${vSub}</div>
      </div>
      <div style="font-family:var(--mono);font-size:10px;color:${vColor};letter-spacing:.12em;text-transform:uppercase;flex-shrink:0;text-align:right;display:none" id="verd-time"></div>`;
    // Show time
    const now=new Date();
    const tEl=vEl.querySelector('#verd-time');
    if(tEl){tEl.style.display='block';tEl.textContent=now.toLocaleTimeString('es-CO',{hour:'2-digit',minute:'2-digit'});}
  } else {
    vEl.style.display='none';
  }
}

// ── WEEKLY COMPARE ────────────────────────────────────────
{
  const now=new Date();
  const w0start=new Date(now-7*86400000);
  const w1start=new Date(now-14*86400000);
  function weekAvg(arr,field,days0,days1){
    const slice=arr.filter(r=>{const d=new Date(r.created_at||r.start);return d>=days0&&d<days1});
    const vals=slice.map(r=>r.score?Number(r.score[field]||0):0).filter(v=>v>0);
    return vals.length?vals.reduce((a,b)=>a+b,0)/vals.length:null;
  }
  const metrics=[
    {k:'Recovery %',field:'recovery_score',src:scRecs,dec:0,col:'var(--teal)'},
    {k:'HRV ms',field:'hrv_rmssd_milli',src:scRecs,dec:1,col:'var(--purple2)'},
    {k:'FC Reposo',field:'resting_heart_rate',src:scRecs,dec:0,col:'var(--blue)'},
    {k:'Strain',field:'strain',src:cycs.filter(c=>c.score),dec:1,col:'var(--amber)'},
  ];
  $('wk-grid').innerHTML=metrics.map(m=>{
    const cur=weekAvg(m.src,m.field,w0start,now);
    const prev=weekAvg(m.src,m.field,w1start,w0start);
    const d=cur&&prev?dlt(cur,prev,'',(m.field==='resting_heart_rate')):'';
    return`<div class="card"><div class="lbl">${m.k}</div><div class="kpi-val" style="color:${m.col};font-size:32px">${cur!=null?cur.toFixed(m.dec):'—'}</div><div style="font-size:10px;color:var(--sub2);margin-top:2px">Esta semana</div>${d?`<div style="margin-top:6px">${d} <span style="font-size:9px;color:var(--sub)">vs sem ant.</span></div>`:''}</div>`;
  }).join('');
}

// ── CHART: TREND ──────────────────────────────────────────
{
  const l7=scRecs.slice(0,7).reverse();
  const labels=l7.map(r=>fDate(r.created_at,true));
  const ctx=$('chTrend').getContext('2d');
  const g1=ctx.createLinearGradient(0,0,0,260);g1.addColorStop(0,'rgba(0,229,195,.2)');g1.addColorStop(1,'rgba(0,229,195,0)');
  const g2=ctx.createLinearGradient(0,0,0,260);g2.addColorStop(0,'rgba(167,139,250,.15)');g2.addColorStop(1,'rgba(167,139,250,0)');
  new Chart(ctx,{type:'line',data:{labels,datasets:[
    {label:'Recovery %',data:l7.map(r=>Math.round(r.score.recovery_score)),borderColor:'#00e5c3',backgroundColor:g1,borderWidth:2.5,pointRadius:4,pointBackgroundColor:'#00e5c3',tension:.4,fill:true,yAxisID:'y'},
    {label:'HRV ms',data:l7.map(r=>+f1(r.score.hrv_rmssd_milli)),borderColor:'#a78bfa',backgroundColor:g2,borderWidth:2,pointRadius:3,pointBackgroundColor:'#a78bfa',tension:.4,fill:true,yAxisID:'y2'},
  ]},options:{...CHART_OPTS,plugins:{...CHART_OPTS.plugins,legend:{labels:{color:'#718096',font:{size:10},boxWidth:10,padding:14}}},interaction:{mode:'index',intersect:false},scales:{x:{...CHART_OPTS.scales.x},y:{...CHART_OPTS.scales.y,min:0,max:100},y2:{position:'right',grid:{display:false},ticks:{color:'#a78bfa',font:{size:9}}}}}});
}

// ── CHART: SLEEP TREND ────────────────────────────────────
{
  const l=scSl.slice(0,7).reverse();
  new Chart($('chSleepTrend'),{type:'bar',data:{labels:l.map(s=>fDate(s.start,true)),datasets:[
    {label:'Performance %',data:l.map(s=>Math.round(s.score.sleep_performance_percentage||0)),backgroundColor:'rgba(245,158,11,.7)',borderRadius:5,yAxisID:'y'},
    {label:'Eficiencia %',data:l.map(s=>+(s.score.sleep_efficiency_percentage||0).toFixed(1)),backgroundColor:'rgba(59,130,246,.5)',borderRadius:5,yAxisID:'y'},
    {label:'REM h',data:l.map(s=>+((s.score.stage_summary?.total_rem_sleep_time_milli||0)/3600000).toFixed(2)),backgroundColor:'rgba(167,139,250,.7)',borderRadius:5,yAxisID:'y2'},
    {label:'Profundo h',data:l.map(s=>+((s.score.stage_summary?.total_slow_wave_sleep_time_milli||0)/3600000).toFixed(2)),backgroundColor:'rgba(0,229,195,.5)',borderRadius:5,yAxisID:'y2'},
  ]},options:{...CHART_OPTS,interaction:{mode:'index',intersect:false},plugins:{...CHART_OPTS.plugins,legend:{labels:{color:'#718096',font:{size:10},boxWidth:10,padding:12}}},scales:{x:{...CHART_OPTS.scales.x},y:{...CHART_OPTS.scales.y,min:0,max:100},y2:{position:'right',grid:{display:false},ticks:{color:'#718096',font:{size:9}}}}}});
}

// ── SLEEP DEBT ────────────────────────────────────────────
{
  const card=$('sleep-debt-card');
  const debtDays=scSl.slice(0,7);
  let totalDebt=0;
  const rows=debtDays.map(sl=>{
    const sn=sl.score;
    const needed=(sn.sleep_needed?.baseline_milli||27000000);
    const actual=(sl.score.stage_summary?.total_in_bed_time_milli||0);
    const debt=Math.max(0,needed-actual);
    totalDebt+=debt;
    const pct=Math.min(100,Math.round(debt/needed*100));
    return{date:fDate(sl.start,true),debt,needed,pct};
  });
  card.innerHTML=`<div class="lbl">Deuda de sueño (últimos 7 días)</div>
    <div style="font-family:var(--mono);font-size:32px;font-weight:500;color:${totalDebt>14400000?'var(--red)':totalDebt>7200000?'var(--amber)':'var(--green)'}">-${msH(totalDebt)}</div>
    <div style="font-size:11px;color:var(--sub2);margin-top:4px;margin-bottom:16px">Total acumulado esta semana</div>
    ${rows.map(r=>`<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px"><span style="color:var(--sub2)">${r.date}</span><span style="font-family:var(--mono);color:${r.pct>20?'var(--red)':r.pct>10?'var(--amber)':'var(--green)'}">-${msH(r.debt)}</span></div><div class="debt-bar"><div class="debt-fill" style="width:${r.pct}%;background:${r.pct>20?'var(--red)':r.pct>10?'var(--amber)':'var(--green)'}"></div></div></div>`).join('')}`;
}

// ── SLEEP LIST ────────────────────────────────────────────
{
  const el=$('sleep-list');
  mainSl.slice(0,14).forEach(sl=>{
    const sc=sl.score_state==='SCORED'&&sl.score?sl.score:null;
    const perf=sc&&sc.sleep_performance_percentage?Math.round(sc.sleep_performance_percentage):null;
    const eff=sc?+(sc.sleep_efficiency_percentage||0).toFixed(0):null;
    const dur=sl.start&&sl.end?msH(new Date(sl.end)-new Date(sl.start)):'—';
    const rem=sc&&sc.stage_summary?msH(sc.stage_summary.total_rem_sleep_time_milli):'—';
    const sws=sc&&sc.stage_summary?msH(sc.stage_summary.total_slow_wave_sleep_time_milli):'—';
    const st=sc&&sc.stage_summary;
    const tot=st?(st.total_light_sleep_time_milli+st.total_rem_sleep_time_milli+st.total_slow_wave_sleep_time_milli+st.total_awake_time_milli)||1:1;
    const pct=v=>st?Math.round((v||0)/tot*100):0;
    const pc=perf>=80?'var(--green)':perf>=60?'var(--amber)':'var(--red)';
    el.innerHTML+=`<div class="sitem"><div class="sh"><div><div class="sd">${fDate(sl.start)}${sl.nap?' · Siesta':''}</div><div class="sdur">Duración: ${dur}</div></div><div class="sstats"><div><div class="ss-v" style="color:${pc}">${perf!=null?perf+'%':'—'}</div><div class="ss-k">Performance</div></div><div><div class="ss-v" style="color:var(--blue)">${eff!=null?eff+'%':'—'}</div><div class="ss-k">Eficiencia</div></div><div><div class="ss-v" style="color:#a78bfa">${rem}</div><div class="ss-k">REM</div></div><div><div class="ss-v" style="color:var(--teal)">${sws}</div><div class="ss-k">Profundo</div></div></div></div>${st?`<div class="sbar-row" style="margin-top:10px"><div class="sbs" style="flex:${pct(st.total_light_sleep_time_milli)};background:#60a5fa;min-width:4px"></div><div class="sbs" style="flex:${pct(st.total_slow_wave_sleep_time_milli)};background:#00e5c3;min-width:4px"></div><div class="sbs" style="flex:${pct(st.total_rem_sleep_time_milli)};background:#a78bfa;min-width:4px"></div><div class="sbs" style="flex:${pct(st.total_awake_time_milli)};background:#334155;min-width:2px"></div></div>`:''}</div>`;
  });
}

// ── CHART: STRAIN ─────────────────────────────────────────
{
  const sc=cycs.filter(c=>c.score).slice(0,14).reverse();
  new Chart($('chStrain'),{type:'bar',data:{labels:sc.map(c=>fDate(c.start,true)),datasets:[{data:sc.map(c=>+f1(c.score.strain)),backgroundColor:sc.map(c=>{const s=c.score.strain;return s>15?'rgba(239,68,68,.75)':s>10?'rgba(245,158,11,.75)':'rgba(34,197,94,.65)'}),borderRadius:5}]},options:{...CHART_OPTS,scales:{x:{...CHART_OPTS.scales.x},y:{...CHART_OPTS.scales.y,min:0,max:21}}}});
}

// ── RECORDS ───────────────────────────────────────────────
{
  const best={hrv:null,rhr:null,rec:null,strain:null,hrv_d:null,rhr_d:null,rec_d:null,strain_d:null};
  scRecs.forEach(r=>{
    const s=r.score;
    if(!best.hrv||s.hrv_rmssd_milli>best.hrv){best.hrv=s.hrv_rmssd_milli;best.hrv_d=r.created_at}
    if(!best.rhr||s.resting_heart_rate<best.rhr){best.rhr=s.resting_heart_rate;best.rhr_d=r.created_at}
    if(!best.rec||s.recovery_score>best.rec){best.rec=s.recovery_score;best.rec_d=r.created_at}
  });
  cycs.filter(c=>c.score).forEach(c=>{if(!best.strain||c.score.strain>best.strain){best.strain=c.score.strain;best.strain_d=c.start}});
  $('records-card').innerHTML=`<div class="lbl">Tus mejores registros</div><div class="rec-list">
    <div class="rec-item"><div class="rec-name">🏆 Mejor HRV</div><div class="rec-right"><div class="rec-val" style="color:var(--teal)">${best.hrv?f1(best.hrv)+' ms':'—'}</div><div class="rec-date">${fDate(best.hrv_d,true)}</div></div></div>
    <div class="rec-item"><div class="rec-name">❤️ Menor FC Reposo</div><div class="rec-right"><div class="rec-val" style="color:var(--purple2)">${best.rhr?Math.round(best.rhr)+' bpm':'—'}</div><div class="rec-date">${fDate(best.rhr_d,true)}</div></div></div>
    <div class="rec-item"><div class="rec-name">💚 Mejor Recovery</div><div class="rec-right"><div class="rec-val" style="color:var(--green)">${best.rec?Math.round(best.rec)+'%':'—'}</div><div class="rec-date">${fDate(best.rec_d,true)}</div></div></div>
    <div class="rec-item"><div class="rec-name">⚡ Mayor Strain</div><div class="rec-right"><div class="rec-val" style="color:var(--amber)">${best.strain?f1(best.strain):'—'}</div><div class="rec-date">${fDate(best.strain_d,true)}</div></div></div>
  </div>`;
}

// ── WORKOUT LIST ──────────────────────────────────────────
{
  const el=$('workout-list');
  const zc=['#1e3a5f','#1d4ed8','#16a34a','#ca8a04','#dc2626','#7c3aed'];
  wrks.slice(0,15).forEach((w,i)=>{
    const sc=w.score;
    const id=`wd${i}`;
    const zd=sc&&sc.zone_durations;
    const vals=zd?[zd.zone_zero_milli,zd.zone_one_milli,zd.zone_two_milli,zd.zone_three_milli,zd.zone_four_milli,zd.zone_five_milli]:[];
    const tot=vals.reduce((a,b)=>a+b,1);
    const mx=Math.max(...vals,1);
    const dur=w.start&&w.end?msH(new Date(w.end)-new Date(w.start)):'—';
    el.innerHTML+=`<div class="wi" id="${id}" onclick="toggleW('${id}')"><div class="wi-h"><div class="wi-l"><div class="ws">${w.sport_name||'Workout'}</div><div class="wd">${fDate(w.start)}</div></div><div class="wi-r"><div class="wst"><div class="wst-v" style="color:var(--teal)">${sc?f1(sc.strain):'—'}</div><div class="wst-k">Strain</div></div><div class="wst"><div class="wst-v">${sc?sc.average_heart_rate:'—'}</div><div class="wst-k">FC Prom</div></div><div class="wst"><div class="wst-v" style="color:var(--amber)">${sc?Math.round(sc.kilojoule*.239):'—'}</div><div class="wst-k">kcal</div></div><div class="wi-chev">⌄</div></div></div><div class="wi-detail" id="${id}d"><div style="display:flex;gap:20px;flex-wrap:wrap;margin-bottom:12px"><div><div style="font-family:var(--mono);font-size:18px;color:#ef4444">${sc?sc.max_heart_rate:'—'}</div><div style="font-size:9px;color:var(--sub);letter-spacing:.12em;margin-top:2px">FC MÁX</div></div><div><div style="font-family:var(--mono);font-size:18px">${dur}</div><div style="font-size:9px;color:var(--sub);letter-spacing:.12em;margin-top:2px">DURACIÓN</div></div>${sc&&sc.distance_meter?`<div><div style="font-family:var(--mono);font-size:18px;color:var(--blue)">${(sc.distance_meter/1000).toFixed(2)} km</div><div style="font-size:9px;color:var(--sub);letter-spacing:.12em;margin-top:2px">DISTANCIA</div></div>`:''}</div>${vals.length?`<div style="font-size:9px;color:var(--sub);letter-spacing:.12em;margin-bottom:8px">ZONAS DE FRECUENCIA CARDÍACA</div><div class="zw">${vals.map((v,j)=>`<div class="zc"><div style="font-size:8px;color:var(--sub2);margin-bottom:2px">${Math.round(v/tot*100)}%</div><div class="zb" style="height:${Math.max(v/mx*44,3)}px;background:${zc[j]}"></div><div class="zl">Z${j}</div></div>`).join('')}</div>`:''}</div></div>`;
  });
}
function toggleW(id){const el=document.getElementById(id),d=document.getElementById(id+'d');el.classList.toggle('open');d.classList.toggle('open')}

// ── BODY CHARTS ───────────────────────────────────────────
{
  const sc=scRecs.slice(0,14).reverse();
  const labels=sc.map(r=>fDate(r.created_at,true));
  const lOpts={responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{backgroundColor:'#0f1422',borderColor:'#18203a',borderWidth:1,bodyColor:'#718096',padding:10}},scales:{x:{grid:{color:'rgba(255,255,255,.03)'},ticks:{color:'#4a5568',font:{size:9}}},y:{grid:{color:'rgba(255,255,255,.03)'},ticks:{color:'#4a5568',font:{size:9}}}}};
  new Chart($('chHRV'),{type:'line',data:{labels,datasets:[{data:sc.map(r=>+f1(r.score.hrv_rmssd_milli)),borderColor:'#a78bfa',backgroundColor:'rgba(167,139,250,.08)',borderWidth:2.5,pointRadius:3,pointBackgroundColor:'#a78bfa',tension:.4,fill:true}]},options:lOpts});
  new Chart($('chRHR'),{type:'line',data:{labels,datasets:[{data:sc.map(r=>+f0(r.score.resting_heart_rate)),borderColor:'#7c3aed',backgroundColor:'rgba(124,58,237,.08)',borderWidth:2.5,pointRadius:3,pointBackgroundColor:'#7c3aed',tension:.4,fill:true}]},options:lOpts});
  const ws=sc.filter(r=>r.score.spo2_percentage);
  new Chart($('chSpo2'),{type:'line',data:{labels:ws.map(r=>fDate(r.created_at,true)),datasets:[{data:ws.map(r=>+f1(r.score.spo2_percentage)),borderColor:'#3b82f6',backgroundColor:'rgba(59,130,246,.08)',borderWidth:2.5,pointRadius:3,pointBackgroundColor:'#3b82f6',tension:.4,fill:true}]},options:{...lOpts,scales:{...lOpts.scales,y:{...lOpts.scales.y,min:90,max:100}}}});
}

// ── ANALYTICS ────────────────────────────────────────────
{
  // Correlation: sleep perf vs recovery
  const pts=scSl.filter(sl=>{const r=scRecs.find(r=>Math.abs(new Date(r.created_at)-new Date(sl.end))<86400000*1.5);return r;}).slice(0,20).map(sl=>{const r=scRecs.find(r=>Math.abs(new Date(r.created_at)-new Date(sl.end))<86400000*1.5);return{x:Math.round(sl.score.sleep_performance_percentage||0),y:Math.round(r.score.recovery_score)};});
  new Chart($('chCorr'),{type:'scatter',data:{datasets:[{data:pts,backgroundColor:'rgba(0,229,195,.6)',pointRadius:6,pointHoverRadius:8}]},options:{...CHART_OPTS,plugins:{...CHART_OPTS.plugins,tooltip:{...CHART_OPTS.plugins.tooltip,callbacks:{label:c=>`Sueño: ${c.raw.x}% → Recovery: ${c.raw.y}%`}}},scales:{x:{...CHART_OPTS.scales.x,title:{display:true,text:'Sleep Performance %',color:'#4a5568',font:{size:10}}},y:{...CHART_OPTS.scales.y,title:{display:true,text:'Recovery %',color:'#4a5568',font:{size:10}}}}}});

  // Distribution
  const buckets=[0,0,0,0,0];
  scRecs.forEach(r=>{const s=Math.round(r.score.recovery_score);if(s<20)buckets[0]++;else if(s<40)buckets[1]++;else if(s<60)buckets[2]++;else if(s<80)buckets[3]++;else buckets[4]++;});
  new Chart($('chDist'),{type:'bar',data:{labels:['0-19','20-39','40-59','60-79','80-100'],datasets:[{data:buckets,backgroundColor:['rgba(239,68,68,.7)','rgba(239,68,68,.5)','rgba(245,158,11,.6)','rgba(34,197,94,.5)','rgba(34,197,94,.8)'],borderRadius:6}]},options:{...CHART_OPTS,scales:{x:{...CHART_OPTS.scales.x,title:{display:true,text:'Recovery Score',color:'#4a5568',font:{size:10}}},y:{...CHART_OPTS.scales.y,ticks:{...CHART_OPTS.scales.y.ticks,stepSize:1}}}}});

  // Weekly averages
  function weeklyAvgs(records,field,n=8){const weeks=[];const now=new Date();for(let i=n-1;i>=0;i--){const end=new Date(now-(i)*7*86400000);const start=new Date(now-(i+1)*7*86400000);const slice=records.filter(r=>{const d=new Date(r.created_at||r.start);return d>=start&&d<end;});const vals=slice.map(r=>r.score?Number(r.score[field]||0):0).filter(v=>v>0);weeks.push(vals.length?vals.reduce((a,b)=>a+b)/vals.length:null);}return weeks;}
  const wLabels=Array.from({length:8},(_,i)=>{const d=new Date(new Date()-(7-i)*7*86400000);return d.toLocaleDateString('es-CO',{month:'short',day:'numeric'});});
  const wkRec=weeklyAvgs(scRecs,'recovery_score');
  const wkHRV=weeklyAvgs(scRecs,'hrv_rmssd_milli');
  const ctx=$('chWeekly').getContext('2d');
  const wg1=ctx.createLinearGradient(0,0,0,260);wg1.addColorStop(0,'rgba(0,229,195,.2)');wg1.addColorStop(1,'rgba(0,229,195,0)');
  new Chart(ctx,{type:'line',data:{labels:wLabels,datasets:[{label:'Recovery %',data:wkRec,borderColor:'#00e5c3',backgroundColor:wg1,borderWidth:2.5,pointRadius:4,pointBackgroundColor:'#00e5c3',tension:.4,fill:true,yAxisID:'y',spanGaps:true},{label:'HRV ms',data:wkHRV,borderColor:'#a78bfa',borderWidth:2,pointRadius:3,pointBackgroundColor:'#a78bfa',tension:.4,yAxisID:'y2',spanGaps:true}]},options:{...CHART_OPTS,interaction:{mode:'index',intersect:false},plugins:{...CHART_OPTS.plugins,legend:{labels:{color:'#718096',font:{size:10},boxWidth:10,padding:12}}},scales:{x:{...CHART_OPTS.scales.x},y:{...CHART_OPTS.scales.y,min:0,max:100},y2:{position:'right',grid:{display:false},ticks:{color:'#a78bfa',font:{size:9}}}}}});

  // General stats
  const recScores=scRecs.map(r=>r.score.recovery_score);
  const avg=v=>v.length?v.reduce((a,b)=>a+b)/v.length:null;
  $('general-stats').innerHTML=`<div class="rec-list">
    <div class="rec-item"><div class="rec-name">Recovery promedio</div><div class="rec-val" style="color:var(--teal)">${avg(recScores)?Math.round(avg(recScores))+'%':'—'}</div></div>
    <div class="rec-item"><div class="rec-name">Días con recovery ≥67%</div><div class="rec-val" style="color:var(--green)">${recScores.filter(s=>s>=67).length}</div></div>
    <div class="rec-item"><div class="rec-name">Días con recovery <34%</div><div class="rec-val" style="color:var(--red)">${recScores.filter(s=>s<34).length}</div></div>
    <div class="rec-item"><div class="rec-name">Total workouts</div><div class="rec-val" style="color:var(--amber)">${wrks.length}</div></div>
    <div class="rec-item"><div class="rec-name">Noches analizadas</div><div class="rec-val">${scSl.length}</div></div>
  </div>`;
}

// ═══════════════════════════════════════════════════════════
//  THREE.JS — PARTICLE HUMAN BODY
// ═══════════════════════════════════════════════════════════
{
  const canvas=$('three-canvas');
  const renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true});
  renderer.setClearColor(0x000000,0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));

  const scene=new THREE.Scene();
  const camera=new THREE.PerspectiveCamera(45,1,0.1,100);
  camera.position.set(0,0.2,4);
  camera.lookAt(0,0.2,0);

  function resize(){
    const w=canvas.parentElement.clientWidth,h=canvas.parentElement.clientHeight;
    renderer.setSize(w,h);
    camera.aspect=w/h;
    camera.updateProjectionMatrix();
  }
  resize();
  window.addEventListener('resize',resize);

  // Color based on recovery
  const col=new THREE.Color(rCol(currentScore));
  const colDim=col.clone().multiplyScalar(0.4);

  // ── Generate human body points ────────────────────────
  const positions=[];
  const colors=[];

  function addSphere(cx,cy,cz,r,n,bright=1){
    for(let i=0;i<n;i++){
      const theta=Math.random()*Math.PI*2;
      const phi=Math.acos(2*Math.random()-1);
      positions.push(cx+r*Math.sin(phi)*Math.cos(theta),cy+r*Math.cos(phi),cz+r*Math.sin(phi)*Math.sin(theta));
      const c=bright>0.5?col:colDim;
      colors.push(c.r*bright,c.g*bright,c.b*bright);
    }
  }

  function addCylinder(cx,cy,cz,r,h,n,tx=0,tz=0,bright=1){
    for(let i=0;i<n;i++){
      const theta=Math.random()*Math.PI*2;
      const t=Math.random();
      const x=r*Math.cos(theta);
      const z=r*Math.sin(theta);
      positions.push(cx+x+t*tx*h,cy+t*h,cz+z+t*tz*h);
      const c=bright>0.5?col:colDim;
      colors.push(c.r*bright,c.g*bright,c.b*bright);
    }
  }

  function addEllipsoid(cx,cy,cz,rx,ry,rz,n,bright=1){
    for(let i=0;i<n;i++){
      const theta=Math.random()*Math.PI*2;
      const phi=Math.acos(2*Math.random()-1);
      positions.push(cx+rx*Math.sin(phi)*Math.cos(theta),cy+ry*Math.cos(phi),cz+rz*Math.sin(phi)*Math.sin(theta));
      const c=bright>0.5?col:colDim;
      colors.push(c.r*bright,c.g*bright,c.b*bright);
    }
  }

  // HEAD
  addSphere(0,1.72,0,0.16,90,.95);
  // NECK
  addCylinder(0,1.52,0,0.055,0.16,18,0,0,.7);
  // SHOULDERS
  addEllipsoid(-0.26,1.43,0,0.09,0.07,0.07,25,.9);
  addEllipsoid(0.26,1.43,0,0.09,0.07,0.07,25,.9);
  // CHEST / TORSO upper
  for(let i=0;i<180;i++){
    const t=Math.random();
    const w=0.19-t*0.04;
    const dw=w*0.6;
    const theta=Math.random()*Math.PI*2;
    const bright=0.7+Math.random()*0.3;
    positions.push(w*Math.cos(theta),1.05+t*0.38,dw*Math.sin(theta));
    colors.push(col.r*bright,col.g*bright,col.b*bright);
  }
  // ABDOMEN
  for(let i=0;i<120;i++){
    const t=Math.random();
    const w=0.15-t*0.02;
    const theta=Math.random()*Math.PI*2;
    const bright=0.6+Math.random()*0.3;
    positions.push(w*Math.cos(theta),0.68+t*0.35,w*0.7*Math.sin(theta));
    colors.push(col.r*bright,col.g*bright,col.b*bright);
  }
  // HIPS
  for(let i=0;i<60;i++){
    const theta=Math.random()*Math.PI*2;
    const bright=0.65+Math.random()*0.25;
    positions.push(0.2*Math.cos(theta),0.62+Math.random()*0.08,0.14*Math.sin(theta));
    colors.push(col.r*bright,col.g*bright,col.b*bright);
  }
  // UPPER ARMS
  addCylinder(-0.27,1.15,0,0.055,0.32,50,-0.28,0,.8);
  addCylinder(0.27,1.15,0,0.055,0.32,50,0.28,0,.8);
  // LOWER ARMS
  addCylinder(-0.36,0.84,0,0.04,0.32,40,-0.06,0,.75);
  addCylinder(0.36,0.84,0,0.04,0.32,40,0.06,0,.75);
  // HANDS
  addSphere(-0.38,0.49,0,0.055,20,.7);
  addSphere(0.38,0.49,0,0.055,20,.7);
  // UPPER LEGS
  addCylinder(-0.1,0.38,0,0.075,0.32,75,0,0,.8);
  addCylinder(0.1,0.38,0,0.075,0.32,75,0,0,.8);
  // LOWER LEGS
  addCylinder(-0.1,0.06,0,0.055,0.34,55,0,0,.7);
  addCylinder(0.1,0.06,0,0.055,0.34,55,0,0,.7);
  // FEET
  for(let i=0;i<25;i++){
    positions.push(-0.1+(Math.random()-.5)*0.1,-.02,-(Math.random()*.14));
    colors.push(col.r*.65,col.g*.65,col.b*.65);
    positions.push(0.1+(Math.random()-.5)*0.1,-.02,-(Math.random()*.14));
    colors.push(col.r*.65,col.g*.65,col.b*.65);
  }

  // ── BODY ZONES BASED ON DATA ─────────────────────────
  // Heart zone (chest) - pulses with HRV
  const hrvScore=r0&&r0.score?Math.min(1,r0.score.hrv_rmssd_milli/80):0.5;
  const heartCol=new THREE.Color(hrvScore>0.6?'#00e5c3':hrvScore>0.3?'#f59e0b':'#ef4444');
  for(let i=0;i<40;i++){
    const theta=Math.random()*Math.PI*2;
    const r2=0.06+Math.random()*0.04;
    positions.push(r2*Math.cos(theta)*0.8,(1.1+Math.random()*0.15),r2*Math.sin(theta)*0.4);
    const b=0.7+Math.random()*0.3;
    colors.push(heartCol.r*b,heartCol.g*b,heartCol.b*b);
  }
  // Head zone - based on sleep performance
  const sleepScore=sl0&&sl0.score?Math.min(1,(sl0.score.sleep_performance_percentage||0)/100):0.5;
  const headCol=new THREE.Color(sleepScore>0.7?'#a78bfa':sleepScore>0.4?'#f59e0b':'#ef4444');
  for(let i=0;i<30;i++){
    const theta=Math.random()*Math.PI*2;
    const phi=Math.acos(2*Math.random()-1);
    const r2=0.17;
    positions.push(r2*Math.sin(phi)*Math.cos(theta),1.72+r2*Math.cos(phi),r2*Math.sin(phi)*Math.sin(theta));
    const b=0.5+Math.random()*0.5;
    colors.push(headCol.r*b,headCol.g*b,headCol.b*b);
  }
  // Legs zone - based on strain
  const strainVal=cycs.length&&cycs[0].score?cycs[0].score.strain:0;
  const strainNorm=Math.min(1,strainVal/21);
  const legCol=new THREE.Color(strainNorm>0.6?'#ef4444':strainNorm>0.3?'#f59e0b':'#3b82f6');
  for(let i=0;i<50;i++){
    const side=i%2===0?-0.1:0.1;
    positions.push(side+(Math.random()-.5)*0.06,0.1+Math.random()*0.6,(Math.random()-.5)*0.08);
    const b=0.5+Math.random()*0.5;
    colors.push(legCol.r*b,legCol.g*b,legCol.b*b);
  }

  // Ambient floating particles
  for(let i=0;i<120;i++){
    const r=1.2+Math.random()*0.8;
    const theta=Math.random()*Math.PI*2;
    const phi=Math.acos(2*Math.random()-1);
    positions.push(r*Math.sin(phi)*Math.cos(theta),r*Math.cos(phi)*0.7+0.5,r*Math.sin(phi)*Math.sin(theta));
    const b=0.08+Math.random()*0.15;
    colors.push(col.r*b,col.g*b,col.b*b);
  }

  const geo=new THREE.BufferGeometry();
  geo.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
  geo.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));

  const mat=new THREE.PointsMaterial({size:0.022,vertexColors:true,sizeAttenuation:true,transparent:true,opacity:.9});
  const points=new THREE.Points(geo,mat);
  points.position.y=-0.2;
  scene.add(points);

  // Holographic ring at base
  const ringGeo=new THREE.TorusGeometry(0.35,0.004,8,80);
  const ringMat=new THREE.MeshBasicMaterial({color:col,transparent:true,opacity:.3});
  const ring=new THREE.Mesh(ringGeo,ringMat);
  ring.rotation.x=Math.PI/2;
  ring.position.y=-0.22;
  scene.add(ring);

  // Animate
  let t=0;
  // Holographic ground circle
  const circleGeo=new THREE.RingGeometry(0.3,0.35,64);
  const circleMat=new THREE.MeshBasicMaterial({color:col,transparent:true,opacity:.15,side:THREE.DoubleSide});
  const circle=new THREE.Mesh(circleGeo,circleMat);
  circle.rotation.x=-Math.PI/2;circle.position.y=-0.22;
  scene.add(circle);

  function animate(){
    requestAnimationFrame(animate);
    t+=0.005;
    points.rotation.y=t*0.35;
    ring.rotation.z=t*0.6;
    circle.rotation.z=-t*0.2;
    // Breathing pulse on overall figure
    const pulse=1+Math.sin(t*1.2)*0.012;
    points.scale.setScalar(pulse);
    mat.opacity=0.82+Math.sin(t*1.8)*0.12;
    mat.size=0.022*(0.95+Math.sin(t*2)*0.05);
    ring.scale.setScalar(1+Math.sin(t*1.5)*0.06);
    renderer.render(scene,camera);
  }
  animate();
}

// ═══════════════════════════════════════════════════════════
//  AI CHAT
// ═══════════════════════════════════════════════════════════
{
  const fab=$('chat-fab'),panel=$('chat-panel'),close=$('chat-close');
  const msgs=$('chat-msgs'),input=$('chat-input'),send=$('chat-send');
  const sugg=$('chat-sugg');
  let history=[],chatOpen=false;

  // Build data context for AI
  const ctx={};
  if(r0&&r0.score){const s=r0.score;ctx.recovery={score:Math.round(s.recovery_score),hrv_ms:+f1(s.hrv_rmssd_milli),resting_hr:Math.round(s.resting_heart_rate),spo2:s.spo2_percentage?+f1(s.spo2_percentage):null};}
  if(sl0&&sl0.score){const s=sl0.score;ctx.last_sleep={performance_pct:Math.round(s.sleep_performance_percentage||0),efficiency_pct:+(s.sleep_efficiency_percentage||0).toFixed(1),rem_min:s.stage_summary?Math.round(s.stage_summary.total_rem_sleep_time_milli/60000):null,deep_min:s.stage_summary?Math.round(s.stage_summary.total_slow_wave_sleep_time_milli/60000):null};}
  if(cycs.length&&cycs[0].score)ctx.today_strain=+f1(cycs[0].score.strain);
  if(scRecs.length>=3){const avg7=scRecs.slice(0,7).map(r=>r.score.recovery_score);ctx.weekly_avg_recovery=Math.round(avg7.reduce((a,b)=>a+b)/avg7.length);}
  ctx.name=prof.first_name||'';

  function toggleChat(){
    chatOpen=!chatOpen;
    panel.classList.toggle('open',chatOpen);
    if(chatOpen)setTimeout(()=>input.focus(),350);
  }
  fab.addEventListener('click',toggleChat);
  close.addEventListener('click',toggleChat);

  sugg.querySelectorAll('.sugg').forEach(s=>{
    s.addEventListener('click',()=>{input.value=s.textContent;sendMsg();});
  });

  function addMsg(role,text){
    const d=document.createElement('div');
    d.className=`msg ${role}`;
    d.innerHTML=`<div class="msg-avatar">${role==='ai'?'🤖':'👤'}</div><div class="msg-bubble">${text.replace(/\n/g,'<br>')}</div>`;
    msgs.appendChild(d);
    msgs.scrollTop=msgs.scrollHeight;
  }

  function showTyping(){
    const d=document.createElement('div');
    d.className='msg ai';d.id='typing';
    d.innerHTML=`<div class="msg-avatar">🤖</div><div class="msg-bubble"><div class="typing"><div class="td"></div><div class="td"></div><div class="td"></div></div></div>`;
    msgs.appendChild(d);
    msgs.scrollTop=msgs.scrollHeight;
  }

  async function sendMsg(){
    const txt=input.value.trim();
    if(!txt||send.disabled)return;
    input.value='';input.style.height='auto';
    sugg.style.display='none';
    addMsg('user',txt);
    history.push({role:'user',content:txt});
    send.disabled=true;
    showTyping();
    try{
      const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:txt,history:history.slice(-6),context:ctx})});
      const data=await r.json();
      const typing=$('typing');if(typing)typing.remove();
      const reply=data.response||'Error al conectar con la IA.';
      addMsg('ai',reply);
      history.push({role:'assistant',content:reply});
    }catch(e){
      const typing=$('typing');if(typing)typing.remove();
      addMsg('ai','Error de conexión. Intenta de nuevo.');
    }
    send.disabled=false;
    input.focus();
  }

  send.addEventListener('click',sendMsg);
  input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMsg();}});
  input.addEventListener('input',()=>{input.style.height='auto';input.style.height=Math.min(input.scrollHeight,80)+'px';});
}

// ═══════════════════════════════════════════════════════════
//  TABS
// ═══════════════════════════════════════════════════════════
function switchTab(name){
  document.querySelectorAll('.tab,.bnav-item').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
  document.querySelectorAll(`[data-tab="${name}"]`).forEach(t=>t.classList.add('active'));
  const tc=document.getElementById('tab-'+name);
  if(tc)tc.classList.add('active');
}
document.querySelectorAll('.tab,.bnav-item').forEach(t=>{
  t.addEventListener('click',()=>switchTab(t.dataset.tab));
});
</script>
</body>
</html>
"""


if __name__ == '__main__':
    print("\n  ✅ WHOOP Dashboard v3 — http://localhost:3000\n")
    app.run(port=3000, debug=False)
