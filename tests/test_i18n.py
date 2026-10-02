"""The Burmese label map: complete, Unicode, Western digits, and honest about review."""

from __future__ import annotations

import pytest

from amber import config, i18n
from amber.i18n import ReviewReason


def test_text_and_fill_give_every_locale():
    assert i18n.text("No coup") == {"en": "No coup", "my": i18n.MY["No coup"]}
    filled = i18n.fill(config.DIVERGENCE_ANCHOR_TEMPLATE, year=1960)
    assert filled["en"] == "The path starts at Myanmar's actual 1960 level."
    assert "1960" in filled["my"] and "{year}" not in filled["my"]
    custom = i18n.fill(config.CUSTOM_SCENARIO_LABEL, base=i18n.text("No coup"))
    assert custom["en"] == "No coup, custom levers"
    assert custom["my"].startswith(i18n.MY["No coup"])


def test_an_untranslated_or_edited_english_string_fails_loudly():
    # Keyed by the English verbatim: editing a caveat in config breaks its lookup,
    # so a stale Burmese caveat cannot ship silently.
    with pytest.raises(KeyError, match="No Burmese translation"):
        i18n.text(config.SC_NOT_CREDIBLE_MESSAGE + " Edited.")


@pytest.mark.parametrize(
    ("my", "problem"),
    [
        ({"Myanmar": ""}, "empty translation"),
        ({"Starts in {year}.": "{anchor} မှ စတင်သည်။"}, "placeholders"),
        ({"Myanmar": "Myanmar"}, "no Burmese script"),
        # Zawgyi types the vowel sign E before its consonant; Unicode stores it after.
        ({"Myanmar": "ေမ်"}, "not Unicode Burmese"),
        ({"Myanmar": "မၠ"}, "not Unicode Burmese"),
        ({"In 2021": "၂၀၂၁ တွင်"}, "Myanmar digits"),
    ],
)
def test_the_validator_rejects_a_label_map_it_cannot_trust(my, problem):
    with pytest.raises(ValueError, match=problem):
        i18n._check_i18n(my=my, review={})


def test_a_review_flag_must_name_a_translated_string():
    with pytest.raises(ValueError, match="flagged for review but not translated"):
        i18n._check_i18n(my={}, review={"Not in the map": ReviewReason.HONESTY})


def test_the_unicode_check_accepts_real_burmese():
    assert i18n.is_unicode_burmese(i18n.MY["Myanmar"])
    assert all(i18n.is_unicode_burmese(burmese) for burmese in i18n.MY.values())


def test_every_honesty_caveat_is_flagged_for_human_review():
    honesty = {
        config.SCENARIO_FRAMING,
        config.SD_NOT_CREDIBLE_MESSAGE,
        config.SC_NOT_CREDIBLE_MESSAGE,
        config.COVERAGE_MESSAGE,
        config.DIVERGENCE_FRAMING,
        config.LOW_RELIABILITY_MESSAGE,
        config.MODELING_WINDOW_MESSAGE,
        config.DIVERGENCE_NO_INFERENCE_MESSAGE,
    }
    assert {
        text for text, reason in i18n.REVIEW.items() if reason is ReviewReason.HONESTY
    } >= honesty
    assert i18n.REVIEW["2021 coup"] is ReviewReason.NEUTRALITY


def test_every_configured_label_has_a_burmese_twin():
    labels = [
        *config.HISTORICAL_COUNTRIES.values(),
        *(ind.name for ind in config.INDICATORS),
        *(lever.label for lever in config.LEVERS.values()),
        *(lever.description for lever in config.LEVERS.values()),
        *(sc.label for sc in config.SCENARIOS),
        *(sc.description for sc in config.SCENARIOS),
        *(o.label for o in config.SC_OUTCOMES),
        *(e.label for e in config.HISTORICAL_EVENTS),
        *(c.label for c in config.DIVERGENCE_COMPARATORS.values()),
    ]
    assert [label for label in labels if label not in i18n.MY] == []
