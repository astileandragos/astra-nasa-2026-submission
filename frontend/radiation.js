// Radiation page: status with what to do and the latest alerts (one panel), the estimated daily exposure against NASA's
// career limit (one panel), and the event history. Needs core.js and chart.js.
// RAD is "external" (real NOAA GOES data, the default) or "simulated" (a labelled demo, switched on by the demo buttons).
// NOAA proton flux is never turned into a dose. The dose is an estimate: an assumed background rate plus event doses that
// are either simulated (demo) or typed in from a dosimeter. NASA's career limit is 600 mSv (NASA-STD-3001 Vol 1, V1 4030).

const RAD = new URLSearchParams(window.location.search).get('rad') === 'simulated' ? 'simulated' : 'external';
const S_LABEL = { 0: 'No storm', 1: 'S1 minor storm', 2: 'S2 moderate storm', 3: 'S3 strong storm', 4: 'S4 severe storm', 5: 'S5 extreme storm' };
const STATE_KEYS = ['normal', 'elevated', 'high', 'severe'];
let expChart = null;

function tile(label, value, unit, sub) {
    const box = el('div', 'tile');
    box.append(el('span', 'label', label));
    const line = el('div', 'tile-value');
    line.append(el('span', '', value));
    if (unit) line.append(el('span', 'unit', unit));
    box.append(line, el('span', 'note', sub || ''));
    return box;
}

const radGet = (path) => api(`/radiation/${path}${path.includes('?') ? '&' : '?'}source=${RAD}`, false);

async function radPost(path, body, source = RAD) {
    const response = await fetch(`${API}/radiation/${path}${path.includes('?') ? '&' : '?'}source=${source}`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.message || `HTTP ${response.status}`);
    return data;
}

const utcDateTime = (iso) => (iso ? `${iso.slice(5, 10)} ${iso.slice(11, 16)}` : '--');
const flux = (v) => (v === null || v === undefined ? '--' : v >= 100 ? Math.round(v).toLocaleString('en-US') : String(Math.round(v * 100) / 100));
const msv = (v) => (v === null || v === undefined ? '--' : v >= 100 ? String(Math.round(v)) : String(Math.round(v * 100) / 100));

function say(id, text, bad) {
    const node = $(id);
    node.textContent = text;
    node.className = bad ? 'message message-error' : 'message';
}

// ---- status, what to do, notifications ----
function actionsNode(actions) {
    const box = el('div', 'rad-actions');
    box.append(el('span', 'label', 'Steps for this alert'));
    const list = el('ol', 'steps');
    actions.forEach((text) => list.append(el('li', '', text)));
    box.append(list);
    return box;
}

function renderStatus(s, alerts) {
    const st = radState(s);
    const level = s.state.level;
    $('rad-card').className = `panel rad-card scard-${st.key}`;
    $('do-box').className = `do-box do-${st.key}`;
    $('rad-level').replaceChildren(stateBadge(st.key), el('span', 'rad-level-name', st.title));
    const cls = s.state.s_class_now;
    const gone = s.data_status === 'stale' || s.data_status === 'no_data';
    const last = s.state.last_sample_at;
    $('rad-sub').textContent = RAD === 'external' && (s.fetch_error || gone)
        ? `The connection to the space weather data (NOAA) was lost. ${last ? `Showing the last information received (${utcDateTime(last)} UTC).` : 'No data have been received yet.'}`
        : st.summary;
    const facts = $('rad-facts');
    facts.replaceChildren();
    [['Storm level', cls === null ? '--' : S_LABEL[cls]], ['Solar particles', s.state.flux_pfu === null ? '--' : `${flux(s.state.flux_pfu)} (higher means a stronger storm)`],
        ['Last update', last ? `${utcDateTime(last)} UTC (${s.data_age_min} min ago)` : 'none yet']]
        .forEach(([term, value]) => facts.append(el('dt', '', term), el('dd', '', value)));
    $('do-text').textContent = st.todo;
    lastState = st.key;
    patchStatusForOutlook();
    $('rad-actions').replaceChildren(...(s.alert && st.key !== 'unknown' ? [actionsNode(s.alert.actions)] : []));
    const ack = $('rad-ack');
    ack.replaceChildren();
    if (s.ack_pending) {
        const button = el('button', 'button', 'Acknowledge alert');
        button.type = 'button';
        button.addEventListener('click', async () => {
            button.disabled = true;
            try { await radPost('ack', { alert_id: s.ack_pending.alert_id }); await loadAll(); } catch (error) { button.disabled = false; $('rad-error').textContent = error.message; }
        });
        ack.append(button);
    } else if (level > 0) {
        ack.append(el('p', 'note', 'Alert acknowledged. The level stays until the radiation falls.'));
    }
    // notifications: the latest alerts, one per change of the situation (never repeated for an unchanged event)
    const notes = $('rad-notes');
    notes.replaceChildren();
    if (alerts.length) {
        notes.append(el('span', 'label', 'Latest alerts'));
        alerts.slice(0, 3).forEach((a) => {
            const item = el('div', 'log-item');
            const top = el('div', 'panel-head');
            top.append(el('strong', '', a.title), el('span', 'note', `${utcDateTime(a.at)} UTC`));
            item.append(top, el('p', 'note', a.message));
            notes.append(item);
        });
    }
    $('rad-error').textContent = '';
}

