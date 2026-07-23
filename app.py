"""
app.py - JamSlayer V3 Flask Application
SCADA Alarm Trend Analysis Dashboard for AGS1 Sort Center
All HTML/CSS/JS embedded - no subfolders needed.
"""

import os
import json
from flask import Flask, request, jsonify, Response

import database
import alarm_parser
import analysis

# Configuration
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max upload

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'jamslayer-dev-key')

# Initialize database on startup
database.init_db()


# ============================================================
# EMBEDDED HTML DASHBOARD
# ============================================================

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JamSlayer - AGS1 Alarm Trend Analysis</title>
<style>
:root {
    --bg: #0f1419;
    --surface: #1a2332;
    --surface-alt: #1e2a3a;
    --border: #2d3f52;
    --text: #e8edf3;
    --text2: #8b9ab5;
    --muted: #5c6f85;
    --red: #ef4444;
    --red-bg: rgba(239,68,68,0.08);
    --orange: #f97316;
    --orange-bg: rgba(249,115,22,0.08);
    --yellow: #eab308;
    --yellow-bg: rgba(234,179,8,0.08);
    --green: #22c55e;
    --green-bg: rgba(34,197,94,0.08);
    --blue: #3b82f6;
    --blue-bg: rgba(59,130,246,0.08);
    --gray: #6b7280;
    --font: -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
    --mono: 'SF Mono','Fira Code',Consolas,monospace;
    --radius: 8px;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:var(--font); background:var(--bg); color:var(--text); min-height:100vh; }

/* Header */
.header { background:var(--surface); border-bottom:1px solid var(--border); padding:16px 24px; position:sticky; top:0; z-index:100; }
.header-inner { max-width:1400px; margin:0 auto; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px; }
.header-title { display:flex; align-items:center; gap:12px; }
.header-title h1 { font-size:1.5rem; font-weight:700; }
.header-title .logo { font-size:1.8rem; }
.header-sub { font-size:0.75rem; color:var(--muted); text-transform:uppercase; letter-spacing:0.05em; }
.header-meta { text-align:right; font-size:0.8rem; color:var(--text2); }

/* Main */
.main { max-width:1400px; margin:0 auto; padding:24px; }

/* Upload */
.dropzone { border:2px dashed var(--border); border-radius:var(--radius); padding:28px; text-align:center; cursor:pointer; background:var(--surface); transition:all 0.2s; margin-bottom:20px; }
.dropzone:hover,.dropzone.dragover { border-color:var(--blue); background:rgba(59,130,246,0.03); }
.dropzone-icon { font-size:2rem; margin-bottom:6px; }
.dropzone-text { color:var(--text2); margin-bottom:4px; }
.dropzone-hint { font-size:0.75rem; color:var(--muted); }
.file-input { display:none; }
.upload-status { margin-bottom:20px; padding:12px 16px; border-radius:var(--radius); display:none; font-size:0.85rem; }
.upload-status.show { display:block; }
.upload-status.loading { background:var(--blue-bg); border:1px solid rgba(59,130,246,0.3); color:var(--blue); }
.upload-status.success { background:var(--green-bg); border:1px solid rgba(34,197,94,0.3); color:var(--green); }
.upload-status.error { background:var(--red-bg); border:1px solid rgba(239,68,68,0.3); color:var(--red); }

/* KPIs */
.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:24px; }
.kpi { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:16px; }
.kpi-label { font-size:0.7rem; text-transform:uppercase; letter-spacing:0.05em; color:var(--muted); margin-bottom:4px; }
.kpi-value { font-size:1.6rem; font-weight:700; font-family:var(--mono); }
.kpi-value.red { color:var(--red); }
.kpi-value.orange { color:var(--orange); }
.kpi-value.yellow { color:var(--yellow); }

/* Section */
.section { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:20px; margin-bottom:20px; }
.section-title { font-size:1rem; font-weight:700; margin-bottom:14px; display:flex; align-items:center; gap:8px; }
.section-title .badge { font-size:0.7rem; padding:3px 8px; border-radius:12px; font-weight:600; }
.badge-red { background:var(--red-bg); color:var(--red); }
.badge-orange { background:var(--orange-bg); color:var(--orange); }
.badge-yellow { background:var(--yellow-bg); color:var(--yellow); }
.badge-green { background:var(--green-bg); color:var(--green); }
.badge-blue { background:var(--blue-bg); color:var(--blue); }

