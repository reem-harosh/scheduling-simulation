## Replay and progress — v0.6.0

The replay now shows material groups with exact quantities before processing, inside machines, after unloading and during capacity-limited transfers. Click a group or active job to inspect every part range. The replay resource strip and worker–machine links follow the displayed time, and the sidebar excludes inactive entities. The Gantt includes machine activity, queues and transfers, with a selected-job filter and adjustable time window; the full-trace overview opens into detailed segments.

Single runs and algorithm experiments display progress, completed/total replications, cache hits and a changing ETA based on observed work. Fresh runs are required for the new material ledger; older JSON files remain viewable and explicitly identify missing material data. See [replay details and validation](docs/replay-v060.md).

To update an existing checkout, stop the old server, run `git pull`, then `python run_factory.py` (Codespaces: `python run_factory.py --host 0.0.0.0 --no-browser`). Open `/production/` and verify **UI / server 0.6.2** before running a new simulation.

## Multi-agent review — v0.5.3

The v0.5.3 release fixed operation-change setup, initialization during an active shift, configuration validation before demand generation, single-replication summaries, and replay export/live inspectors. Machine service, occupied time and waiting time are separate metrics. The floor now shows actual ready-queue counts and distinguishes setup specialists.

Read [the three-round review and verification limits](docs/multi-agent-review-2026-09-11.md). Reproducible current finite-horizon evidence, including raw runs and a source manifest, is in `research/multi_agent_review/`:

```bash
python tools/run_review_verification.py
```

These runs are implementation verification, not a new capacity calibration or proof of stationarity. Earlier v0.5 calibration/grid records predate the operation-setup correction. Codespaces user access remains unverified; the normal Python launch below is unchanged.

## Test v0.6.2 from your phone

