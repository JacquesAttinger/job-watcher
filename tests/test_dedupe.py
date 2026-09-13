# Last edited: 2026-09-13 12:48 CDT
from watcher.models import Posting, normalize_text


def test_same_company_and_title_across_sources_share_a_key():
    a = Posting("simplify", "1", "Stripe", "Software Engineer Intern", "https://a")
    b = Posting("jobright", "2", "Stripe", "Software Engineer, Intern", "https://b")
    assert a.key == b.key


def test_different_titles_differ():
    a = Posting("simplify", "1", "Stripe", "Software Engineer Intern", "https://a")
    b = Posting("simplify", "2", "Stripe", "Data Engineer Intern", "https://b")
    assert a.key != b.key


def test_missing_company_falls_back_to_url():
    a = Posting("zshah", "1", "", "SWE Intern", "https://x")
    assert a.key == "url|https://x"


def test_normalize_text():
    assert normalize_text("  Data & ML/AI  Intern!! ") == "data and ml ai intern"


def test_round_trip_dict():
    a = Posting("simplify", "1", "Stripe", "SWE Intern", "u", terms=["Summer 2027"], locations=["NYC"])
    assert Posting.from_dict(a.to_dict()) == a
