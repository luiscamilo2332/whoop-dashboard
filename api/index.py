from flask import Flask, redirect, request, session, render_template_string
import requests
import json
import secrets
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'whoop-dash-secret-dev')

CLIENT_ID     = os.environ.get('WHOOP_CLIENT_ID', '').strip()
CLIENT_SECRET = os.environ.get('WHOOP_CLIENT_SECRET', '').strip()
REDIRECT_URI  = os.environ.get('REDIRECT_URI', 'http://localhost:3000/callback').strip()

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
    except Exception:
        session.clear()
        return redirect('/login')
    return render_template_string(HTML, data=json.dumps(data, default=str))

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
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WHOOP Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{
  --bg:#06080f;
  --s1:#0b0e1a;
  --s2:#0f1220;
  --card:#111624;
  --border:#1a2035;
  --border2:#222840;
  --teal:#00e5c3;
  --teal2:#00b89c;
  --teal3:rgba(0,229,195,.08);
  --purple:#7c3aed;
  --purple2:#a78bfa;
  --amber:#f59e0b;
  --red:#ef4444;
  --green:#22c55e;
  --blue:#3b82f6;
  --text:#e2e8f0;
  --sub:#64748b;
  --sub2:#94a3b8;
  --mono:'JetBrains Mono',monospace;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'Space Grotesk',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;overflow-x:hidden}

/* NOISE */
body::before{content:'';position:fixed;inset:0;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.035'/%3E%3C/svg%3E");pointer-events:none;z-index:0;opacity:.6}

/* GLOW ORBS */
.orb{position:fixed;border-radius:50%;filter:blur(80px);pointer-events:none;z-index:0}
.orb1{width:500px;height:500px;top:-150px;right:-150px;background:rgba(0,229,195,.04)}
.orb2{width:400px;height:400px;bottom:-100px;left:-100px;background:rgba(124,58,237,.04)}

/* HEADER */
header{
  position:sticky;top:0;z-index:200;
  display:flex;align-items:center;justify-content:space-between;
  padding:16px 32px;
  background:rgba(6,8,15,.85);
  border-bottom:1px solid var(--border);
  backdrop-filter:blur(20px);
}
.logo{display:flex;align-items:center;gap:10px;font-size:13px;font-weight:700;letter-spacing:.18em;color:var(--teal);text-transform:uppercase}
.logo-dot{width:8px;height:8px;border-radius:50%;background:var(--teal);box-shadow:0 0 12px var(--teal);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.6;transform:scale(.85)}}
.header-right{display:flex;align-items:center;gap:20px}
.header-user{font-size:13px;color:var(--sub2);font-weight:500}
.btn-logout{
  font-family:var(--mono);font-size:11px;letter-spacing:.08em;
  padding:7px 16px;background:transparent;
  border:1px solid var(--border2);color:var(--sub);
  border-radius:8px;cursor:pointer;text-decoration:none;
  transition:all .2s;
}
.btn-logout:hover{border-color:var(--teal);color:var(--teal)}

/* TABS */
.tabs-wrap{
  position:sticky;top:57px;z-index:100;
  background:rgba(6,8,15,.9);
  border-bottom:1px solid var(--border);
  backdrop-filter:blur(20px);
  padding:0 32px;
}
.tabs{display:flex;gap:0}
.tab{
  padding:14px 22px;font-size:13px;font-weight:600;
  color:var(--sub);border-bottom:2px solid transparent;
  cursor:pointer;transition:all .2s;letter-spacing:.02em;
  user-select:none;
}
.tab:hover{color:var(--text)}
.tab.active{color:var(--teal);border-bottom-color:var(--teal)}

/* MAIN */
main{padding:32px;max-width:1440px;margin:0 auto;position:relative;z-index:1}
.tab-content{display:none}
.tab-content.active{display:block}

/* PROFILE HERO */
.profile-hero{
  display:grid;grid-template-columns:auto 1fr auto;
  align-items:center;gap:24px;
  padding:24px 28px;margin-bottom:32px;
  background:var(--card);border:1px solid var(--border);border-radius:20px;
  position:relative;overflow:hidden;
}
.profile-hero::before{
  content:'';position:absolute;inset:0;
  background:linear-gradient(135deg,rgba(0,229,195,.04) 0%,transparent 50%);
  pointer-events:none;
}
.avatar{
  width:60px;height:60px;border-radius:50%;
  background:linear-gradient(135deg,var(--teal2),var(--purple));
  display:flex;align-items:center;justify-content:center;
  font-size:24px;font-weight:800;flex-shrink:0;
  box-shadow:0 0 30px rgba(0,229,195,.2);
}
.profile-info .name{font-size:20px;font-weight:700}
.profile-info .email{font-size:12px;color:var(--sub2);margin-top:3px}
.profile-stats{display:flex;gap:36px}
.pstat{text-align:right}
.pstat-val{font-family:var(--mono);font-size:20px;font-weight:500}
.pstat-key{font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:var(--sub);margin-top:3px}

