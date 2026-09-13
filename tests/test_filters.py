# Last edited: 2026-09-13 12:48 CDT
from watcher import sources
from watcher.filters import exclusion_reason, is_non_us
from watcher.models import Posting


def _by_company(feed_text, company):
    postings = sources.parse_simplify(feed_text[sources.SIMPLIFY_URL])
    return next(p for p in postings if p.company == company)


def test_software_summer_2027_us_passes(feed_text):
    assert exclusion_reason(_by_company(feed_text, "Salesforce")) is None


def test_phd_only_is_excluded():
    posting = Posting(
        "simplify", "1", "Citadel", "ML Research Intern", "u", terms=["Summer 2027"], degrees=["PhD"]
    )
    assert "bachelor" in exclusion_reason(posting)


def test_masters_only_is_excluded():
    posting = Posting("simplify", "1", "Acme", "SWE Intern", "u", terms=["Summer 2027"], degrees=["Master's"])
    assert "bachelor" in exclusion_reason(posting)


def test_bachelors_plus_masters_passes():
    posting = Posting(
        "simplify", "1", "Acme", "SWE Intern", "u", terms=["Summer 2027"], degrees=["Bachelor's", "Master's"]
    )
    assert exclusion_reason(posting) is None


def test_wrong_term_is_excluded(feed_text):
    assert "term" in exclusion_reason(_by_company(feed_text, "Etched.ai"))


def test_quant_category_is_excluded():
    posting = Posting(
        "simplify", "1", "Point72", "Quant Intern", "u", terms=["Summer 2027"], category="Quant"
    )
    assert "category" in exclusion_reason(posting)


def test_all_non_us_locations_excluded():
    posting = Posting(
        "simplify", "1", "Shopify", "SWE Intern", "u", locations=["Toronto, ON, Canada", "London, UK"]
    )
    assert "outside the US" in exclusion_reason(posting)


def test_mixed_locations_pass():
    posting = Posting("simplify", "1", "Shopify", "SWE Intern", "u", locations=["Toronto, ON, Canada", "NYC"])
    assert exclusion_reason(posting) is None


def test_unstated_term_and_category_pass(feed_text):
    utexas = _by_company(feed_text, "University of Texas at Austin")
    assert exclusion_reason(utexas) is None


def test_title_exclusion():
    posting = Posting("jobright", "1", "Acme", "Financial Analyst Intern", "u")
    assert "title" in exclusion_reason(posting)


def test_is_non_us_examples():
    assert is_non_us("Toronto, ON, Canada")
    assert is_non_us("London, UK")
    assert not is_non_us("Remote in USA")
    assert not is_non_us("USA, Eden Prairie, Minnesota, 55344")
    assert not is_non_us("SF")
    assert not is_non_us("")


def test_grad_level_and_non_tech_titles_excluded():
    for title in ("Grad Intern - Data Engineer", "Campus Graduate Masters Program", "Communications Intern"):
        assert "title" in exclusion_reason(Posting("zshah", "1", "Acme", title, "u")), title


def test_undergraduate_title_passes():
    posting = Posting("zshah", "1", "Amex", "Campus Undergraduate Summer Internship - AI Engineer", "u")
    assert exclusion_reason(posting) is None
