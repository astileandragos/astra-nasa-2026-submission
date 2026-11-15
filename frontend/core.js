// ASTRA dashboard core: shared by every page.
// - the dashboard has ONE combined view (SOURCE = dashboard): earlier days are the pre-recorded SIMULATED baseline week,
//   today comes from the LIVE sensor (or the simulator when no live reading arrived). There is no source switch.
// - builds the top bar, the connection pill, the status strip and the page header
// - shared components: source chip, day strip (unified timeline)
// Text from the API is always written with textContent, never innerHTML.

const API = '/api';
const SOURCE = 'dashboard';

const SOURCE_NAMES = {
    live_hardware: 'LIVE', simulated: 'SIMULATED', self_reported: 'SELF-REPORTED', external: 'EXTERNAL', dashboard: 'BASELINE + TODAY',
};
const NAV = [
    ['index.html', 'Overview'], ['timeline.html', 'Timeline'], ['radiation.html', 'Radiation'], ['activity.html', 'Activity'],
    ['journal.html', 'Journal'], ['sensors.html', 'Sensors'],
];
const STATUS_REFRESH_MS = 2000;
const STALE_AFTER_S = 10;           // five readings at the suggested 2 s interval

// ---- small helpers ----
function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}
const $ = (id) => document.getElementById(id);
const show = (value, unit = '') => (value === null || value === undefined ? '--' : `${value}${unit}`);

async function api(path, withSource = true) {
    const url = withSource ? `${API}${path}${path.includes('?') ? '&' : '?'}source=${SOURCE}` : `${API}${path}`;
    const response = await fetch(url);
    if (!response.ok) {
        const error = new Error(`HTTP ${response.status}`);
        error.status = response.status;
        throw error;
    }
    return response.json();
}

