// Detailed, specific guidance for the Timeline warnings and the "Events and what to do" panel.
// Needs core.js. All text is written with textContent. Nothing here changes the backend or the rules that raise a warning;
// it only explains a warning that the existing rules already raised, using the real numbers behind it (GET /api/observation).
//
// Two kinds of statements are kept apart and labelled on screen:
//   NASA GUIDANCE   = something NASA documents say (source linked below the text).
//   ASTRA SUGGESTION = a prototype idea of this team, NOT a NASA procedure and NOT medical advice.
// NASA publishes no heart rate, SpO2 or movement thresholds for crew alerts, so none are invented here: the limits
// that raise a warning are each person's own baseline and day-to-day variation. ASTRA is not a medical diagnostic system.
//
// Research used (read on 14 Nov 2026):
//  - NASA HRP Evidence Report "Risk of Cardiac Rhythm Problems during Spaceflight": evidence is mostly case reports;
//    arrhythmias were seen at rest, during exercise and during EVA; heart rhythm is not ECG-monitored during routine
//    exercise; ISS astronauts are encouraged to wear heart rate sensors to monitor exercise intensity and log sessions;
//    heart rate logs can only screen, confirming an arrhythmia needs an ECG.
//  - NASA OCHMO TB-031 (NASA-STD-3001 Vol 1 Rev C): in-mission aerobic capacity kept at or above 80% of pre-mission
//    [V1 4003]; ISS treadmill aerobic training was prescribed at 70 to 100% of maximum heart rate and cycle training at
//    70 to 100% of VO2peak (measured treadmill average 131 bpm, peak 162 bpm).
//  - NASA "Seven ways astronauts improve sleep": scheduled sleep and wake times, light, sleep environment (privacy,
//    temperature, airflow, noise, CO2), well-timed exercise, medication only after non-drug options.
//  - NASA OCHMO TB-044 Medical Operations: flight surgeons support the crew's medical care; private medical conferences.

const ADVICE_SOURCES = {
    rhythm: ['NASA Evidence Report: Risk of Cardiac Rhythm Problems during Spaceflight', 'https://humanresearchroadmap.nasa.gov/evidence/other/Arrhythmia.pdf'],
    exercise: ['NASA OCHMO TB-031: Exercise (NASA-STD-3001 Vol 1 Rev C)', 'https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-031-exercise-overview.pdf'],
    sleep: ['NASA: Seven ways astronauts improve sleep', 'https://www.nasa.gov/missions/station/seven-ways-astronauts-improve-sleep-may-help-you-snooze-better-on-earth/'],
    medops: ['NASA OCHMO TB-044: Medical Operations', 'https://www.nasa.gov/wp-content/uploads/2025/08/ochmo-tb-044-medical-operations.pdf'],
};
const NASA = 'nasa';
const ASTRA = 'astra';
// Three levels of care for a crew far from Earth: treat yourself, tell the crew medical officer, emergency.
// A message to Earth can take many minutes each way on a long mission, so an emergency is handled on board first.
const SELF_CARE = 'Start with the steps above. Small changes usually settle with rest and water.';
const TELL_CMO = 'Tell your crew medical officer or a crew mate';
const EMERGENCY = 'Emergency: call your crew for help now and follow your onboard emergency procedures. Contact mission control at the same time, and do not wait for their reply.';

let adviceObs = {};
async function refreshAdviceObs() {
    try {
        const data = await api(`/observation?date=${localToday()}`);
        adviceObs = Object.fromEntries(data.observations.map((o) => [o.id, o]));
    } catch (error) { adviceObs = {}; }
}

