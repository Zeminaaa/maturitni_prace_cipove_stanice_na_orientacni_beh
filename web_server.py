"""
Jednoduchý neblokující HTTP server pro dashboard na master stanici.

Použití je záměrně jednoduché: vytvoří se `WebServer(state)` a v hlavní
smyčce se opakovaně volá `handle()`.
"""

import socket
import time

try:
    import os
except ImportError:
    import uos as os

try:
    import json
except ImportError:
    import ujson as json

try:
    import machine
except ImportError:
    machine = None


MAX_SYNC_STATIONS = 8
MAX_VISIBLE_STATIONS = MAX_SYNC_STATIONS + 1
RACES_DIR = 'races'
ACTIVE_RACE_STATE_PATH = '%s/active_race.json' % RACES_DIR
HTML_PARTS = (
    "<!DOCTYPE html>\n<html lang=\"cs\">\n<head>\n<meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n<title>Ovládání Orientačního Běhu</title>\n<style>\n:root{\n  color-scheme:light;\n  --bg:#f5f5f7;\n  --panel:#fff;\n  --panel-alt:#f0f1f4;\n  --line:#d2d5db;\n  --text:#111214;\n  --muted:#50545c;\n  --accent:#007aff;\n  --danger:#c9342f;\n  --danger-soft:#fff1f0;\n  --safe:#147a2e;\n  --safe-soft:#e7f7eb;\n  --shadow:0 10px 28px rgba(0,0,0,.08);\n  --radius:18px;\n}\n[data-theme=\"dark\"]{\n  color-scheme:dark;\n  --bg:#111214;\n  --panel:#1b1d21;\n  --panel-alt:#262930;\n  --line:#353942;\n  --text:#f5f7fa;\n  --muted:#b0b6c2;\n  --accent:#4da3ff;\n  --danger:#ff7b72;\n  --danger-soft:#472625;\n  --safe:#7ee787;\n  --safe-soft:#183824;\n  --shadow:0 10px 28px rgba(0,0,0,.35);\n}\n*{box-sizing:border-box}\nhtml,body{margin:0;padding:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif}\nbutton,input{font:inherit}\n.app{max-width:980px;margin:0 auto;padding:16px 16px 28px}\n.topbar{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:16px}\nh1{font-size:2rem;line-height:1.1;margin:0;letter-spacing:0}\n.theme-toggle{height:44px;border:0;border-radius:12px;background:var(--panel-alt);color:var(--text);padding:0 14px;font-weight:700}\n.panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow)}\n.stack{display:flex;flex-direction:column;gap:14px}\n.status-card,.control-card,.table-shell{padding:18px}\n.status-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:14px}\n.eyebrow{font-size:.82rem;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.04em}\n.mode{display:",
    "inline-flex;align-items:center;gap:8px;padding:8px 12px;border-radius:999px;background:var(--panel-alt);font-weight:700}\n.mode-dot{width:10px;height:10px;border-radius:50%;background:var(--muted)}\n.mode.IDLE .mode-dot{background:#7d8188}\n.mode.SYNCING .mode-dot{background:var(--accent)}\n.mode.READING .mode-dot{background:var(--safe)}\n.status-copy{font-size:1.08rem;font-weight:700;line-height:1.35;margin-top:6px}\n.status-meta{display:flex;flex-wrap:wrap;gap:10px 18px;padding-top:2px}\n.status-meta-item{color:var(--muted);font-size:.95rem;font-weight:600}\n.status-meta-item strong{color:var(--text);font-weight:800}\n.control-row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}\n.field{display:flex;flex-direction:column;gap:10px;min-width:180px;flex:1}\n.field label{font-size:.9rem;color:var(--muted);font-weight:600}\n.slider-row{display:flex;align-items:center;gap:14px}\n.slider-value{min-width:42px;height:42px;display:flex;align-items:center;justify-content:center;border-radius:12px;background:var(--panel-alt);font-size:1.15rem;font-weight:800}\ninput[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:6px;border-radius:999px;background:#d7dae0;outline:none}\ninput[type=range]::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:28px;height:28px;border-radius:50%;background:var(--accent);border:0;box-shadow:0 2px 6px rgba(0,0,0,.18)}\ninput[type=range]::-moz-range-thumb{width:28px;height:28px;border-radius:50%;background:var(--accent);border:0;box-shadow:0 2px 6px rgba(0,0,0,.18)}\n.slider-scale{display:flex;justify-content:space-between;color:var(--muted);font-size:.82rem;padding:0 2px}\n.btn{height:50px;border:0;border-radius:14px;padding:0 18px;font-weight:700}\n.btn-primary{background:var(--accent);color:#fff}\n.btn-secondary{background:var",
    "(--panel-alt);color:var(--text)}\n.btn-danger{background:var(--danger-soft);color:var(--danger)}\n.btn-safe{background:var(--safe-soft);color:var(--safe)}\n.error-banner{display:none;padding:14px 16px;border-radius:14px;background:var(--danger-soft);color:var(--danger);font-weight:700}\n.error-banner.visible{display:block}\n.warning-banner{display:none;padding:14px 16px;border-radius:14px;background:#fff7d6;color:#6a5200;font-weight:700;line-height:1.45}\n.warning-banner.visible{display:block}\n[data-theme=\"dark\"] .warning-banner{background:#4a3b08;color:#ffe08a}\n.section-title{padding:0 4px}\n.section-title h2{margin:0;font-size:1.15rem}\n.table-wrap{overflow:auto;margin-top:12px;border:1px solid var(--line);border-radius:14px}\ntable{width:100%;border-collapse:collapse;min-width:560px;background:var(--panel)}\nth,td{text-align:left;padding:12px 14px;border-bottom:1px solid var(--line);white-space:nowrap}\nth{font-size:.85rem;color:var(--muted);background:var(--panel);position:sticky;top:0}\ntbody tr:nth-child(even) td{background:var(--panel-alt)}\n.icon-btn{border:0;background:var(--panel-alt);color:var(--text);width:40px;height:40px;border-radius:12px;font-weight:800}\n.name-action{display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;border:0;background:transparent;color:var(--text);padding:0;text-align:left;font-weight:700}\n.name-action.empty{color:var(--accent)}\n.name-text{overflow:hidden;text-overflow:ellipsis}\n.name-edit-indicator{color:var(--muted);font-size:1rem;flex:0 0 auto}\n.detail-row td{white-space:normal;background:var(--panel-alt)!important;padding:0}\n.detail-shell{padding:14px}\n.detail-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}\n.detail-cell{background:var(--panel);border-radius:12px;padding:10px 8px}\n.detail-",
    "cell strong{display:block;font-size:.82rem;color:var(--muted);margin-bottom:6px}\n.detail-cell span{font-size:1rem;font-weight:700;word-break:break-word}\n.empty{padding:20px;border-radius:14px;background:var(--panel-alt);color:var(--muted);font-weight:600}\n.sheet{position:fixed;inset:0;background:rgba(17,18,20,.28);display:none;align-items:flex-start;justify-content:center;padding:calc(env(safe-area-inset-top,0px) + 12px) 12px 12px}\n.sheet.open{display:flex}\n.sheet-card{width:min(100%,560px);background:var(--panel);border-radius:18px;padding:18px 18px 22px;box-shadow:var(--shadow)}\n.sheet-head{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px}\n.sheet-head h3{margin:0;font-size:1.15rem}\n.sheet-head p{margin:4px 0 0;color:var(--muted);font-size:.92rem}\n.sheet-close{border:0;background:var(--panel-alt);width:36px;height:36px;border-radius:50%;font-size:1.15rem;color:var(--text)}\n.sheet-actions{display:flex;gap:10px;margin-top:14px;flex-wrap:wrap}\n.warning-text{color:var(--danger);font-weight:700;line-height:1.45}\n.warning-copy{color:var(--muted);line-height:1.5;margin-top:10px}\n@media(max-width:759px){\n  .app{padding:14px 14px 24px}\n  h1{font-size:1.72rem}\n  .status-copy{font-size:1rem}\n  .control-row{flex-direction:column;align-items:stretch}\n  .field{width:100%}\n  .btn{width:100%}\n  .sheet{padding:calc(env(safe-area-inset-top,0px) + 8px) 10px 10px}\n  .detail-grid{grid-template-columns:repeat(2,minmax(0,1fr))}\n  }\n</style>\n</head>\n<body data-theme=\"light\">\n<div class=\"app stack\">\n  <div class=\"topbar\">\n    <h1>Ovládání Orientačního Běhu</h1>\n    <button class=\"theme-toggle\" onclick=\"toggleTheme()\">Tmavý režim</button>\n  </div>\n  <div id=\"errorBanner\" class=\"error-banner\"></div>\n  <div id=\"connectionBanner\" class=\"warning-banner\"></di",
    "v>\n  <section class=\"panel status-card\">\n    <div class=\"status-head\">\n      <div>\n        <div class=\"eyebrow\">Status</div>\n        <div id=\"modeBadge\" class=\"mode IDLE\"><span class=\"mode-dot\"></span><span>Ukončeno</span></div>\n        <div id=\"statusCopy\" class=\"status-copy\">Závod skončil</div>\n      </div>\n    </div>\n    <div class=\"status-meta\">\n      <div class=\"status-meta-item\">Stanice celkem: <strong id=\"stationCountValue\">0</strong></div>\n      <div class=\"status-meta-item\">Synchronizováno: <strong id=\"syncedValue\">0 / 0</strong></div>\n    </div>\n  </section>\n  <section class=\"panel control-card\">\n    <div class=\"control-row\">\n      <div class=\"field\">\n        <label for=\"stationInput\">Počet slave stanic pro synchronizaci</label>\n        <div class=\"slider-row\">\n          <input id=\"stationInput\" type=\"range\" min=\"1\" max=\"8\" step=\"1\" value=\"8\" oninput=\"updateStationValue()\">\n          <div id=\"stationSliderValue\" class=\"slider-value\">8</div>\n        </div>\n        <div class=\"slider-scale\"><span>1</span><span>8</span></div>\n      </div>\n      <button class=\"btn btn-primary\" onclick=\"startSync()\">Spustit synchronizaci</button>\n      <button class=\"btn btn-secondary\" onclick=\"resumeLastRace()\">Pokračovat v posledním závodě</button>\n      <button class=\"btn btn-danger\" onclick=\"openStopSheet()\">Ukončit závod</button>\n    </div>\n  </section>\n  <div class=\"section-title\"><h2>Výsledky</h2></div>\n  <section class=\"panel table-shell\">\n    <div class=\"control-row\">\n      <button class=\"btn btn-secondary\" onclick=\"downloadCsv()\">Stáhnout CSV</button>\n    </div>\n    <div class=\"table-wrap\">\n      <table>\n        <thead><tr id=\"tableHeadRow\"></tr></thead>\n        <tbody id=\"tableBody\"></tbody>\n      </table>\n    </div>\n  </section>\n</div>\n<div id=\"nameSheet\" class=\"sheet\" aria-hidden=\"true\">\n  <div class=\"sheet-card\">\n    <div class=\"sheet-head\">\n      <div>\n        <h3>Upravit jméno běžce",
    "</h3>\n        <p id=\"sheetUid\">UID</p>\n      </div>\n      <button class=\"sheet-close\" onclick=\"closeSheet()\" aria-label=\"Zavřít\">x</button>\n    </div>\n    <div class=\"field\">\n      <label for=\"runnerNameInput\">Jméno běžce</label>\n      <input id=\"runnerNameInput\" type=\"text\" maxlength=\"80\" placeholder=\"Neznámý běžec\">\n    </div>\n    <div class=\"sheet-actions\">\n      <button class=\"btn btn-primary\" onclick=\"saveName()\">Uložit</button>\n      <button class=\"btn btn-secondary\" onclick=\"clearName()\">Vymazat</button>\n    </div>\n  </div>\n</div>\n<div id=\"stopSheet\" class=\"sheet\" aria-hidden=\"true\">\n  <div class=\"sheet-card\">\n    <div class=\"sheet-head\">\n      <div><h3>Ukončit závod?</h3></div>\n      <button class=\"sheet-close\" onclick=\"closeStopSheet()\" aria-label=\"Zavřít\">x</button>\n    </div>\n    <div class=\"warning-text\">Toto je zásadní rozhodnutí. Ukončení závod nadobro ukončí a nepůjde již znovu pokračovat. Celý závod by se tak musel běhat znovu, pokud ještě není dokončený.</div>\n    <div class=\"warning-copy\">Potvrďte pouze tehdy, pokud je závod skutečně ukončen nebo vědomě končíte tuto relaci. Před finálním potvrzením musíte počkat 10 sekund.</div>\n    <div class=\"sheet-actions\">\n      <button id=\"stopConfirmButton\" class=\"btn btn-danger\" onclick=\"confirmStop()\" disabled>Potvrdit zastavení (10)</button>\n      <button class=\"btn btn-safe\" onclick=\"closeStopSheet()\">Vrátit se k závodu</button>\n    </div>\n  </div>\n</div>\n<div id=\"syncSheet\" class=\"sheet\" aria-hidden=\"true\">\n  <div class=\"sheet-card\">\n    <div class=\"sheet-head\">\n      <div><h3>Znovu spustit synchronizaci?</h3></div>\n      <button class=\"sheet-close\" onclick=\"closeSyncSheet()\" aria-label=\"Zavřít\">x</button>\n    </div>\n    <div class=\"warning-text\">Druhý sync je destruktivní nouzová akce. Stanice, které už přešly do závodu, už na nový sync neodpoví a synchronizace se pravděpodobně nikdy nedokončí.</div>\n    <div class=\"warning-copy\">Pokračujte pouze tehdy, pokud se při prvním syncu nepřipojila ani jedna stanice a vědomě chcete začít synchronizaci znovu. Před potvrzením musíte počkat 10 sekund.</div>\n    <div class=\"sheet-actions\">\n      <button id=\"syncConfirmButton\" class=\"btn btn-danger\" onclick=\"confirmForcedSync()\" disabled>Vím co dělám (10)</button>\n      <button class=\"btn btn-safe\" onclick=\"closeSyncSheet()\">Zrušit</button>\n    </div>\n  </div>\n</div>\n<script>\nvar currentStatus=null;\nvar activeReadId=null;\nvar expandedReads={};\nvar stopCountdownTimer=null;\nvar stopCountdownValue=10;\nvar syncCountdownTimer=null;\nvar syncCountdownValue=10;\nvar pendingSyncValue=null;\nvar CACHE_KEY='race-control-cache-v2';\nvar PENDING_NAMES_KEY='race-control-pending-names-v1';\nvar lastLiveStatusAt=0;\nvar showingCachedStatus=false;\nfunction applyTheme(theme){\n  document.body.setAttribute('data-theme',theme);",
    "\n  document.querySelector('.theme-toggle').textContent=theme==='dark'?'Světlý režim':'Tmavý režim';\n  try{window.localStorage.setItem('race-control-theme',theme)}catch(e){}\n}\nfunction toggleTheme(){\n  var current=document.body.getAttribute('data-theme')||'light';\n  applyTheme(current==='dark'?'light':'dark');\n}\nfunction updateStationValue(){\n  document.getElementById('stationSliderValue').textContent=document.getElementById('stationInput').value;\n}\nfunction showError(message){\n  var banner=document.getElementById('errorBanner');\n  banner.textContent=message;\n  banner.classList.add('visible');\n}\nfunction clearError(){\n  var banner=document.getElementById('errorBanner');\n  banner.textContent='';\n  banner.classList.remove('visible');\n}\nfunction showConnectionWarning(message){\n  var banner=document.getElementById('connectionBanner');\n  banner.textContent=message;\n  banner.classList.add('visible');\n}\nfunction clearConnectionWarning(){\n  var banner=document.getElementById('connectionBanner');\n  banner.textContent='';\n  banner.classList.remove('visible');\n}\nfunction saveCachedStatus(status){\n  try{\n    window.localStorage.setItem(CACHE_KEY,JSON.stringify({\n      saved_at:Date.now(),\n      status:status\n    }));\n  }catch(e){}\n}\nfunction loadCachedEnvelope(){\n  try{\n    var raw=window.localStorage.getItem(CACHE_KEY);\n    return raw?JSON.parse(raw):null;\n  }catch(e){\n    return null;\n  }\n}\nfunction loadPendingNames(){\n  try{\n    var raw=window.localStorage.getItem(PENDING_NAMES_KEY);\n    return raw?JSON.parse(raw):[];\n  }catch(e){\n    return [];\n  }\n}\nfunction savePendingNames(items){\n  try{\n    window.localStorage.setItem(PENDING_NAMES_KEY,JSON.stringify(items));\n  }catch(e){}\n}\nfunction queuePendingName(readId,name){\n  var items=loadPendingNames();\n  var replaced=false;\n  for(v",
    "ar i=0;i<items.length;i+=1){\n    if(items[i].id===readId){\n      items[i].name=name;\n      replaced=true;\n      break;\n    }\n  }\n  if(!replaced){\n    items.push({id:readId,name:name});\n  }\n  savePendingNames(items);\n}\nfunction applyPendingNameToCache(readId,name){\n  var envelope=loadCachedEnvelope();\n  if(!envelope||!envelope.status){return}\n  var rows=envelope.status.table_rows||[];\n  var reads=envelope.status.chip_readings||[];\n  for(var i=0;i<rows.length;i+=1){\n    if(rows[i].id===readId){rows[i].name=name}\n  }\n  for(var j=0;j<reads.length;j+=1){\n    if(reads[j].id===readId){reads[j].name=name}\n  }\n  saveCachedStatus(envelope.status);\n}\nfunction showCachedStatus(reason){\n  var envelope=loadCachedEnvelope();\n  if(!envelope||!envelope.status){return false}\n  showingCachedStatus=true;\n  applyStatus(envelope.status);\n  showConnectionWarning(reason+' Zobrazená data jsou poslední uložený stav v telefonu. Nová čtení se teď neaktualizují.');\n  return true;\n}\nfunction persistExpandedState(){\n  if(currentStatus){saveCachedStatus(currentStatus)}\n}\nfunction startSync(){\n  clearError();\n  var value=document.getElementById('stationInput').value||'1';\n  var stationCount=parseInt(value,10);\n  if(!Number.isInteger(stationCount)||stationCount<1||stationCount>8){\n    showError('Maximální počet stanic je 8 a minimální je 1.');\n    return;\n  }\n  fetch('/start-sync?n='+encodeURIComponent(value),{cache:'no-store'})\n    .then(function(response){\n      if(!response.ok){\n        return response.json().then(function(data){\n          throw new Error(data.error||'Počet stanic musí být mezi 1 a 8.');\n        });\n      }\n      return response.json();\n    })\n    .then(function(){poll(true)})\n    .catch(function(error){showError(error.message)});\n}\nfunction resumeLastRace(){\n  clearError();\n  fetch('/resume-last',{cache:'no-store'})\n    .then(function(response){\n      if(!response.ok){\n        return response.json().then(function(data){\n          throw new Error(data.error||'Poslední závod nejde obnovit.');\n        });\n      }\n      return response.json();\n    })\n    .then(function(){poll(true)})\n    .catch(function(error){showError(error.message)});\n}\nfunction stopFlow(){\n  fetch('/stop',{cache:'no-sto",
    "re'})\n    .then(function(response){\n      if(!response.ok){throw new Error('Závod se nepodařilo ukončit.')}\n      return response.json();\n    })\n    .then(function(){poll(true)})\n    .catch(function(){\n      showCachedStatus('Spojení se stanicí se přerušilo během ukončování závodu.');\n    });\n}\nfunction openStopSheet(){\n  stopCountdownValue=10;\n  var sheet=document.getElementById('stopSheet');\n  var button=document.getElementById('stopConfirmButton');\n  button.disabled=true;\n  button.textContent='Potvrdit zastavení ('+stopCountdownValue+')';\n  sheet.classList.add('open');\n  sheet.setAttribute('aria-hidden','false');\n  if(stopCountdownTimer){window.clearInterval(stopCountdownTimer)}\n  stopCountdownTimer=window.setInterval(function(){\n    stopCountdownValue-=1;\n    if(stopCountdownValue<=0){\n      button.disabled=false;\n      button.textContent='Potvrdit zastavení';\n      window.clearInterval(stopCountdownTimer);\n      stopCountdownTimer=null;\n      return;\n    }\n    button.textContent='Potvrdit zastavení ('+stopCountdownValue+')';\n  },1000);\n}\nfunction closeStopSheet(){\n  var sheet=document.getElementById('stopSheet');\n  sheet.classList.remove('open');\n  sheet.setAttribute('aria-hidden','true');\n  if(stopCountdownTimer){\n    window.clearInterval(stopCountdownTimer);\n    stopCountdownTimer=null;\n  }\n}\nfunction confirmStop(){\n  var button=document.getElementById('stopConfirmButton');\n  if(button.disabled){return}\n  closeStopSheet();\n  stopFlow();\n}\nfunction openSheet(readId){\n  if(!currentStatus){return}\n  var readings=currentStatus.chip_readings||[];\n  var match=null;\n  for(var i=0;i<readings.length;i++){\n    if(readings[i].id===readId){match=readings[i];break}\n  }\n  if(!match){return}\n  activeReadId=readId;\n  document.getElementById('sheetUid').textContent=match.uid;\n  d",
    "ocument.getElementById('runnerNameInput').value=match.name||'';\n  var sheet=document.getElementById('nameSheet');\n  sheet.classList.add('open');\n  sheet.setAttribute('aria-hidden','false');\n  document.getElementById('runnerNameInput').focus();\n}\nfunction closeSheet(){\n  activeReadId=null;\n  var sheet=document.getElementById('nameSheet');\n  sheet.classList.remove('open');\n  sheet.setAttribute('aria-hidden','true');\n}\nfunction saveName(){\n  if(activeReadId===null){return}\n  var nameValue=document.getElementById('runnerNameInput').value;\n  fetch('/name',{\n    method:'POST',\n    headers:{'Content-Type':'application/json'},\n    cache:'no-store',\n    body:JSON.stringify({id:activeReadId,name:nameValue})\n  }).then(function(response){\n    if(!response.ok){throw new Error('offline')}\n    return response.json();\n  }).then(function(){\n    closeSheet();\n    poll(true);\n  }).catch(function(){\n    queuePendingName(activeReadId,nameValue);\n    applyPendingNameToCache(activeReadId,nameValue);\n    closeSheet();\n    showCachedStatus('Jméno bylo dočasně uloženo jen v telefonu, protože spojení se stanicí není dostupné.');\n  });\n}\nfunction clearName(){\n  document.getElementById('runnerNameInput').value='';\n  saveName();\n}\nfunction toggleReadDetails(readId){\n  expandedReads[readId]=!expandedReads[readId];\n  if(currentStatus){renderTable(currentStatus.table_rows||[],currentStatus.visible_station_count||0)}\n}\nfunction formatResult(value){\n  if(value===null||value===undefined){return 'Nedokončeno'}\n  return value+' s';\n}\nfunction formatMode(mode){\n  if(mode==='IDLE'){return 'Ukončeno'}\n  if(mode==='SYNCING'){return 'Synchronizace'}\n  if(mode==='READING'){return 'Probíhá'}\n  return mode;\n}\nfunction formatStatusCopy(mode){\n  if(mode==='SYNCING'){return 'Probíhá synchronizace stanic'}\n  if(mode===",
    "'READING'){return 'Závod probíhá, běžci mohou běhat'}\n  return 'Závod skončil';\n}\nfunction renderTable(rows, visibleStationCount){\n  var target=document.getElementById('tableBody');\n  var head=document.getElementById('tableHeadRow');\n  head.innerHTML='<th>Jméno</th><th>Výsledek</th><th>Čas čtení</th><th></th>';\n  if(!rows.length){\n    target.innerHTML='<tr><td colspan=\"4\">Zatím žádné záznamy.</td></tr>';\n    return;\n  }\n  target.innerHTML=rows.map(function(row){\n    var expanded=!!expandedReads[row.id];\n    var details='';\n    if(expanded){\n      var detailCells='<div class=\"detail-cell\"><strong>UID</strong><span>'+row.uid+'</span></div>';\n      for(var index=1;index<=visibleStationCount;index+=1){\n        detailCells+='<div class=\"detail-cell\"><strong>S'+index+'</strong><span>'+row['S'+index]+'</span></div>';\n      }\n      details='<tr class=\"detail-row\"><td colspan=\"4\"><div class=\"detail-shell\"><div class=\"detail-grid\">'+detailCells+'</div></div></td></tr>';\n    }\n    var nameLabel=row.name?'<span class=\"name-text\">'+row.name+'</span><span class=\"name-edit-indicator\">&#9998;</span>':'<span class=\"name-text\">Přidat jméno</span><span class=\"name-edit-indicator\">&#9998;</span>';\n    var nameClass=row.name?'name-action':'name-action empty';\n    return '<tr>'+\n      '<td><button class=\"'+nameClass+'\" onclick=\"openSheet('+row.id+')\">'+nameLabel+'</button></td>'+\n      '<td>'+formatResult(row.result_seconds)+'</td>'+\n      '<td>'+row.read_at+'</td>'+\n      '<td><button class=\"icon-btn\" onclick=\"toggleReadDetails('+row.id+')\">'+(expanded?'−':'+')+'</button></td>'+\n    '</tr>'+details;\n  }).join('');\n}\nfunction applyStatus(status){\n  showingCachedStatus=false;\n  currentStatus=status;\n  var modeEl=document.getElementById('modeBadge');\n  modeEl.className='mode '+status.mode;\n  m",
    "odeEl.innerHTML='<span class=\"mode-dot\"></span><span>'+formatMode(status.mode)+'</span>';\n  document.getElementById('statusCopy').textContent=formatStatusCopy(status.mode);\n  document.getElementById('stationCountValue').textContent=status.total_station_count||0;\n  document.getElementById('syncedValue').textContent=status.synced_ids.length+' / '+status.num_stations;\n  renderTable(status.table_rows||[],status.visible_station_count||0);\n  saveCachedStatus(status);\n}\nfunction flushPendingNames(){\n  var items=loadPendingNames();\n  if(!items.length){return Promise.resolve()}\n  var item=items[0];\n  return fetch('/name',{\n    method:'POST',\n    headers:{'Content-Type':'application/json'},\n    cache:'no-store',\n    body:JSON.stringify(item)\n  }).then(function(response){\n    if(!response.ok){throw new Error('pending-name-failed')}\n    items.shift();\n    savePendingNames(items);\n    return flushPendingNames();\n  });\n}\nfunction poll(userTriggered){\n  return fetch('/status',{cache:'no-store'})\n    .then(function(response){\n      if(!response.ok){throw new Error('status-failed')}\n      return response.json();\n    })\n    .then(function(status){\n      lastLiveStatusAt=Date.now();\n      clearConnectionWarning();\n      applyStatus(status);\n      return flushPendingNames().then(function(){return status});\n    })\n    .catch(function(){\n      if(!showCachedStatus('Spojení se stanicí bylo ztraceno.')){\n        showConnectionWarning('Spojení se stanicí bylo ztraceno. Připojte telefon znovu k Wi‑Fi OrientacniBeh a otevřete stránku znovu.');\n      }\n      if(userTriggered){showError('Požadavek se nepodařilo odeslat do stanice.');}\n    });\n}\nfunction ping(){\n  fetch('/ping',{cache:'no-store'}).catch(function(){\n    if(Date.now()-lastLiveStatusAt>3500){\n      showCachedStatus('Spojení se stanicí bylo přeru",
    "šeno.');\n    }\n  });\n}\nfunction performStartSync(value,force){\n  window.syncStartedLocally=true;\n  fetch('/start-sync?n='+encodeURIComponent(value)+'&force='+(force?'1':'0'),{cache:'no-store'})\n    .then(function(response){\n      if(!response.ok){\n        return response.json().then(function(data){\n          throw new Error(data.error||'Počet stanic musí být mezi 1 a 8.');\n        });\n      }\n      return response.json();\n    })\n    .then(function(){poll(true)})\n    .catch(function(error){showError(error.message)});\n}\nfunction startSync(){\n  clearError();\n  var value=document.getElementById('stationInput').value||'1';\n  var stationCount=parseInt(value,10);\n  if(!Number.isInteger(stationCount)||stationCount<1||stationCount>8){\n    showError('Maximální počet stanic je 8 a minimální je 1.');\n    return;\n  }\n  var alreadyStarted=window.syncStartedLocally||(currentStatus&&(currentStatus.mode==='SYNCING'||currentStatus.mode==='READING'));\n  if(alreadyStarted){\n    openSyncSheet(value);\n    return;\n  }\n  performStartSync(value,false);\n}\nfunction openSyncSheet(value){\n  pendingSyncValue=value;\n  syncCountdownValue=10;\n  var sheet=document.getElementById('syncSheet');\n  var button=document.getElementById('syncConfirmButton');\n  button.disabled=true;\n  button.textContent='Vím co dělám ('+syncCountdownValue+')';\n  sheet.classList.add('open');\n  sheet.setAttribute('aria-hidden','false');\n  if(syncCountdownTimer){window.clearInterval(syncCountdownTimer)}\n  syncCountdownTimer=window.setInterval(function(){\n    syncCountdownValue-=1;\n    if(syncCountdownValue<=0){\n      button.disabled=false;\n      button.textContent='Vím co dělám';\n      window.clearInterval(syncCountdownTimer);\n      syncCountdownTimer=null;\n      return;\n    }\n    button.textContent='Vím co dělám ('+syncCountdownValue+')';\n  },1000);\n}\nfunction closeSyncSheet(){\n  var sheet=document.getElementById('syncSheet');\n  sheet.classList.remove('open');\n  sheet.setAttribute('aria-hidden','true');\n  pendingSyncValue=null;\n  if(syncCountdownTimer){\n    window.clearInterval(syncCountdownTimer);\n    syncCountdownTimer=null;\n  }\n}\nfunction confirmForcedSync(){\n  var button=document.getElementById('syncConfirmButton');\n  if(button.disabled||pendingSyncValue===null){return}\n  var value=pendingSyncValue;\n  closeSyncSheet();\n  performStartSync(value,true);\n}\nfunction downloadCsv(){\n  window.location.href='/export.csv';\n}\ndocument.getElementById('nameSheet').addEventListener('click',function(event){\n  if(event.target.id==='nameSheet'){closeSheet()}\n});\ndocument.getElementById('stopSheet').addEventListener('click',function(event){\n  if(event.target.id==='stopSheet'){closeStopSheet()}\n});\ndocument.getElementById('syncSheet').addEventListener('click',function(event){\n  if(event.target.id==='syncSheet'){closeSyncSheet()}\n});\nwindow.addEventListener('offline',function(){\n  showCachedStatus('Telefon je offline nebo není připojený ke stanici.');\n});\nwindow.addEventListener('online',function(){\n  clearConnectionWarning();\n  poll(false);\n});\ntry{applyTheme(window.localStorage.getItem('race-control-theme')||'light')}catch(e){applyTheme('light')}\nupdateStationValue();\nif(!showCachedStatus('Načítám poslední uložený stav ze zařízení.')){\n  showConnectionWarning('Načítám spojení se stanicí.');\n}\nsetInterval(poll,1000);\nsetInterval(ping,5000);\npoll(false);\n</script>\n</body>\n</html>\n",
)