function clock(iso) {
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? '--' : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
function formatAge(seconds) {
    if (seconds < 60) return `${Math.round(seconds)} s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
    return `${(seconds / 3600).toFixed(1)} h`;
}
function shortDate(isoDate) {
    const d = new Date(`${isoDate}T12:00:00`);
    return d.toLocaleDateString([], { weekday: 'short', day: 'numeric' });
}
function localToday() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// ---- source chip: always text plus a shape, never color alone ----
function chip(source) {
    if (source === 'dashboard') return demoChips();
    return el('span', `chip chip-${source}`, SOURCE_NAMES[source] || source.toUpperCase());
}

// What the combined view is made of. Filled from /api/demo/status; every pair of chips on the page updates when it arrives.
const DEMO = { today_source: 'simulated', baseline_days: null, today_readings: null };
const demoViews = [];
function demoChips() {
    const wrap = el('span', 'chip-pair');
    const fill = () => {
        const live = DEMO.today_source === 'live_hardware';
        wrap.replaceChildren(el('span', 'chip chip-simulated', 'BASELINE: SIMULATED WEEK'),
            el('span', `chip chip-${DEMO.today_source}`, live ? 'TODAY: LIVE SENSOR' : 'TODAY: SIMULATOR'));
    };
    fill();
    demoViews.push(fill);
    return wrap;
}
async function loadDemo() {
    try { Object.assign(DEMO, await api('/demo/status', false)); } catch (error) { /* offline: keep the defaults */ }
    demoViews.forEach((fill) => fill());
}


// ---- one radiation status vocabulary for every page (Overview, Timeline, Radiation) ----
// NOAA's S-scale (S1 to S5) rates a solar storm. It is not the astronaut's dose. The "what to do" texts are
// example messages, not NASA flight rules; ASTRA cannot allow or cancel a spacewalk.
const RAD_STATE_TEXT = {
    normal: { title: 'NORMAL', badge: 'normal', mark: '●', summary: 'The Sun is quiet. Radiation from solar storms is at its usual low level.',
              todo: 'Nothing to do. Carry on with your planned work.' },
    elevated: { title: 'ELEVATED', badge: 'elevated', mark: '▲', summary: 'A small solar storm has started. Radiation is a little above normal.',
                todo: 'Stay alert. Check this page again and listen to mission control.' },
    high: { title: 'HIGH', badge: 'high', mark: '▲', summary: 'A strong solar storm. Radiation is high.',
            todo: 'Get ready to go to the radiation shelter and follow mission control.' },
    severe: { title: 'SEVERE', badge: 'severe', mark: '◆', summary: 'A very strong solar storm. Radiation is very high.',
              todo: "Go to the radiation shelter now and follow the mission's emergency plan." },
    unknown: { title: 'DATA UNAVAILABLE', badge: 'unknown', mark: '?', summary: 'There is no radiation data right now, so we do not know the situation.',
               todo: 'Do not assume everything is fine. Check the connection and listen to mission control.' },
};

// s = answer of GET /api/radiation/status. Never NORMAL when there is no current data.
function radState(s) {
    if (!s || !s.state || s.data_status === 'no_data') return { key: 'unknown', current: false, ...RAD_STATE_TEXT.unknown };
    const level = s.state.level;
    const current = s.data_status === 'ok' || s.data_status === 'delayed';
    if (level === 0 && !current) return { key: 'unknown', current: false, ...RAD_STATE_TEXT.unknown };
    const key = ['normal', 'elevated', 'high', 'severe'][level];
    return { key, current, ...RAD_STATE_TEXT[key] };
}

function stateBadge(key) {
    const t = RAD_STATE_TEXT[key];
    const badge = el('span', `badge badge-${t.badge}`);
    const mark = el('span', 'badge-mark', t.mark);
    mark.setAttribute('aria-hidden', 'true');
    badge.append(mark, document.createTextNode(` ${t.title}`));
    return badge;
}

// ---- shell ----
function buildShell(page, title, options = {}) {
    document.title = `${title} · ASTRA`;
    const skip = el('a', 'skip-link', 'Skip to content');
    skip.href = '#main';

    const bar = el('header', 'topbar');
    const inner = el('div', 'topbar-inner');
    const brand = el('a', 'brand');
    brand.href = `index.html?source=${SOURCE}`;
    brand.setAttribute('aria-label', 'ASTRA, overview');
    const mark = el('span', 'brand-mark');
    mark.setAttribute('aria-hidden', 'true');
    brand.append(mark, el('span', 'brand-name', 'ASTRA'));

    const nav = el('nav', 'nav');
    nav.setAttribute('aria-label', 'Main');
    NAV.forEach(([file, label]) => {
        const link = el('a', '', label);
        link.href = `${file}?source=${SOURCE}`;
        if (file === page) link.setAttribute('aria-current', 'page');
        nav.append(link);
    });

    const tools = el('div', 'topbar-tools');
    const deviceStatus = !options.hideDeviceStatus;
    const pill = el('span', 'pill', 'Connecting');
    pill.id = 'conn-pill';
    if (deviceStatus) tools.append(pill);

    inner.append(brand, nav, tools);
    bar.append(inner);
    document.body.prepend(skip, bar);

    const main = $('main');
    const banner = el('div', 'banner');
    banner.id = 'status-banner';
    banner.setAttribute('role', 'status');
    banner.setAttribute('aria-live', 'polite');
    const head = el('header', 'page-head');
    head.append(el('h1', '', title));
    const line = el('p', `source-line source-line-${SOURCE}`);
    const sourceText = ' The earlier days are a pre-recorded simulated week, not real measurements. Today comes from the sensor.';
    if (options.sourceLine) line.append(...options.sourceLine); else line.append(chip(SOURCE), document.createTextNode(sourceText));
    head.append(line);
    main.prepend(banner, head);
    const foot = el('p', 'page-foot', 'ASTRA is an educational prototype, not a medical device. Mission procedures and medical staff are authoritative.');
    main.append(foot);

    if (window.Chart) {
        Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
        Chart.defaults.color = '#44546A';
        Chart.defaults.borderColor = '#E3E7EC';
        Chart.defaults.animation = false;
    }
    loadDemo();
    if (deviceStatus) startStatus();
    showPageNotices(head);
}

// ---- connection status (pill + strip) ----
function setConnection(level, pillText, bannerText) {
    const pill = $('conn-pill');
    pill.className = `pill pill-${level}`;
    pill.textContent = pillText;
    const banner = $('status-banner');
    banner.className = bannerText ? `banner banner-${level}` : 'banner';
    banner.textContent = bannerText || '';
}

async function refreshStatus() {
    let detail = { offline: true, stale: true, total: 0 };
    try {
        const s = await api(`/status?stale_after=${STALE_AFTER_S}`);
        detail = s;
        if (s.total === 0) {
            setConnection('info', 'No readings yet', 'No readings yet. Start the sensor or the simulator.');
        } else if (s.stale) {
            setConnection('warn', `No new readings · ${formatAge(s.seconds_since_last)}`,
                `No new readings for ${formatAge(s.seconds_since_last)} (last reading at ${clock(s.last_received_at)}). The values shown are not current.`);
        } else {
            const gap = s.median_interval_seconds === null ? '' : ` · every ~${s.median_interval_seconds} s`;
            setConnection('ok', `Receiving · ${clock(s.last_received_at)}${gap}`, '');
        }
    } catch (error) {
        setConnection('error', 'Server offline', 'Server not reachable. The values shown are not current.');
    }
    document.body.classList.toggle('not-current', Boolean(detail.stale));
    document.dispatchEvent(new CustomEvent('astra-status', { detail }));
}

function startStatus() {
    refreshStatus();
    setInterval(refreshStatus, STATUS_REFRESH_MS);
}

// ---- notifications and advice (contract 6.14) ----
const LEVEL_TEXT = { ok: 'OK', warning: 'Warning', danger: 'Action needed', suggestion: 'Suggestion' };
const LEVEL_MARK = { ok: '●', warning: '▲', danger: '◆', suggestion: '○' };   // shape + text, never color alone

function noticeHref(item) {
    return `${item.page}?source=${SOURCE}&from=${encodeURIComponent(item.id)}`;
}

function levelBadge(level) {
    const badge = el('span', `badge badge-${level}`);
    badge.append(el('span', 'badge-mark', LEVEL_MARK[level]), document.createTextNode(` ${LEVEL_TEXT[level]}`));
    badge.firstChild.setAttribute('aria-hidden', 'true');
    return badge;
}

// Every measurement page shows the notifications that belong to it, all the time (not only after a click on the
// Overview): status, what it means and step-by-step advice. Suggestions for the page are listed too. The page
// refreshes them every 5 seconds. The Overview itself lists everything, so it shows none here.
const PAGE_FILE = window.location.pathname.split('/').pop() || 'index.html';

function adviceBlock(item, level) {
    const box = el('article', `pn-item advice-${level}`);
    const top = el('div', 'panel-head');
    top.append(el('h3', 'pn-title', item.title), levelBadge(level));
    box.append(top);
    // warnings come with specific, sourced guidance (advice.js) when it has some for this item
    const rich = level !== 'suggestion' && window.richAdvice ? window.richAdvice(item, level) : null;
    if (rich) { box.append(window.richBody(rich)); return box; }
    if (item.message || item.text) box.append(el('p', 'pn-message', item.message || item.text));
    box.append(el('p', 'note', item.advice.meaning));
    if (item.advice.steps.length) {
        box.append(el('span', 'label', 'What to do'));
        const list = el('ol', 'steps');
        item.advice.steps.forEach((text) => list.append(el('li', '', text)));
        box.append(list);
    } else {
        box.append(el('p', 'note', 'No action needed.'));
    }
    return box;
}

function showPageNotices(head) {
    if (PAGE_FILE === 'index.html' || PAGE_FILE === 'radiation.html') return;      // the Radiation page shows its own notifications in its status panel
    const fromId = new URLSearchParams(window.location.search).get('from');
    const section = el('section', 'panel pn');
    section.setAttribute('aria-labelledby', 'pn-h');
    section.hidden = true;
    head.after(section);

    async function refresh() {
        try {
            const data = await api('/notifications');
            const own = data.notifications.filter((n) => n.page === PAGE_FILE);
            const sugg = data.suggestions.filter((s) => s.page === PAGE_FILE);
            document.querySelectorAll('.is-target').forEach((node) => node.classList.remove('is-target'));
            const children = [];
            const top = el('div', 'panel-head');
            const title = el('h2', 'label', 'Notifications and advice for this page');
            title.id = 'pn-h';
            top.append(title);
            children.push(top);
            own.forEach((n) => {
                children.push(adviceBlock(n, n.level));
                const box = n.level !== 'ok' && $(n.target) ? $(n.target).closest('.panel') : null;
                if (box) box.classList.add('is-target');
            });
            sugg.forEach((s) => children.push(adviceBlock(s, 'suggestion')));
            if (fromId && ![...own, ...sugg].some((x) => x.id === fromId)) {
                children.push(el('p', 'note', 'The item you opened is no longer active: the situation it described has changed.'));
            }
            if (own.length + sugg.length === 0 && !fromId) { section.hidden = true; return; }
            section.replaceChildren(...children);
            section.hidden = false;
        } catch (error) {
            section.hidden = true;     // a connection problem is already shown by the status pill and banner
        }
    }
    refresh();
    setInterval(refresh, 5000);
}