// ---- builders: one per kind of warning. They return null when there is nothing better than the default text. ----
function heartRateAdvice(item, level) {
    const o = adviceObs.hr_vs_baseline;
    const b = o ? o.based_on : null;
    const higher = b ? b.difference > 0 : /higher/i.test(item.title);
    const diff = b ? Math.abs(b.difference) : null;
    const urgent = level === 'danger';
    const numbers = b ? `Your average heart rate today is ${b.today_median} beats per minute (bpm). Your usual is ${b.baseline_median} bpm. That is ${diff} bpm ${higher ? 'higher' : 'lower'}, and your heart rate normally changes only about ±${b.limit} bpm from day to day.`
        : item.message;
    if (higher) {
        return {
            what: numbers,
            why: ['A higher heart rate can come from exercise, a short night, stress, coffee or too little water. It can also be a bad reading from the sensor.',
                  'ASTRA only counts your pulse at the fingertip. It cannot see your heart rhythm. NASA\'s research report says there is little proof that spaceflight raises the risk of serious heart rhythm problems, and that what is known comes mostly from single cases. It also says a heart rate record can only give a hint: a heart tracing (ECG) is needed to be sure.'],
            steps: [
                [urgent ? 'Stop what you are doing. Sit down or secure yourself, drink a glass of water and rest quietly for 10 minutes.' : 'Sit down, drink a glass of water and rest quietly for 10 minutes.', ASTRA],
                ['Then measure again: finger flat on the sensor, hand still, wait for a steady signal. Measure once more an hour later.', ASTRA],
                ['For the next hour, avoid coffee, hard exercise and stressful tasks.', ASTRA],
                ['Keep wearing the sensor during exercise and log your sessions. NASA encourages ISS astronauts to do this so the heart rate record can be reviewed later.', NASA],
            ],
            seekTitle: 'When to ask for help',
            seek: [
                SELF_CARE,
                `${TELL_CMO} if your heart rate is still higher than usual after resting and measuring twice, or on two days in a row. NASA notes that people can be slow to report symptoms, so do not wait.`,
                `${EMERGENCY} Warning signs: chest pain or pressure, a pounding or uneven heartbeat, fainting or nearly fainting, dizziness, trouble breathing while resting.`,
                urgent ? 'The difference is large, so tell a crew mate what is happening, even if you feel fine.' : 'If you feel fine and it settles with rest, there is nothing more to do.',
            ],
            sources: ['rhythm', 'exercise', 'medops'],
        };
    }
    return {
        what: numbers,
        why: ['A lower heart rate can simply mean good rest or the effect of regular exercise. It matters when it comes with dizziness, a faint feeling or unusual tiredness. ASTRA cannot tell which one it is.',
              'NASA notes that heart rhythm is not checked by ECG during normal exercise, so a pulse from a fingertip is only a hint. It cannot confirm or rule out a rhythm problem.'],
        steps: [
            ['Sit down and drink a glass of water. If you feel light-headed, secure yourself and stay seated until it passes.', ASTRA],
            ['Stand up slowly. Do not rush.', ASTRA],
            ['Measure again with the finger flat and the hand still. A poor contact can read low.', ASTRA],
        ],
        seekTitle: 'When to ask for help',
        seek: [SELF_CARE,
               `${TELL_CMO} if it stays low after resting and measuring twice.`,
               `${EMERGENCY} Warning signs: dizziness or fainting, weakness, chest pain, trouble breathing.`],
        sources: ['rhythm', 'medops'],
    };
}

function spo2Advice(item) {
    const o = adviceObs.spo2_vs_baseline;
    const b = o ? o.based_on : null;
    const lower = b ? b.difference < 0 : /lower/i.test(item.title);
    return {
        what: b ? `Your blood oxygen estimate (SpO2) today is ${b.today_median}%. Your usual is ${b.baseline_median}%. That is ${Math.abs(b.difference)} points ${lower ? 'lower' : 'higher'}.` : item.message,
        why: ['A finger sensor can read low when the hand is cold, moving or badly placed. So ASTRA first asks you to measure again.',
              'This is an estimate from a low-cost sensor. It is not a medical measurement, and NASA gives no alert numbers that ASTRA could use.'],
        steps: lower ? [
            ['Sit upright, breathe slowly and deeply, and warm your hand. Cold fingers give low numbers.', ASTRA],
            ['After 5 minutes, put your finger flat on the sensor and measure once more.', ASTRA],
            ['If the signal is poor, ignore the number. The Sensors page shows the signal.', ASTRA],
        ] : [
            ['Measure again with the finger flat and the hand still. A reading higher than usual is not a problem by itself.', ASTRA],
        ],
        seekTitle: 'When to ask for help',
        seek: [SELF_CARE,
               `${TELL_CMO} if the number stays low after resting and measuring twice.`,
               `${EMERGENCY} Warning signs: shortness of breath, dizziness, confusion, a headache that will not go away.`],
        sources: ['medops'],
    };
}

