#!/usr/bin/env python3
"""Daily internship scanner.

Pulls postings from public career-site APIs (Greenhouse, Lever, Ashby,
Workday, SmartRecruiters, Amazon, Microsoft, Google, TikTok), keeps intern
roles in the USA, Singapore or India that match research/engineering keywords, and
writes data/internships.json for internships.html.

Stdlib only so it runs anywhere (GitHub Actions, cron, laptop):
    python3 scripts/scan_internships.py
"""
import concurrent.futures as cf
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "internships.json"
UA = "Mozilla/5.0 (X11; Linux x86_64) internship-scanner"
TODAY = dt.date.today().isoformat()

# ---------------------------------------------------------------- sources
# (company display name, board token). "av" marks autonomy/robotics companies
# where every technical intern role is treated as core-relevant.
GREENHOUSE = [
    ("Waymo", "waymo", "av"), ("Nuro", "nuro", "av"), ("Motional", "motional", "av"),
    ("Wayve", "wayve", "av"), ("Kodiak", "kodiak", "av"), ("Figure AI", "figureai", "av"),
    ("Agility Robotics", "agilityrobotics", "av"), ("Anthropic", "anthropic", ""),
    ("Scale AI", "scaleai", ""), ("Databricks", "databricks", ""), ("Groww", "groww", ""),
]
LEVER = [
    ("Zoox", "zoox", "av"), ("Waabi", "waabi", "av"),
    ("Toyota Research Institute", "tri", "av"), ("Shield AI", "shieldai", "av"),
    ("Meesho", "meesho", ""), ("CRED", "cred", ""),
]
ASHBY = [
    ("OpenAI", "openai", ""), ("Skydio", "skydio", "av"),
    ("Physical Intelligence", "physicalintelligence", "av"), ("Cohere", "cohere", ""),
]
WORKDAY = [  # (name, tenant, wd host, site)
    ("NVIDIA", "nvidia", "wd5", "NVIDIAExternalCareerSite", ""),
    ("Intel", "intel", "wd1", "External", ""),
    ("Adobe", "adobe", "wd5", "external_experienced", ""),
]
SMARTRECRUITERS = [("Grab", "Grab", ""), ("Bosch", "BoschGroup", "")]

# Big-tech portals that block scripted access; linked on the page for manual checks.
MANUAL = [
    ("Apple", "https://jobs.apple.com/en-us/search?team=internships-STDNT-INTRN"),
    ("Meta", "https://www.metacareers.com/jobs?roles[0]=Internship"),
    ("Qualcomm", "https://careers.qualcomm.com/careers?query=intern"),
    ("Tesla", "https://www.tesla.com/careers/search/?type=3"),
    ("ByteDance", "https://jobs.bytedance.com/en/position?type=3"),
    ("Sea / Shopee", "https://careers.shopee.sg/jobs?level=1"),
    ("Flipkart", "https://www.flipkartcareers.com/#!/joblist"),
    ("Ola / Krutrim", "https://www.olakrutrim.com/careers"),
    ("Samsung R&D India", "https://research.samsung.com/careers"),
    ("A*STAR", "https://www.a-star.edu.sg/Scholarships/for-undergraduate-studies/a-star-research-internship-award-aria"),
]

# ---------------------------------------------------------------- filters
INTERN_RE = re.compile(r"\b(intern(ship)?s?|co-?op|student researcher|phd residen\w*|summer associate)\b", re.I)
CORE_RE = re.compile(
    r"autonom|self-driving|driving|vehicle|\bav\b|robot|planning|planner|motion|perception|"
    r"v2x|multi-agent|simulation|reinforcement|\brl\b|trajectory|prediction|behavior|mapping|"
    r"localization|slam|lidar|sensor fusion|embodied|drone|autonomy|\bcontrols\b|motion control|"
    r"chassis control", re.I)
RESEARCH_RE = re.compile(
    r"research|scien|\bphd\b|machine learning|\bml\b|\bai\b|deep learning|computer vision|"
    r"\bvision\b|\bllm|language model|generative|foundation model|\bnlp\b|multimodal|"
    r"agent|optimization|data scien", re.I)
