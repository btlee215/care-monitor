import sys
import time
from dataclasses import dataclass
from typing import Optional

import yaml

from scorer import Scorer


@dataclass
class FakeSubreddit:
    display_name: str


@dataclass
class FakePost:
    subreddit: FakeSubreddit
    id: str
    title: str
    selftext: str
    permalink: str
    author: str
    created_utc: float


def make_post(sub: str, title: str, body: str = "") -> FakePost:
    return FakePost(
        subreddit=FakeSubreddit(display_name=sub),
        id=f"fake_{sub}_{int(time.time())}",
        title=title,
        selftext=body,
        permalink=f"/r/{sub}/comments/fake/",
        author="test_user",
        created_utc=time.time(),
    )


def run_tests(scorer: Scorer):
    tests = [
        # (description, post, expected_score)
        (
            "CAR-T + insurance mention on multiplemyeloma → score 5",
            make_post("multiplemyeloma", "CAR-T therapy question", "Does insurance cover CAR-T treatment?"),
            5,
        ),
        (
            "CASGEVY + scheduling on sicklecell → score 5",
            make_post("sicklecell", "CASGEVY approval", "I got approved for CASGEVY but don't know about scheduling next steps."),
            5,
        ),
        (
            "gene therapy mention without access context on lymphoma → score 0",
            make_post("lymphoma", "gene therapy is amazing", "I read about gene therapy in a journal article. Very interesting science."),
            0,
        ),
        (
            "passed around between specialists on breastcancer → score 4",
            make_post("breastcancer", "So frustrated", "I keep getting passed around between specialists and nobody is helping."),
            4,
        ),
        (
            "can't get appointment on cancer → score 4",
            make_post("cancer", "Can't get an appointment", "I can't get an appointment anywhere. The wait is ridiculous."),
            4,
        ),
        (
            "prior auth denied on lupus → score 3",
            make_post("lupus", "Insurance nightmare", "My prior authorization was denied and I don't know what to do."),
            3,
        ),
        (
            "newly diagnosed overwhelmed on leukemia (tier 1) → score 2",
            make_post("leukemia", "Newly diagnosed", "I was just diagnosed and I'm completely overwhelmed. Where do I even start?"),
            2,
        ),
        (
            "newly diagnosed overwhelmed on ChronicIllness (tier 5) → score 0",
            make_post("ChronicIllness", "Newly diagnosed", "I was just diagnosed and I'm completely overwhelmed. Where do I even start?"),
            0,
        ),
        (
            "billing complaint on cancer → score 0",
            make_post("cancer", "Billing error on my account", "I was overcharged on my last bill. There's a billing error I need to fix."),
            0,
        ),
        (
            "out-of-network referral on cancer → score 4 (exclusion override)",
            make_post("cancer", "Out of network issue", "I was overcharged and also got referred to the wrong out of network specialist. No one is coordinating my care."),
            4,
        ),
        (
            "GLP-1 cost question on HealthInsurance → score 0",
            make_post("HealthInsurance", "GLP-1 coverage", "How much does semaglutide cost? Is GLP-1 covered? Looking into weight loss medication options."),
            0,
        ),
    ]

    passed = 0
    failed = 0

    for desc, post, expected in tests:
        result = scorer.evaluate(post)
        actual = result.score if result else 0
        ok = actual == expected
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        label = result.priority_label if result else "None"
        reason = result.reason if result else "no match"
        print(f"[{status}] {desc}")
        if not ok:
            print(f"       Expected score={expected}, got score={actual} (label={label}, reason={reason})")
        else:
            print(f"       score={actual}, label={label}")

    print(f"\n{passed}/{passed + failed} tests passed.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    scorer = Scorer(config)
    run_tests(scorer)