// ---- demo (the only way to see made-up data; real NOAA data is never touched) ----
function setupDemo() {
    $('demo-banner').hidden = RAD !== 'simulated';
    $('rad-chip').replaceChildren(chip(RAD));
    $('exp-chip').replaceChildren(chip(RAD === 'simulated' ? 'simulated' : 'self_reported'));
    $('ev-chip').replaceChildren(chip(RAD));
    $('outlook-chip').replaceChildren(chip(RAD));
    const box = $('sim-buttons');
    [['quiet', 'Quiet'], ['watch', 'Watch'], ['prepare', 'Prepare'], ['s1', 'S1 storm'], ['s2', 'S2 storm'], ['s3', 'S3 storm'], ['s4', 'S4 storm'], ['history', 'Sample week']].forEach(([name, label]) => {
        const button = el('button', 'button button-quiet', label);
        button.type = 'button';
        button.addEventListener('click', async () => {
            try {
                await radPost('simulate', { scenario: name }, 'simulated');
                if (RAD !== 'simulated') { window.location.search = `?rad=simulated${window.location.search.includes('source=') ? `&source=${SOURCE}` : ''}`; return; }
                say('sim-msg', `"${label}" started.`);
                await loadAll();
            } catch (error) { say('sim-msg', error.message, true); }
        });
        box.append(button);
    });
    const exit = $('demo-exit');
    exit.href = `radiation.html?source=${SOURCE}`;
}

