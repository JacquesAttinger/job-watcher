# Last edited: 2026-09-18 21:10 CDT
from watcher import sources


def test_simplify_keeps_only_active_visible(feed_text):
    postings = sources.parse_simplify(feed_text[sources.SIMPLIFY_URL])
    companies = {p.company for p in postings}
    assert "Salesforce" in companies
    assert "Loop" not in companies  # inactive row is dropped at parse time
    assert all(p.source == "simplify" for p in postings)


def test_simplify_na_term_becomes_unstated(feed_text):
    postings = sources.parse_simplify(feed_text[sources.SIMPLIFY_URL])
    utexas = next(p for p in postings if p.company.startswith("University of Texas"))
    assert utexas.terms == []


def test_zshah_fields(feed_text):
    postings = sources.parse_zshah(feed_text[sources.ZSHAH_URL])
    assert len(postings) == 4
    bracco = next(p for p in postings if p.company == "Bracco")
    assert bracco.terms == ["Summer 2027"]
    assert bracco.category == "Software"
    newsbreak = next(p for p in postings if p.company == "NewsBreak")
    assert newsbreak.terms == []  # "Not stated" -> unstated


def test_jobright_table_rows(feed_text):
    postings = sources.parse_jobright(feed_text[sources.JOBRIGHT_URL])
    assert len(postings) == 4
    copart = next(p for p in postings if p.company == "Copart")
    assert copart.title == "Software Engineering Intern"
    assert copart.source_id == "6a5380168576ec69c014fee5"
    assert copart.url.startswith("https://jobright.ai/jobs/info/")
    assert copart.terms == [] and copart.category is None


def test_speedyapply_rows_with_and_without_salary_column(feed_text):
    postings = sources.parse_speedyapply(feed_text[sources.SPEEDYAPPLY_URL])
    assert len(postings) == 3
    tiktok = next(p for p in postings if p.company == "TikTok")
    assert tiktok.title == "Software Engineer Intern - ML Infra - 2027 Summer"
    assert tiktok.locations == ["San Jose, CA"]
    assert tiktok.url == "https://lifeattiktok.com/search/7668584161852229893"
    abridge = next(p for p in postings if p.company == "Abridge")  # no salary column
    assert abridge.locations == ["San Francisco, CA"]
    assert all(p.source == "speedyapply" for p in postings)


def test_chieler_rows(feed_text):
    postings = sources.parse_chieler(feed_text[sources.CHIELER_URL])
    assert len(postings) == 3
    qualcomm = next(p for p in postings if p.company == "Qualcomm")
    assert qualcomm.title == "Low Power AI Software Development Intern"
    assert qualcomm.url == "https://qualcomm.eightfold.ai/careers/job/446721143440"
    assert all(p.source == "chieler" for p in postings)


def test_applyguy_uses_listing_url_and_cleans_unstated_season(feed_text):
    postings = sources.parse_applyguy(feed_text[sources.APPLYGUY_URL])
    assert len(postings) == 2
    applied = next(p for p in postings if p.company == "Applied Innovation")
    assert applied.url == "https://appliedinnovation.applytojob.com/apply/DWiAHxQUJn"
    assert applied.terms == []  # "Not specified" -> unstated
    athene = next(p for p in postings if p.company == "Athene")
    assert athene.terms == ["Summer 2027"]
    assert all(p.source == "applyguy" for p in postings)


def test_fetch_all_reports_failures_without_blocking(feed_text):
    def fetch(url):
        if url == sources.ZSHAH_URL:
            raise OSError("boom")
        if url == sources.JOBRIGHT_URL:
            return "no table here"
        return feed_text[url]

    postings, errors = sources.fetch_all(fetch)
    assert {p.source for p in postings} == {"simplify", "speedyapply", "chieler", "applyguy"}
    assert errors["zshah"].startswith("OSError")
    assert "0 postings" in errors["jobright"]
