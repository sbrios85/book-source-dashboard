#!/usr/bin/env python3
"""
Book Source Dashboard — data builder.

Reads scraper/config.yaml, pulls every enabled source, and writes:
  data/sales.json      (Live Feed: library/Friends sales, estate sales, book lots)
  data/leads.json      (Outreach: estate cos, junk haulers, school libraries)
  data/libraries.json  (every public library in radius; powers Library Sales tab
                        and the library rows in the Outreach tab)

Robustness: each source is wrapped so one broken feed never kills the run.
Merges by stable `id` and PRESERVES manual fields you edit in the dashboard
(status / last_contacted / outreach_notes / librarian_* / fol_facebook / sales_notes).
Network calls only succeed where the runner has open egress (GitHub Actions).
"""

import json, math, re, io, csv, zipfile, datetime, pathlib, time
import yaml, requests

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"
CFG = yaml.safe_load((HERE / "config.yaml").read_text())

CENTER = (CFG["center"]["lat"], CFG["center"]["lng"])
RADIUS = CFG["radius_miles"]
UA = {"User-Agent": "book-source-dashboard/1.0 (personal sourcing tool)"}
TODAY = datetime.date.today()

# High-school outreach is limited to these areas: Nueces County, San Patricio County,
# Kingsville (Kleberg), and Victoria. (Other school types are not restricted.)
HS_KEEP_CITIES = {
    # Nueces County
    "corpus christi", "robstown", "agua dulce", "banquete", "bishop", "driscoll",
    "port aransas", "petronila",
    # San Patricio County
    "sinton", "portland", "ingleside", "aransas pass", "mathis", "taft", "gregory",
    "odem", "edroy", "st. paul", "st paul", "lake city", "lakeside",
    # Kingsville (Kleberg)
    "kingsville", "riviera", "ricardo",
    # Victoria
    "victoria",
}

def hs_allowed(school_type, city):
    """High schools are kept only in the target areas; everything else passes through."""
    if school_type != "High":
        return True
    return (city or "").strip().lower() in HS_KEEP_CITIES


# Library OUTREACH region — the hand-drawn boundary: San Antonio + I-10 corridor to Houston/
# Galveston + the full coast down to Kingsville + back up through Alice/Pleasanton. Libraries
# inside this polygon go on the Outreach (who-to-call) list; the Library Sales tab still shows
# the wider 250-mi set. Vertices are (lng, lat), traced clockwise.
OUTREACH_POLYGON = [
    (-98.75, 29.82), (-98.02, 29.78), (-97.35, 29.55), (-96.30, 29.78),
    (-95.70, 30.05), (-95.45, 30.18), (-95.10, 29.95), (-94.88, 29.55),
    (-94.78, 29.28), (-95.36, 28.94), (-96.00, 28.66), (-96.42, 28.40),
    (-97.05, 27.83), (-97.38, 27.30), (-97.72, 27.40), (-98.10, 27.78),
    (-98.20, 28.55), (-98.50, 29.10), (-98.78, 29.45), (-98.75, 29.82),
]


def in_outreach_region(lat, lng):
    if lat is None or lng is None:
        return False
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return False
    poly = OUTREACH_POLYGON
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def miles(lat, lng):
    if lat is None or lng is None:
        return None
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180) or (lat == 0 and lng == 0):
        return None
    R = 3958.8
    p1, p2 = math.radians(CENTER[0]), math.radians(lat)
    dphi = math.radians(lat - CENTER[0]); dlmb = math.radians(lng - CENTER[1])
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def load(path, key):
    try:
        return json.loads(path.read_text())
    except Exception:
        return {key: []}


def log(m): print(f"[build] {m}", flush=True)


def _pick(header, *cands):
    low = {h.lower(): h for h in header}
    for c in cands:
        if c.lower() in low:
            return low[c.lower()]
    return None