/* INSIGHT BANNER */
.insights{display:flex;gap:12px;margin-bottom:28px;flex-wrap:wrap}
.insight{
  display:flex;align-items:center;gap:10px;
  padding:12px 16px;border-radius:12px;
  border:1px solid;font-size:13px;font-weight:500;
  flex:1;min-width:200px;
}
.insight-icon{font-size:18px;flex-shrink:0}
.insight.good{background:rgba(34,197,94,.08);border-color:rgba(34,197,94,.2);color:#86efac}
.insight.warn{background:rgba(245,158,11,.08);border-color:rgba(245,158,11,.2);color:#fcd34d}
.insight.info{background:rgba(59,130,246,.08);border-color:rgba(59,130,246,.2);color:#93c5fd}
.insight.bad {background:rgba(239,68,68,.08);border-color:rgba(239,68,68,.2);color:#fca5a5}

/* GRID */
.grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.grid-2{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}
.grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
.grid-hero{display:grid;grid-template-columns:280px 1fr;gap:20px;margin-bottom:28px}

/* CARDS */
.card{
  background:var(--card);border:1px solid var(--border);
  border-radius:18px;padding:24px;
  position:relative;overflow:hidden;
  transition:border-color .3s,transform .2s;
}
.card:hover{border-color:var(--border2)}
.card-glow::after{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at top left,rgba(0,229,195,.04) 0%,transparent 60%);pointer-events:none}
.label{font-family:var(--mono);font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--sub);margin-bottom:10px}
.big-val{font-family:var(--mono);font-size:48px;font-weight:500;line-height:1;letter-spacing:-.02em}
.big-unit{font-size:16px;color:var(--sub2);margin-left:4px}
.section-title{font-size:11px;font-weight:700;letter-spacing:.22em;text-transform:uppercase;color:var(--sub);margin-bottom:18px;padding-bottom:12px;border-bottom:1px solid var(--border)}
.section{margin-bottom:40px}

/* DELTA */
.delta{display:inline-flex;align-items:center;gap:4px;font-family:var(--mono);font-size:11px;padding:3px 8px;border-radius:6px;margin-top:6px}
.delta.up{background:rgba(34,197,94,.12);color:var(--green)}
.delta.down{background:rgba(239,68,68,.12);color:var(--red)}
.delta.flat{background:rgba(100,116,139,.12);color:var(--sub2)}

/* RECOVERY RING */
.ring-card{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:32px 24px}
.ring-wrap{position:relative;width:160px;height:160px;margin-bottom:16px}
.ring-wrap svg{transform:rotate(-90deg)}
.ring-bg{fill:none;stroke:var(--border);stroke-width:12}
.ring-fg{fill:none;stroke-width:12;stroke-linecap:round;transition:stroke-dashoffset 1.4s cubic-bezier(.4,0,.2,1)}
.ring-center{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.ring-score{font-family:var(--mono);font-size:40px;font-weight:500;line-height:1}
.ring-label{font-size:11px;color:var(--sub2);margin-top:2px}

/* RECOVERY MINI BARS */
.mini-bars{display:flex;gap:6px;align-items:flex-end;height:48px;margin-top:16px;width:100%}
.mbar-col{flex:1;display:flex;flex-direction:column;align-items:center;gap:4px}
.mbar{width:100%;border-radius:3px;transition:height .8s ease}
.mbar-lbl{font-family:var(--mono);font-size:9px;color:var(--sub)}

/* METRICS ROW */
.metric-row{display:flex;flex-direction:column;gap:20px}
.metric-item{}
.metric-val{font-family:var(--mono);font-size:32px;font-weight:500;line-height:1}
.metric-key{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--sub);margin-top:4px}

/* CHART */
.chart-wrap{position:relative;height:180px;margin-top:16px}
.chart-wrap-tall{position:relative;height:240px;margin-top:16px}

/* SLEEP STAGES */
.stages{margin-top:16px;display:flex;flex-direction:column;gap:10px}
.stage-row{display:flex;align-items:center;gap:10px}
.sdot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.sname{font-size:12px;color:var(--sub2);width:65px;flex-shrink:0}
.sbar-wrap{flex:1;background:var(--border);border-radius:4px;height:5px;overflow:hidden}
.sbar{height:100%;border-radius:4px;transition:width 1.2s ease}
.sval{font-family:var(--mono);font-size:11px;width:44px;text-align:right;flex-shrink:0}

/* WORKOUT LIST */
.workout-list{display:flex;flex-direction:column;gap:10px}
.workout-item{
  background:var(--s1);border:1px solid var(--border);border-radius:14px;
  padding:16px 20px;cursor:pointer;
  transition:border-color .2s,background .2s;
}
.workout-item:hover{border-color:var(--border2);background:var(--s2)}
.workout-item.open{border-color:rgba(0,229,195,.2)}
.wi-header{display:flex;align-items:center;justify-content:space-between}
.wi-left{}
.wi-sport{font-size:14px;font-weight:600;text-transform:capitalize;margin-bottom:3px}
.wi-date{font-family:var(--mono);font-size:10px;color:var(--sub)}
.wi-right{display:flex;gap:24px;align-items:center}
.wstat{text-align:right}
.wstat-val{font-family:var(--mono);font-size:18px;font-weight:500}
.wstat-key{font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--sub);margin-top:2px}
.wi-detail{display:none;margin-top:16px;padding-top:16px;border-top:1px solid var(--border)}
.wi-detail.open{display:block}
.zones-wrap{display:flex;gap:6px;align-items:flex-end;height:60px}
.zone-col{flex:1;display:flex;flex-direction:column;align-items:center;gap:5px}
.zone-bar{width:100%;border-radius:4px 4px 0 0;min-height:4px;transition:height .6s}
.zone-lbl{font-family:var(--mono);font-size:9px;color:var(--sub)}
.zone-pct{font-family:var(--mono);font-size:9px;color:var(--sub2)}
.wi-chevron{color:var(--sub);transition:transform .3s;font-size:16px}
.workout-item.open .wi-chevron{transform:rotate(180deg)}

/* SLEEP LIST */
.sleep-list{display:flex;flex-direction:column;gap:10px}
.sleep-item{
  background:var(--s1);border:1px solid var(--border);border-radius:14px;
  padding:16px 20px;
}
.sl-header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}
.sl-date{font-weight:600;font-size:14px}
.sl-dur{font-family:var(--mono);font-size:11px;color:var(--sub2);margin-top:2px}
.sl-stats{display:flex;gap:24px;flex-wrap:wrap}
.sl-stat-val{font-family:var(--mono);font-size:16px;font-weight:500}
.sl-stat-key{font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--sub);margin-top:2px}
.sl-stages{margin-top:14px;padding-top:14px;border-top:1px solid var(--border)}
.sl-bar-row{display:flex;height:8px;border-radius:6px;overflow:hidden;gap:2px;margin-top:8px}
.sl-bar-seg{border-radius:3px;transition:flex .8s ease}

