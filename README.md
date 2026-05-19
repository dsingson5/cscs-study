# CSCS Daily Study

Interactive HTML study generator for the NSCA CSCS exam, built on *Essentials of Strength Training and Conditioning* (4th ed.). Generates a fresh self-contained HTML page every morning with one new lesson, spaced-repetition reviews, topic-themed visuals, and an adaptive SM-2 personal review queue persisted in localStorage.

## Local use

Already works on Windows via the bundled `install_schedule.bat` (Windows Task Scheduler at 7 AM daily). Open `daily/cscs_today.html` each morning.

## Deploying to GitHub Pages for mobile access

1. **Create a new GitHub repository.** Public or private both work; private repos can still use Pages.
2. **Initial commit.** From a terminal in this folder:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git
   git push -u origin main
   ```
3. **Enable GitHub Pages.** In the repo settings → Pages, set the source to **GitHub Actions**.
4. The workflow at `.github/workflows/daily.yml` runs at 14:00 UTC every day and on every push. After the first run, your site is live at `https://YOUR-USERNAME.github.io/YOUR-REPO/`. Open that URL on your phone, save it to the home screen.

### What the workflow does each day

- Checks out the repo
- Runs `python generate_daily.py` on GitHub's servers
- Commits the new `index.html` and dated archive in `daily/`
- Deploys the static site to GitHub Pages

### Manual triggers

In the Actions tab of your repo, the **Daily CSCS HTML build** workflow has a "Run workflow" button — useful if you want to force a regeneration without waiting.

### Cron schedule

`14:00 UTC` translates to:
- `07:00` Pacific (PDT, summer)
- `08:00` Pacific (PST, winter)
- `10:00` Eastern (EDT, summer)
- `09:00` Eastern (EST, winter)
- `22:00` Manila (PHT, year-round — no DST)

Edit `.github/workflows/daily.yml` (the `cron:` line) if you want a different time. Use [crontab.guru](https://crontab.guru/) to compose expressions.

## File layout

```
.
├── generate_daily.py        # main script
├── widgets.py               # topic-specific interactive widgets
├── themes.py                # procedural daily theme (unique per day)
├── motifs.py                # topic motifs — visual identity per lesson
├── styles.css               # base stylesheet
├── app.js                   # localStorage persistence + SM-2 spacing
├── data/
│   ├── curriculum.json      # 26-week curriculum (42 lessons + deep review)
│   └── questions.json       # question bank keyed by topic_id
├── index.html               # rolling GitHub Pages entry (auto-regenerated)
├── daily/
│   ├── cscs_today.html      # rolling local entry
│   └── cscs_YYYY-MM-DD.html # dated archive
├── install_schedule.bat     # Windows Task Scheduler installer (optional)
├── run_now.bat              # one-click local regen + open
└── .github/workflows/daily.yml  # GitHub Actions daily regen
```

## How the adaptive review queue works

Each question gets a stable ID `topicId__index`. localStorage tracks per-question state:

| Field | Meaning |
|---|---|
| seen_count | total times you've answered it |
| last_seen | ISO date of most recent attempt |
| last_mark | `correct` / `partial` / `missed` |
| ease | SM-2 ease factor (1.3 floor, 2.7 ceiling, default 2.5) |
| interval | days until next due |
| next_due | ISO date when it should resurface |
| history | last 10 marks for inspection |

On page load, the JS scans localStorage and inserts a "Personal review queue" section above today's lesson with any question whose `next_due ≤ today`. Missed-mark questions rank first, then partials, then any due correct ones.

### Limitations

localStorage is per-browser/per-device. Phone and laptop track separately. Use the Export/Import buttons in the study tip box to move progress between devices manually.

## Daily content

The generator picks today's lesson from `data/curriculum.json` based on day_number (today minus the curriculum start date `2026-05-19`). Days beyond the populated 42 enter "Deep Review" mode and randomly rotate through populated lessons.

To extend the curriculum, add entries to `curriculum.json` keyed by day_number (string), with the existing schema (`title`, `topic_id`, `domain`, `chapter`, `page_refs`, `key_concept`, `key_facts[]`, `training_link`, `video{}`, `audio{}`). Add matching questions to `questions.json` keyed by `topic_id`.