# ── PUBLIC LIBRARIES (IMLS PLS Outlet file) ──────────────────────────────────
def parse_outlet_csv(text):
    out = []
    reader = csv.DictReader(io.StringIO(text))
    hdr = reader.fieldnames or []
    c_name = _pick(hdr, "LIBNAME", "LIBRARY", "NAME")
    c_lat = _pick(hdr, "LATITUDE", "LATITUD", "LAT", "Y")
    c_lng = _pick(hdr, "LONGITUD", "LONGITUDE", "LONG", "LON", "X")
    c_state = _pick(hdr, "STABR", "STATE")
    c_addr = _pick(hdr, "ADDRESS", "ADDRES")
    c_city = _pick(hdr, "CITY")
    c_zip = _pick(hdr, "ZIP")
    c_phone = _pick(hdr, "PHONE")
    c_type = _pick(hdr, "C_OUT_TY")
    c_county = _pick(hdr, "CNTY", "COUNTY")
    if not (c_name and c_lat and c_lng):
        log(f"outlet CSV missing key columns; header sample={hdr[:8]}")
        return out
    type_map = {"CE": "Central", "BR": "Branch", "BS": "Bookmobile", "BM": "Books-by-Mail"}
    want_state = CFG.get("imls", {}).get("state", "TX").upper()
    keep_bm = CFG.get("imls", {}).get("include_bookmobiles", False)
    rad = RADIUS["library_sales"]
    for row in reader:
        if c_state and (row.get(c_state) or "").upper() != want_state:
            continue
        otype = (row.get(c_type) or "").upper() if c_type else ""
        if not keep_bm and otype in ("BS", "BM"):
            continue
        d = miles(row.get(c_lat), row.get(c_lng))
        if d is None or d > rad:
            continue
        name = (row.get(c_name) or "").strip().title()
        city = (row.get(c_city) or "").strip().title()
        addr = (row.get(c_addr) or "").strip().title()
        zc = (row.get(c_zip) or "").strip()
        full = ", ".join(filter(None, [addr, city, f"{want_state} {zc}".strip()]))
        out.append({
            "id": f"lib-{slug(name)}-{slug(city)}",
            "name": name, "city": city, "address": full,
            "phone": (row.get(c_phone) or "").strip() if c_phone else "",
            "website": "", "lat": float(row[c_lat]), "lng": float(row[c_lng]),
            "distance_mi": d, "outlet_type": type_map.get(otype, "Library"),
            "in_outreach": in_outreach_region(row.get(c_lat), row.get(c_lng)),
            "county": (row.get(c_county) or "").strip().title() if c_county else "",
            "librarian_name": "", "librarian_phone": "", "librarian_email": "",
            "fol_facebook": "", "sales_notes": "",
            "status": "new", "last_contacted": "", "outreach_notes": "",
        })
    return out


def fetch_libraries():
    im = CFG.get("imls", {})
    if not im.get("enabled"):
        return []
    try:
        url = im["outlet_csv_zip_url"]
        log(f"downloading IMLS zip: {url}")
        r = requests.get(url, headers=UA, timeout=120)
        r.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        cand = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        outlet = next((n for n in cand if "outlet" in n.lower()), None)
        rows = []
        if outlet:
            rows = parse_outlet_csv(zf.read(outlet).decode("latin-1", errors="replace"))
            log(f"parsed outlet file {outlet}: {len(rows)} TX libraries in radius")
        if not rows:
            for n in cand:
                rows = parse_outlet_csv(zf.read(n).decode("latin-1", errors="replace"))
                if rows:
                    log(f"parsed {n} (fallback): {len(rows)} libraries")
                    break
        return rows
    except Exception as e:
        log(f"IMLS libraries FAILED: {e}")
        return []