/* MINI CARDS */
.mini4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px}
.mc{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:18px;text-align:center}
.mc-val{font-family:var(--mono);font-size:26px;font-weight:500;line-height:1}
.mc-key{font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:var(--sub);margin-top:6px}

/* TAG */
.tag{display:inline-block;padding:4px 10px;border-radius:6px;font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;font-weight:500}
.tag-green{background:rgba(34,197,94,.15);color:var(--green)}
.tag-amber{background:rgba(245,158,11,.15);color:var(--amber)}
.tag-red{background:rgba(239,68,68,.15);color:var(--red)}
.tag-blue{background:rgba(59,130,246,.15);color:var(--blue)}
.tag-purple{background:rgba(167,139,250,.15);color:var(--purple2)}

/* FADE IN */
@keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
.fade-up{animation:fadeUp .5s ease forwards;opacity:0}
.fade-up:nth-child(1){animation-delay:.05s}
.fade-up:nth-child(2){animation-delay:.1s}
.fade-up:nth-child(3){animation-delay:.15s}
.fade-up:nth-child(4){animation-delay:.2s}
.fade-up:nth-child(5){animation-delay:.25s}

/* DIVIDER */
.divider{height:1px;background:var(--border);margin:28px 0}

@media(max-width:900px){
  main{padding:16px}
  .grid-3,.grid-4,.mini4{grid-template-columns:repeat(2,1fr)}
  .grid-hero{grid-template-columns:1fr}
  .profile-hero{grid-template-columns:auto 1fr;gap:16px}
  .profile-stats{display:none}
  header,.tabs-wrap{padding-left:16px;padding-right:16px}
  .tab{padding:12px 14px;font-size:12px}
}
</style>
</head>
<body>
<div class="orb orb1"></div>
<div class="orb orb2"></div>

<header>
  <div class="logo"><div class="logo-dot"></div>WHOOP</div>
  <div class="header-right">
    <span class="header-user" id="huser"></span>
    <a href="/logout" class="btn-logout">Salir</a>
  </div>
</header>

<div class="tabs-wrap">
  <div class="tabs">
    <div class="tab active" data-tab="overview">Resumen</div>
    <div class="tab" data-tab="sleep">Sueño</div>
    <div class="tab" data-tab="training">Entrenamiento</div>
    <div class="tab" data-tab="body">Cuerpo</div>
  </div>
</div>

<main>

<!-- ═══ TAB: OVERVIEW ═══ -->
<div class="tab-content active" id="tab-overview">

  <div class="profile-hero fade-up">
    <div class="avatar" id="avatar">?</div>
    <div class="profile-info">
      <div class="name" id="pname">—</div>
      <div class="email" id="pemail">—</div>
    </div>
    <div class="profile-stats">
      <div class="pstat"><div class="pstat-val" id="ps-h">—</div><div class="pstat-key">Altura</div></div>
      <div class="pstat"><div class="pstat-val" id="ps-w">—</div><div class="pstat-key">Peso</div></div>
      <div class="pstat"><div class="pstat-val" id="ps-hr">—</div><div class="pstat-key">FC Máx</div></div>
    </div>
  </div>

  <div class="insights fade-up" id="insights"></div>

  <div class="grid-hero fade-up">
    <!-- Recovery Ring -->
    <div class="card ring-card card-glow">
      <div class="ring-wrap">
        <svg width="160" height="160" viewBox="0 0 160 160">
          <circle class="ring-bg" cx="80" cy="80" r="68"/>
          <circle class="ring-fg" id="ring-fg" cx="80" cy="80" r="68" stroke-dasharray="427.26" stroke-dashoffset="427.26"/>
        </svg>
        <div class="ring-center">
          <div class="ring-score" id="rec-score">—</div>
          <div class="ring-label">RECOVERY</div>
        </div>
      </div>
      <div class="label">Recovery de hoy</div>
      <div id="rec-tag"></div>
      <div id="rec-delta" style="margin-top:8px"></div>
      <div class="mini-bars" id="rec-bars"></div>
    </div>

    <!-- Right metrics + chart -->
    <div style="display:flex;flex-direction:column;gap:16px">
      <div class="card card-glow">
        <div class="label">Tendencia — Recovery, HRV & Strain (7 días)</div>
        <div class="chart-wrap-tall"><canvas id="chartTrend"></canvas></div>
      </div>
    </div>
  </div>

  <!-- KPIs row -->
  <div class="mini4 fade-up">
    <div class="mc">
      <div class="mc-val" id="kpi-hrv" style="color:var(--teal)">—</div>
      <div class="mc-key">HRV (ms)</div>
      <div id="kpi-hrv-d" style="margin-top:6px"></div>
    </div>
    <div class="mc">
      <div class="mc-val" id="kpi-rhr" style="color:var(--purple2)">—</div>
      <div class="mc-key">FC Reposo</div>
      <div id="kpi-rhr-d" style="margin-top:6px"></div>
    </div>
    <div class="mc">
      <div class="mc-val" id="kpi-spo2" style="color:var(--blue)">—</div>
      <div class="mc-key">SpO₂ %</div>
    </div>
    <div class="mc">
      <div class="mc-val" id="kpi-strain" style="color:var(--amber)">—</div>
      <div class="mc-key">Strain hoy</div>
    </div>
  </div>

  <!-- Sleep summary -->
  <div class="section fade-up">
    <div class="section-title">Último sueño</div>
    <div class="grid-3">
      <div class="card">
        <div class="label">Performance</div>
        <div class="big-val" id="sl-perf" style="color:var(--amber)">—</div><span class="big-unit">%</span>
        <div id="sl-perf-d" style="margin-top:8px"></div>
      </div>
      <div class="card">
        <div class="label">Eficiencia & Duración</div>
        <div class="big-val" id="sl-eff" style="font-size:36px;color:var(--blue)">—</div><span class="big-unit">%</span>
        <div style="margin-top:10px;font-family:var(--mono);font-size:13px;color:var(--sub2)" id="sl-dur">—</div>
        <div class="stages" id="sl-stages-ov"></div>
      </div>
      <div class="card">
        <div class="label">Desglose por etapas</div>
        <div id="sl-bar-ov"></div>
        <div class="chart-wrap"><canvas id="chartSleepDonut"></canvas></div>
      </div>
    </div>
  </div>