[Open the mobile review in GitHub Codespaces](https://codespaces.new/reem-harosh/scheduling-simulation/tree/mobile-review-v062)

1. Open the link in your phone browser and sign in to GitHub. Verify the branch is **mobile-review-v062**, then choose **Create codespace**.
2. Wait for the environment to finish preparing. Dependencies and the Python server start automatically.
3. If the simulation does not open automatically, open **Ports → 8000 → Open in Browser**. Keep the port private and use the same GitHub account. Rotate the phone to landscape for the factory view.
4. Verify **UI / server 0.6.2**, then run a new simulation. Saved v0.6.1 results that used operator assistance do not change when replayed; their policy warning explains why a new run is needed.

This review branch restores exclusive operation ownership for loading, cycle changes and unloading, while preserving shift handoffs and the replay display fixes. A qualified free worker may therefore wait while another worker owns the operation. Setup and transport retain their original eligibility rules.

The Python engine runs in the Codespace; nothing needs installing on the phone. GitHub account quotas apply. The app is available while the Codespace runs; resume it later at [your Codespaces](https://github.com/codespaces). This is a separate review branch, not a main release. Cloud account creation and phone-browser access must be completed in your own account; they have not been tested on your device.

Version **0.5.2** adds backend version identification, cache prevention, and a processing-only flow-time lower bound (not a proven optimum). See [cloud launch and reference definition](docs/cloud-and-flow-reference-v052.md).

# Scheduling Simulation — research world v0.5

```bash
pip install -r requirements.txt
python run_factory.py
```

Open http://127.0.0.1:8000/production/ if the browser does not open automatically.
The default world is `research/world_v05/world.json`; v0.4 remains available with
`python run_factory.py --calibration research/world/world.json`.

The new world has18 families (including two single-operation families with5%
combined demand),50 operations,68 physical machines and4 setup specialists.
Milling distinguishes3/4-axis capabilities; four-axis machines also accept
three-axis work. Quantities follow bounded triangular distributions with a
weighted mean175 at the base scale. Family frequencies remain nonuniform.
Workers stay on their floor; parts may travel via a shared capacity-limited lift.

Tables in the browser expose all families, operation requirements, quantity
parameters, physical machines, processing entries, setup matrices and rosters.
CSV exports and the complete frozen world are in `research/world_v05/`.

```bash
python tools/build_research_world.py --rate 12
python tools/run_world_experiments.py run --days 28 --warmup 14
python tools/run_world_experiments.py grid --scales .5 .75 1 1.25 1.5 --replications 3 --days 28 --warmup 14
python -m unittest discover -s tests -p 'test_*.py'
```

The experiment axes remain arrival intensity and job size. All raw runs are
retained. Same seed/replication yields identical demand across algorithms.
Calibration is offline; the generator never responds to live queues or resources.
Finite-horizon pilot results are not a proof of stationarity.
Read [the v0.5 implementation and calibration record](docs/research-world-v05.md).

The following documentation describes the retained **legacy v0.3** world and
print-shop prototype. Its old arrivals, source-file requirements, splitting
policies and operating-point approvals do not apply to the new default.

---

## Confirmed demand baseline and validation

The demand-intensity correction and reviewer procedure are documented in
[docs/demand-calibration.md](docs/demand-calibration.md). The latest independent
review scored **8.70/10**, with **41 passing tests**.

The private `Simulation_Validation.zip` delivered with this revision contains the
source-matched operating point, replication evidence and final replay. Extract it
**inside this repository** after importing your original source ZIP:

```bash
python -m zipfile -e Simulation_Validation.zip .
python run_factory.py
```

The server and CLI automatically load `results/load-calibration/operating_point.json`
when its source/data hashes match. The UI labels an absent or incompatible point
as uncalibrated. Raw data and this private evidence bundle are not in public git.
The confirmed burn-in is long; load `results/final-baseline-replay.json` in the UI
to inspect the saved replay immediately instead of rerunning it.

```bash
python tools/validate_replay.py results/final-baseline-replay.json
```

# Production Lab — Python production-floor simulation

The new production world is in `factory/` and `dist/production/`. The original PrintFlow demo remains available unchanged at `dist/index.html` and through `python run.py`.

## Start the production world

Python 3.10+ is required (tested on Python 3.12). From the repository directory:

```bash
python -m pip install -r requirements.txt
python tools/import_project.py /path/to/Simulation_Project_v0_3.zip
python run_factory.py
```

On Windows, use `py` instead of `python` if needed. The last command opens the local browser interface. The numerical engine runs in Python; HTML/JavaScript replay and inspect its recorded events. There is no second JavaScript simulation engine.

The ZIP is the source package supplied with this project. Input spreadsheets, the facility map, calibration and detailed specification are intentionally excluded from this **public** repository: publication of those inputs was blocked by automatic approval review. The import command installs them locally, verifies an existing file is identical before reuse, and leaves Git exclusions intact. It never overwrites differing source data. No secret credentials are stored in source.

Without a Python backend, `/production/` can still open a saved result JSON for replay. The existing hosted PrintFlow demo has not been replaced or redeployed by this development work.

## Run modes

```bash
# Single-run diagnostic, with seven days of event replay and full drain
python -m factory --days 28 --out results/run.json

# Shared warm-up and matched replications for FIFO and CYCLE_TRANSFER
python -m factory --mode scenario --days 28 --out results/comparison.json

# Full 5 x 5 response grid (can take considerable time)
python -m factory --mode grid --out results/surface.json

# Deterministic controlled jobs, read from your own JSON list
python -m factory --manual jobs.json --out results/controlled.json

# Verification
python -m unittest discover -s tests -v
python tools/verify_research_protocol.py
```

The browser offers arrival load, batch size, horizon, algorithm and seed controls; a floor replay with speed and precise-time controls; entity inspectors; and research scenario/grid controls. Source-data runs can be large. Cancellation preserves a clearly labeled partial diagnostic or completed replication checkpoints. Resuming an unchanged research request reuses compatible cached replications, keyed by code, input, configuration and seed. Changed code or data invalidates that cache.

**A single run is not a steady-state research estimate.** The research runner first applies the shared pilot protocol, then runs matched replications and nominal Student-t confidence intervals. `NOT_STABILIZED`, `PRECISION_NOT_MET`, empty cohorts, cancellation and failures remain explicit. Missing surface cells are not interpolated. The controlled protocol verification uses generic test data and is not a production performance estimate.

## Extending scheduling policies

Implement `decide(snapshot)` and pass the policy to `Simulation(..., policy=policy)`. The snapshot contains released jobs, legal ready/output ranges, resource state, skills/ownership, known distribution definitions and calendar rules. It excludes future arrivals and sampled outcomes. Actions `allocate`, `split`, and `transfer` are validated atomically. Part ranges are half-open ordinal intervals. A transfer may request `preserve_batch=True` to retain one logical execution batch while moving it in several capacity-limited trips. Invalid actions return a reason code. See `factory/policies.py` and the extension tests.

## Review and limitations

See `docs/production-quality-review.md` for independent scores, evidence and remaining issues. Research computations and real source-derived replay exports live in the excluded `results/` directory. Keep those outputs with their source hashes. This is an experimental scheduling model, not a validated digital twin.

---

## Original PrintFlow documentation

# PrintFlow — מעבדת סימולציה לבית דפוס

מנוע סימולציה בפייתון ותצוגת רצפה מונפשת בדפדפן. זהו תרחיש אזרחי עצמאי עם ארבע מנות סינתטיות, שתי מדפסות, עמדת כריכה ושני עובדים. נתוני התרחיש אינם נגזרים מקובצי מפעל אחרים.

## הפעלה מקומית

נדרש Python 3.10 ומעלה ודפדפן מודרני התומך ב־WebAssembly. אין צורך להתקין חבילות pip או Node כדי להפעיל את הפרויקט. קובצי סביבת הפייתון לדפדפן כלולים בהורדה; אין צורך בשירות ענן לחישוב.

פתח מסוף בתיקיית הפרויקט והריץ:

```bash
python run.py
```

ב־Windows אפשר להשתמש ב־`py run.py`. הדפדפן ייפתח אוטומטית. לעצירה: Ctrl+C. לבחירת פורט אחר: `python run.py --port 8080`.

יש להפעיל דרך שרת זה או שרת HTTP אחר, ולא לפתוח את index.html כקובץ מקומי, משום שהדפדפן טוען Worker וקובצי WebAssembly.

## מה אפשר לעשות

- לראות עובדים הולכים במעבר המרכזי ומפעילים מכונות.
- להפעיל, להשהות, לשנות מהירות, לחזור בזמן או להתקדם לאירוע הבא.
- לבחור אופק הרצה בדקות, כלל שיבוץ, זרע אקראי וזמני עבודה משתנים.
- לצפות במצב כל מנה, עובד ומכונה, ביומן האירועים ובציר זמן המשאבים.
- להריץ 1–500 רפליקציות, לבחון פיזור תוצאות ולהוריד CSV.
- להשוות כללי שיבוץ באותה סדרת ניסויים; נשמרים עד 20 ניסויים שונים כל עוד הדף פתוח.
- להוריד את קוד המקור מתוך הממשק.

## ארכיטקטורה

| קובץ | אחריות |
|---|---|
| `dist/scenario.json` | קלט בית הדפוס: מנות, מכונות, עובדים, כשירויות, מיקומים וזמנים |
| `dist/experiments.js` | שמירת ניסויים והשוואה רק בתנאים ובסדרות זרעים זהים |
| `dist/engine.py` | ישויות התרחיש, דגימת זמנים, שיבוץ, מנוע אירועים ומדדי תוצאה |
| `dist/worker.js` | טעינת CPython באמצעות Pyodide והרצת המנוע מחוץ לשרשור התצוגה |
| `dist/view-model.js` | חישוב המצב החזותי בזמן נתון מתוך יומן האירועים בלבד |
| `dist/app.js` | ממשק, הנפשת תרשים הרצפה ובקרות צפייה וניסויים |
| `dist/index.html`, `dist/styles.css` | מבנה הממשק בעברית ועיצוב רספונסיבי |
| `run.py` | הפעלת שרת מקומי בפייתון |
| `tests/test_engine.py` | בדיקות התנהגות המנוע |
| `dist/model.md` | מפרט המקרה המקורי ללא זמן הליכה |

המנוע בפייתון מחשב יומן אירועים. התצוגה ב־JavaScript מנגנת אותו ומציגה גם את המשך התרחיש בציר הזמן; היא אינה משבצת פעולות מחדש. שינוי מהירות התצוגה אינו משנה תוצאות. אותו engine.py פועל ללא שינוי ב־Python מקומי וב־CPython בדפדפן.

## עריכת קלט התרחיש

הקובץ `dist/scenario.json` מופרד ממנוע הסימולציה. אפשר לערוך בו את רשימות המנות, המכונות והעובדים, את זמני הפעולות ואת הכשירויות. לאחר עריכה יש לרענן את הדף. בפייתון אפשר להעביר מילון תרחיש אל `simulate(options, scenario=model)` או לקרוא קובץ באמצעות `load_scenario(path)`.

המנוע בודק מזהים ייחודיים, זמנים חיוביים, צבעי #RRGGBB וזמינות מכונה ועובד כשיר לכל סוג פעולה. הגרסה הנוכחית תומכת בהדפסה וכריכה, וכל המנות זמינות בזמן 0. הוספת מועדי הגעה משתנים מחייבת הרחבת המודל בהמשך. המיקומים סכמטיים על רצפה של 900×560, ויש לבחור אותם ידנית כך שהעמדות אינן חופפות. אין כאן עדיין מחולל מפעל גדול או עורך רצפה. מספרי הישויות והכשירויות בממשק נגזרים מהקלט. תרשים הרצפה מציג עד ארבע תגיות מנה בכל אזור, ושאר המנות זמינות כולן בפאנל העבודות.

## הנחות ומדדים

כל פעולה דורשת מכונה ועובד כשיר לכל משכה. רק W2 כשיר לכריכה. כל המנות זמינות בזמן 0. אין פיצול מנות, תקלות, הפסקות או זמני הכנה נפרדים. הדפסת המנה כולה מסתיימת לפני הכריכה. זמני העיבוד הם למנה כולה, ואין להכפיל אותם בכמות היחידות.

בברירת המחדל זמן הליכה פעיל: העבודה והמכונה נשמרות לעובד, ורק לאחר הגעתו מתחיל העיבוד. ההליכה עוברת דרך מעבר משותף לפי מרחק סכמטי ומהירות של 180 יחידות שרטוט לדקה. אין מודל התנגשויות בין הולכים או הובלת חומר. אם העובד נמצא כבר בעמדה, זמן ההליכה אפס. אלה פרמטרים מומצאים לתרגיל, ללא קנה מידה פיזי מאומת.

זמן השהייה למנה הוא סיום הפעולה האחרונה פחות זמן הכניסה. הממוצע נותן לכל מנה משקל שווה. בזמן צפייה מוצג ממוצע למנות שהושלמו עד אז בלבד. כאשר אופק ההרצה קצר, אין להציג ממוצע חלקי כאילו הוא תוצאת המערכת המלאה: ה־CSV משאיר את השדה הסופי ריק ומסמן `complete=false`.

בהרצה מלאה, ניצולת מחושבת כזמן העיבוד בלבד חלקי משך התצפית; זמן הליכה/שמירת מכונה אינם נחשבים עיבוד. מועד יעד הוא שיקול רך ולא אילוץ קשיח. למנת המלאי אין איחור מוגדר.

## שחזור הדוגמה הידנית

בחר "סדר קבוע", כבה זמן הליכה וזמני עבודה משתנים, והגדר אופק של 26 דקות לפחות. מתקבלים:

| מנה | זמן השלמה |
|---|---:|
| A | 22 |
| B | 6 |
| C | 16 |
| D | 26 |

זמן השהייה הממוצע: **17.5 דקות**. עם הליכה פעילה וללא שונות: כ־**20.75 דקות**. אלו תוצאות של כלל בסיס מוגדר; אין טענה לאופטימליות.

כלל SPT ממיין לפי זמני הפעולות שנדגמו מראש, בהנחה שהם ידועים בזמן השיבוץ. זוהי הנחת מידע מפורשת: אין כאן מודל שבו משך הפעולה האמיתי מתגלה רק עם סיומה.

## רפליקציות

כל זמן פעולה נדגם פעם אחת מטווח אחיד סביב משך הבסיס, למשל ±20%. הדגימה נעשית לפי מנה ופעולה לפני השיבוץ, כך שאותו זרע יוצר אותם זמני פעולה גם תחת כלל שיבוץ אחר. בכל רפליקציה הזרע גדל באחד. ללא שונות, כל הרפליקציות זהות.

ההרצה החזותית נפסקת בסיום כל המנות או באופק שנבחר, המוקדם מביניהם. המנוע מחשב גם את הסיומים שמעבר לאופק לצורך עקביות התרחיש, אך הם אינם נספרים בתוצאות הנצפות. בתוצאות ניסוי, סטיית התקן היא סטיית תקן מדגמית בין זמני השהייה הממוצעים של הרפליקציות המלאות. כאשר חלק מההרצות אינן מלאות, הממשק מציין את מספרן ואינו מציג את ממוצע ההרצות המלאות כאומדן בלתי מוטה של כל ההרצות.

## השוואת כללי שיבוץ

הרץ ניסוי בסדר קבוע, שנה רק את כלל השיבוץ, החל את ההגדרות והריץ ניסוי נוסף. טבלת ההשוואה מציגה קודם זמן שהייה ממוצע, ואחריו זמן סיום כולל, איחור כולל ואחוז שיפור מול הסדר הקבוע. הזמנים הם ממוצעים בין הרפליקציות. השוואה מתאפשרת רק לאותו תרחיש, אופק, מצב הליכה, שונות וסדרת זרעים בפועל; ניסויים בתנאים אחרים מופיעים בסדרה נפרדת שניתן לבחור. סדרה המכילה הרצות חלקיות אינה מקבלת ממוצע מדורג או אחוז שיפור. המיטב בטבלה הוא רק מבין הכללים שנבדקו, ללא הוכחת אופטימליות או מובהקות סטטיסטית.

ההשוואות נשמרות בזיכרון הדף, עד 20 ניסויים שונים; רענון הדף מוחק אותן. יצוא CSV של הניסוי הנוכחי מאפשר לשמור את תוצאותיו בנפרד.

## הרצה ללא ממשק ובדיקות

```bash
python dist/engine.py --no-walking
python dist/engine.py --policy spt --variation 0.2 --seed 42 --horizon 60
python -m unittest discover -s tests -v
node tests/test_view_model.mjs
python tools/package_source.py
```

אחרי שינוי קוד, `python tools/package_source.py` מעדכן את ארכיון ההורדה ובודק שתוכנו תואם לקבצים.

בדיקות התצוגה וההשוואה דורשות Node.js 22 ומעלה לצורכי פיתוח בלבד; הפעלת הסימולציה המקומית אינה דורשת Node.

## ניהול ב־GitHub

המאגר: [reem-harosh/scheduling-simulation](https://github.com/reem-harosh/scheduling-simulation), ענף `main`. אפשר לשכפל את המאגר, להריץ `python run.py`, ולשמור שינויים באמצעות commit ו־push בהרשאות חשבון GitHub שלך. במרחב העבודה של Sites, `origin` מצביע לאירוח ו־`github` למאגר GitHub; לאחר שמירה יש לאמת ששני היעדים מכילים את אותם קבצים. הקוד אינו מכיל סיסמאות או הרשאות GitHub.

קובצי האתר נערכים ישירות תחת dist; אין שלב build. לכן **יש לשמור את dist במאגר**. קובצי המקור זמינים גם מחוץ לארכיון ההורדה שבתוכו. קובץ `.openai/hosting.json`, אם קיים בגרסת Sites, הוא מזהה האירוח ואינו דרוש להרצה מקומית.

## רכיבי צד שלישי

קובצי `dist/runtime` הם Pyodide 0.27.7 (CPython 3.12.7), מההפצה הרשמית. המנוע משתמש בספרייה התקנית בלבד. ראו [Pyodide](https://pyodide.org/en/0.27.7/usage/index.html), [קוד ורישוי Pyodide](https://github.com/pyodide/pyodide/tree/0.27.7), ו[רישיון Python](https://docs.python.org/3.12/license.html). ההפצה כוללת רכיבים של CPython ו־Emscripten תחת רישיונותיהם. שימוש ב־Web Worker להרצת המנוע תואם את הנחיות [התיעוד הרשמי](https://pyodide.org/en/stable/usage/index.html#web-workers).

### Live observability v0.5.1

Run status, live resource counts, operation detail and preserved/partial response surfaces are now available. Restart the Python server after updating. See [design and validation notes](docs/live-observability-v051.md).
