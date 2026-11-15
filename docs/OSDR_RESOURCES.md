# NASA OSDR: what we found and what we use

Checked on 14 Nov 2026 with the public NASA Open Science Data Repository (OSDR) search API and web page: https://osdr.nasa.gov/bio/repo/search?q=&data_source=cgene,alsda,esa&data_type=study

## 1. What OSDR is, in one paragraph
OSDR is NASA's open archive of space biology and human research studies. The "GeneLab" archive (`cgene`) and the Ames Life Sciences Data Archive (`alsda`) hold the studies we searched. The data are mostly omics (gene, protein, methylation), imaging, behaviour and physiology measurements of mice, rats, cells and some human samples. The study metadata (title, organism, factors, description, release date) is open and searchable by a public search API. Data files have their own access conditions on each study page.

## 2. The honest main finding
**OSDR has no wearable heart rate, SpO2 or movement recordings that we could compare with the MAX30102 and ICM-20948.** The search API returned no study (0 results in both archives) for *actigraphy*, *accelerometer*, *oxygen saturation* and *heart rate variability*. *Heart rate* matched 14 GeneLab and 2 Ames studies; the ones we read are mouse, rat, fly or cell studies. The "ESA" data source filter of the web page returned nothing for *heart rate*, and the API does not accept `esa` as a type. The Inspiration4 wearable data are controlled access (see the entry `i4-cardiovascular-paper` in `data/reference.json`).

So OSDR is **not a source of numbers to plot next to our sensors**. It is a source of **scientific context and citations** for the risks ASTRA monitors, and of a live search we can show the jury. Everything we take from it is kept in the external reference list, labelled `EXTERNAL` and "not comparable".

## 3. Studies that fit ASTRA (links)
We only read the study descriptions, not the papers or the data files. Each is in `data/reference.json` (status `needs_review`) with what it says and why it cannot be compared with our readings.

**Radiation and the heart (supports the Radiation Risk Monitor and the heart rate monitoring)**
- OSD-435, echocardiogram data: https://osdr.nasa.gov/bio/repo/data/studies/OSD-435 (companion OSD-591: https://osdr.nasa.gov/bio/repo/data/studies/OSD-591). Mice exposed to 16O ions, protons and gamma rays; the description names the concern about space radiation and the cardiovascular system.
- OSD-720: https://osdr.nasa.gov/bio/repo/data/studies/OSD-720 and OSD-881: https://osdr.nasa.gov/bio/repo/data/studies/OSD-881. Long-term heart changes after gamma and simulated galactic cosmic ray radiation in mice (a heart failure with preserved ejection fraction like phenotype 660 days after exposure, only in males, according to the description).
- OSD-334: https://osdr.nasa.gov/bio/repo/data/studies/OSD-334. HZE radiation, microRNA signatures and countermeasures, heart tissue.

**Radiation, fatigue, vigilance and isolation (supports the journal and the stress and fatigue questions)**
- OSD-896: https://osdr.nasa.gov/bio/repo/data/studies/OSD-896 (also OSD-897, OSD-939). Sustained attention in rats after proton radiation, using an analog of the human Psychomotor Vigilance Test.
- OSD-1018: https://osdr.nasa.gov/bio/repo/data/studies/OSD-1018. Social isolation and space radiation, behaviour and motor learning, with sleep named in the description.
- OSD-776: https://osdr.nasa.gov/bio/repo/data/studies/OSD-776 (also OSD-777, OSD-778). Deep space radiation and cognitive performance in mice.
- OSD-140: https://osdr.nasa.gov/bio/repo/data/studies/OSD-140. Mars-520 isolation simulation, 6 crew, mood and epigenetic profiling.

**Radiation sensing (supports the roadmap "onboard detector")**
- OSD-964: https://osdr.nasa.gov/bio/repo/data/studies/OSD-964. BioSentinel: yeast cells as a biological radiation sensor beyond low Earth orbit.

**Human spaceflight, heart and activity**
- OSD-575: https://osdr.nasa.gov/bio/repo/data/studies/OSD-575. Inspiration4 serum with immune and cardiac cytokine panels (blood biomarkers, not heart rate).
- OSD-484: https://osdr.nasa.gov/bio/repo/data/studies/OSD-484. Plasma from 3 astronauts applied to human cardiomyocyte cells.
- OSD-942: https://osdr.nasa.gov/bio/repo/data/studies/OSD-942. The NASA 70-day bed rest study: exercise training counteracted the decline in aerobic capacity, muscle mass, strength and endurance (as the description states). Also OSD-51: https://osdr.nasa.gov/bio/repo/data/studies/OSD-51 and OSD-540: https://osdr.nasa.gov/bio/repo/data/studies/OSD-540. This is the scientific background for our movement and activity view.

## 4. Documentation of the API
- Biological Data API tutorial: https://osdr-tutorials.readthedocs.io/en/latest/pages/guides/biological_data_api.html
- Biological Data API (versioned query endpoints): https://visualization.osdr.nasa.gov/biodata/api
- The search endpoint we use: `https://osdr.nasa.gov/osdr/data/search?term=<text>&from=0&size=<n>&type=cgene|alsda`. It is the endpoint the OSDR search page itself uses. We found it by trying it; we did not find a documentation page for it, so treat its parameters as subject to change.
- Study pages: `https://osdr.nasa.gov/bio/repo/data/studies/OSD-<number>`.

## 5. What we implemented (branch `feat/osdr-resources`)
1. **A "Search NASA OSDR studies" box on the Data page** (`GET /api/osdr/search?q=&type=&size=`, backend `osdr.py`). It searches both archives live, shows title, accession, organism, material, release date and a short summary with a link to the study, and labels every result `EXTERNAL`. Example buttons: radiation heart, sleep, bed rest exercise, isolation, heart rate, actigraphy (the last one shows the "no study found" result on purpose). Safety: the term is limited to letters, digits and a few characters, results are cached for 10 minutes, it fails with a clear message when there is no internet, and the text from NASA is shown as plain text.
2. **Ten new curated entries in `data/reference.json`** (the studies above plus one entry that records the search finding of section 2), each with `statements` limited to what the study description says, a `cannot_be_compared` list, and the `needs_review` status.
3. **Topics.** Reference entries have optional topics (radiation, heart, sleep and activity, isolation, human spaceflight, countermeasures). `GET /api/reference?topic=radiation` filters; the Data page has topic buttons and topic chips.
4. **A panel "NASA research related to radiation" on the Radiation page** that lists the radiation-topic references with the first statement and the first reason they cannot be compared.

## 6. What we deliberately do not do
- We do not plot OSDR numbers next to our sensor data and do not compare them.
- We do not claim any finding from a study whose results we did not read.
- We do not turn mouse radiation doses (Gy) into anything about the proton flux (pfu) or the astronaut dose on the Radiation page.

## 7. Ideas if there is time
- Ask Red to read the three or four most relevant papers behind these studies (OSD-435, OSD-896, OSD-942) and promote their entries to `reviewed` with real numbers.
- Use the OSDR Biological Data API only if the team wants omics data; it is outside ASTRA's scope.
- Cite OSD-896 and OSD-1018 in the pitch as the reason ASTRA keeps self-reported fatigue and stress next to the sensors.