</div><!-- /overview -->


<!-- ═══ TAB: SLEEP ═══ -->
<div class="tab-content" id="tab-sleep">
  <div class="section">
    <div class="section-title">Tendencia de sueño (últimas noches)</div>
    <div class="card card-glow">
      <div class="chart-wrap-tall"><canvas id="chartSleepTrend"></canvas></div>
    </div>
  </div>
  <div class="section">
    <div class="section-title">Historial detallado</div>
    <div class="sleep-list" id="sleep-list"></div>
  </div>
</div>


<!-- ═══ TAB: TRAINING ═══ -->
<div class="tab-content" id="tab-training">
  <div class="section">
    <div class="section-title">Strain acumulado (últimos ciclos)</div>
    <div class="card card-glow">
      <div class="chart-wrap-tall"><canvas id="chartStrain"></canvas></div>
    </div>
  </div>
  <div class="section">
    <div class="section-title">Workouts recientes</div>
    <div class="workout-list" id="workout-list"></div>
  </div>
</div>


<!-- ═══ TAB: BODY ═══ -->
<div class="tab-content" id="tab-body">
  <div class="grid-3 fade-up" style="margin-bottom:28px">
    <div class="card card-glow" style="text-align:center;padding:36px">
      <div class="label">Altura</div>
      <div class="big-val" id="b-height" style="color:var(--teal)">—</div>
      <div class="big-unit" style="font-size:18px">cm</div>
    </div>
    <div class="card card-glow" style="text-align:center;padding:36px">
      <div class="label">Peso</div>
      <div class="big-val" id="b-weight" style="color:var(--purple2)">—</div>
      <div class="big-unit" style="font-size:18px">kg</div>
    </div>
    <div class="card card-glow" style="text-align:center;padding:36px">
      <div class="label">FC Máxima</div>
      <div class="big-val" id="b-maxhr" style="color:var(--red)">—</div>
      <div class="big-unit" style="font-size:18px">bpm</div>
    </div>
  </div>

  <div class="section fade-up">
    <div class="section-title">Tendencias biométricas</div>
    <div class="grid-2">
      <div class="card card-glow">
        <div class="label">HRV diario (RMSSD ms)</div>
        <div class="chart-wrap-tall"><canvas id="chartHRV"></canvas></div>
      </div>
      <div class="card card-glow">
        <div class="label">FC en Reposo diario (bpm)</div>
        <div class="chart-wrap-tall"><canvas id="chartRHR"></canvas></div>
      </div>
    </div>
  </div>

  <div class="section fade-up">
    <div class="section-title">SpO₂ & Temperatura</div>
    <div class="card card-glow">
      <div class="chart-wrap"><canvas id="chartSpo2"></canvas></div>
    </div>
  </div>
</div>

</main>

<script>
const RAW = {{ data | safe }};

// ── UTILS ─────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const f1 = v => v!=null?Number(v).toFixed(1):'—';
const f0 = v => v!=null?Math.round(v):'—';
function msToH(ms){if(!ms)return '—';const h=Math.floor(ms/3600000),m=Math.floor((ms%3600000)/60000);return `${h}h ${m}m`}
function fmtDate(s,short=false){if(!s)return '—';const d=new Date(s);return d.toLocaleDateString('es-CO',short?{month:'short',day:'numeric'}:{weekday:'short',month:'short',day:'numeric'})}
function rColor(s){return s>=67?'#22c55e':s>=34?'#f59e0b':'#ef4444'}
function rTag(s){
  const [cls,txt]=s>=67?['tag-green','Óptimo']:s>=34?['tag-amber','Moderado']:['tag-red','Bajo'];
  return `<span class="tag ${cls}">${txt}</span>`;
}
function delta(cur,prev,unit='',inv=false){
  if(cur==null||prev==null) return '';
  const diff=cur-prev, pct=Math.round(diff);
  if(Math.abs(diff)<0.5) return '<span class="delta flat">= Sin cambio</span>';
  const up = inv ? diff<0 : diff>0;
  const sign=diff>0?'+':'';
  return `<span class="delta ${up?'up':'down'}">${up?'↑':'↓'} ${sign}${f1(diff)}${unit}</span>`;
}

// ── DATA ──────────────────────────────────────────────────
const prof = RAW.profile||{};
const body = RAW.body||{};
const recs  = RAW.recovery||[];
const sleeps= RAW.sleep||[];
const wrks  = RAW.workouts||[];
const cycs  = RAW.cycles||[];

const mainSleeps = sleeps.filter(s=>!s.nap);
const scoredRecs = recs.filter(r=>r.score_state==='SCORED'&&r.score);
const scoredSleeps = mainSleeps.filter(s=>s.score_state==='SCORED'&&s.score);