/* Tables */
table { width:100%; border-collapse:collapse; font-size:0.8rem; }
th { text-align:left; padding:8px 10px; border-bottom:2px solid var(--border); color:var(--muted); font-weight:600; text-transform:uppercase; font-size:0.65rem; letter-spacing:0.05em; white-space:nowrap; }
td { padding:8px 10px; border-bottom:1px solid var(--border); vertical-align:middle; }
tr:hover { background:var(--surface-alt); }
.device-name { font-family:var(--mono); font-size:0.75rem; font-weight:500; }
.plc-name { font-family:var(--mono); font-size:0.7rem; color:var(--text2); }
.score-cell { display:flex; align-items:center; gap:6px; }
.score-bar { height:5px; border-radius:3px; min-width:3px; max-width:60px; }
.score-num { font-weight:700; font-family:var(--mono); min-width:28px; }
.action-text { font-size:0.7rem; color:var(--text2); max-width:220px; line-height:1.3; }
/* Device link */
.device-link { color:var(--blue); cursor:pointer; text-decoration:none; font-family:var(--mono); font-size:0.75rem; font-weight:500; } .device-link:hover { text-decoration:underline; }

/* Modal */
.modal-overlay { position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.7); z-index:999; display:flex; align-items:center; justify-content:center; padding:20px; }
.modal { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:24px; max-width:700px; width:100%; max-height:80vh; overflow-y:auto; position:relative; }
.modal-close { position:absolute; top:12px; right:16px; background:none; border:none; color:var(--muted); font-size:1.5rem; cursor:pointer; } .modal-close:hover { color:var(--text); }
.modal h3 { font-size:1.1rem; margin-bottom:4px; font-family:var(--mono); }
.modal p { font-size:0.8rem; color:var(--muted); margin-bottom:16px; }
.chart-container { width:100%; height:200px; }
.chart-bar-row { display:flex; align-items:center; gap:6px; margin-bottom:3px; font-size:0.7rem; }
.chart-date { width:55px; text-align:right; color:var(--muted); font-family:var(--mono); }
.chart-bar { height:16px; border-radius:3px; background:var(--blue); min-width:1px; transition:width 0.3s; }
.chart-val { color:var(--text2); font-family:var(--mono); min-width:20px; }

/* Ratio tooltip */
.ratio-header { position:relative; }
.ratio-hint { position:absolute; top:100%; left:0; background:var(--surface); border:1px solid var(--border); border-radius:6px; padding:8px 12px; font-size:0.7rem; color:var(--text2); width:220px; z-index:50; display:none; font-weight:400; text-transform:none; letter-spacing:normal; line-height:1.4; box-shadow:0 4px 12px rgba(0,0,0,0.4); }
.ratio-header:hover .ratio-hint { display:block; }

.tag { display:inline-block; padding:2px 6px; border-radius:4px; font-size:0.6rem; font-weight:700; text-transform:uppercase; letter-spacing:0.03em; }
.tag-worsening { background:var(--red-bg); color:var(--red); }
.tag-chronic { background:var(--yellow-bg); color:var(--yellow); }
.tag-stb { background:var(--orange-bg); color:var(--orange); }
.tag-improving { background:var(--green-bg); color:var(--green); }
.tag-stable { background:rgba(107,114,128,0.1); color:var(--gray); }

/* Sortable headers */
th.sortable { cursor:pointer; user-select:none; } th.sortable:hover { color:var(--blue); } th.sortable::after { content:' \\2195'; font-size:0.7em; opacity:0.4; } th.sorted-asc::after { content:' \\2191'; opacity:1; } th.sorted-desc::after { content:' \\2193'; opacity:1; }

/* Row tints */
.row-worsening { background:var(--red-bg); }
.row-chronic { background:var(--yellow-bg); }
.row-stb { background:var(--orange-bg); }
.row-improving { background:var(--green-bg); }

/* Empty state */
.empty-state { text-align:center; padding:60px 24px; }
.empty-state h3 { font-size:1.2rem; margin:12px 0 8px; }
.empty-state p { color:var(--muted); }