function inactivityAdvice(item) {
    return {
        what: item.message,
        why: ['Sitting or lying still for a long time is not good for the body. It can also mean the device is lying on a table and not on you.',
              'Astronauts exercise almost every day because muscles and bones weaken without movement. ISS crews are given about 2.5 hours a day, 6 days a week, for this.'],
        steps: [
            ['Stand up. Walk around or stretch for 3 to 5 minutes.', ASTRA],
            ['Check that you are wearing the device. If it is on a table, put it back on.', ASTRA],
            ['Do your planned exercise. NASA exercise specialists make each astronaut\'s plan personal, so follow yours.', NASA],
            ['During long tasks, stand up for a minute about once an hour.', ASTRA],
        ],
        seekTitle: 'When to ask for help',
        seek: ['If you cannot move because you feel unwell, tell your crew medical officer or a crew mate.'],
        sources: ['exercise'],
    };
}

function restAdvice(item) {
    const o = adviceObs.rest_start_vs_usual;
    const b = o ? o.based_on : null;
    const later = b ? (b.difference_min > 0) : /later/i.test(item.message);
    return {
        what: b ? `Last night your rest started at ${b.last_night}. That is ${Math.abs(Math.round(b.difference_min))} minutes ${later ? 'later' : 'earlier'} than your usual ${b.usual}. ASTRA works this out from movement only.` : item.message,
        why: ['Going to rest at the same time every day keeps your body clock steady. In space, odd light and dark cycles, noise and a busy schedule all disturb it. NASA lists a fixed sleep schedule as the first thing that helps.'],
        steps: [
            [`Go to rest around ${b ? b.usual : 'your usual time'} tonight and get up at the same time tomorrow.`, NASA],
            ['Dim bright lights in the hour before rest.', NASA],
            ['Make the sleeping area dark, quiet and comfortable. Check the temperature, air flow and noise.', NASA],
            ['Do hard exercise earlier in the day, not right before rest.', NASA],
        ],
        seekTitle: 'When to ask for help',
        seek: ['If your rest stays off schedule for several nights, report it so the schedule can be reviewed.',
               'If tiredness could affect a safety-critical task, tell the crew before you do it.'],
        sources: ['sleep'],
    };
}

function restLengthAdvice(item) {
    const o = adviceObs.rest_length_vs_usual;
    const b = o ? o.based_on : null;
    const short = b ? b.difference_min < 0 : /shorter/i.test(item.title);
    return {
        what: b ? `Last night's rest was ${b.last_night_h} hours. You usually rest about ${b.usual_h} hours. ASTRA works this out from movement, so it is an estimate and not a sleep measurement.` : item.message,
        why: [short ? 'One short night is common and you usually recover. Several in a row make it harder to concentrate. NASA treats sleep, the length of the workday and exercise as part of protecting the crew.'
                    : 'A much longer night than usual can follow a hard day or a short earlier night. It is only something to watch.'],
        steps: short ? [
            ['Go to rest at your usual time tonight and keep your usual wake-up time.', NASA],
            ['Dim bright lights before rest. Keep the sleeping area dark, quiet and comfortable.', NASA],
            ['Do not plan hard exercise right before rest.', NASA],
            ['If you feel very sleepy, tell a crew mate before you start a task that needs your full attention.', ASTRA],
        ] : [
            ['Keep your usual rest and wake-up times tonight.', NASA],
            ['If you feel unusually tired, drink water, eat something and take a short walk.', ASTRA],
        ],
        seekTitle: 'When to ask for help',
        seek: ['If short nights continue for several nights, report it so your schedule can be reviewed.',
               'If tiredness could affect a safety-critical task, tell the crew before you do it.'],
        sources: ['sleep'],
    };
}

function connectionAdvice(item, level) {
    const lost = level === 'danger';
    return {
        what: lost ? `${item.message} No data are coming in, so everything on the screen is old.` : item.message,
        why: ['Without new readings ASTRA cannot warn you about anything, and old numbers must not be read as how you are now.'],
        steps: [
            ['Check that the device has power and the sensor cable is firmly connected.', ASTRA],
            ['Check that the laptop is on the same Wi-Fi and the ASTRA program is running.', ASTRA],
            ['Restart the device if it does not come back. New readings show on the Sensors page.', ASTRA],
            ['Until readings return, nothing on the screen is current.', ASTRA],
        ],
        seekTitle: 'When to ask for help',
        seek: [lost ? 'If the data stay missing after these checks, tell the person responsible for the hardware.' : 'If it stays missing for more than a few minutes, tell the person responsible for the hardware.'],
        sources: [],
    };
}