TEST_HTML_PARTS = (
    "<!DOCTYPE html>\n<html lang=\"cs\">\n<head>\n<meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n<title>Test - CSV soubory</title>\n<style>\n:root{\n  --bg:#f5f5f7;\n  --panel:#fff;\n  --line:#d2d5db;\n  --text:#111214;\n  --muted:#50545c;\n  --danger:#c9342f;\n  --danger-soft:#fff1f0;\n  --accent:#007aff;\n}\n*{box-sizing:border-box}\nbody{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif}\n.app{max-width:900px;margin:0 auto;padding:16px}\n.panel{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:18px}\n.stack{display:flex;flex-direction:column;gap:14px}\n.topbar{display:flex;justify-content:space-between;align-items:center;gap:12px}\nh1,h2{margin:0}\n.muted{color:var(--muted)}\n.btn{height:44px;border:0;border-radius:12px;padding:0 14px;font:inherit;font-weight:700}\n.btn-primary{background:var(--accent);color:#fff}\n.btn-danger{background:var(--danger-soft);color:var(--danger)}\n.list{display:flex;flex-direction:column;gap:10px}\n.row{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px;border:1px solid var(--line);border-radius:14px}\n.row-main{display:flex;flex-direction:column;gap:4px;min-width:0}\n.row-main strong,.row-main span{overflow:hidden;text-overflow:ellipsis}\n.empty{padding:16px;border:1px dashed var(--line);border-radius:14px}\n.error{display:none;padding:12px 14px;border-radius:12px;background:var(--danger-soft);color:var(--danger);font-weight:700}\n.error.visible{display:block}\n@media(max-width:720px){\n  .row{flex-direction:column;align-items:stretch}\n  .btn{width:100%}\n}\n</style>\n</head>\n<body>\n<div class=\"app stack\">\n  <div class=\"topbar\">\n    <h1>Skrytý test - CSV soubory</h1>\n    <button class=\"btn btn-primary\" onclick",
    "=\"loadFiles()\">Obnovit</button>\n  </div>\n  <div id=\"errorBox\" class=\"error\"></div>\n  <section class=\"panel stack\">\n    <div>\n      <h2>Flash úložiště</h2>\n      <div id=\"storageInfo\" class=\"muted\">Načítám...</div>\n    </div>\n    <div>\n      <h2>Uložené závody</h2>\n      <div id=\"fileList\" class=\"list\"></div>\n    </div>\n  </section>\n</div>\n<script>\nfunction showError(message){\n  var box=document.getElementById('errorBox');\n  box.textContent=message;\n  box.classList.add('visible');\n}\nfunction clearError(){\n  var box=document.getElementById('errorBox');\n  box.textContent='';\n  box.classList.remove('visible');\n}\nfunction formatBytes(value){\n  if(value===null||value===undefined){return 'Neznámé'}\n  if(value<1024){return value+' B'}\n  if(value<1024*1024){return (value/1024).toFixed(1)+' KB'}\n  return (value/(1024*1024)).toFixed(2)+' MB'\n}\nfunction renderStorage(data){\n  var info='Volné místo: '+formatBytes(data.free_bytes)+' | Celkem: '+formatBytes(data.total_bytes)+' | CSV souborů: '+data.file_count;\n  document.getElementById('storageInfo').textContent=info;\n}\nfunction renderFiles(files){\n  var root=document.getElementById('fileList');\n  if(!files.length){\n    root.innerHTML='<div class=\"empty muted\">Zatím nejsou uložené žádné CSV soubory.</div>';\n    return;\n  }\n  root.innerHTML=files.map(function(file){\n    return '<div class=\"row\">'+\n      '<div class=\"row-main\"><strong>'+file.name+'</strong><span class=\"muted\">'+formatBytes(file.size_bytes)+'</span></div>'+\n      '<button class=\"btn btn-danger\" onclick=\"deleteFile(\\''+file.name.replace(/'/g,\"\\\\'\")+'\\')\">Smazat</button>'+\n    '</div>';\n  }).join('');\n}\nfunction loadFiles(){\n  clearError();\n  fetch('/test/storage',{cache:'no-store'})\n    .then(function(response){\n      if(!response.ok){throw new Error('Načtení test stránky",
    " selhalo.')}\n      return response.json();\n    })\n    .then(function(data){\n      renderStorage(data);\n      renderFiles(data.files||[]);\n    })\n    .catch(function(error){showError(error.message)});\n}\nfunction deleteFile(name){\n  if(!window.confirm('Opravdu smazat '+name+'?')){return}\n  clearError();\n  fetch('/test/delete-race',{\n    method:'POST',\n    headers:{'Content-Type':'application/json'},\n    cache:'no-store',\n    body:JSON.stringify({name:name})\n  }).then(function(response){\n    if(!response.ok){throw new Error('Mazání CSV selhalo.')}\n    return response.json();\n  }).then(function(){loadFiles()})\n    .catch(function(error){showError(error.message)});\n}\nloadFiles();\n</script>\n</body>\n</html>\n",
)