/* Responsive */
@media (max-width:768px) {
    .main { padding:12px; }
    .kpi-grid { grid-template-columns:repeat(3,1fr); }
    table { font-size:0.7rem; }
    th, td { padding:6px; }
}
@media print {
    .dropzone, .upload-status, .header { display:none; }
    body { background:#fff; color:#000; }
    .section { border:1px solid #ccc; }
    table { font-size:9px; }
}
</style>
</head>
<body>
<header class="header">
<div class="header-inner">
<div class="header-title">
<span class="logo">&#9889;</span>
<div><h1>JamSlayer</h1><span class="header-sub">AGS1 Sort Center &bull; PEC Blockage Trend Analysis</span></div>
</div>
<div class="header-meta">
<div id="last-updated">Loading...</div>
<div id="data-range"></div>
</div>
</div>
</header>

<main class="main">
<!-- Upload -->
<div class="dropzone" id="dropzone">
<div class="dropzone-icon">&#128193;</div>
<div class="dropzone-text">Drop SCADA alarm export here or click to upload</div>
<div class="dropzone-hint">Accepts any file type &mdash; XML SpreadsheetML, .xlsx, .xlsm, .xls, .csv (no extension OK)</div>
<input type="file" class="file-input" id="file-input">
</div>
<div class="upload-status" id="upload-status"></div>

<!-- KPIs -->
<div class="kpi-grid" id="kpi-grid">
<div class="kpi"><div class="kpi-label">Total Devices</div><div class="kpi-value" id="kpi-devices">&mdash;</div></div>
<div class="kpi"><div class="kpi-label">Worsening</div><div class="kpi-value red" id="kpi-worsening">&mdash;</div></div>
<div class="kpi"><div class="kpi-label">Chronic</div><div class="kpi-value yellow" id="kpi-chronic">&mdash;</div></div>
<div class="kpi"><div class="kpi-label">Starting to Block</div><div class="kpi-value orange" id="kpi-stb">&mdash;</div></div>
<div class="kpi"><div class="kpi-label">Total PEC Alarms</div><div class="kpi-value" id="kpi-total">&mdash;</div></div>
<div class="kpi"><div class="kpi-label">Active Days</div><div class="kpi-value" id="kpi-days">&mdash;</div></div>
</div>

<!-- Worsening -->
<div class="section" id="sec-worsening" style="display:none">
<div class="section-title">&#128308; Worsening Devices <span class="badge badge-red" id="cnt-worsening">0</span></div>
<table id="table-worsening"><thead><tr><th>#</th><th class="sortable" data-col="device" data-type="str">Device</th><th class="sortable" data-col="plc" data-type="str">PLC</th><th class="sortable" data-col="priority_score" data-type="num">Score</th><th class="sortable" data-col="slope" data-type="num">Slope</th><th class="sortable" data-col="full_avg" data-type="num">Avg/Day</th><th class="sortable ratio-header" data-col="increase_ratio" data-type="num">Ratio<span class="ratio-hint">Recent avg &divide; Early avg. Shows how much worse (or better) this device is now vs. the start of the data. 3.0x = tripled.</span></th><th class="sortable" data-col="days_active" data-type="num">Days Active</th></tr></thead>
<tbody id="tbl-worsening"></tbody></table>
</div>

<!-- Starting to Block -->
<div class="section" id="sec-stb" style="display:none">
<div class="section-title">&#128992; Starting to Block <span class="badge badge-orange" id="cnt-stb">0</span></div>
<table id="table-stb"><thead><tr><th>#</th><th class="sortable" data-col="device" data-type="str">Device</th><th class="sortable" data-col="plc" data-type="str">PLC</th><th class="sortable" data-col="priority_score" data-type="num">Score</th><th class="sortable" data-col="slope" data-type="num">Slope</th><th class="sortable" data-col="full_avg" data-type="num">Avg/Day</th><th class="sortable ratio-header" data-col="increase_ratio" data-type="num">Ratio<span class="ratio-hint">Recent avg &divide; Early avg. Shows how much worse (or better) this device is now vs. the start of the data. 3.0x = tripled.</span></th><th class="sortable" data-col="days_active" data-type="num">Days Active</th></tr></thead>
<tbody id="tbl-stb"></tbody></table>
</div>

<!-- Chronic -->
<div class="section" id="sec-chronic" style="display:none">
<div class="section-title">&#128993; Chronic Devices <span class="badge badge-yellow" id="cnt-chronic">0</span></div>
<table id="table-chronic"><thead><tr><th>#</th><th class="sortable" data-col="device" data-type="str">Device</th><th class="sortable" data-col="plc" data-type="str">PLC</th><th class="sortable" data-col="priority_score" data-type="num">Score</th><th class="sortable" data-col="slope" data-type="num">Slope</th><th class="sortable" data-col="full_avg" data-type="num">Avg/Day</th><th class="sortable" data-col="consistency" data-type="num">Consistency</th><th class="sortable" data-col="days_active" data-type="num">Days Active</th></tr></thead>
<tbody id="tbl-chronic"></tbody></table>
</div>

<!-- Top 25 -->
<div class="section" id="sec-top25" style="display:none">
<div class="section-title">&#127919; Top 25 Priority Devices</div>
<table id="table-top25"><thead><tr><th>#</th><th class="sortable" data-col="device" data-type="str">Device</th><th class="sortable" data-col="plc" data-type="str">PLC</th><th>Class</th><th class="sortable" data-col="priority_score" data-type="num">Score</th><th class="sortable" data-col="slope" data-type="num">Slope</th><th class="sortable" data-col="full_avg" data-type="num">Avg/Day</th><th class="sortable" data-col="increase_ratio" data-type="num">Ratio</th><th class="sortable" data-col="days_active" data-type="num">Days</th></tr></thead>
<tbody id="tbl-top25"></tbody></table>
</div>

<!-- Empty state -->
<div class="empty-state" id="empty-state">
<div style="font-size:3rem">&#128202;</div>
<h3>No Data Yet</h3>
<p>Upload a SCADA alarm export to start analyzing PEC blockage trends.</p>
</div>
</main>

<script>
var API_URL = '/api/data';
var UPLOAD_URL = '/upload';
var dashData = null;

document.addEventListener('DOMContentLoaded', function() {
    setupDropzone();
    loadData();
});

function setupDropzone() {
    var dz = document.getElementById('dropzone');
    var fi = document.getElementById('file-input');
    
    dz.addEventListener('click', function() { fi.click(); });
    fi.addEventListener('change', function() { if (fi.files.length > 0) uploadFile(fi.files[0]); });
    
    dz.addEventListener('dragover', function(e) { e.preventDefault(); dz.classList.add('dragover'); });
    dz.addEventListener('dragleave', function() { dz.classList.remove('dragover'); });
    dz.addEventListener('drop', function(e) {
        e.preventDefault();
        dz.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) uploadFile(e.dataTransfer.files[0]);
    });
}

function showStatus(msg, type) {
    var el = document.getElementById('upload-status');
    el.textContent = msg;
    el.className = 'upload-status show ' + type;
}

function uploadFile(file) {
    showStatus('Processing ' + file.name + ' (' + (file.size / 1024 / 1024).toFixed(1) + ' MB)... This may take 30-60 seconds for large files.', 'loading');
    
    var fd = new FormData();
    fd.append('file', file);
    
    fetch(UPLOAD_URL, { method: 'POST', body: fd })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            showStatus('Success: ' + data.message, 'success');
            loadData();
        } else {
            showStatus('Error: ' + data.error, 'error');
        }
    })
    .catch(function(err) {
        showStatus('Upload failed: ' + err.message, 'error');
    });
}

