#!/usr/bin/env python3
"""
Book Source Dashboard — data builder.

Reads scraper/config.yaml, pulls every enabled source, and writes:
  data/sales.json   (Live Feed: library/Friends sales, estate sales, book lots)
  data/leads.json   (Outreach tracker: estate cos, junk haulers, school libraries)

Design notes
------------
* Each source is wrapped in try/except so one broken feed never kills the run
  (same robustness pattern as the NCAD/CCLN scrapers).
* Per-category radius comes straight from config.radius_miles — change a number
  there and that category re-scopes on the next run.
* Merges by stable `id`. For leads it PRESERVES your CRM fields
  (status / last_contacted / outreach_notes) so a refresh never wipes your work.
* Network calls only work where the runner has open egress (GitHub Actions),
  not in a restricted sandbox.
"""

import json, math, re, sys, datetime, pathlib, time

import yaml
import requests

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"
CFG = yaml.safe_load((HERE / "config.yaml").read_text())

CENTER = (CFG["center"]["lat"], CFG["center"]["lng"])
RADIUS = CFG["radius_miles"]
UA = {"User-Agent": "book-source-dashboard/1.0 (personal sourcing tool; contact: owner)"}
TODAY = datetime.date.today()


# ── helpers ──────────────────────────────────────────────────────────────────
def miles(lat, lng):
    """Great-circle distance in miles from the configured center."""
    if lat is None or lng is None:
        return None
    R = 3958.8
    p1, p2 = math.radians(CENTER[0]), math.radians(lat)
    dphi = math.radians(lat - CENTER[0])
    dlmb = math.radians(lng - CENTER[1])
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def load(path, key):
    try:
        return json.loads(path.read_text())
    except Exception:
        return {key: []}


def log(msg):
    print(f"[build] {msg}", flush=True)


# ── SCHOOLS  (Urban Institute Education Data API over NCES) ───────────────────
def fetch_schools():
    """
    Public K-12 (CCD), private (PSS), colleges (IPEDS) within radius_miles.schools.
    NOTE: Urban Institute field names occasionally shift between data years; if a
    pull comes back empty, check the JSON shape once and adjust the .get() keys.
    """
    out = []
    s = CFG.get("schools", {})
    fips = s.get("state_fips", "48")
    rad = RADIUS["schools"]
    base = "https://educationdata.urban.org/api/v1"

    jobs = []
    if s.get("include_public_k12"):
        jobs.append(("Public K-12", f"{base}/schools/ccd/directory/2022/?fips={fips}",
                     "school_name", "phone", "latitude", "longitude", "school_level"))
    if s.get("include_private"):
        jobs.append(("Private", f"{base}/schools/pss/directory/2021/?fips={fips}",
                     "name", "phone", "latitude", "longitude", "school_level"))
    if s.get("include_colleges"):
        jobs.append(("College", f"{base}/college-university/ipeds/directory/2022/?fips={fips}",
                     "inst_name", "phone_number", "latitude", "longitude", None))

    level_map = {1: "Elementary", 2: "Middle", 3: "High", 4: "Other K-12"}

    for label, url, nk, pk, latk, lngk, lvlk in jobs:
        try:
            page, pulled = url, 0
            while page:
                r = requests.get(page, headers=UA, timeout=40)
                r.raise_for_status()
                j = r.json()
                for row in j.get("results", []):
                    lat, lng = row.get(latk), row.get(lngk)
                    d = miles(lat, lng)
                    if d is None or d > rad:
                        continue
                    name = row.get(nk) or row.get("name") or "Unknown"
                    st = label if lvlk is None else level_map.get(row.get(lvlk), label)
                    out.append({
                        "id": f"school-{slug(name)}",
                        "category": "schools",
                        "school_type": st,
                        "name": name,
                        "city": row.get("city_mailing") or row.get("city") or "",
                        "address": " ".join(filter(None, [
                            row.get("street_mailing") or row.get("address"),
                            row.get("city_mailing") or row.get("city"),
                            "TX", str(row.get("zip_mailing") or "")])),
                        "phone": str(row.get(pk) or ""),
                        "website": row.get("inst_url") or "",
                        "lat": lat, "lng": lng,
                        "distance_mi": d,
                        "priority": 1 if "olleg" in st or "niversit" in st else 3,
                        "notes": "Auto-pulled. Find the librarian on the campus/district staff directory; weeding peaks April–May.",
                        "outreach_window": s.get("outreach_window", "April–May"),
                        "status": "new", "last_contacted": "", "outreach_notes": "",
                    })
                page = j.get("next")
                pulled += 1
                if pulled > 25:      # safety cap
                    break
                time.sleep(0.5)
            log(f"schools[{label}]: collected so far {len(out)}")
        except Exception as e:
            log(f"schools[{label}] FAILED: {e}")
    return out


