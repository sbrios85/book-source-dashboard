[README.md](https://github.com/user-attachments/files/28374866/README.md)
# book-source-dashboard# Book Source Dashboard

A sourcing dashboard for the book business. Two halves:

- **Live Feed** — library/Friends book sales, estate sales, and book lots worth driving to, within a configurable radius.
- **Outreach Leads** — estate-sale companies, junk/haul-out companies, and school libraries (K-12, private, colleges), with a built-in CRM (status, last-contacted, notes) and one-click outreach pitches.

Built to run exactly like the other GitHub-Pages dashboards: a scheduled Action refreshes two JSON files, the static page reads them.

## How it works

```
index.html              ← the dashboard (reads data/*.json at runtime)
data/sales.json         ← Live Feed contents
data/leads.json         ← Outreach contents (your CRM status is preserved on refresh)
scraper/build_data.py   ← pulls every source, writes the two JSON files
scraper/config.yaml      ← coverage + sources. PER-CATEGORY RADIUS lives here.
scraper/requirements.txt
.github/workflows/refresh.yml  ← weekly + manual refresh, commits data back
```

## Per-category radius

In `scraper/config.yaml`:

```yaml
radius_miles:
  schools: 110          # Kingsville → Victoria. Set to ~250 to add San Antonio + Houston.
  estate_companies: 45  # tighter — you drive to these
  junk_removal: 45
  book_sales: 90
```

Each category re-scopes on the next run when you change its number.

## Sources

- **Schools** — Urban Institute Education Data API (a clean JSON layer over NCES public/private/college directories). The first live run may need one field-name tweak in `fetch_schools()` if Urban shifts a column for the data year; the code logs what it pulled.
- **Library/Friends sales** — CivicPlus municipal iCal feeds (add each town's iCal URL), plus **fixed schedules** for sales that never hit any aggregator (Victoria's Jan/May/Sept is pre-loaded).
- **Estate sales** — EstateSales.net (polite scrape).
- **Book lots** — Craigslist RSS (the Marketplace replacement that doesn't fight automation).

## CRM persistence

Status/notes save in your browser (localStorage). Click **Export leads.json** to download the merged file and commit it to `data/` so your outreach state lives in the repo and survives across devices.

## Notes

- The page must be served over http (GitHub Pages or `python -m http.server`), not opened from disk, or the browser blocks the JSON fetches.
- After a refresh commit, if Pages serves a stale file, hard-refresh once.
- Adding a new town = add its iCal URL (or a fixed-schedule block) to `config.yaml`. No code changes.
