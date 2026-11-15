"""Tests for the NASA OSDR search (GET /api/osdr/search) and the reference topics (GET /api/reference?topic=)."""
import json
from datetime import datetime, timedelta, timezone

import pytest

import osdr
import reference
from app import create_app


def hit(acc, title="A study", organism="Mus musculus", released=1684886400, description="Purpose: something.", **extra):
    source = {"Accession": acc, "Study Title": title, "organism": organism, "Material Type": "Heart",
              "Study Factor Type": "Ionizing Radiation", "Study Public Release Date": released, "Study Description": description}
    source.update(extra)
    return {"_source": source}


def answer(*hits, total=None):
    return {"hits": {"total": len(hits) if total is None else total, "hits": list(hits)}}


@pytest.fixture(autouse=True)
def fresh_cache():
    osdr.clear_cache()
    yield
    osdr.clear_cache()


@pytest.fixture
def env(tmp_path):
    calls = []
    replies = {"cgene": answer(hit("OSD-334", "HZE heart"), hit("OSD-720")), "alsda": answer(hit("OSD-435", "Echo"), hit("OSD-591"))}

    def fake(url):
        calls.append(url)
        kind = "alsda" if "type=alsda" in url else "cgene"
        reply = replies[kind]
        if isinstance(reply, Exception):
            raise reply
        return reply

    app = create_app(tmp_path / "o.db", osdr_fetch=fake)
    return app.test_client(), calls, replies


# ---------- query cleaning ----------
@pytest.mark.parametrize("raw,clean", [("  radiation   heart ", "radiation heart"), ("HZE, O-16", "HZE, O-16"), ("a+b", "a+b")])
def test_clean_query_accepts_ordinary_terms(raw, clean):
    assert osdr.clean_query(raw) == clean


@pytest.mark.parametrize("bad", ["", " ", "a", "x" * 101, "heart; DROP TABLE", "<script>alert(1)</script>", "a&b=c", "q\nr\x00", 5, None])
def test_clean_query_rejects_odd_input(bad):
    with pytest.raises(ValueError):
        osdr.clean_query(bad)


# ---------- parsing and the search ----------
def test_results_are_mapped_labelled_and_linked(env):
    c, calls, _ = env
    body = c.get("/api/osdr/search?q=radiation heart&size=4").get_json()
    assert body["source"] == "external" and body["type"] == "all" and body["shown"] == 4 and body["total"] == 4
    first = body["results"][0]
    assert first["accession"] == "OSD-334" and first["title"] == "HZE heart" and first["label"] == "external"
    assert first["url"] == "https://osdr.nasa.gov/bio/repo/data/studies/OSD-334" and first["released"] == "2023-05-24"
    assert first["data_type_name"] == "NASA GeneLab" and "not comparable" in body["note"]
    assert any("term=radiation+heart" in u and "type=alsda" in u for u in calls)


def test_the_two_archives_are_interleaved(env):
    c, _, _ = env
    order = [r["data_type"] for r in c.get("/api/osdr/search?q=heart&size=4").get_json()["results"]]
    assert order == ["cgene", "alsda", "cgene", "alsda"]


def test_single_archive_and_size_limit(env):
    c, calls, _ = env
    body = c.get("/api/osdr/search?q=heart&type=alsda&size=1").get_json()
    assert [r["accession"] for r in body["results"]] == ["OSD-435"] and len(calls) == 1 and "type=cgene" not in calls[0]


def test_no_release_date_is_none_and_bad_hits_are_dropped(env):
    c, _, replies = env
    replies["cgene"] = answer(hit("OSD-1", released=0), {"_source": {"Accession": "not an accession"}}, {"x": 1}, hit("OSD-2", released=None))
    replies["alsda"] = answer()
    body = c.get("/api/osdr/search?q=zero").get_json()
    assert [r["accession"] for r in body["results"]] == ["OSD-1", "OSD-2"]
    assert all(r["released"] is None for r in body["results"])


def test_text_from_nasa_is_returned_as_plain_text_and_summaries_are_short(env):
    c, _, replies = env
    replies["cgene"] = answer(hit("OSD-9", title="<b>bold</b> & \"quotes\"", description="word " * 200))
    replies["alsda"] = answer()
    r = c.get("/api/osdr/search?q=markup").get_json()["results"][0]
    assert r["title"] == "<b>bold</b> & \"quotes\""                 # unchanged: the dashboard writes it with textContent
    assert len(r["summary"]) <= osdr.DESCRIPTION_CHARS + 3