HARDWARE_RE = re.compile(
    r"electrical|mechanical|hardware|asic|silicon|packaging|manufactur\w*|process engineer|"
    r"design engineer|firmware|rf\b|analog|circuit|thermal|materials", re.I)
ENG_RE = re.compile(r"software|engineer|developer|\bswe\b|systems|infrastructure|compiler|gpu|cuda|hpc", re.I)
EXCLUDE_RE = re.compile(
    r"\b(finance|financial|accounting|tax|audit|marketing|sales|legal|counsel|recruit\w*|"
    r"human resources|\bhr\b|people ops|supply chain|procurement|facilities|communications|"
    r"brand|content|creative|category management|operations intern|business|policy|"
    r"customer|account manage\w*|real estate|payroll|events?|social media|graphic|"
    r"product manage\w*|project manage\w*|program manage\w*|project intern|analyst|talent|"
    r"moderation|user research|designer|design intern|operations|technician|logistics|"
    r"quality|service engineer|plastics|risk control|governance)\b", re.I)

IN_RE = re.compile(
    r"\bindia\b|bengaluru|bangalore|hyderabad|\bpune\b|gurugram|gurgaon|noida|chennai|mumbai|"
    r"new delhi|\bdelhi\b|kolkata|ahmedabad", re.I)
US_STATES = ("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV "
             "NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC").split()
US_STATE_RE = re.compile(r"(,|\s-)\s*(" + "|".join(US_STATES) + r")\b")
US_WORDS_RE = re.compile(
    r"united states|\busa?\b|u\.s\.|california|washington|new york|texas|massachusetts|"
    r"pennsylvania|michigan|san francisco|mountain view|seattle|boston|pittsburgh|austin|"
    r"santa clara|palo alto|sunnyvale|foster city|redmond|bay area|los angeles|ann arbor|"
    r"san jose|san diego|atlanta|chicago|denver|remote.{0,4}(us|north america)", re.I)


def region_of(loc: str) -> str:
    if not loc:
        return ""
    if re.search(r"singapore", loc, re.I):
        return "SG"
    if IN_RE.search(loc):
        return "IN"
    if US_STATE_RE.search(loc) or US_WORDS_RE.search(loc):
        return "US"
    return ""


def classify(title: str, company_tag: str) -> str:
    """Return relevance tier: core / research / eng, or '' to drop."""
    if not INTERN_RE.search(title) or EXCLUDE_RE.search(title):
        return ""
    if HARDWARE_RE.search(title):
        return "eng"
    if CORE_RE.search(title):
        return "core"
    if RESEARCH_RE.search(title):
        return "core" if company_tag == "av" else "research"
    if ENG_RE.search(title):
        return "core" if company_tag == "av" else "eng"
    return ""


# ---------------------------------------------------------------- http
def get(url, data=None, headers=None, timeout=30):
    h = {"User-Agent": UA, "Accept": "application/json"}
    h.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h)
    for attempt in range(4):  # back off on rate limits / transient 5xx
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
            time.sleep(15 * 2 ** attempt)
    return raw if h["Accept"] != "application/json" else json.loads(raw)


def job(company, title, loc, url, posted="", tag=""):
    locs = [l.strip() for l in (loc if isinstance(loc, list) else [loc]) if l and l.strip()]
    regions = sorted({region_of(l) for l in locs} - {""})
    tier = classify(title, tag)
    if not tier or not regions:
        return None
    return {"company": company, "title": title.strip(), "location": "; ".join(locs[:4]),
            "regions": regions, "tier": tier, "url": url, "posted": (posted or "")[:10]}


def ts(sec_or_ms):
    if not sec_or_ms:
        return ""
    v = int(sec_or_ms)
    v = v / 1000 if v > 1e11 else v
    return dt.datetime.fromtimestamp(v, dt.timezone.utc).date().isoformat()


# ---------------------------------------------------------------- scrapers
def greenhouse(name, token, tag):
    d = get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    return [job(name, j["title"], j.get("location", {}).get("name", ""), j["absolute_url"],
                j.get("first_published") or j.get("updated_at", ""), tag) for j in d["jobs"]]