function loadData() {
    fetch(API_URL)
    .then(function(r) { return r.json(); })
    .then(function(result) {
        if (result.success && result.data) {
            renderDashboard(result.data);
            dashData = result.data;
        }
    })
    .catch(function(err) { console.error('Load failed:', err); });
}

function renderDashboard(data) {
    if (data.empty) {
        document.getElementById('empty-state').style.display = 'block';
        document.getElementById('sec-worsening').style.display = 'none';
        document.getElementById('sec-stb').style.display = 'none';
        document.getElementById('sec-chronic').style.display = 'none';
        document.getElementById('sec-top25').style.display = 'none';
        return;
    }
    
    document.getElementById('empty-state').style.display = 'none';
    
    // KPIs
    var stats = data.stats || {};
    var cls = data.classifications || {};
    document.getElementById('kpi-devices').textContent = (stats.total_devices || 0).toLocaleString();
    document.getElementById('kpi-worsening').textContent = cls.WORSENING || 0;
    document.getElementById('kpi-chronic').textContent = cls.CHRONIC || 0;
    document.getElementById('kpi-stb').textContent = cls.STARTING_TO_BLOCK || 0;
    document.getElementById('kpi-total').textContent = (stats.total_alarms || 0).toLocaleString();
    document.getElementById('kpi-days').textContent = stats.active_days || 0;
    
    // Meta
    var dr = data.date_range || {};
    if (dr.start && dr.end) {
        document.getElementById('data-range').textContent = 'Data: ' + dr.start + ' to ' + dr.end + ' (' + dr.days + ' days)';
    }
    if (data.generated_at) {
        var dt = new Date(data.generated_at);
        document.getElementById('last-updated').textContent = 'Last analysis: ' + dt.toLocaleDateString() + ' ' + dt.toLocaleTimeString();
    }
    
    // Worsening table
    renderSection('sec-worsening', 'tbl-worsening', 'cnt-worsening', data.worsening || [], 'worsening');
    
    // Starting to block
    renderSection('sec-stb', 'tbl-stb', 'cnt-stb', data.starting_to_block || [], 'stb');
    
    // Chronic
    renderSection('sec-chronic', 'tbl-chronic', 'cnt-chronic', data.chronic || [], 'chronic');
    
    // Top 25
    if (data.top25 && data.top25.length > 0) {
        document.getElementById('sec-top25').style.display = 'block';
        var tbody = document.getElementById('tbl-top25');
        tbody.innerHTML = '';
        (data.top25 || []).forEach(function(d, i) {
            var tagClass = getTagClass(d.classification);
            var scoreColor = getScoreColor(d.priority_score);
            tbody.innerHTML += '<tr>' +
                '<td>' + (i+1) + '</td>' +
                '<td><a class="device-link" onclick="showDeviceChart(\'' + d.device + '\')">' + d.device + '</a></td>' +
                '<td class="plc-name">' + (d.plc || '') + '</td>' +
                '<td><span class="tag ' + tagClass + '">' + d.classification.replace('_',' ') + '</span></td>' +
                '<td><div class="score-cell"><span class="score-num" style="color:' + scoreColor + '">' + d.priority_score + '</span><div class="score-bar" style="width:' + d.priority_score*0.6 + 'px;background:' + scoreColor + '"></div></div></td>' +
                '<td>' + (d.slope > 0 ? '+' : '') + d.slope + '</td>' +
                '<td>' + d.full_avg + '</td>' +
                '<td>' + d.increase_ratio + 'x</td>' +
                '<td>' + d.days_active + '</td>' +
                '</tr>';
        });
    }
}

