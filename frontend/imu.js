// Activity metrics from the ICM-20948 (motion sensor). Shared by the Activity and Timeline pages. Needs core.js.
// Everything is calculated from the stored acceleration readings through GET /api/activity (mean distance of the
// acceleration magnitude from 1 g per time block). Nothing is hardcoded or invented; a block without readings counts as
// "no data", never as still or as 0.
//
// Intensity bands for the mean movement of a 5-minute block (APPROXIMATE, a prototype choice):
//   still    below 0.05 g     (the stillness threshold of the rest analysis)
//   light    0.05 to 0.10 g
//   moderate 0.10 to 0.42 g
//   high     0.42 g and above
// The light, moderate and high limits are rounded from published adult wrist-worn ENMO cut-points (Hildebrand et al.
// 2014: about 45, 93 to 101 and 418 to 429 mg; see the GGIR cut-point table). They were derived for other devices, other
// body positions and shorter epochs, so they are an approximation here and are not validated for this sensor.
// Inactivity: an unbroken run of still blocks of at least INACTIVE_MIN minutes while awake (between the end of the
// night's rest and the start of the next one). The 60 minutes is a prototype choice, not a NASA value.

const IMU = { STILL_G: 0.05, MODERATE_G: 0.10, HIGH_G: 0.42, BLOCK_MIN: 5, INACTIVE_MIN: 60 };
const INTENSITY_NAMES = { still: 'Still', light: 'Light', moderate: 'Moderate', high: 'High' };
const INTENSITY_COLORS = { still: '#C9D2DE', light: '#8FD0D6', moderate: '#0E7C86', high: '#0A3F46', none: '#F6F7F9' };
const IMU_SOURCES = {
    cutpoints: ['Hildebrand et al. 2014 ENMO cut-points (GGIR cut-point table)', 'https://cran.r-project.org/web/packages/GGIR/vignettes/CutPoints.html'],
};

function intensityOf(index) {
    if (index === null || index === undefined) return null;
    if (index < IMU.STILL_G) return 'still';
    if (index < IMU.MODERATE_G) return 'light';
    if (index < IMU.HIGH_G) return 'moderate';
    return 'high';
}

const imuCache = {};
async function imuWindows(date, windowMin) {
    const key = `${SOURCE}|${date}|${windowMin}`;
    const hit = imuCache[key];
    const live = date === localToday();
    if (hit && (!live || Date.now() - hit.at < 20000)) return hit.windows;
    const data = await api(`/activity?window_min=${windowMin}&date=${date}`);
    imuCache[key] = { at: Date.now(), windows: data.windows };
    return data.windows;
}

const minutesOf = (w) => Number(w.start.slice(0, 2)) * 60 + Number(w.start.slice(3, 5));

// Totals for one day of 5-minute blocks. `untilMin` stops at the current time for today.
function summarizeDay(windows, windowMin, untilMin = 1440) {
    const out = { still: 0, light: 0, moderate: 0, high: 0, noData: 0, blocks: 0 };
    windows.forEach((w) => {
        if (minutesOf(w) >= untilMin) return;
        out.blocks += 1;
        const level = intensityOf(w.movement_index);
        if (level === null) out.noData += windowMin; else out[level] += windowMin;
    });
    out.active = out.light + out.moderate + out.high;
    out.withData = out.still + out.active;
    return out;
}

// Runs of still blocks inside [fromMin, toMin). Only blocks with data count; a gap ends a run.
function inactivityRuns(windows, windowMin, fromMin, toMin) {
    const runs = [];
    let start = null;
    let last = null;
    const close = () => { if (start !== null) { runs.push({ start, end: last + windowMin, min: last + windowMin - start }); } start = null; };
    windows.forEach((w) => {
        const m = minutesOf(w);
        if (m < fromMin || m >= toMin) { close(); return; }
        if (intensityOf(w.movement_index) === 'still') { if (start === null) start = m; last = m; } else close();
    });
    close();
    return runs.filter((r) => r.min >= IMU.INACTIVE_MIN);
}

const clockOf = (min) => `${String(Math.floor(min / 60) % 24).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`;
const hm = (min) => `${Math.floor(Math.round(min) / 60)} h ${String(Math.round(min) % 60).padStart(2, '0')} min`;
const hmShort = (min) => (min >= 60 ? hm(min) : `${Math.round(min)} min`);

// Awake period of a day from the rest analysis (GET /api/rest): from the end of the night that ends on that day to the
// start of the next rest if that starts the same evening. null when the rest is unknown (no inactivity analysis then).
let restNightsCache = null;
async function restNights() {
    if (restNightsCache && Date.now() - restNightsCache.at < 30000) return restNightsCache.nights;
    try {
        const data = await api('/rest?nights=8');
        restNightsCache = { at: Date.now(), nights: data.per_night };
    } catch (error) { restNightsCache = { at: Date.now(), nights: [] }; }
    return restNightsCache.nights;
}
function timeToMin(text) { return Number(text.slice(0, 2)) * 60 + Number(text.slice(3, 5)); }

async function awakeRange(date) {
    const nights = await restNights();
    const ending = nights.find((n) => n.date === date && n.status === 'ok');
    if (!ending) return null;
    const from = timeToMin(ending.rest_end);
    let to = 1440;
    const next = nights.find((n) => n.status === 'ok' && n.date > date && n.date <= nextDate(date));
    if (next && timeToMin(next.rest_start) >= 18 * 60) to = timeToMin(next.rest_start);
    return { from, to };
}
function nextDate(date) {
    const d = new Date(`${date}T12:00:00`);
    d.setDate(d.getDate() + 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function nowMinutes() { const d = new Date(); return d.getHours() * 60 + d.getMinutes(); }