def lever(name, token, tag):
    d = get(f"https://api.lever.co/v0/postings/{token}?mode=json")
    return [job(name, j["text"], j.get("categories", {}).get("allLocations")
                or [j.get("categories", {}).get("location", "")], j["hostedUrl"],
                ts(j.get("createdAt")), tag) for j in d]


def ashby(name, token, tag):
    d = get(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
    out = []
    for j in d.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations", [])]
        out.append(job(name, j["title"], locs, j["jobUrl"], j.get("publishedAt", ""), tag))
    return out


def workday(name, tenant, host, site, tag):
    base = f"https://{tenant}.{host}.myworkdayjobs.com"
    api = f"{base}/wday/cxs/{tenant}/{site}"
    out = []
    for off in range(0, 400, 20):
        d = get(f"{api}/jobs", {"appliedFacets": {}, "limit": 20, "offset": off, "searchText": "intern"})
        posts = d.get("jobPostings", [])
        for p in posts:
            title = p.get("title", "")
            if not classify(title, tag):
                continue
            locs = [p.get("locationsText", "")]
            if re.match(r"\d+ Locations", locs[0] or ""):  # expand "3 Locations"
                try:
                    info = get(api + p["externalPath"])["jobPostingInfo"]
                    locs = [info.get("location", "")] + info.get("additionalLocations", [])
                except Exception:
                    pass
            out.append(job(name, title, locs, f"{base}/{site}{p['externalPath']}", "", tag))
        if len(posts) < 20:
            break
    return out


def smartrecruiters(name, token, tag):
    out = []
    for off in range(0, 1000, 100):
        d = get(f"https://api.smartrecruiters.com/v1/companies/{token}/postings?q=intern&limit=100&offset={off}")
        for j in d.get("content", []):
            l = j.get("location", {})
            loc = l.get("fullLocation") or f"{l.get('city', '')}, {l.get('country', '').upper()}"
            if (l.get("country") or "").lower() == "us" and not region_of(loc):
                loc += ", United States"
            out.append(job(name, j["name"], loc, f"https://jobs.smartrecruiters.com/{token}/{j['id']}",
                           j.get("releasedDate", ""), tag))
        if off + 100 >= d.get("totalFound", 0):
            break
    return out


def amazon():
    out = []
    for cc, country in (("USA", "United States"), ("SGP", "Singapore"), ("IND", "India")):
        for off in range(0, 1000, 100):
            d = get("https://www.amazon.jobs/en/search.json?base_query=intern&result_limit=100"
                    f"&offset={off}&normalized_country_code[]={cc}")
            for j in d.get("jobs", []):
                loc = f"{j.get('city', '')}, {j.get('state', '') or ''} {country}"
                try:
                    posted = dt.datetime.strptime(j.get("posted_date", ""), "%B %d, %Y").date().isoformat()
                except ValueError:
                    posted = ""
                out.append(job("Amazon", j["title"], loc, "https://www.amazon.jobs" + j["job_path"], posted))
            if off + 100 >= d.get("hits", 0):
                break
    return out


def microsoft():
    out = []
    for where in ("United States", "Singapore", "India"):
        for start in range(0, 300, 10):
            q = urllib.parse.urlencode({"domain": "microsoft.com", "query": "intern",
                                        "location": where, "start": start})
            d = get(f"https://apply.careers.microsoft.com/api/pcsx/search?{q}")["data"]
            for p in d.get("positions", []):
                out.append(job("Microsoft", p["name"], p.get("locations", []),
                               "https://apply.careers.microsoft.com" + p["positionUrl"], ts(p.get("postedTs"))))
            if start + 10 >= d.get("count", 0):
                break
            time.sleep(4)
    return out


def google():
    out = []
    for where in ("United States", "Singapore", "India"):
        for page in range(1, 15):
            q = urllib.parse.urlencode({"target_level": "INTERN_AND_APPRENTICE", "location": where, "page": page})
            s = get(f"https://www.google.com/about/careers/applications/jobs/results/?{q}",
                    headers={"Accept": "text/html"})
            m = re.search(r"AF_initDataCallback\(\{key: 'ds:1'.*?data:(.*?), sideChannel", s, re.S)
            if not m:
                break
            d = json.loads(m.group(1))
            rows = d[0] or []
            for r in rows:
                slug = re.sub(r"[^a-z0-9]+", "-", r[1].lower()).strip("-")
                locs = [l[0] for l in (r[9] or [])]
                out.append(job("Google", r[1], locs,
                               f"https://www.google.com/about/careers/applications/jobs/results/{r[0]}-{slug}",
                               ts((r[12] or [None])[0])))
            if not rows or page * 20 >= (d[2] or 0):
                break
    return out


def tiktok():
    out = []
    for off in range(0, 2000, 100):
        d = get("https://api.lifeattiktok.com/api/v1/public/supplier/search/job/posts",
                {"keyword": "intern", "limit": 100, "offset": off}, {"website-path": "tiktok"})["data"]
        for j in d.get("job_post_list", []):
            c, parts = j.get("city_info") or {}, []
            while c:
                parts.append(c.get("en_name") or "")
                c = c.get("parent")
            out.append(job("TikTok", j["title"], ", ".join(p for p in parts if p),
                           f"https://lifeattiktok.com/search/{j['id']}"))
        if off + 100 >= d.get("count", 0):
            break
    return out


def tasks():
    for n, t, g in GREENHOUSE:
        yield f"{n} (Greenhouse)", greenhouse, (n, t, g)
    for n, t, g in LEVER:
        yield f"{n} (Lever)", lever, (n, t, g)
    for n, t, g in ASHBY:
        yield f"{n} (Ashby)", ashby, (n, t, g)
    for n, t, h, s, g in WORKDAY:
        yield f"{n} (Workday)", workday, (n, t, h, s, g)
    for n, t, g in SMARTRECRUITERS:
        yield f"{n} (SmartRecruiters)", smartrecruiters, (n, t, g)
    yield "Amazon", amazon, ()
    yield "Microsoft", microsoft, ()
    yield "Google", google, ()
    yield "TikTok", tiktok, ()


# ---------------------------------------------------------------- main
def main():
    prev = {}
    if OUT.exists():
        try:
            prev = {j["url"]: j for j in json.loads(OUT.read_text())["jobs"]}
        except Exception:
            pass

    jobs, status = {}, []
    with cf.ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(fn, *args): label for label, fn, args in tasks()}
        for f in cf.as_completed(futs):
            label = futs[f]
            try:
                found = [j for j in f.result() if j]
                for j in found:
                    jobs.setdefault(j["url"], j)
                status.append({"source": label, "ok": True, "count": len(found)})
            except Exception as e:  # one broken board must not kill the run
                status.append({"source": label, "ok": False, "error": str(e)[:160]})
                print(f"[warn] {label}: {e}", file=sys.stderr)

    # A failed source keeps yesterday's postings instead of dropping them.
    failed = {s["source"].split(" (")[0] for s in status if not s["ok"]}
    for url, j in prev.items():
        if url not in jobs and j["company"] in failed:
            jobs[url] = j

    for url, j in jobs.items():
        j["first_seen"] = prev.get(url, {}).get("first_seen", TODAY)
        j["title"] = html.unescape(j["title"])

    order = {"core": 0, "research": 1, "eng": 2}
    ranked = sorted(jobs.values(), key=lambda j: (order[j["tier"]], j["first_seen"] != TODAY,
                                                  j["company"], j["title"]))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "sources": sorted(status, key=lambda s: s["source"]),
        "manual": [{"company": c, "url": u} for c, u in MANUAL],
        "jobs": ranked,
    }, indent=1, ensure_ascii=False) + "\n")
    new = sum(j["first_seen"] == TODAY for j in ranked)
    print(f"{len(ranked)} postings ({new} new) from {len(status) - len(failed)}/{len(status)} sources")


if __name__ == "__main__":
    main()