function renderSection(secId, tblId, cntId, devices, type) {
    var sec = document.getElementById(secId);
    if (!devices || devices.length === 0) {
        sec.style.display = 'none';
        return;
    }
    sec.style.display = 'block';
    document.getElementById(cntId).textContent = devices.length;
    
    var tbody = document.getElementById(tblId);
    tbody.innerHTML = '';
    devices.forEach(function(d, i) {
        var scoreColor = getScoreColor(d.priority_score);
        var ratioText = d.increase_ratio + 'x';
        if (type === 'chronic') {
            ratioText = (d.consistency * 100).toFixed(0) + '%';
        }
        tbody.innerHTML += '<tr>' +
            '<td>' + (i+1) + '</td>' +
            '<td><a class="device-link" onclick="showDeviceChart(\'' + d.device + '\')">' + d.device + '</a></td>' +
            '<td class="plc-name">' + (d.plc || '') + '</td>' +
            '<td><div class="score-cell"><span class="score-num" style="color:' + scoreColor + '">' + d.priority_score + '</span><div class="score-bar" style="width:' + d.priority_score*0.6 + 'px;background:' + scoreColor + '"></div></div></td>' +
            '<td>' + (d.slope > 0 ? '+' : '') + d.slope + '</td>' +
            '<td>' + d.full_avg + '</td>' +
            '<td>' + ratioText + '</td>' +
            '<td>' + d.days_active + '</td>' +
            '</tr>';
    });
}