def merge_libraries(fresh):
    existing = load(DATA / "libraries.json", "libraries")
    by_id = {l["id"]: l for l in existing.get("libraries", [])}
    MANUAL = ("librarian_name", "contact_title", "librarian_phone", "librarian_email", "fol_facebook",
              "sales_notes", "status", "last_contacted", "follow_up", "outreach_notes", "website")
    for l in fresh:
        if l["id"] in by_id:
            for f in MANUAL:
                if by_id[l["id"]].get(f):
                    l[f] = by_id[l["id"]][f]
        by_id[l["id"]] = {**by_id.get(l["id"], {}), **l}
    return {"generated": TODAY.isoformat(), "note": existing.get("note", ""),
            "radii": {"outreach": RADIUS["libraries_outreach"], "library_sales": RADIUS["library_sales"]},
            "libraries": sorted(by_id.values(), key=lambda x: (x.get("distance_mi") or 9999, x.get("name", "")))}


# ── SCHOOLS (Urban Institute Education Data API over NCES) ────────────────────
def fetch_schools():
    out = []
    s = CFG.get("schools", {})
    fips = s.get("state_fips", "48"); rad = RADIUS["schools"]
    base = "https://educationdata.urban.org/api/v1"
    jobs = []
    if s.get("include_public_k12"):
        jobs.append(("Public K-12", f"{base}/schools/ccd/directory/2022/?fips={fips}",
                     "school_name", "phone", "latitude", "longitude", "school_level"))
    if s.get("include_private"):
        # PSS is biennial; the API ingests years on a lag. Try newest-first.
        pss = None
        for y in (2021, 2019, 2017):
            u = f"{base}/schools/pss/directory/{y}/?fips={fips}"
            try:
                if requests.get(u, headers=UA, timeout=30).status_code == 200:
                    pss = u; break
            except Exception:
                pass
        if pss:
            jobs.append(("Private", pss, "name", "phone", "latitude", "longitude", "school_level"))
        else:
            log("schools[Private]: no working PSS year found, skipping")
    if s.get("include_colleges"):
        jobs.append(("College", f"{base}/college-university/ipeds/directory/2022/?fips={fips}",
                     "inst_name", "phone_number", "latitude", "longitude", None))
    level_map = {1: "Elementary", 2: "Middle", 3: "High", 4: "Other K-12"}
    for label, url, nk, pk, latk, lngk, lvlk in jobs:
        try:
            page, pulled = url, 0
            while page:
                r = requests.get(page, headers=UA, timeout=40); r.raise_for_status()
                j = r.json()
                for row in j.get("results", []):
                    d = miles(row.get(latk), row.get(lngk))
                    if d is None or d > rad:
                        continue
                    name = row.get(nk) or row.get("name") or "Unknown"
                    st = label if lvlk is None else level_map.get(row.get(lvlk), label)
                    # Outreach focuses on high schools, colleges, universities (more/better discards).
                    if st in ("Elementary", "Middle"):
                        continue
                    city_now = (row.get("city_mailing") or row.get("city") or "").strip().title()
                    # High schools restricted to Nueces / San Patricio / Kingsville / Victoria.
                    if not hs_allowed(st, city_now):
                        continue
                    out.append({
                        "id": f"school-{slug(name)}", "category": "schools", "school_type": st,
                        "name": name, "city": (row.get("city_mailing") or row.get("city") or "").strip().title(),
                        "address": " ".join(filter(None, [row.get("street_mailing") or row.get("address"),
                                  row.get("city_mailing") or row.get("city"), "TX", str(row.get("zip_mailing") or "")])),
                        "phone": str(row.get(pk) or ""), "website": row.get("inst_url") or "",
                        "lat": row.get(latk), "lng": row.get(lngk), "distance_mi": d,
                        "priority": 1 if ("olleg" in st or "niversit" in st) else 3,
                        "notes": "Auto-pulled. Find the librarian on the campus/district staff directory; weeding peaks April–May.",
                        "outreach_window": s.get("outreach_window", "April–May"),
                        "librarian_name": "", "librarian_phone": "", "librarian_email": "",
                        "status": "new", "last_contacted": "", "outreach_notes": "",
                    })
                page = j.get("next"); pulled += 1
                if pulled > 25:
                    break
                time.sleep(0.5)
            log(f"schools[{label}]: total {len(out)}")
        except Exception as e:
            log(f"schools[{label}] FAILED: {e}")
    return out