def test_results_are_cached_for_ten_minutes(env):
    c, calls, _ = env
    c.get("/api/osdr/search?q=cache me")
    n = len(calls)
    again = c.get("/api/osdr/search?q=CACHE ME").get_json()
    assert len(calls) == n and again["cached"] is True
    count = {"n": 0}

    def counting(url):
        count["n"] += 1
        return answer(hit("OSD-3"))

    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    osdr.search("ttl check", "alsda", 5, fetch=counting, now=t0)
    osdr.search("ttl check", "alsda", 5, fetch=counting, now=t0 + timedelta(seconds=osdr.CACHE_TTL_S - 1))
    assert count["n"] == 1                                          # still cached
    osdr.search("ttl check", "alsda", 5, fetch=counting, now=t0 + timedelta(seconds=osdr.CACHE_TTL_S + 1))
    assert count["n"] == 2                                          # expired, fetched again


def test_network_failure_is_a_clean_502(env):
    c, _, replies = env
    replies["cgene"] = TimeoutError("timed out")
    answerr = c.get("/api/osdr/search?q=offline")
    assert answerr.status_code == 502 and "could not be reached" in answerr.get_json()["message"]


def test_an_unexpected_answer_shape_does_not_crash(env):
    c, _, replies = env
    replies["cgene"] = {"unexpected": True}
    replies["alsda"] = ["not", "a", "dict"]
    body = c.get("/api/osdr/search?q=odd").get_json()
    assert body["results"] == [] and body["total"] == 0


def test_input_checks_on_the_endpoint(env):
    c, calls, _ = env
    for url in ("/api/osdr/search", "/api/osdr/search?q=", "/api/osdr/search?q=a", "/api/osdr/search?q=ok&type=esa",
                "/api/osdr/search?q=ok&size=0", "/api/osdr/search?q=ok&size=21", "/api/osdr/search?q=ok&size=x",
                "/api/osdr/search?q=%3Cscript%3E"):
        assert c.get(url).status_code == 400, url
    assert calls == []                                              # nothing reached NASA


# ---------- reference topics ----------
def test_reference_items_have_topics_and_can_be_filtered(env):
    c, _, _ = env
    everything = c.get("/api/reference").get_json()
    assert everything["count"] >= 15 and all(isinstance(i["topics"], list) for i in everything["items"])
    radiation = c.get("/api/reference?topic=radiation").get_json()
    ids = {i["id"] for i in radiation["items"]}
    assert {"nasa-ochmo-tb-020", "noaa-swpc-radiation-storms", "osdr-435-591-radiation-heart", "osdr-964-biosentinel"} <= ids
    assert all("radiation" in i["topics"] for i in radiation["items"])
    assert c.get("/api/reference?topic=nonsense").status_code == 400


def test_the_osdr_entries_are_external_reviewable_and_honest_about_what_was_read():
    items = {i["id"]: i for i in reference.load()}
    osdr_items = [i for k, i in items.items() if k.startswith("osdr-")]
    assert len(osdr_items) >= 8
    for item in osdr_items:
        assert item["label"] == "external" and item["status"] == "needs_review"
        assert item["source_url"].startswith("https://osdr.nasa.gov/")
        assert item["cannot_be_compared"] and item["statements"]
    assert "Only the description was read" in " ".join(items["osdr-435-591-radiation-heart"]["cannot_be_compared"]) or \
           "results were not read" in " ".join(items["osdr-435-591-radiation-heart"]["cannot_be_compared"])
    finding = " ".join(items["osdr-search-finding"]["statements"])
    assert "no study" in finding and "actigraphy" in finding


def test_a_bad_topic_in_the_file_is_rejected(tmp_path):
    good = json.loads(reference.DEFAULT_PATH.read_text(encoding="utf-8"))["items"][0]
    for bad in (["unknown"], "radiation", [1]):
        path = tmp_path / "r.json"
        path.write_text(json.dumps({"items": [{**good, "topics": bad}]}), encoding="utf-8")
        with pytest.raises(ValueError):
            reference.load(path)
    path.write_text(json.dumps({"items": [{k: v for k, v in good.items() if k != "topics"}]}), encoding="utf-8")
    assert reference.load(path)[0]["topics"] == []                  # topics are optional