// ── PROFILE ───────────────────────────────────────────────
const fn = prof.first_name||'';
const ln = prof.last_name||'';
$('avatar').textContent = fn[0]||'?';
$('pname').textContent = [fn,ln].filter(Boolean).join(' ')||'—';
$('pemail').textContent = prof.email||'—';
$('huser').textContent = fn||'';
$('ps-h').textContent = body.height_meter ? Math.round(body.height_meter*100)+'cm' : '—';
$('ps-w').textContent = body.weight_kilogram ? body.weight_kilogram.toFixed(1)+'kg' : '—';
$('ps-hr').textContent = body.max_heart_rate ? body.max_heart_rate+'bpm' : '—';
$('b-height').textContent = body.height_meter ? Math.round(body.height_meter*100) : '—';
$('b-weight').textContent = body.weight_kilogram ? body.weight_kilogram.toFixed(1) : '—';
$('b-maxhr').textContent = body.max_heart_rate||'—';

// ── RECOVERY ──────────────────────────────────────────────
const r0 = scoredRecs[0], r1 = scoredRecs[1];
if(r0){
  const sc=r0.score, score=Math.round(sc.recovery_score);
  $('rec-score').textContent = score;
  $('rec-tag').innerHTML = rTag(score);
  $('rec-delta').innerHTML = r1 ? delta(score,Math.round(r1.score.recovery_score),'%') : '';
  const circ=427.26, offset=circ-(score/100)*circ;
  const ring=$('ring-fg');
  ring.style.stroke=rColor(score);
  setTimeout(()=>ring.style.strokeDashoffset=offset,200);

  $('kpi-hrv').textContent = f1(sc.hrv_rmssd_milli);
  $('kpi-rhr').textContent = f0(sc.resting_heart_rate);
  $('kpi-spo2').textContent = sc.spo2_percentage ? f1(sc.spo2_percentage) : '—';
  if(r1){
    $('kpi-hrv-d').innerHTML = delta(sc.hrv_rmssd_milli,r1.score.hrv_rmssd_milli,' ms');
    $('kpi-rhr-d').innerHTML = delta(sc.resting_heart_rate,r1.score.resting_heart_rate,' bpm',true);
  }
}

// Strain from latest cycle
if(cycs.length&&cycs[0].score){
  $('kpi-strain').textContent = f1(cycs[0].score.strain);
}

// Recovery bars
const barsEl = $('rec-bars');
scoredRecs.slice(0,8).reverse().forEach(r=>{
  const s=Math.round(r.score.recovery_score);
  const col=rColor(s);
  const div=document.createElement('div');
  div.className='mbar-col';
  div.innerHTML=`<div class="mbar" style="height:${Math.max(s*.45,4)}px;background:${col}"></div><div class="mbar-lbl">${s}</div>`;
  barsEl.appendChild(div);
});

// ── SLEEP OVERVIEW ────────────────────────────────────────
const sl0=scoredSleeps[0], sl1=scoredSleeps[1];
if(sl0){
  const ss=sl0.score;
  const perf=Math.round(ss.sleep_performance_percentage||0);
  const eff=ss.sleep_efficiency_percentage||0;
  const dur=sl0.start&&sl0.end?msToH(new Date(sl0.end)-new Date(sl0.start)):'—';
  $('sl-perf').textContent=perf;
  $('sl-eff').textContent=eff.toFixed(0);
  $('sl-dur').textContent='Duración: '+dur;
  if(sl1) $('sl-perf-d').innerHTML=delta(perf,Math.round(sl1.score.sleep_performance_percentage||0),'%');

  if(ss.stage_summary){
    const st=ss.stage_summary,tot=st.total_in_bed_time_milli||1;
    const stages=[
      {n:'Ligero',v:st.total_light_sleep_time_milli,c:'#60a5fa'},
      {n:'Profundo',v:st.total_slow_wave_sleep_time_milli,c:'#00e5c3'},
      {n:'REM',v:st.total_rem_sleep_time_milli,c:'#a78bfa'},
      {n:'Despierto',v:st.total_awake_time_milli,c:'#475569'},
    ];
    $('sl-stages-ov').innerHTML=stages.map(sg=>{
      const pct=Math.round((sg.v||0)/tot*100);
      return `<div class="stage-row">
        <div class="sdot" style="background:${sg.c}"></div>
        <div class="sname">${sg.n}</div>
        <div class="sbar-wrap"><div class="sbar" style="width:${pct}%;background:${sg.c}"></div></div>
        <div class="sval">${msToH(sg.v)}</div>
      </div>`;
    }).join('');

    // Donut
    new Chart($('chartSleepDonut'),{
      type:'doughnut',
      data:{
        labels:['Ligero','Profundo','REM','Despierto'],
        datasets:[{data:stages.map(s=>Math.round((s.v||0)/60000)),backgroundColor:stages.map(s=>s.c),borderWidth:0,hoverOffset:6}]
      },
      options:{
        responsive:true,maintainAspectRatio:false,
        cutout:'72%',
        plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>' '+msToH(c.raw*60000)}}},
      }
    });
  }
}