# ── CIVICPLUS iCAL  (municipal calendars -> library/Friends sales) ────────────
def fetch_civicplus():
    out = []
    try:
        from icalendar import Calendar
    except Exception as e:
        log(f"icalendar not installed: {e}")
        return out
    for feed in CFG.get("civicplus_ical", []):
        try:
            r = requests.get(feed["url"], headers=UA, timeout=40)
            r.raise_for_status()
            cal = Calendar.from_ical(r.content)
            for ev in cal.walk("vevent"):
                title = str(ev.get("summary", ""))
                if "book" not in title.lower() and "sale" not in title.lower():
                    continue
                dt = ev.get("dtstart")
                ds = dt.dt.isoformat() if dt else ""
                if ds and ds[:10] < TODAY.isoformat():
                    continue
                out.append({
                    "id": f"civic-{slug(feed['name'])}-{slug(title)}-{ds[:10]}",
                    "source": feed["name"], "kind": "library_sale",
                    "title": title, "org": feed["name"],
                    "venue": str(ev.get("location", "")), "address": str(ev.get("location", "")),
                    "city": feed["name"].replace("City of ", ""),
                    "date_start": ds[:10], "date_note": "",
                    "url": str(ev.get("url", feed["url"])),
                    "details": str(ev.get("description", ""))[:400],
                })
            log(f"civicplus[{feed['name']}]: ok")
        except Exception as e:
            log(f"civicplus[{feed['name']}] FAILED: {e}")
    return out


# ── CRAIGSLIST RSS  (book lots / free books = Marketplace replacement) ────────
def fetch_craigslist():
    out = []
    try:
        import feedparser
    except Exception as e:
        log(f"feedparser not installed: {e}")
        return out
    cl = CFG.get("craigslist", {})
    for region in cl.get("regions", []):
        for sec in cl.get("sections", ["sss"]):
            for term in cl.get("search_terms", []):
                try:
                    q = requests.utils.quote(term)
                    url = f"https://{region}.craigslist.org/search/{sec}?query={q}&format=rss"
                    feed = feedparser.parse(url)
                    for e in feed.entries[:25]:
                        out.append({
                            "id": f"cl-{slug(region)}-{slug(e.get('title',''))[:40]}",
                            "source": f"Craigslist/{region}", "kind": "book_lot",
                            "title": e.get("title", ""), "org": "Craigslist seller",
                            "venue": "", "address": "", "city": region,
                            "date_start": e.get("updated", "")[:10] or TODAY.isoformat(),
                            "date_note": "listing date",
                            "url": e.get("link", ""),
                            "details": e.get("summary", "")[:300],
                        })
                    time.sleep(1.0)   # be polite
                except Exception as ex:
                    log(f"craigslist[{region}/{sec}/{term}] FAILED: {ex}")
    log(f"craigslist: {len(out)} hits")
    return out