// Column sorting
document.addEventListener('click', function(e) {
    var th = e.target.closest('th.sortable');
    if (!th) return;
    var table = th.closest('table');
    var tbody = table.querySelector('tbody');
    var col = th.getAttribute('data-col');
    var type = th.getAttribute('data-type');
    var isAsc = th.classList.contains('sorted-asc');
    
    // Clear other sort indicators in this table
    table.querySelectorAll('th.sortable').forEach(function(h) { h.classList.remove('sorted-asc','sorted-desc'); });
    
    // Determine which data array to sort
    var dataKey = null;
    if (table.id === 'table-worsening') dataKey = 'worsening';
    else if (table.id === 'table-stb') dataKey = 'starting_to_block';
    else if (table.id === 'table-chronic') dataKey = 'chronic';
    else if (table.id === 'table-top25') dataKey = 'top25';
    
    if (!dataKey || !dashData || !dashData[dataKey]) return;
    
    var arr = dashData[dataKey].slice();
    arr.sort(function(a, b) {
        var va = a[col], vb = b[col];
        if (type === 'num') {
            va = parseFloat(va) || 0;
            vb = parseFloat(vb) || 0;
        } else {
            va = (va || '').toString().toLowerCase();
            vb = (vb || '').toString().toLowerCase();
        }
        if (va < vb) return isAsc ? 1 : -1;
        if (va > vb) return isAsc ? -1 : 1;
        return 0;
    });
    
    th.classList.add(isAsc ? 'sorted-desc' : 'sorted-asc');
    
    // Re-render
    if (dataKey === 'top25') {
        dashData.top25 = arr;
        renderDashboard(dashData);
    } else {
        dashData[dataKey] = arr;
        var tblId = 'tbl-' + (dataKey === 'starting_to_block' ? 'stb' : dataKey);
        var cntId = 'cnt-' + (dataKey === 'starting_to_block' ? 'stb' : dataKey);
        var secType = dataKey === 'starting_to_block' ? 'stb' : dataKey;
        renderSection('sec-' + secType, tblId, cntId, arr, secType);
    }
});

function getScoreColor(score) {
    if (score >= 70) return 'var(--red)';
    if (score >= 40) return 'var(--orange)';
    if (score >= 20) return 'var(--yellow)';
    return 'var(--text2)';
}

function getTagClass(cls) {
    if (cls === 'WORSENING') return 'tag-worsening';
    if (cls === 'CHRONIC') return 'tag-chronic';
    if (cls === 'STARTING_TO_BLOCK') return 'tag-stb';
    if (cls === 'IMPROVING') return 'tag-improving';
    return 'tag-stable';
}

// Device chart popup
function showDeviceChart(device) {
    fetch('/api/device/' + encodeURIComponent(device))
    .then(function(r) { return r.json(); })
    .then(function(result) {
        if (!result.success) return;
        var data = result.data;
        var maxVal = Math.max.apply(null, data.counts.map(function(c){return c.count;})) || 1;
        
        var barsHtml = '';
        data.counts.forEach(function(d) {
            var pct = (d.count / maxVal) * 100;
            var dateShort = d.date.substring(5); // MM-DD
            barsHtml += '<div class="chart-bar-row">' +
                '<span class="chart-date">' + dateShort + '</span>' +
                '<div class="chart-bar" style="width:' + pct + '%"></div>' +
                '<span class="chart-val">' + d.count + '</span>' +
                '</div>';
        });
        
        var modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.id = 'device-modal';
        modal.innerHTML = '<div class="modal">' +
            '<button class="modal-close" onclick="closeModal()">&times;</button>' +
            '<h3>' + device + '</h3>' +
            '<p>Daily PEC Blockage count &mdash; ' + data.date_range.start + ' to ' + data.date_range.end + ' (' + data.total_alarms + ' total)</p>' +
            '<div class="chart-container">' + barsHtml + '</div>' +
            '</div>';
        
        document.body.appendChild(modal);
        
        // Close on clicking overlay background
        modal.addEventListener('click', function(e) {
            if (e.target === modal) closeModal();
        });
    })
    .catch(function(err) { console.error('Device chart error:', err); });
}

function closeModal() {
    var modal = document.getElementById('device-modal');
    if (modal) modal.remove();
}

