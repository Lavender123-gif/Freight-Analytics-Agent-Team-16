"""Redaction engines (task 10 section 4). Synthetic sentences only; no dev text, no real names."""

import pytest

from freight_lineitems import redaction_variants as rv
from freight_lineitems import textprep
from freight_lineitems.config import RULES

LIGHT = ["presidio", "names_list", "allowlist"]
needs_model = pytest.mark.skipif(not rv.local_ner_available(), reason="local NER model is not in the Hugging Face cache")
ALL = [*LIGHT, pytest.param("local_ner", marks=needs_model)]


@pytest.fixture
def engine(monkeypatch):
    def select(name):
        monkeypatch.setenv("FL_REDACTION_ENGINE", name)
    return select


@pytest.mark.parametrize("name", ALL)
def test_context_name_is_masked_digits_and_charge_words_kept(engine, name):
    engine(name)
    text = "LIFTGATE $75.00 AND TONU 250 DETENTION 2 HRS APPROVED BY JENNIFER KOWALSKI ON 5/12/2022"
    red, n_person, _ = textprep.redact(text)
    assert "JENNIFER" not in red and "KOWALSKI" not in red
    assert n_person == 1 and "[PERSON_1]" in red
    for kept in ("LIFTGATE", "$75.00", "TONU", "250", "DETENTION", "5/12/2022"):
        assert kept in red
    assert not textprep.redaction_altered_digits(text, red)


@pytest.mark.parametrize("name", ALL)
def test_email_and_phone_handling_is_kept(engine, name):
    engine(name)
    red, _, n_email = textprep.redact("FUEL SURCHARGE 12.50 CALL 412-555-0100 OR WRITE TO PAT.EXAMPLE@EXAMPLE.COM")
    assert n_email == 1 and "[EMAIL_1]" in red and "[PHONE_1]" in red
    assert "EXAMPLE.COM" not in red and "12.50" in red and "FUEL SURCHARGE" in red


def test_presidio_engine_is_unchanged(monkeypatch):
    # the configured default became `allowlist` by the pre-stated selection rule (task 10 section 4); the old
    # engine must still behave exactly as before when selected
    monkeypatch.setenv("FL_REDACTION_ENGINE", "presidio")
    assert RULES["redaction"]["engine"] == "allowlist"
    called = []
    monkeypatch.setattr(rv, "spans", lambda *a: called.append(a) or [])
    monkeypatch.setattr(rv, "clip", lambda *a: called.append(a) or [])
    # the context rule still takes two words before 'FROM PPG', exactly as before the variants existed
    assert textprep.redact("ROAD CLOSURE ZED QUUX FROM PPG NOTIFIED $8.39")[0] == "ROAD CLOSURE [PERSON_1] FROM PPG NOTIFIED $8.39"
    assert textprep.person_spans("STORAGE $150 AS PER CONTRACT") == []
    assert called == []                      # the default path never enters the variants module


def test_unknown_engine_is_an_error_not_silent_no_redaction(engine):
    engine("presidoi")
    with pytest.raises(ValueError):
        textprep.redact("APPROVED BY JENNIFER KOWALSKI")


def test_email_only_engine_still_means_no_name_detector(engine):
    engine("email_only")
    assert textprep.redact("STORAGE 3 DAYS $150 JENNIFER")[0] == "STORAGE 3 DAYS $150 JENNIFER"


def test_names_list_masks_ambiguous_names_only_in_a_name_context(engine):
    engine("names_list")
    r = lambda t: textprep.redact(t)[0]
    assert r("TONU $250 PER BILL OF LADING 12345") == "TONU $250 PER BILL OF LADING 12345"
    assert r("PLEASE MARK THE PRICE AS PAID AND BILL TO PPG") == "PLEASE MARK THE PRICE AS PAID AND BILL TO PPG"
    assert r("DETENTION 2 HRS $100 PER BILL") == "DETENTION 2 HRS $100 PER [PERSON_1]"
    assert r("SPOKE WITH MARK PRICE RE FEE 45.00") == "SPOKE WITH [PERSON_1] RE FEE 45.00"
    assert r("REDELIVERY $60 MARK APPROVED") == "REDELIVERY $60 [PERSON_1] APPROVED"
    assert r("INVOICE DATED MAY 5 PER MAY STATEMENT") == "INVOICE DATED MAY 5 PER MAY STATEMENT"