# ── CIVICPLUS iCAL ────────────────────────────────────────────────────────────
def fetch_civicplus():
    out = []
    try:
        from icalendar import Calendar
    except Exception as e:
        log(f"icalendar missing: {e}"); return out
    for feed in CFG.get("civicplus_ical", []):
        try:
            r = requests.get(feed["url"], headers=UA, timeout=40); r.raise_for_status()
            cal = Calendar.from_ical(r.content)
            for ev in cal.walk("vevent"):
                title = str(ev.get("summary", ""))
                if "book" not in title.lower() and "sale" not in title.lower():
                    continue
                dt = ev.get("dtstart"); ds = dt.dt.isoformat() if dt else ""
                if ds and ds[:10] < TODAY.isoformat():
                    continue
                out.append({"id": f"civic-{slug(feed['name'])}-{slug(title)}-{ds[:10]}",
                    "source": feed["name"], "kind": "library_sale", "title": title, "org": feed["name"],
                    "venue": str(ev.get("location", "")), "address": str(ev.get("location", "")),
                    "city": feed["name"].replace("City of ", ""), "date_start": ds[:10], "date_note": "",
                    "url": str(ev.get("url", feed["url"])), "details": str(ev.get("description", ""))[:400]})
            log(f"civicplus[{feed['name']}]: ok")
        except Exception as e:
            log(f"civicplus[{feed['name']}] FAILED: {e}")
    return out


# ── CRAIGSLIST RSS ────────────────────────────────────────────────────────────
def fetch_craigslist():
    out = []
    try:
        import feedparser
    except Exception as e:
        log(f"feedparser missing: {e}"); return out
    cl = CFG.get("craigslist", {})
    for region in cl.get("regions", []):
        for sec in cl.get("sections", ["sss"]):
            for term in cl.get("search_terms", []):
                try:
                    q = requests.utils.quote(term)
                    url = f"https://{region}.craigslist.org/search/{sec}?query={q}&format=rss"
                    feed = feedparser.parse(url)
                    for e in feed.entries[:25]:
                        out.append({"id": f"cl-{slug(region)}-{slug(e.get('title',''))[:40]}",
                            "source": f"Craigslist/{region}", "kind": "book_lot", "title": e.get("title", ""),
                            "org": "Craigslist seller", "venue": "", "address": "", "city": region,
                            "date_start": e.get("updated", "")[:10] or TODAY.isoformat(),
                            "date_note": "listing date", "url": e.get("link", ""), "details": e.get("summary", "")[:300]})
                    time.sleep(1.0)
                except Exception as ex:
                    log(f"craigslist[{region}/{sec}/{term}] FAILED: {ex}")
    log(f"craigslist: {len(out)} hits")
    return out


# ── ESTATESALES.NET ───────────────────────────────────────────────────────────
def fetch_estatesales_net():
    out = []
    es = CFG.get("estatesales_net", {})
    if not es.get("enabled"):
        return out
    try:
        from bs4 import BeautifulSoup
        url = f"https://www.estatesales.net/TX/{es.get('city','Corpus-Christi')}/{es.get('zip','78412')}"
        r = requests.get(url, headers=UA, timeout=40); r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("a[href*='/TX/']")[:50]:
            title = a.get_text(" ", strip=True)
            if not title or len(title) < 8:
                continue
            out.append({"id": f"es-{slug(title)[:48]}", "source": "EstateSales.net", "kind": "estate_sale",
                "title": title, "org": "", "venue": "", "address": "", "city": "", "date_start": "",
                "date_note": "see listing", "url": "https://www.estatesales.net" + a.get("href", ""),
                "details": "Estate sale — check listing for book/library mentions."})
        log(f"estatesales.net: {len(out)} candidates")
    except Exception as e:
        log(f"estatesales.net FAILED: {e}")
    return out