// ── INSIGHTS ──────────────────────────────────────────────
const insightsEl=$('insights');
const iList=[];
if(r0){
  const sc=r0.score,s=Math.round(sc.recovery_score);
  if(s>=80) iList.push({cls:'good',icon:'💚',txt:`Recovery excelente hoy (${s}%) — buena para entrenar fuerte`});
  else if(s<40) iList.push({cls:'bad',icon:'🔴',txt:`Recovery bajo (${s}%) — considera descansar o entrenar suave`});
  if(sc.hrv_rmssd_milli){
    const avgHRV=scoredRecs.slice(0,7).reduce((a,r)=>a+(r.score.hrv_rmssd_milli||0),0)/Math.min(scoredRecs.length,7);
    if(sc.hrv_rmssd_milli>avgHRV*1.1) iList.push({cls:'good',icon:'📈',txt:`Tu HRV (${f1(sc.hrv_rmssd_milli)} ms) está por encima de tu promedio semanal`});
    else if(sc.hrv_rmssd_milli<avgHRV*0.85) iList.push({cls:'warn',icon:'⚠️',txt:`Tu HRV está por debajo de tu promedio — señal de fatiga acumulada`});
  }
}
if(sl0&&sl0.score){
  const p=Math.round(sl0.score.sleep_performance_percentage||0);
  if(p>=90) iList.push({cls:'good',icon:'🌙',txt:`Dormiste excelente anoche (${p}% performance)`});
  else if(p<60) iList.push({cls:'warn',icon:'😴',txt:`Sueño insuficiente anoche (${p}%) — intenta acostarte más temprano`});
  if(sl0.score.stage_summary){
    const rem=sl0.score.stage_summary.total_rem_sleep_time_milli||0;
    if(rem<3600000) iList.push({cls:'info',icon:'🧠',txt:`Bajo REM anoche (${msToH(rem)}) — el REM óptimo es 90-120 min`});
  }
}
if(!iList.length) iList.push({cls:'info',icon:'📊',txt:'Sigue entrenando para ver más insights personalizados'});
insightsEl.innerHTML=iList.slice(0,3).map(i=>`<div class="insight ${i.cls}"><span class="insight-icon">${i.icon}</span><span>${i.txt}</span></div>`).join('');

// ── CHART: TREND (Recovery + HRV + Strain) ───────────────
{
  const last7rec=scoredRecs.slice(0,7).reverse();
  const last7cyc=cycs.filter(c=>c.score).slice(0,7).reverse();
  const labels=last7rec.map(r=>fmtDate(r.created_at,true));
  const recScores=last7rec.map(r=>Math.round(r.score.recovery_score));
  const hrvVals=last7rec.map(r=>f1(r.score.hrv_rmssd_milli));
  const strainVals=last7cyc.map(c=>f1(c.score.strain));
  const strainLabels=last7cyc.map(c=>fmtDate(c.start,true));

  const ctx=$('chartTrend').getContext('2d');
  const grad=ctx.createLinearGradient(0,0,0,240);
  grad.addColorStop(0,'rgba(0,229,195,.25)');grad.addColorStop(1,'rgba(0,229,195,0)');
  const gradP=ctx.createLinearGradient(0,0,0,240);
  gradP.addColorStop(0,'rgba(167,139,250,.2)');gradP.addColorStop(1,'rgba(167,139,250,0)');

  new Chart(ctx,{
    type:'line',
    data:{
      labels,
      datasets:[
        {label:'Recovery %',data:recScores,borderColor:'#00e5c3',backgroundColor:grad,borderWidth:2.5,pointRadius:4,pointBackgroundColor:'#00e5c3',tension:.4,fill:true,yAxisID:'y'},
        {label:'HRV ms',data:hrvVals,borderColor:'#a78bfa',backgroundColor:gradP,borderWidth:2,pointRadius:3,pointBackgroundColor:'#a78bfa',tension:.4,fill:true,yAxisID:'y2'},
      ]
    },
    options:{
      responsive:true,maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},
      plugins:{
        legend:{labels:{color:'#94a3b8',font:{size:11},boxWidth:12,padding:16}},
        tooltip:{backgroundColor:'#111624',borderColor:'#1a2035',borderWidth:1,titleColor:'#e2e8f0',bodyColor:'#94a3b8',padding:12}
      },
      scales:{
        x:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#64748b',font:{size:10}}},
        y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#64748b',font:{size:10}},min:0,max:100},
        y2:{position:'right',grid:{display:false},ticks:{color:'#a78bfa',font:{size:10}}},
      }
    }
  });
}

// ── CHART: SLEEP TREND ────────────────────────────────────
{
  const last7sl=scoredSleeps.slice(0,7).reverse();
  const labels=last7sl.map(s=>fmtDate(s.start,true));
  const perf=last7sl.map(s=>Math.round(s.score.sleep_performance_percentage||0));
  const eff=last7sl.map(s=>+(s.score.sleep_efficiency_percentage||0).toFixed(1));
  const rem=last7sl.map(s=>+((s.score.stage_summary?.total_rem_sleep_time_milli||0)/3600000).toFixed(2));
  const sws=last7sl.map(s=>+((s.score.stage_summary?.total_slow_wave_sleep_time_milli||0)/3600000).toFixed(2));

  new Chart($('chartSleepTrend'),{
    type:'bar',
    data:{
      labels,
      datasets:[
        {label:'Performance %',data:perf,backgroundColor:'rgba(245,158,11,.7)',borderRadius:6,yAxisID:'y'},
        {label:'Eficiencia %',data:eff,backgroundColor:'rgba(59,130,246,.5)',borderRadius:6,yAxisID:'y'},
        {label:'REM (h)',data:rem,backgroundColor:'rgba(167,139,250,.7)',borderRadius:6,yAxisID:'y2'},
        {label:'Profundo (h)',data:sws,backgroundColor:'rgba(0,229,195,.5)',borderRadius:6,yAxisID:'y2'},
      ]
    },
    options:{
      responsive:true,maintainAspectRatio:false,
      interaction:{mode:'index',intersect:false},
      plugins:{
        legend:{labels:{color:'#94a3b8',font:{size:11},boxWidth:12,padding:16}},
        tooltip:{backgroundColor:'#111624',borderColor:'#1a2035',borderWidth:1,titleColor:'#e2e8f0',bodyColor:'#94a3b8',padding:12}
      },
      scales:{
        x:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#64748b',font:{size:10}}},
        y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#64748b',font:{size:10}},min:0,max:100},
        y2:{position:'right',grid:{display:false},ticks:{color:'#94a3b8',font:{size:10}}},
      }
    }
  });
}