function signalAdvice(item) {
    return {
        what: `${item.message} Bad readings are not used for your usual values or for any notice, so ASTRA can say less.`,
        why: ['A fingertip sensor needs steady contact. Cold fingers, movement, pressing too hard or too lightly, and bright light all disturb it. A bad reading can look normal or alarming for no reason.'],
        steps: [
            ['Clean and dry your finger and the sensor window.', ASTRA],
            ['Put the finger flat on the sensor with light, steady pressure: not too tight, not loose. Warm your hand if it is cold.', ASTRA],
            ['Keep your hand still, at the height of your heart, away from strong light.', ASTRA],
            ['Do not act on a heart rate or SpO2 number until the signal is good. The Sensors page shows it.', ASTRA],
        ],
        seekTitle: 'When to ask for help',
        seek: ['If the signal stays poor after you reposition the finger, tell the person responsible for the hardware.'],
        sources: [],
    };
}

function wearAdvice(item) {
    return {
        what: item.message,
        why: ['Your rest, your activity and your usual values are only as good as the data behind them. A day with gaps can look different from a full day.'],
        steps: [
            ['Keep the device on and connected for the rest of the day, including the night.', ASTRA],
            ['Wear the sensor during exercise and log the session. NASA encourages ISS astronauts to do this.', NASA],
        ],
        seekTitle: 'When to ask for help',
        seek: ['If the device keeps stopping, tell the person responsible for the hardware.'],
        sources: ['rhythm'],
    };
}

function richAdvice(item, level) {
    switch (item.id) {
        case 'hr_vs_baseline': return level === 'ok' ? null : heartRateAdvice(item, level);
        case 'spo2_vs_baseline': return level === 'ok' ? null : spo2Advice(item);
        case 'inactivity': return level === 'ok' ? null : inactivityAdvice(item);
        case 'rest_start_vs_usual': return level === 'ok' ? null : restAdvice(item);
        case 'rest_length_vs_usual': return level === 'ok' ? null : restLengthAdvice(item);
        case 'connection': return level === 'ok' ? null : connectionAdvice(item, level);
        case 'signal_quality': return level === 'ok' ? null : signalAdvice(item);
        case 'wear_time': return level === 'ok' ? null : wearAdvice(item);
        default: return null;
    }
}

// Radiation alerts: the alert text is the team's illustrative demonstration text, not a NASA flight rule.
function radiationAdvice(alert, why) {
    return {
        what: alert.message,
        why: [why],
        steps: alert.actions.map((t) => [t, ASTRA]),
        seekTitle: 'When to get help',
        seek: ['Follow mission control instructions and the mission\'s own radiation procedures.'],
        sources: [],
    };
}

// ---- rendering (shared by the Timeline warnings and the events panel) ----
function stepsList(steps) {
    const list = el('ol', 'steps');
    steps.forEach(([text, tag]) => {
        const li = el('li');
        li.append(el('span', `chip ${tag === NASA ? 'chip-external' : 'chip-plain'}`, tag === NASA ? 'NASA GUIDANCE' : 'ASTRA SUGGESTION'), document.createTextNode(` ${text}`));
        list.append(li);
    });
    return list;
}

function richBody(g) {
    const box = el('div', 'rich');
    const dl = el('dl', 'rwu');
    dl.append(el('dt', '', 'What happened'), el('dd', '', g.what));
    dl.append(el('dt', '', 'Why it matters'));
    const why = el('dd');
    g.why.forEach((t) => why.append(el('p', 'note', t)));
    dl.append(why);
    dl.append(el('dt', '', 'What to do'));
    const todo = el('dd');
    todo.append(g.steps.length ? stepsList(g.steps) : el('p', '', 'No action needed.'));
    dl.append(todo);
    if (g.seek && g.seek.length) {
        dl.append(el('dt', '', g.seekTitle || 'When to get help'));
        const seek = el('dd');
        const list = el('ul', 'ref-list');
        g.seek.forEach((t) => list.append(el('li', '', t)));
        seek.append(list);
        dl.append(seek);
    }
    box.append(dl);
    if (g.sources && g.sources.length) {
        const src = el('p', 'note');
        src.append(document.createTextNode('Sources: '));
        g.sources.forEach((key, i) => {
            const [label, url] = ADVICE_SOURCES[key];
            const a = el('a', '', label);
            a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer';
            if (i) src.append(document.createTextNode(' · '));
            src.append(a);
        });
        box.append(src);
    }
    return box;
}

window.richAdvice = richAdvice;
window.richBody = richBody;
window.radiationAdvice = radiationAdvice;
window.refreshAdviceObs = refreshAdviceObs;

document.addEventListener('DOMContentLoaded', () => {
    refreshAdviceObs();
    setInterval(refreshAdviceObs, 10000);
});
