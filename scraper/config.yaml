# ─────────────────────────────────────────────────────────────────────────────
# Book Source Dashboard — configuration
# Edit this file to change coverage. Each lead/source CATEGORY has its OWN radius.
# ─────────────────────────────────────────────────────────────────────────────

# Center point everything is measured from (Corpus Christi, TX)
center:
  lat: 27.8006
  lng: -97.3964

# ── Per-category radius (miles) ──────────────────────────────────────────────
# Change a number here and that category re-scopes on the next run.
radius_miles:
  schools: 110        # Kingsville (south) up to Victoria (north). Bump to 250 to pull in San Antonio + Houston.
  estate_companies: 45    # tighter — you physically drive to these pickups
  junk_removal: 45        # tighter — same reason
  book_sales: 90          # library / Friends sales worth a day trip

# ── Live event feeds (populate the "Live Feed" tab) ──────────────────────────
# CivicPlus municipal calendars expose an iCal feed; add the iCal URL for each town.
# Find it on the city's Calendar.aspx page -> "iCalendar" / RSS link.
civicplus_ical:
  - name: "City of Victoria"
    url: "https://www.victoriatx.gov/common/modules/iCalendar/iCalendar.aspx?catID=23&feed=calendar"
  # - name: "City of Corpus Christi"
  #   url: "PASTE_ICAL_URL_HERE"

# Craigslist regions to monitor (RSS). Searches run for each term below.
craigslist:
  regions:
    - "corpuschristi"     # https://corpuschristi.craigslist.org
    # - "victoriatx"
  search_terms:
    - "book lot"
    - "books free"
    - "estate books"
    - "library books"
  sections:               # craigslist category codes
    - "zip"               # free stuff
    - "sss"               # for-sale (all)

# Estate-sale aggregators (HTML scrape, polite). zip + radius set per site in the scraper.
estatesales_net:
  enabled: true
  zip: "78412"
  radius: 50

# Fixed-schedule sales that never get posted to aggregators (encode them once).
# These show up in the Live Feed automatically as their dates approach.
fixed_schedule_sales:
  - org: "Friends of the Victoria Public Library"
    venue: "Victoria Public Library"
    address: "302 N Main St, Victoria, TX 77901"
    lat: 28.8053
    lng: -97.0036
    months: [1, 5, 9]          # January, May, September every year
    note: "Member presale Sunday; open to public Mon–Fri during library hours. Most items $2 or less, cash/check only."
  - org: "Aransas County Public Library"
    venue: "Aransas County Public Library"
    address: "701 E Mimosa St, Rockport, TX 78382"
    lat: 28.0207
    lng: -97.0586
    months: [1,2,3,4,5,6,7,8,9,10,11,12]   # ongoing in-library sale
    note: "Ongoing book sale during library hours."

# ── School lead source ───────────────────────────────────────────────────────
# Pulls from the Urban Institute Education Data API (a clean JSON layer over NCES
# CCD public schools, PSS private schools, and IPEDS colleges). No giant downloads.
schools:
  include_public_k12: true
  include_private: true
  include_colleges: true
  state_fips: "48"        # Texas
  # Outreach reminder window — schools weed at year-end.
  outreach_window: "April–May (before year-end weeding)"