def test_names_list_masks_listed_names_anywhere_and_carries_the_neighbour(engine):
    engine("names_list")
    r = lambda t: textprep.redact(t)[0]
    assert r("STORAGE 3 DAYS $150 JENNIFER") == "STORAGE 3 DAYS $150 [PERSON_1]"
    assert r("STORAGE 3 DAYS $150 JENNIFER ZZYZKOWICZ") == "STORAGE 3 DAYS $150 [PERSON_1]"      # surname in no list
    assert r("STORAGE 3 DAYS $150 JENNIFER PRICE") == "STORAGE 3 DAYS $150 [PERSON_1]"           # surname is a word
    assert r("CONFIRMED BY QWERTZU ZZYZKOWICZ $20") == "CONFIRMED BY [PERSON_1] $20"             # cue, both unknown
    assert r("SAME JENNIFER TWICE: JENNIFER") == "SAME [PERSON_1] TWICE: [PERSON_1]"


def test_single_name_before_from_ppg_does_not_take_the_charge_word(engine):
    """With the variants the older context rule cannot swallow the charge word in front of a one-word name."""
    engine("names_list")
    assert textprep.redact("ROAD CLOSURE JENNIFER FROM PPG NOTIFIED $8.39")[0] == "ROAD CLOSURE [PERSON_1] FROM PPG NOTIFIED $8.39"


def test_allowlist_masks_unknown_words_but_not_misspelled_charge_words(engine):
    engine("allowlist")
    r = lambda t: textprep.redact(t)[0]
    assert r("STORAGE 3 DAYS $150 ZZYZKOWICZ") == "STORAGE 3 DAYS $150 [PERSON_1]"
    assert r("TAILAGTE FEE 45.00 AND DETENTON 2 HRS") == "TAILAGTE FEE 45.00 AND DETENTON 2 HRS"
    assert r("LIFTGATE 75.00 PRO123ABC BOL 9988 INVOICE WAS SHORT PAID") == "LIFTGATE 75.00 PRO123ABC BOL 9988 INVOICE WAS SHORT PAID"
    assert rv.near_spelling("TAILAGTE") and not rv.near_spelling("ZZYZKOWICZ")


@pytest.mark.parametrize("name", ["names_list", "allowlist"])
def test_variants_never_touch_digits_or_ids(engine, name):
    engine(name)
    text = "REF JENNIFER7 AND 7KOWALSKI 20 000 LBS $1,234.56 [PERSON_3] ZED9"
    red = textprep.redact(text)[0]
    assert red == text                       # words glued to digits are IDs; an existing placeholder is left alone
    assert all(not any(ch.isdigit() for ch in text[a:b]) for a, b in textprep.person_spans(text))


def test_clip_removes_protected_words_and_digits_from_any_span():
    text = "LIFTGATE 75.00 JENNIFER"
    assert rv.clip(text, [(0, len(text))]) == [(15, 23)]


@needs_model
def test_local_ner_reads_uppercase_names(engine):
    engine("local_ner")
    red = textprep.redact("PLEASE CALL JENNIFER KOWALSKI ABOUT THE LIFTGATE CHARGE OF $75.00")[0]
    assert "KOWALSKI" not in red and "LIFTGATE" in red and "$75.00" in red


@needs_model
def test_union_of_engines(engine):
    engine("allowlist+local_ner")
    red = textprep.redact("STORAGE 3 DAYS $150 ZZYZKOWICZ. PLEASE CALL JENNIFER KOWALSKI ABOUT LIFTGATE $75.00")[0]
    assert "ZZYZKOWICZ" not in red and "KOWALSKI" not in red
    assert "STORAGE 3 DAYS $150" in red and "LIFTGATE $75.00" in red


def test_union_with_an_unknown_engine_is_an_error(engine):
    engine("allowlist+nope")
    with pytest.raises(ValueError):
        textprep.redact("APPROVED BY JENNIFER KOWALSKI")