# ── FIXED SCHEDULES ───────────────────────────────────────────────────────────
def expand_fixed_sales():
    out = []
    for s in CFG.get("fixed_schedule_sales", []):
        months = s.get("months", [])
        d = miles(s.get("lat"), s.get("lng"))
        if d is not None and d > RADIUS["book_sales"]:
            continue
        if months == list(range(1, 13)):
            out.append(_fixed_event(s, "ongoing", "During library hours", d)); continue
        for off in range(0, 13):
            m = ((TODAY.month - 1 + off) % 12) + 1
            y = TODAY.year + ((TODAY.month - 1 + off) // 12)
            if m in months:
                approx = datetime.date(y, m, 13)
                if approx >= TODAY:
                    out.append(_fixed_event(s, approx.isoformat(), s.get("note", ""), d))
    return out


def _fixed_event(s, date_start, note, d):
    return {"id": f"fixed-{slug(s['org'])}-{date_start}", "source": "Fixed schedule",
        "kind": "library_sale", "title": f"{s['org']} — Book Sale", "org": s["org"],
        "venue": s.get("venue", ""), "address": s.get("address", ""),
        "city": s.get("address", "").split(",")[-2].strip() if "," in s.get("address", "") else "",
        "lat": s.get("lat"), "lng": s.get("lng"), "date_start": date_start, "date_note": note,
        "distance_mi": d, "url": "", "details": s.get("note", "")}


# ── merge + write (leads & sales) ─────────────────────────────────────────────
def merge_leads(fresh):
    existing = load(DATA / "leads.json", "leads")
    by_id = {l["id"]: l for l in existing.get("leads", [])}
    # Drop any elementary/middle schools that were stored before we narrowed scope.
    by_id = {k: v for k, v in by_id.items()
             if v.get("school_type") not in ("Elementary", "Middle")}
    # Drop high schools outside the target areas (Nueces / San Patricio / Kingsville / Victoria).
    by_id = {k: v for k, v in by_id.items()
             if hs_allowed(v.get("school_type"), v.get("city"))}
    for l in fresh:
        if l["id"] in by_id:
            for f in ("status", "last_contacted", "follow_up", "outreach_notes", "priority",
                      "librarian_name", "contact_title", "librarian_phone", "librarian_email"):
                if by_id[l["id"]].get(f):
                    l[f] = by_id[l["id"]][f]
        by_id[l["id"]] = {**by_id.get(l["id"], {}), **l}
    merged = sorted(by_id.values(), key=lambda x: (x.get("category", ""), x.get("priority", 9)))
    for l in merged:
        if l.get("city"):
            l["city"] = l["city"].strip().title()
    return {"generated": TODAY.isoformat(), "note": existing.get("note", ""),
            "leads": merged}


def merge_sales(fresh):
    existing = load(DATA / "sales.json", "events")
    by_id = {e["id"]: e for e in existing.get("events", [])}
    for e in fresh:
        by_id[e["id"]] = {**by_id.get(e["id"], {}), **e}
    keep = [e for e in by_id.values() if e.get("date_start") in ("", "ongoing")
            or e.get("date_start", "9999") >= TODAY.isoformat()]
    return {"generated": TODAY.isoformat(), "note": existing.get("note", ""),
            "events": sorted(keep, key=lambda x: (x.get("date_start") or "9999"))}


def main():
    log(f"center={CENTER}  radius={RADIUS}")

    leads = fetch_schools()
    DATA.joinpath("leads.json").write_text(json.dumps(merge_leads(leads), indent=2))
    log("wrote leads.json")

    libs = fetch_libraries()
    DATA.joinpath("libraries.json").write_text(json.dumps(merge_libraries(libs), indent=2))
    log("wrote libraries.json")

    sales = expand_fixed_sales() + fetch_civicplus() + fetch_craigslist() + fetch_estatesales_net()
    DATA.joinpath("sales.json").write_text(json.dumps(merge_sales(sales), indent=2))
    log("wrote sales.json")


if __name__ == "__main__":
    main()