_CAPTIVE_URLS = (
    '/generate_204',
    '/gen_204',
    '/hotspot-detect.html',
    '/library/test/success.html',
    '/connectivity-check.html',
    '/ncsi.txt',
    '/redirect',
    '/canonical.html',
)


class WebServer:
    def __init__(self, state):
        self.state = state
        self.state.setdefault('boot_id', self._make_boot_id())
        self.state.setdefault('race_session_id', '')
        self.state.setdefault('race_csv_path', '')
        self.state.setdefault('_persisted_snapshot', '')
        self.state.setdefault('_persist_error_snapshot', '')
        self.state.setdefault('recoverable_race', self._recoverable_race_info())
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', 80))
        self.sock.listen(3)
        self.sock.setblocking(False)
        print('[WEB] Dashboard listening on :80  ->  http://192.168.4.1')

    def sync_state(self, force=False):
        self._prepare_readings()
        self._persist_race_snapshot(force=force)

    def handle(self):
        """Process one pending HTTP request without blocking the main loop."""
        try:
            conn, addr = self.sock.accept()
        except OSError:
            return

        try:
            conn.settimeout(3.0)
            raw = self._recv_request(conn)
            first = raw.split(b'\r\n', 1)[0].decode('utf-8', 'ignore')
            parts = first.split(' ')
            if len(parts) >= 2:
                method = parts[0]
                path = parts[1]
                body = self._body_from_raw(raw)
                self._dispatch(conn, method, path, body)
        except Exception as err:
            print(f'[WEB] Chyba zpracovani: {err}')
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _recv_request(self, conn):
        raw = b''
        while True:
            try:
                chunk = conn.recv(512)
                if not chunk:
                    break
                raw += chunk
                if b'\r\n\r\n' in raw:
                    content_length = self._content_length(raw)
                    header_end = raw.find(b'\r\n\r\n') + 4
                    if len(raw) >= header_end + content_length:
                        break
                if len(raw) > 8192:
                    break
            except OSError:
                break
        return raw

    def _content_length(self, raw):
        headers = raw.split(b'\r\n\r\n', 1)[0].decode('utf-8', 'ignore')
        for line in headers.split('\r\n'):
            lower = line.lower()
            if lower.startswith('content-length:'):
                try:
                    return int(line.split(':', 1)[1].strip())
                except ValueError:
                    return 0
        return 0

    def _body_from_raw(self, raw):
        marker = b'\r\n\r\n'
        pos = raw.find(marker)
        if pos < 0:
            return b''
        return raw[pos + len(marker):]

    def _dispatch(self, conn, method, path, body):
        base = path.split('?')[0]

        if base == '/' or base in _CAPTIVE_URLS:
            self._send_parts(conn, '200 OK', 'text/html; charset=utf-8', HTML_PARTS)
        elif base == '/test':
            self._send_parts(conn, '200 OK', 'text/html; charset=utf-8', TEST_HTML_PARTS)
        elif base == '/status':
            self._serve_status(conn)
        elif base == '/ping':
            self._send(conn, '204 No Content', 'text/plain', '')
        elif base == '/start-sync':
            self._serve_start_sync(conn, path)
        elif base == '/resume-last':
            self._serve_resume_last(conn)
        elif base == '/stop':
            self._serve_stop(conn)
        elif base == '/name' and method == 'POST':
            self._serve_name(conn, body)
        elif base == '/export.csv':
            self._serve_csv(conn)
        elif base == '/test/storage':
            self._serve_test_storage(conn)
        elif base == '/test/delete-race' and method == 'POST':
            self._serve_test_delete_race(conn, body)
        else:
            self._redirect(conn, '/')

    def _serve_status(self, conn):
        self._prepare_readings()
        visible_count = self._visible_station_count()
        readings = self._readings_for_client()
        data = {
            'boot_id': self.state.get('boot_id', ''),
            'race_session_id': self.state.get('race_session_id', ''),
            'mode': self.state.get('mode', 'IDLE'),
            'num_stations': self.state.get('num_stations', 0),
            'total_station_count': visible_count,
            'synced_ids': list(self.state.get('synced_ids', set())),
            'chip_readings': readings,
            'visible_station_count': visible_count,
            'table_rows': self._table_rows(readings, visible_count),
            'recoverable_race': self.state.get('recoverable_race', None),
            'log': self.state.get('log', []),
        }
        self._send(conn, '200 OK', 'application/json', json.dumps(data))

    def _serve_start_sync(self, conn, path):
        n = self._station_count_from_path(path)
        force = self._force_sync_from_path(path)
        if n < 1 or n > MAX_SYNC_STATIONS:
            data = {
                'ok': False,
                'error': 'Počet stanic musí být mezi 1 a 8.',
            }
            self._send(conn, '400 Bad Request', 'application/json', json.dumps(data))
            return

        if self.state.get('race_ended', False):
            data = {
                'ok': False,
                'error': 'Závod už byl ukončen. Pro nový závod restartujte zařízení.',
            }
            self._send(conn, '409 Conflict', 'application/json', json.dumps(data))
            return

        if self.state.get('mode') in ('SYNCING', 'READING') and not force:
            data = {
                'ok': False,
                'error': 'Sync už probíhá nebo závod běží. Opakovaný sync může rozbít závod.',
            }
            self._send(conn, '409 Conflict', 'application/json', json.dumps(data))
            return

        if self.state.get('mode') in ('SYNCING', 'READING') and force and self.state.get('synced_ids', set()):
            data = {
                'ok': False,
                'error': 'Druhý sync je povolený jen pokud ještě není synchronizovaná žádná stanice.',
            }
            self._send(conn, '409 Conflict', 'application/json', json.dumps(data))
            return

        self._start_sync(n, force=force)
        self._send(conn, '200 OK', 'application/json', json.dumps({
            'ok': True,
            'station_count': n,
        }))

    def _serve_resume_last(self, conn):
        restored, message = self._resume_last_race()
        if not restored:
            self._send(conn, '404 Not Found', 'application/json',
                       json.dumps({'ok': False, 'error': message}))
            return
        self._send(conn, '200 OK', 'application/json',
                   json.dumps({'ok': True, 'message': message}))

    def _serve_stop(self, conn):
        self._stop()
        self._send(conn, '200 OK', 'application/json', json.dumps({'ok': True}))

    def _serve_name(self, conn, body):
        try:
            payload = json.loads(body.decode('utf-8'))
            read_id = int(payload.get('id', 0))
            name = str(payload.get('name', '')).strip()
        except (ValueError, TypeError, AttributeError):
            self._send(conn, '400 Bad Request', 'application/json',
                       json.dumps({'ok': False}))
            return

        changed = self._rename_read(read_id, name)
        if changed:
            self._send(conn, '200 OK', 'application/json',
                       json.dumps({'ok': True}))
        else:
            self._send(conn, '404 Not Found', 'application/json',
                       json.dumps({'ok': False}))

    def _serve_csv(self, conn):
        self._prepare_readings()
        visible_count = self._visible_station_count()
        rows = self._table_rows(self._readings_for_client(), visible_count)
        csv_text = self._csv_from_rows(rows, visible_count)
        filename = self.state.get('race_session_id') or 'vysledky'
        self._send(conn, '200 OK', 'text/csv; charset=utf-8', csv_text,
                   extra='Content-Disposition: attachment; filename="%s.csv"\r\n' % filename)

    def _serve_test_storage(self, conn):
        data = self._storage_status()
        self._send(conn, '200 OK', 'application/json', json.dumps(data))

    def _serve_test_delete_race(self, conn, body):
        try:
            payload = json.loads(body.decode('utf-8'))
            name = str(payload.get('name', ''))
        except (ValueError, TypeError, AttributeError):
            self._send(conn, '400 Bad Request', 'application/json', json.dumps({'ok': False}))
            return
        if not self._delete_race_file(name):
            self._send(conn, '404 Not Found', 'application/json', json.dumps({'ok': False}))
            return
        self._send(conn, '200 OK', 'application/json', json.dumps({'ok': True}))

    def _station_count_from_path(self, path):
        if '?n=' not in path:
            return 1
        try:
            return int(path.split('?n=')[1].split('&')[0])
        except ValueError:
            return 0

    def _force_sync_from_path(self, path):
        return 'force=1' in path

    def _start_sync(self, n, force=False):
        if force or self.state.get('mode') != 'SYNCING':
            self.state['mode'] = 'SYNCING'
            self.state['num_stations'] = n
            self.state['synced_ids'] = set()
            self.state['chip_readings'] = []
            self.state['race_ended'] = False
            self.state['_next_read_id'] = 1
            self.state['race_session_id'] = self._next_race_session_id()
            self.state['race_csv_path'] = self._race_path(self.state['race_session_id'])
            now = self._safe_epoch()
            self.state['race_started_epoch'] = now
            self.state['synced_epoch'] = 0
            self.state['last_saved_epoch'] = now
            self.state['race_recovered'] = False
            self.state['sync_reset_requested'] = True
            self.state['_persisted_snapshot'] = ''
            self.state['_persist_error_snapshot'] = ''
            self._log(f'Sync zahájen pro {n} stanic.')
            self._persist_race_snapshot(force=True)

    def _stop(self):
        self.state['mode'] = 'IDLE'
        self.state['race_ended'] = True
        self._log('Závod ukončen.')
        self._persist_race_snapshot(force=True)

    def _resume_last_race(self):
        data = self._load_active_race_state()
        if not data:
            return False, 'Žádný rozpracovaný závod není uložený.'
        if data.get('race_ended', False):
            return False, 'Poslední uložený závod už byl ukončený.'
        if data.get('mode') not in ('READING', 'SYNCING'):
            return False, 'Poslední závod není ve stavu pro obnovení.'

        station_count = int(data.get('num_stations', 0))
        if station_count < 1 or station_count > MAX_SYNC_STATIONS:
            return False, 'Uložený závod má neplatný počet stanic.'

        readings = data.get('chip_readings', [])
        if not isinstance(readings, list):
            readings = []

        synced_ids = data.get('synced_ids', [])
        if not synced_ids:
            synced_ids = list(range(1, station_count + 1))

        self.state['mode'] = 'READING'
        self.state['num_stations'] = station_count
        self.state['synced_ids'] = set(synced_ids)
        self.state['chip_readings'] = readings
        self.state['race_ended'] = False
        self.state['race_session_id'] = data.get('race_session_id', '') or self._next_race_session_id()
        self.state['race_csv_path'] = data.get('race_csv_path', '') or self._race_path(self.state['race_session_id'])
        self.state['race_started_epoch'] = int(data.get('race_started_epoch', 0))
        self.state['synced_epoch'] = int(data.get('synced_epoch', 0))
        self.state['last_saved_epoch'] = int(data.get('last_saved_epoch', 0))
        self.state['_next_read_id'] = int(data.get('_next_read_id', 1))
        self.state['race_recovered'] = True
        self.state['_persisted_snapshot'] = ''
        self.state['_persist_error_snapshot'] = ''
        self._restore_clock_from_saved_state(data)
        self._log('Nouzově pokračuji v posledním závodě bez nové synchronizace.')
        self._persist_race_snapshot(force=True)
        return True, 'Závod obnoven bez nové synchronizace.'

    def _prepare_readings(self):
        next_id = self.state.get('_next_read_id', 1)
        for reading in self.state.get('chip_readings', []):
            if 'id' not in reading:
                reading['id'] = next_id
                next_id += 1
            if 'name' not in reading:
                reading['name'] = ''
            if 'master_time' not in reading:
                reading['master_time'] = ''
            reading['result_seconds'] = self._result_seconds(
                reading,
                self.state.get('num_stations', 0),
            )
        self.state['_next_read_id'] = next_id

    def _rename_read(self, read_id, name):
        self._prepare_readings()
        for reading in self.state.get('chip_readings', []):
            if reading.get('id') == read_id:
                reading['name'] = name
                self._persist_race_snapshot(force=True)
                return True
        return False

    def _visible_station_count(self):
        sync_station_count = self.state.get('num_stations', 0)
        if sync_station_count <= 0:
            return 0
        count = sync_station_count + 1
        if count > MAX_VISIBLE_STATIONS:
            return MAX_VISIBLE_STATIONS
        return count

    def _times_for_display(self, reading):
        sync_station_count = self.state.get('num_stations', 0)
        visible_count = self._visible_station_count()
        raw_times = list(reading.get('times', []))
        display_times = raw_times[:sync_station_count]
        while len(display_times) < sync_station_count:
            display_times.append('0')
        if visible_count > sync_station_count:
            display_times.append(str(reading.get('master_time', '') or '0'))
        return display_times[:visible_count]

    def _readings_for_client(self):
        readings = []
        source = self.state.get('chip_readings', [])
        for index in range(len(source) - 1, -1, -1):
            original = source[index]
            readings.append({
                'id': original.get('id'),
                'name': original.get('name', ''),
                'uid': original.get('uid', ''),
                'times': self._times_for_display(original),
                'ts': original.get('ts', ''),
                'result_seconds': original.get('result_seconds'),
                'master_time': original.get('master_time', ''),
            })
        return readings

    def _table_rows(self, readings, visible_count):
        rows = []
        for reading in readings:
            row = {
                'id': reading.get('id'),
                'name': reading.get('name', ''),
                'uid': reading.get('uid', ''),
                'read_at': reading.get('ts', ''),
                'result_seconds': reading.get('result_seconds'),
            }
            times = reading.get('times', [])
            for index in range(visible_count):
                row[f'S{index + 1}'] = times[index] if index < len(times) else '0'
            rows.append(row)
        return rows

    def _result_seconds(self, reading, station_count):
        times = reading.get('times', [])
        if station_count < 1 or not times:
            return None
        try:
            start = int(times[0])
        except (ValueError, TypeError):
            return None
        master_time = reading.get('master_time', '')
        try:
            finish = int(master_time)
        except (ValueError, TypeError):
            finish = None
        if finish is None or finish <= 0:
            finish_index = station_count - 1
            if finish_index < 0 or len(times) <= finish_index:
                return None
            try:
                finish = int(times[finish_index])
            except (ValueError, TypeError):
                return None
        if start <= 0 or finish <= 0:
            return None
        if finish < start:
            finish += 65536
        return finish - start

    def _csv_from_rows(self, rows, visible_count):
        headers = ['jmeno', 'uid']
        for index in range(visible_count):
            headers.append(f'S{index + 1}')
        headers.extend(['vysledek_s', 'cas_cteni'])
        lines = [','.join(headers)]
        for row in rows:
            values = [
                row.get('name', ''),
                row.get('uid', ''),
            ]
            for index in range(visible_count):
                values.append(row.get(f'S{index + 1}', '0'))
            values.append('' if row.get('result_seconds') is None
                          else str(row.get('result_seconds')))
            values.append(row.get('read_at', ''))
            lines.append(','.join(self._csv_cell(value) for value in values))
        return '\r\n'.join(lines) + '\r\n'

    def _csv_cell(self, value):
        text = str(value)
        if '"' in text:
            text = text.replace('"', '""')
        if ',' in text or '"' in text or '\n' in text or '\r' in text:
            text = '"' + text + '"'
        return text

    def _make_boot_id(self):
        try:
            now = time.localtime()
            return '%04d%02d%02d-%02d%02d%02d' % (
                now[0], now[1], now[2], now[3], now[4], now[5]
            )
        except Exception:
            return 'boot-%d' % time.ticks_ms()

    def _safe_epoch(self):
        try:
            return int(time.time())
        except Exception:
            return 0

    def _load_active_race_state(self):
        try:
            with open(ACTIVE_RACE_STATE_PATH, 'r') as handle:
                return json.loads(handle.read())
        except (OSError, ValueError):
            return None

    def _recoverable_race_info(self):
        data = self._load_active_race_state()
        if not data or data.get('race_ended', False):
            return None
        mode = data.get('mode')
        if mode not in ('READING', 'SYNCING'):
            return None
        return {
            'race_session_id': data.get('race_session_id', ''),
            'mode': mode,
            'num_stations': data.get('num_stations', 0),
            'read_count': len(data.get('chip_readings', [])),
            'last_saved_epoch': data.get('last_saved_epoch', 0),
        }

    def _restore_clock_from_saved_state(self, data):
        epoch = int(data.get('last_saved_epoch', 0) or
                    data.get('synced_epoch', 0) or
                    data.get('race_started_epoch', 0))
        if machine is None or epoch <= 0:
            return
        try:
            tm = time.localtime(epoch)
            machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6],
                                    tm[3], tm[4], tm[5], 0))
            self._log('RTC obnoveno z uloženého času závodu.')
        except Exception as err:
            self._log('RTC se nepodařilo obnovit: %s' % err)

    def _ensure_races_dir(self):
        try:
            os.listdir(RACES_DIR)
        except OSError:
            try:
                os.mkdir(RACES_DIR)
            except OSError:
                pass

    def _next_race_session_id(self):
        self._ensure_races_dir()
        highest = 0
        try:
            entries = os.listdir(RACES_DIR)
        except OSError:
            entries = []
        for name in entries:
            if not name.startswith('zavod_') or not name.endswith('.csv'):
                continue
            try:
                value = int(name[6:-4])
            except ValueError:
                continue
            if value > highest:
                highest = value
        return 'zavod_%04d' % (highest + 1)

    def _race_path(self, race_session_id):
        return '%s/%s.csv' % (RACES_DIR, race_session_id)

    def _race_files(self):
        self._ensure_races_dir()
        files = []
        try:
            entries = os.listdir(RACES_DIR)
        except OSError:
            entries = []
        for name in entries:
            if not name.endswith('.csv'):
                continue
            path = '%s/%s' % (RACES_DIR, name)
            size_bytes = 0
            try:
                size_bytes = os.stat(path)[6]
            except Exception:
                size_bytes = 0
            files.append({
                'name': name,
                'size_bytes': size_bytes,
            })
        files.sort(key=lambda item: item['name'])
        return files

    def _storage_status(self):
        total_bytes = None
        free_bytes = None
        try:
            statvfs = os.statvfs('/')
            block_size = statvfs[0]
            total_bytes = block_size * statvfs[2]
            free_bytes = block_size * statvfs[3]
        except Exception:
            pass
        files = self._race_files()
        return {
            'total_bytes': total_bytes,
            'free_bytes': free_bytes,
            'file_count': len(files),
            'files': files,
        }

    def _delete_race_file(self, name):
        if not name or '/' in name or '\\' in name or not name.endswith('.csv'):
            return False
        path = '%s/%s' % (RACES_DIR, name)
        try:
            os.remove(path)
        except OSError:
            return False
        if self.state.get('race_csv_path') == path:
            self.state['race_csv_path'] = ''
            self.state['race_session_id'] = ''
        return True

    def _snapshot_payload(self):
        visible_count = self._visible_station_count()
        readings = self._readings_for_client()
        rows = self._table_rows(readings, visible_count)
        csv_text = self._csv_from_rows(rows, visible_count)
        return visible_count, rows, csv_text

    def _persist_race_snapshot(self, force=False):
        race_path = self.state.get('race_csv_path', '')
        if not race_path:
            return
        self._prepare_readings()
        visible_count, rows, csv_text = self._snapshot_payload()
        snapshot = json.dumps({
            'mode': self.state.get('mode', 'IDLE'),
            'num_stations': visible_count,
            'race_ended': self.state.get('race_ended', False),
            'rows': rows,
        })
        if not force and snapshot == self.state.get('_persisted_snapshot', ''):
            return
        self.state['last_saved_epoch'] = self._safe_epoch()
        state_payload = self._active_race_payload()
        self._ensure_races_dir()
        try:
            with open(race_path, 'w') as handle:
                handle.write(csv_text)
            with open(ACTIVE_RACE_STATE_PATH, 'w') as handle:
                handle.write(json.dumps(state_payload))
            self.state['_persisted_snapshot'] = snapshot
            self.state['_persist_error_snapshot'] = ''
            self.state['recoverable_race'] = self._recoverable_race_info()
        except OSError as err:
            if self.state.get('_persist_error_snapshot') != snapshot:
                self.state['_persist_error_snapshot'] = snapshot
                self._log('Nepodarilo se ulozit CSV: %s' % err)

    def _active_race_payload(self):
        synced_ids = self.state.get('synced_ids', set())
        if isinstance(synced_ids, set):
            synced_ids = list(synced_ids)
        return {
            'version': 1,
            'mode': self.state.get('mode', 'IDLE'),
            'num_stations': self.state.get('num_stations', 0),
            'synced_ids': synced_ids,
            'chip_readings': self.state.get('chip_readings', []),
            'race_ended': self.state.get('race_ended', False),
            'race_session_id': self.state.get('race_session_id', ''),
            'race_csv_path': self.state.get('race_csv_path', ''),
            'race_started_epoch': self.state.get('race_started_epoch', 0),
            'synced_epoch': self.state.get('synced_epoch', 0),
            'last_saved_epoch': self.state.get('last_saved_epoch', 0),
            '_next_read_id': self.state.get('_next_read_id', 1),
        }

    def _log(self, msg):
        log = self.state.setdefault('log', [])
        log.append(msg)
        if len(log) > 200:
            del log[:50]


    def _send_parts(self, conn, status, ctype, parts, extra=''):
        if 'Cache-Control:' not in extra:
            extra += 'Cache-Control: no-store\r\n'
        total = 0
        encoded_parts = []
        for part in parts:
            if isinstance(part, str):
                part = part.encode('utf-8')
            encoded_parts.append(part)
            total += len(part)
        header = (
            f'HTTP/1.1 {status}\r\n'
            f'Content-Type: {ctype}\r\n'
            f'Content-Length: {total}\r\n'
            f'{extra}'
            f'Connection: close\r\n'
            f'\r\n'
        ).encode('utf-8')
        conn.sendall(header)
        for part in encoded_parts:
            conn.sendall(part)

    def _send(self, conn, status, ctype, body, extra=''):
        if isinstance(body, str):
            body = body.encode('utf-8')
        if 'Cache-Control:' not in extra:
            extra += 'Cache-Control: no-store\r\n'
        header = (
            f'HTTP/1.1 {status}\r\n'
            f'Content-Type: {ctype}\r\n'
            f'Content-Length: {len(body)}\r\n'
            f'{extra}'
            f'Connection: close\r\n'
            f'\r\n'
        ).encode('utf-8')
        conn.sendall(header + body)

    def _redirect(self, conn, location):
        resp = (
            f'HTTP/1.1 302 Found\r\n'
            f'Location: {location}\r\n'
            f'Content-Length: 0\r\n'
            f'Connection: close\r\n'
            f'\r\n'
        ).encode('utf-8')
        conn.sendall(resp)