// ---- exposure and the career limit ----
function renderExposure(b) {
    const limit = b.budget_msv;
    $('exp-day').textContent = msv(b.daily_exposure_msv);
    $('exp-day-sub').textContent = b.daily_event_msv_24h > 0
        ? `A solar storm added ${msv(b.daily_event_msv_24h)} mSv in the last 24 hours, on top of the usual ${msv(b.daily_background_msv)} mSv for today.`
        : `Today's radiation is about ${msv(b.daily_background_msv)} mSv. It changes a little from day to day. No solar storm dose in the last 24 hours.`;
    $('exp-total').textContent = msv(b.accumulated_msv);
    $('exp-meter').style.width = `${Math.max(1, Math.round(b.used_share * 100))}%`;
    const days = b.estimated_days_remaining;
    $('exp-total-sub').textContent = b.exceeded ? `The ${limit} mSv limit is reached.`
        : `${Math.round(b.used_share * 1000) / 10}% of the limit used. ${msv(b.remaining_msv)} mSv left${days === null ? '' : `, enough for about ${Math.round(days).toLocaleString('en-US')} more days at the usual rate`}.`;
    $('exp-note').textContent = RAD === 'external'
        ? `mSv (millisievert) is a unit of radiation dose. NASA sets a limit of ${limit} mSv over an astronaut's whole career. ASTRA cannot turn the solar particle count into a dose, so you can add a reading from your radiation badge under "Adjust values". For scale, astronauts on the space station get about 0.4 to 1 mSv a day.`
        : `mSv (millisievert) is a unit of radiation dose. NASA sets a limit of ${limit} mSv over an astronaut's whole career. The storm doses here are made up for the demo.`;
    const m = b.mission;
    $('mission-tiles').replaceChildren(
        tile('Mission day', `${m.day_now}`, `of ${m.days_total}`, 'demo mission, assumed'),
        tile('Days left', `${m.days_left}`, 'days', m.days_left === 0 ? 'the mission length is reached' : 'until the end of the mission'),
        tile('Expected dose at the end', msv(m.projected_total_msv), 'mSv', m.within_limit ? `under the ${m.limit_msv} mSv limit` : `OVER the ${m.limit_msv} mSv limit`));
    $('mission-note').textContent = 'The mission is an example for the demo. You can change its length and the day under "Adjust values". The expected dose uses the usual daily rate. A solar storm would add to it.';
    const labels = b.daily.map((d) => shortDate(d.date));
    const datasets = [
        { label: 'Usual radiation (estimate)', data: b.daily.map((d) => d.background_msv), backgroundColor: '#8FA3B8', borderRadius: 2 },
        { label: 'Solar storm', data: b.daily.map((d) => d.event_msv), backgroundColor: '#A12116', borderRadius: 2 },
    ];
    const options = {
        responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        plugins: { legend: { display: true, labels: { usePointStyle: true, boxWidth: 8 } },
                   tooltip: { callbacks: { footer: (items) => `Total ${msv(b.daily[items[0].dataIndex].total_msv)} mSv`, label: (i) => `${i.dataset.label}: ${msv(i.parsed.y)} mSv` } } },
        scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, title: { display: true, text: 'mSv per day (estimate)' } } },
    };
    if (expChart) { expChart.data = { labels, datasets }; expChart.options = options; expChart.update(); } else {
        expChart = new Chart($('exp-chart').getContext('2d'), { type: 'bar', data: { labels, datasets }, options });
    }
    const form = $('cfg-form');
    if (!form.dataset.filled) { $('cfg-initial').value = b.initial_msv; $('cfg-rate').value = b.baseline_rate_msv_day; $('cfg-mdays').value = m.days_total; $('cfg-mday').value = m.day_now; form.dataset.filled = '1'; }
    $('exp-error').textContent = '';
}

function setupForms() {
    $('dose-form').addEventListener('submit', async (event) => {
        event.preventDefault();
        const value = Number($('dose-msv').value);
        if (!$('dose-msv').value || !(value > 0)) { say('dose-msg', 'Enter a dose above 0 mSv.', true); return; }
        try { await radPost('dose', { msv: value, note: $('dose-note').value }); say('dose-msg', 'Dose added.'); $('dose-msv').value = ''; $('dose-note').value = ''; await loadExposure(); }
        catch (error) { say('dose-msg', error.message, true); }
    });
    $('cfg-form').addEventListener('submit', async (event) => {
        event.preventDefault();
        try { await radPost('budget', { initial_msv: Number($('cfg-initial').value), baseline_rate_msv_day: Number($('cfg-rate').value), mission_days: Number($('cfg-mdays').value), mission_day: Number($('cfg-mday').value) }); say('cfg-msg', 'Saved.'); await loadExposure(); }
        catch (error) { say('cfg-msg', error.message, true); }
    });
}

// ---- event history ----
function eventItem(e) {
    const li = el('li', `event event-${e.active ? 'active' : 'past'}`);
    const top = el('div', 'panel-head');
    const key = STATE_KEYS[e.level_max];
    top.append(el('strong', '', S_LABEL[e.s_class_peak]), stateBadge(key), el('span', e.active ? 'badge badge-warning' : 'badge badge-ok', e.active ? 'ACTIVE' : 'ENDED'));
    li.append(top, el('p', 'note', `Started ${utcDateTime(e.started_at)} UTC${e.ended_at ? `, ended ${utcDateTime(e.ended_at)} UTC` : ''} · duration ${e.duration_min >= 60 ? `${Math.floor(e.duration_min / 60)} h ${e.duration_min % 60} min` : `${e.duration_min} min`} · peak ${flux(e.peak_flux_pfu)} pfu`),
        el('p', 'note', `What to do: ${RAD_STATE_TEXT[key].todo}`));
    return li;
}

function renderEvents(d) {
    $('ev-list').replaceChildren(...(d.events.length ? d.events.map(eventItem)
        : [el('li', 'note', RAD === 'external' ? 'No solar storms in the last 7 days.' : 'No made-up storms yet. Use the demo buttons above.')]));
    $('ev-error').textContent = '';
}