// ── SLEEP LIST ────────────────────────────────────────────
{
  const el=$('sleep-list');
  mainSleeps.slice(0,14).forEach(sl=>{
    const sc=sl.score_state==='SCORED'&&sl.score?sl.score:null;
    const perf=sc&&sc.sleep_performance_percentage?Math.round(sc.sleep_performance_percentage):null;
    const eff=sc?+(sc.sleep_efficiency_percentage||0).toFixed(0):null;
    const dur=sl.start&&sl.end?msToH(new Date(sl.end)-new Date(sl.start)):'—';
    const rem=sc&&sc.stage_summary?msToH(sc.stage_summary.total_rem_sleep_time_milli):'—';
    const sws=sc&&sc.stage_summary?msToH(sc.stage_summary.total_slow_wave_sleep_time_milli):'—';
    const light=sc&&sc.stage_summary?sc.stage_summary.total_light_sleep_time_milli:0;
    const remMs=sc&&sc.stage_summary?sc.stage_summary.total_rem_sleep_time_milli:0;
    const swsMs=sc&&sc.stage_summary?sc.stage_summary.total_slow_wave_sleep_time_milli:0;
    const awk=sc&&sc.stage_summary?sc.stage_summary.total_awake_time_milli:0;
    const tot=(light+remMs+swsMs+awk)||1;
    const pct=v=>Math.round(v/tot*100);

    const perfColor=perf>=80?'#22c55e':perf>=60?'#f59e0b':'#ef4444';
    el.innerHTML+=`<div class="sleep-item">
      <div class="sl-header">
        <div><div class="sl-date">${fmtDate(sl.start)}</div><div class="sl-dur">Duración: ${dur}${sl.nap?' · Siesta':''}</div></div>
        <div class="sl-stats">
          <div class="sl-stat"><div class="sl-stat-val" style="color:${perfColor}">${perf!=null?perf+'%':'—'}</div><div class="sl-stat-key">Performance</div></div>
          <div class="sl-stat"><div class="sl-stat-val" style="color:#3b82f6">${eff!=null?eff+'%':'—'}</div><div class="sl-stat-key">Eficiencia</div></div>
          <div class="sl-stat"><div class="sl-stat-val" style="color:#a78bfa">${rem}</div><div class="sl-stat-key">REM</div></div>
          <div class="sl-stat"><div class="sl-stat-val" style="color:#00e5c3">${sws}</div><div class="sl-stat-key">Profundo</div></div>
        </div>
      </div>
      ${sc&&sc.stage_summary?`<div class="sl-stages">
        <div class="sl-bar-row">
          <div class="sl-bar-seg" style="flex:${pct(light)};background:#60a5fa;min-width:4px" title="Ligero ${msToH(light)}"></div>
          <div class="sl-bar-seg" style="flex:${pct(swsMs)};background:#00e5c3;min-width:4px" title="Profundo ${sws}"></div>
          <div class="sl-bar-seg" style="flex:${pct(remMs)};background:#a78bfa;min-width:4px" title="REM ${rem}"></div>
          <div class="sl-bar-seg" style="flex:${pct(awk)};background:#334155;min-width:2px" title="Despierto ${msToH(awk)}"></div>
        </div>
        <div style="display:flex;gap:16px;margin-top:8px;flex-wrap:wrap">
          <span style="font-size:10px;color:#60a5fa">■ Ligero ${msToH(light)}</span>
          <span style="font-size:10px;color:#00e5c3">■ Profundo ${sws}</span>
          <span style="font-size:10px;color:#a78bfa">■ REM ${rem}</span>
          <span style="font-size:10px;color:#475569">■ Despierto ${msToH(awk)}</span>
        </div>
      </div>`:''}
    </div>`;
  });
}

// ── CHART: STRAIN ─────────────────────────────────────────
{
  const scored=cycs.filter(c=>c.score).slice(0,14).reverse();
  const labels=scored.map(c=>fmtDate(c.start,true));
  const strain=scored.map(c=>+f1(c.score.strain));
  const ctx=$('chartStrain').getContext('2d');
  const grad=ctx.createLinearGradient(0,0,0,240);
  grad.addColorStop(0,'rgba(245,158,11,.3)');grad.addColorStop(1,'rgba(245,158,11,0)');
  new Chart(ctx,{
    type:'bar',
    data:{
      labels,
      datasets:[{label:'Strain diario',data:strain,backgroundColor:strain.map(v=>v>15?'rgba(239,68,68,.7)':v>10?'rgba(245,158,11,.7)':'rgba(34,197,94,.6)'),borderRadius:6}]
    },
    options:{
      responsive:true,maintainAspectRatio:false,
      plugins:{
        legend:{display:false},
        tooltip:{backgroundColor:'#111624',borderColor:'#1a2035',borderWidth:1,titleColor:'#e2e8f0',bodyColor:'#94a3b8',padding:12}
      },
      scales:{
        x:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#64748b',font:{size:10}}},
        y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#64748b',font:{size:10}},min:0,max:21,
          afterDataLimits(a){a.max=21}
        },
      }
    }
  });
}

