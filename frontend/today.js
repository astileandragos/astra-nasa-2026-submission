// Activity page: "Activity today" (from the ICM-20948) and "Today's recommendations". Needs core.js, imu.js, rest.js.
// Metrics come from the stored acceleration readings (see imu.js). Recommendations adapt to today's activity, the recent
// rest and the time of day, and say when there are not enough data. Each recommendation is tagged:
//   NASA GUIDANCE    = something a NASA document says (sources listed under the recommendations);
//   ADAPTED FROM NASA = a NASA fact turned into an everyday example; the card says what is NASA's and what is ASTRA's;
//   ASTRA SUGGESTION = a prototype idea of the team, not a NASA procedure.
// The ISS exercise schedule is context only: NASA individualizes plans, so it is not a prescription for anyone.

const TODAY_SOURCES = [
    ['NASA Evidence Report: Risk of Cardiac Rhythm Problems during Spaceflight', 'https://humanresearchroadmap.nasa.gov/evidence/other/Arrhythmia.pdf'],
    ['NASA OCHMO TB-031: Exercise (NASA-STD-3001 Vol 1 Rev C)', 'https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-031-exercise-overview.pdf'],
    ['NASA Evidence Report: Risk of Reduced Physical Performance Capabilities', 'https://humanresearchroadmap.nasa.gov/evidence/reports/Aerobic.pdf'],
    ['NASA: Seven ways astronauts improve sleep', 'https://www.nasa.gov/missions/station/seven-ways-astronauts-improve-sleep-may-help-you-snooze-better-on-earth/'],
];
const MIN_DATA_MIN = 120;           // at least 2 hours of motion data before any activity message

function rec(title, text, tag, basis) { return { title, text, tag, basis }; }

function recCard(r) {
    const box = el('div', 'guide');
    const top = el('div', 'chip-row');
    top.append(el('span', `chip ${r.tag === 'nasa' || r.tag === 'adapted' ? 'chip-external' : 'chip-plain'}`, r.tag === 'nasa' ? 'NASA GUIDANCE' : r.tag === 'adapted' ? 'ADAPTED FROM NASA' : 'ASTRA SUGGESTION'));
    box.append(el('span', 'guide-title', r.title), top, el('p', '', r.text));
    if (r.basis) box.append(el('p', 'note', r.basis));
    return box;
}

function intensityLegend(box, withRanges) {
    const ranges = { still: `below ${IMU.STILL_G} g`, light: `${IMU.STILL_G} to ${IMU.MODERATE_G} g`, moderate: `${IMU.MODERATE_G} to ${IMU.HIGH_G} g`, high: `${IMU.HIGH_G} g and above` };
    box.replaceChildren();
    ['still', 'light', 'moderate', 'high'].forEach((k) => {
        const item = el('span', 'legend-item');
        const sw = el('span', 'swatch');
        sw.style.background = INTENSITY_COLORS[k];
        item.append(sw, document.createTextNode(`${INTENSITY_NAMES[k]}${withRanges ? ` (${ranges[k]})` : ''}`));
        box.append(item);
    });
    const none = el('span', 'legend-item');
    const sw = el('span', 'swatch band-none');
    sw.style.background = INTENSITY_COLORS.none;
    none.append(sw, document.createTextNode('No data'));
    box.append(none);
}

function tileOf(label, value, sub) {
    const box = el('div', 'tile');
    box.append(el('span', 'label', label), el('div', 'tile-value', value), el('span', 'note', sub || ''));
    return box;
}

let todayState = null;

async function loadToday() {
    $('today-chip').replaceChildren(chip(SOURCE));
    try {
        const today = localToday();
        const nowMin = nowMinutes();
        const windows = await imuWindows(today, IMU.BLOCK_MIN);
        const m = summarizeDay(windows, IMU.BLOCK_MIN, nowMin + IMU.BLOCK_MIN);
        const enough = m.withData >= MIN_DATA_MIN;
        const awake = await awakeRange(today);
        let runs = [];
        let current = 0;
        if (awake) {
            const to = Math.min(awake.to, nowMin + IMU.BLOCK_MIN);
            runs = inactivityRuns(windows, IMU.BLOCK_MIN, awake.from, to);
            const last = runs[runs.length - 1];
            if (last && last.end >= nowMin - IMU.BLOCK_MIN) current = last.min;      // the run reaches the present
        }
        todayState = { m, enough, awake, runs, current, nowMin };
        if (!enough) {
            $('today-tiles').replaceChildren(tileOf('Active time', '--', 'not enough data yet'), tileOf('Light', '--', ''), tileOf('Moderate', '--', ''), tileOf('High', '--', ''));
            $('today-still').textContent = `Not enough motion data today (${hmShort(m.withData)} so far; ${hm(MIN_DATA_MIN)} are needed). Wear the device so activity can be tracked.`;
        } else {
            $('today-tiles').replaceChildren(
                tileOf('Active time', hm(m.active), `${Math.round((m.active / m.withData) * 100)}% of the time with data`),
                tileOf('Light', hmShort(m.light), 'movement above the stillness limit'),
                tileOf('Moderate', hmShort(m.moderate), ''),
                tileOf('High', hmShort(m.high), ''));
            if (!awake) {
                $('today-still').textContent = 'Still periods can be shown once last night\'s rest has been found (it needs enough motion data for the night).';
            } else if (!runs.length) {
                $('today-still').textContent = `No still period of ${IMU.INACTIVE_MIN} minutes or more while awake since ${clockOf(awake.from)}.`;
            } else {
                const longest = runs.reduce((a, b) => (b.min > a.min ? b : a));
                $('today-still').textContent = `Still periods of ${IMU.INACTIVE_MIN} minutes or more while awake: ${runs.length}. Longest ${hm(longest.min)} (${clockOf(longest.start)} to ${clockOf(longest.end)}).${current ? ` You have been still for ${hm(current)} now.` : ''}`;
            }
        }
        $('today-basis').textContent = `From ${hmShort(m.withData)} of ICM-20948 motion data today${m.noData ? `; ${hmShort(m.noData)} without readings are not counted` : ''}. Intensity is approximate: bands rounded from published adult wrist accelerometer cut-points, not validated for this sensor.`;
        intensityLegend($('today-legend'), true);
        $('today-error').textContent = '';
    } catch (error) {
        $('today-error').textContent = 'Could not load today\'s activity (server not reachable?).';
        todayState = null;
    }
    loadRecs();
}