// Close modal with Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeModal();
});
</script>
</body>
</html>"""


# ============================================================
# FLASK ROUTES
# ============================================================

@app.route('/')
def index():
    """Serve the dashboard."""
    return Response(DASHBOARD_HTML, mimetype='text/html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload — wipes previous data and runs fresh analysis."""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Read file content (accept ANY file type)
        filename = file.filename or 'unnamed_export'
        file_content = file.read()
        
        if len(file_content) == 0:
            return jsonify({'success': False, 'error': 'File is empty'}), 400
        
        # Wipe all existing data — each upload is a fresh analysis period
        database.clear_all_data()
        
        # Parse file
        try:
            events, format_type, record_count = alarm_parser.parse_file(file_content, filename)
        except alarm_parser.ParseError as e:
            return jsonify({'success': False, 'error': str(e)}), 422
        
        # Get date range from events
        dates = sorted(set(e['date'] for e in events if e.get('date')))
        date_start = dates[0] if dates else None
        date_end = dates[-1] if dates else None
        
        # Store in database
        file_hash = database.compute_file_hash(file_content)
        upload_id = database.record_upload(
            filename, file_hash, record_count, format_type, date_start, date_end
        )
        database.insert_alarm_events(events, upload_id)
        
        # Run analysis
        analysis_result = analysis.run_analysis()
        
        # Cache analysis
        database.save_analysis_cache(json.dumps(analysis_result, default=str))
        
        return jsonify({
            'success': True,
            'message': 'Processed ' + str(record_count) + ' events (' + str(format_type) + ') from ' + filename + ' [' + str(date_start) + ' to ' + str(date_end) + ']',
            'format_detected': format_type,
            'record_count': record_count
        })
    
    except Exception as e:
        app.logger.error("Upload error: " + str(e), exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Server error: ' + str(e)
        }), 500


@app.route('/api/data')
def get_data():
    """Return current analysis data as JSON."""
    try:
        cached = database.get_analysis_cache()
        if cached:
            analysis_data = json.loads(cached['analysis_json'])
            analysis_data['cached_at'] = cached['generated_at']
            return jsonify({'success': True, 'data': analysis_data})
        
        stats = database.get_total_stats()
        if stats['total_devices'] == 0:
            return jsonify({
                'success': True,
                'data': {
                    'devices': [],
                    'stats': stats,
                    'classifications': {'WORSENING': 0, 'CHRONIC': 0, 'STARTING_TO_BLOCK': 0, 'IMPROVING': 0, 'STABLE': 0},
                    'worsening': [],
                    'chronic': [],
                    'starting_to_block': [],
                    'top25': [],
                    'date_range': {'start': None, 'end': None, 'days': 0},
                    'empty': True
                }
            })
        
        analysis_result = analysis.run_analysis()
        database.save_analysis_cache(json.dumps(analysis_result, default=str))
        return jsonify({'success': True, 'data': analysis_result})
    
    except Exception as e:
        app.logger.error("API error: " + str(e), exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/uploads')
def get_uploads():
    """Return upload history."""
    try:
        uploads = database.get_recent_uploads(20)
        return jsonify({'success': True, 'uploads': uploads})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device/<path:device_name>')
def get_device_data(device_name):
    """Return daily timeseries for a specific device (for chart popup)."""
    try:
        # Get this device's daily counts
        device_counts = database.get_device_daily_timeseries(device_name)
        
        if not device_counts:
            return jsonify({'success': False, 'error': 'No data for device: ' + device_name}), 404
        
        # Get all dates to fill gaps with zeros
        all_dates = database.get_all_dates()
        count_map = {r['date']: r['count'] for r in device_counts}
        
        # Build full timeseries with zeros for missing days
        full_counts = [{'date': d, 'count': count_map.get(d, 0)} for d in all_dates]
        total_alarms = sum(c['count'] for c in full_counts)
        
        return jsonify({
            'success': True,
            'data': {
                'device': device_name,
                'counts': full_counts,
                'total_alarms': total_alarms,
                'date_range': {'start': all_dates[0], 'end': all_dates[-1]},
                'days_active': len([c for c in full_counts if c['count'] > 0])
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_data():
    """Reset all data."""
    try:
        database.clear_all_data()
        return jsonify({'success': True, 'message': 'All data cleared'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Error handlers
@app.errorhandler(413)
def too_large(e):
    return jsonify({'success': False, 'error': 'File too large. Max 100MB.'}), 413

@app.errorhandler(404)
def not_found(e):
    return jsonify({'success': False, 'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