// ── WORKOUT LIST ──────────────────────────────────────────
{
  const el=$('workout-list');
  const zc=['#334155','#1d4ed8','#16a34a','#ca8a04','#dc2626','#7c3aed'];
  wrks.slice(0,15).forEach((w,i)=>{
    const sc=w.score;
    const strain=sc?f1(sc.strain):'—';
    const kcal=sc?Math.round(sc.kilojoule*0.239):'—';
    const avghr=sc?sc.average_heart_rate:'—';
    const maxhr=sc?sc.max_heart_rate:'—';
    const dist=sc&&sc.distance_meter?(sc.distance_meter/1000).toFixed(2)+' km':'';

    let zonesHtml='';
    if(sc&&sc.zone_durations){
      const zd=sc.zone_durations;
      const vals=[zd.zone_zero_milli,zd.zone_one_milli,zd.zone_two_milli,zd.zone_three_milli,zd.zone_four_milli,zd.zone_five_milli];
      const tot=vals.reduce((a,b)=>a+b,1);
      const mx=Math.max(...vals);
      zonesHtml=`<div style="margin-top:12px">
        <div style="font-family:var(--mono);font-size:10px;color:var(--sub);margin-bottom:8px;letter-spacing:.12em">ZONAS DE FC</div>
        <div class="zones-wrap">${vals.map((v,j)=>`<div class="zone-col">
          <div class="zone-pct">${Math.round(v/tot*100)}%</div>
          <div class="zone-bar" style="height:${mx>0?Math.max(v/mx*48,4):4}px;background:${zc[j]}"></div>
          <div class="zone-lbl">Z${j}</div>
        </div>`).join('')}</div>
      </div>`;
    }

    const id=`wd-${i}`;
    el.innerHTML+=`<div class="workout-item" id="${id}" onclick="toggleWorkout('${id}')">
      <div class="wi-header">
        <div class="wi-left">
          <div class="wi-sport">${w.sport_name||'Workout'}</div>
          <div class="wi-date">${fmtDate(w.start)}${dist?' · '+dist:''}</div>
        </div>
        <div class="wi-right">
          <div class="wstat"><div class="wstat-val" style="color:var(--teal)">${strain}</div><div class="wstat-key">Strain</div></div>
          <div class="wstat"><div class="wstat-val">${avghr}</div><div class="wstat-key">FC Prom</div></div>
          <div class="wstat"><div class="wstat-val" style="color:var(--amber)">${kcal}</div><div class="wstat-key">kcal</div></div>
          <div class="wi-chevron">⌄</div>
        </div>
      </div>
      <div class="wi-detail" id="${id}-d">
        <div style="display:flex;gap:28px;flex-wrap:wrap">
          <div><div style="font-family:var(--mono);font-size:20px;color:#ef4444">${maxhr}</div><div style="font-size:10px;color:var(--sub);margin-top:3px;letter-spacing:.12em">FC MÁXIMA</div></div>
          <div><div style="font-family:var(--mono);font-size:20px">${msToH(w.start&&w.end?new Date(w.end)-new Date(w.start):0)}</div><div style="font-size:10px;color:var(--sub);margin-top:3px;letter-spacing:.12em">DURACIÓN</div></div>
          ${dist?`<div><div style="font-family:var(--mono);font-size:20px;color:#3b82f6">${dist}</div><div style="font-size:10px;color:var(--sub);margin-top:3px;letter-spacing:.12em">DISTANCIA</div></div>`:''}
        </div>
        ${zonesHtml}
      </div>
    </div>`;
  });
}

function toggleWorkout(id){
  const item=document.getElementById(id);
  const detail=document.getElementById(id+'-d');
  item.classList.toggle('open');
  detail.classList.toggle('open');
}

// ── BODY CHARTS ───────────────────────────────────────────
{
  const scored=scoredRecs.slice(0,14).reverse();
  const labels=scored.map(r=>fmtDate(r.created_at,true));

  // HRV
  new Chart($('chartHRV'),{type:'line',data:{labels,datasets:[{label:'HRV ms',data:scored.map(r=>+f1(r.score.hrv_rmssd_milli)),borderColor:'#a78bfa',backgroundColor:'rgba(167,139,250,.1)',borderWidth:2.5,pointRadius:4,pointBackgroundColor:'#a78bfa',tension:.4,fill:true}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{backgroundColor:'#111624',borderColor:'#1a2035',borderWidth:1,titleColor:'#e2e8f0',bodyColor:'#94a3b8',padding:12}},
    scales:{x:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#64748b',font:{size:10}}},y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#a78bfa',font:{size:10}}}}}
  });

  // RHR
  new Chart($('chartRHR'),{type:'line',data:{labels,datasets:[{label:'FC Reposo',data:scored.map(r=>+f0(r.score.resting_heart_rate)),borderColor:'#7c3aed',backgroundColor:'rgba(124,58,237,.1)',borderWidth:2.5,pointRadius:4,pointBackgroundColor:'#7c3aed',tension:.4,fill:true}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{backgroundColor:'#111624',borderColor:'#1a2035',borderWidth:1,titleColor:'#e2e8f0',bodyColor:'#94a3b8',padding:12}},
    scales:{x:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#64748b',font:{size:10}}},y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7c3aed',font:{size:10}}}}}
  });

  // SPO2
  const withSpo2=scored.filter(r=>r.score.spo2_percentage);
  new Chart($('chartSpo2'),{type:'line',data:{labels:withSpo2.map(r=>fmtDate(r.created_at,true)),datasets:[{label:'SpO₂ %',data:withSpo2.map(r=>+f1(r.score.spo2_percentage)),borderColor:'#3b82f6',backgroundColor:'rgba(59,130,246,.1)',borderWidth:2.5,pointRadius:4,pointBackgroundColor:'#3b82f6',tension:.4,fill:true}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{backgroundColor:'#111624',borderColor:'#1a2035',borderWidth:1,titleColor:'#e2e8f0',bodyColor:'#94a3b8',padding:12}},
    scales:{x:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#64748b',font:{size:10}}},y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#3b82f6',font:{size:10}},min:90,max:100}}}
  });
}

// ── TABS ──────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(tab=>{
  tab.addEventListener('click',()=>{
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-'+tab.dataset.tab).classList.add('active');
  });
});
</script>
</body>
</html>
"""


if __name__ == '__main__':
    print("\n  ✅ WHOOP Dashboard v2 corriendo en: http://localhost:3000\n")
    app.run(port=3000, debug=False)