// ---- the outlook: five stages and what to do at each ----
let lastOutlook = null;
let lastState = null;
// While the particle level is still NORMAL but the early signs say watch or prepare, the status panel must not say "all quiet".
function patchStatusForOutlook() {
    if (!lastOutlook || !lastState || lastState !== 'normal') return;
    const key = lastOutlook.stage.key;
    if (key !== 'watch' && key !== 'prepare') return;
    $('rad-sub').textContent = 'The particle level is still normal, but there are early signs of a solar storm.';
    $('do-text').textContent = 'Nothing to do yet at this level, but follow the steps in "Get ready" above.';
}

const STAGE_CLASS = { clear: 'normal', watch: 'elevated', prepare: 'high', build: 'severe', shelter: 'severe', unknown: 'unknown' };

function renderOutlook(o) {
    lastOutlook = o;
    const key = o.stage.key;
    const css = STAGE_CLASS[key];
    $('outlook-panel').className = `panel scard-${css}`;
    $('outlook-stages').replaceChildren(...o.stages.map((s, i) => {
        const li = el('li', `stage${i === o.stage.index ? ` stage-now stage-${STAGE_CLASS[s.key]}` : ''}${o.stage.index !== null && i < o.stage.index ? ' stage-done' : ''}`);
        li.append(el('span', 'stage-num', String(i + 1)), document.createTextNode(` ${s.title}`));
        if (i === o.stage.index) li.setAttribute('aria-current', 'step');
        return li;
    }));
    $('outlook-headline').replaceChildren(el('strong', '', `${o.stage.title}: `), document.createTextNode(o.stage.headline));
    const box = $('outlook-steps');
    box.replaceChildren();
    if (o.stage.steps.length) {
        box.append(el('span', 'label', 'What to do'));
        const list = el('ol', 'steps');
        o.stage.steps.forEach((s) => {
            const li = el('li');
            li.append(el('span', `chip ${s.tag === 'nasa' ? 'chip-external' : 'chip-plain'}`, s.tag === 'nasa' ? 'FROM NASA' : 'ASTRA EXAMPLE'), document.createTextNode(` ${s.text}`));
            list.append(li);
        });
        box.append(list);
    }
    $('outlook-signals').replaceChildren(...o.signals.map((s) => {
        const li = el('li', `signal${s.active ? ' signal-on' : ''}`);
        li.append(el('span', 'signal-mark', s.active ? '▲' : '○'), document.createTextNode(` ${s.text}`));
        return li;
    }));
    $('outlook-limits').textContent = o.limits;
    $('outlook-sources').replaceChildren(...o.sources.map((s) => {
        const li = el('li');
        const a = el('a', '', s.label);
        a.href = s.url; a.target = '_blank'; a.rel = 'noopener noreferrer';
        li.append(a);
        return li;
    }));
    $('outlook-error').textContent = '';
    patchStatusForOutlook();
}

async function loadOutlook() {
    try { renderOutlook(await radGet('outlook')); } catch (error) { $('outlook-error').textContent = 'Could not load the outlook (server not reachable?).'; }
}

// ---- loading ----
let lastAlerts = [];
async function loadStatus() {
    try { renderStatus(await radGet('status'), lastAlerts); } catch (error) { $('rad-error').textContent = 'Could not load the radiation status (server not reachable?).'; }
}
async function loadEvents() {
    try {
        const d = await radGet('events?days=7');
        lastAlerts = d.alerts;
        renderEvents(d);
        await loadStatus();
    } catch (error) { $('ev-error').textContent = 'Could not load events.'; }
}
async function loadExposure() {
    try { renderExposure(await radGet('budget')); } catch (error) { $('exp-error').textContent = 'Could not load the exposure (server not reachable?).'; }
}
function loadAll() { return Promise.all([loadEvents(), loadExposure(), loadOutlook()]); }

document.addEventListener('DOMContentLoaded', () => {
    const line = [chip(RAD), document.createTextNode(RAD === 'external' ? ' Data from NOAA, the US space weather service (external).' : ' Data source: simulated demo. Not a measurement.')];
    buildShell('radiation.html', 'Radiation', { hideDeviceStatus: true, sourceLine: line });
    setupDemo();
    setupForms();
    loadAll();
    setInterval(loadEvents, 5000);
    setInterval(loadOutlook, 15000);
    setInterval(loadExposure, 15000);
});