# ── ESTATESALES.NET  (polite HTML scrape of upcoming sales) ───────────────────
def fetch_estatesales_net():
    out = []
    es = CFG.get("estatesales_net", {})
    if not es.get("enabled"):
        return out
    try:
        from bs4 import BeautifulSoup
        url = f"https://www.estatesales.net/TX/{es.get('zip','78412')}?radius={es.get('radius',50)}"
        r = requests.get(url, headers=UA, timeout=40)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # EstateSales.net markup changes periodically; anchors to sale pages are the
        # stable hook. Adjust the selector if the layout shifts.
        for a in soup.select("a[href*='/TX/']")[:40]:
            title = a.get_text(" ", strip=True)
            if not title or len(title) < 8:
                continue
            out.append({
                "id": f"es-{slug(title)[:48]}",
                "source": "EstateSales.net", "kind": "estate_sale",
                "title": title, "org": "", "venue": "", "address": "",
                "city": "", "date_start": "", "date_note": "see listing",
                "url": "https://www.estatesales.net" + a.get("href", ""),
                "details": "Estate sale — check listing for book/library mentions.",
            })
        log(f"estatesales.net: {len(out)} candidate listings")
    except Exception as e:
        log(f"estatesales.net FAILED: {e}")
    return out


# ── FIXED SCHEDULES  (sales that never hit any aggregator) ────────────────────
def expand_fixed_sales():
    out = []
    for s in CFG.get("fixed_schedule_sales", []):
        months = s.get("months", [])
        d = miles(s.get("lat"), s.get("lng"))
        if d is not None and d > RADIUS["book_sales"]:
            continue
        if months == list(range(1, 13)):   # ongoing
            out.append(_fixed_event(s, "ongoing", "During library hours", d))
            continue
        # next occurrence in each listed month within ~12 months
        for off in range(0, 13):
            m = ((TODAY.month - 1 + off) % 12) + 1
            y = TODAY.year + ((TODAY.month - 1 + off) // 12)
            if m in months:
                approx = datetime.date(y, m, 13)   # mid-month placeholder
                if approx >= TODAY:
                    out.append(_fixed_event(s, approx.isoformat(), s.get("note", ""), d))
    return out


def _fixed_event(s, date_start, note, d):
    return {
        "id": f"fixed-{slug(s['org'])}-{date_start}",
        "source": "Fixed schedule", "kind": "library_sale",
        "title": f"{s['org']} — Book Sale", "org": s["org"],
        "venue": s.get("venue", ""), "address": s.get("address", ""),
        "city": s.get("address", "").split(",")[-2].strip() if "," in s.get("address", "") else "",
        "lat": s.get("lat"), "lng": s.get("lng"),
        "date_start": date_start, "date_note": note,
        "distance_mi": d, "url": "", "details": s.get("note", ""),
    }


# ── merge + write ─────────────────────────────────────────────────────────────
def merge_leads(fresh):
    existing = load(DATA / "leads.json", "leads")
    by_id = {l["id"]: l for l in existing.get("leads", [])}
    for l in fresh:
        if l["id"] in by_id:
            # preserve user CRM fields
            for f in ("status", "last_contacted", "outreach_notes", "priority"):
                if by_id[l["id"]].get(f):
                    l[f] = by_id[l["id"]][f]
        by_id[l["id"]] = {**by_id.get(l["id"], {}), **l}
    return {"generated": TODAY.isoformat(),
            "note": existing.get("note", ""),
            "leads": sorted(by_id.values(),
                            key=lambda x: (x.get("category", ""), x.get("priority", 9)))}


def merge_sales(fresh):
    existing = load(DATA / "sales.json", "events")
    by_id = {e["id"]: e for e in existing.get("events", [])}
    for e in fresh:
        by_id[e["id"]] = {**by_id.get(e["id"], {}), **e}
    # keep upcoming + ongoing only
    keep = [e for e in by_id.values()
            if e.get("date_start") in ("", "ongoing")
            or e.get("date_start", "9999") >= TODAY.isoformat()]
    return {"generated": TODAY.isoformat(),
            "note": existing.get("note", ""),
            "events": sorted(keep, key=lambda x: (x.get("date_start") or "9999"))}


def main():
    log(f"center={CENTER}  radius={RADIUS}")

    leads = []
    leads += fetch_schools()
    DATA.joinpath("leads.json").write_text(json.dumps(merge_leads(leads), indent=2))
    log("wrote leads.json")

    sales = []
    sales += expand_fixed_sales()
    sales += fetch_civicplus()
    sales += fetch_craigslist()
    sales += fetch_estatesales_net()
    DATA.joinpath("sales.json").write_text(json.dumps(merge_sales(sales), indent=2))
    log("wrote sales.json")


if __name__ == "__main__":
    main()