async function usualActive() {
    const days = lastDays(7).slice(1);                               // yesterday first
    const sums = await Promise.all(days.map(async (d) => ({ date: d, m: summarizeDay(await imuWindows(d, IMU.BLOCK_MIN), IMU.BLOCK_MIN) })));
    const usable = sums.filter((s) => s.m.withData >= 6 * 60);
    return { yesterday: usable.find((s) => s.date === days[0]) || null, earlier: usable.filter((s) => s.date !== days[0]) };
}

async function loadRecs() {
    const list = [];
    try {
        const st = todayState;
        const [rest, obs, usual] = await Promise.all([api('/rest?nights=8'), api(`/observation?date=${localToday()}`).catch(() => ({ observations: [] })), usualActive()]);
        const last = rest.per_night[rest.per_night.length - 1];
        const restOk = last && last.status === 'ok';
        const restObs = obs.observations.find((o) => o.id === 'rest_start_vs_usual');
        const hard = (s) => s.m.moderate + s.m.high;

        // 1. exercise. What the sensor saw today against the person's own plan (ASTRA does not know the plan).
        if (st && st.enough) {
            const hardToday = st.m.moderate + st.m.high;
            if (hardToday === 0 && st.nowMin >= 12 * 60 && st.nowMin < 21 * 60) {
                list.push(rec('No exercise seen yet today', 'The motion sensor has not seen any real exercise today, only light movement. If exercise is on your plan, do it before your evening wind-down. Strength exercises can look small to a motion sensor, so check against your plan.', 'astra',
                    `Today so far: ${hmShort(st.m.active)} of movement, all of it light.`));
            } else if (hardToday > 0) {
                list.push(rec('Exercise seen today', `The sensor saw ${hmShort(hardToday)} of brisk or hard movement today. Compare it with your plan and do what is still left on it.`, 'astra', `${hmShort(st.m.moderate)} brisk, ${hmShort(st.m.high)} hard.`));
            }
        }
        list.push(rec('Your exercise plan comes first', 'ISS astronauts are given about 2.5 hours a day, 6 days a week, for exercise, and NASA exercise specialists make each plan personal. Use the plan you were given. This is only for context.', 'nasa', 'ASTRA only shows what the sensor saw. It does not give you a plan.'));

        // exercise examples taken from NASA's Evidence Report "Risk of Cardiac Rhythm Problems during Spaceflight", section "Exercise"
        list.push(rec('Example: a 20-minute easy-to-brisk session',
            'Rest sitting for 5 minutes. Then 5 minutes very easy (you could sing), 5 minutes steady (you can talk in full sentences) and 5 minutes brisk (you can say only a few words at a time). Stop earlier if you feel unwell.',
            'adapted', 'From NASA: early ISS astronauts did a monthly test of 5 minutes of rest and then three 5-minute steps at 25%, 50% and 75% of their maximum fitness. The "how it feels" words are ASTRA\'s. NASA used this as a fitness test, not as a workout.'));
        list.push(rec('Example: mix hard and easy efforts',
            'If you are healthy and used to exercise, you can alternate short hard efforts with easy ones, for example 1 minute hard and 2 minutes easy, repeated 4 to 6 times, with an easy warm-up and cool-down.',
            'adapted', 'From NASA: astronauts on the Shuttle, Mir and ISS have been prescribed interval exercise, with near-maximal efforts alternating with easy ones. The 1 and 2 minutes and the repeats are ASTRA\'s example, not a NASA prescription.'));
        list.push(rec('Do not go to your maximum on your own',
            'Keep your own tests and hard efforts at about 85% of your hardest possible effort or below. Stop and rest if you get chest pain or pressure, a pounding or uneven heartbeat, dizziness or trouble breathing, and tell someone.',
            'adapted', 'From NASA: it has limited exercise tests for medical and research purposes to 85% of pre-flight maximum, because of concern about heart rhythm changes at high effort, except in carefully controlled cases.'));
        list.push(rec('Wear the sensor when you exercise',
            'Keep the device on during exercise and write the session in your check-in. Your heart rate record can then be compared with your usual.',
            'nasa', 'From NASA: ISS astronauts are encouraged to wear heart rate sensors to watch exercise intensity and to log their sessions. A heart rate record can only hint at a rhythm problem; an ECG is needed to confirm one.'));
        const quiet = st && st.enough && (st.m.moderate + st.m.high) === 0;
        if (quiet || (usual.yesterday && usual.earlier.length >= 3 && hard(usual.yesterday) === 0)) {
            list.push(rec('Start slowly after a quiet period',
                'After days with little exercise, start easy and build up over several days. Do not go straight to hard efforts.',
                'adapted', 'From NASA: astronauts follow a reconditioning program, typically during the first 45 days after landing, and long-duration crews begin with gentle (submaximal) exercise.'));
        }

        // 2. movement breaks
        if (st && st.awake && st.current >= IMU.INACTIVE_MIN) {
            list.push(rec('Take a movement break', `You have been still for ${hm(st.current)}. Stand up, walk around and stretch for a few minutes before you continue.`, 'astra', `A still stretch of ${IMU.INACTIVE_MIN} minutes or more is ASTRA's own trigger.`));
        } else if (st && st.enough && st.runs.length) {
            const longest = st.runs.reduce((a, b) => (b.min > a.min ? b : a));
            list.push(rec('Plan short movement breaks', `Today you sat or lay still for an hour or more ${st.runs.length} time${st.runs.length > 1 ? 's' : ''} (longest ${hm(longest.min)}). Add a short movement break to long tasks.`, 'astra', null));
        }

        // 3. recovery
        const reasons = [];
        if (usual.yesterday && usual.earlier.length >= 3) {
            const avg = usual.earlier.reduce((a, s) => a + hard(s), 0) / usual.earlier.length;
            if (avg > 0 && hard(usual.yesterday) > 1.6 * avg) reasons.push(`yesterday you had ${hmShort(hard(usual.yesterday))} of moderate or high movement, against about ${hmShort(avg)} on your earlier days`);
        }
        if (restObs && restObs.level === 'notable') reasons.push(`last night's rest started at ${restObs.based_on.last_night}, ${Math.abs(Math.round(restObs.based_on.difference_min))} minutes ${restObs.based_on.difference_min > 0 ? 'later' : 'earlier'} than usual`);
        if (reasons.length) {
            list.push(rec('Recovery', `${reasons.join(', and ')[0].toUpperCase()}${reasons.join(', and ').slice(1)}. Keep today's effort easier where your plan allows, and protect tonight's sleep period.`, 'astra', null));
        }

        // 4. sleep schedule
        const u = rest.usual;
        if (u) {
            const startMin = timeToMin(u.start_median);
            const toStart = ((startMin - nowMinutes()) + 1440) % 1440;
            if (toStart <= 90) {
                list.push(rec('Wind down for your usual rest', `Your usual rest starts around ${u.start_median}. Dim bright light, avoid hard exercise now and get the sleeping area ready: dark, quiet, comfortable.`, 'nasa', 'NASA lists a fixed sleep schedule, light control, the sleep environment and well-timed exercise as countermeasures.'));
            } else {
                list.push(rec('Keep a consistent sleep schedule', `Your usual rest runs from about ${u.start_median} to ${u.end_median} (${u.nights_used} earlier nights). Keep your sleep and wake times close to these.`, 'nasa', 'A fixed sleep and wake time supports the internal body clock.'));
            }
        } else {
            list.push(rec('Keep a consistent sleep schedule', 'ASTRA learns your usual rest times after 3 nights with enough motion data. Until then, keep fixed sleep and wake times.', 'nasa', restOk ? null : 'Last night has too little motion data to find a rest period.'));
        }

        // data gaps
        if (st && !st.enough) list.push(rec('Wear the device', `Only ${hmShort(st.m.withData)} of motion data so far today. Wear it so activity, still periods and rest can be tracked.`, 'astra', null));

        $('recs-list').replaceChildren(...list.map(recCard));
        $('recs-basis').textContent = `Adapted to today's motion data${restOk ? `, last night's rest (${last.duration_h} h, ${last.rest_start} to ${last.rest_end})` : ', with last night\'s rest unknown'} and the time of day.`;
        const src = $('recs-sources');
        src.replaceChildren(document.createTextNode('Sources: '));
        TODAY_SOURCES.forEach(([label, url], i) => {
            const a = el('a', '', label);
            a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer';
            if (i) src.append(document.createTextNode(' · '));
            src.append(a);
        });
        $('recs-error').textContent = '';
    } catch (error) {
        $('recs-error').textContent = 'Could not build the recommendations (server not reachable?).';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadToday();
    setInterval(loadToday, 30000);
});
