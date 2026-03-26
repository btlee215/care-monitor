import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ScoredPost:
    subreddit: str
    tier: int
    post_id: str
    title: str
    body: str
    url: str
    author: str
    created_utc: float
    score: int
    priority_label: str
    reason: str


class Scorer:
    def __init__(self, config: dict):
        self.config = config
        self.settings = config.get("settings", {})
        self.min_score = self.settings.get("min_score", 2)

        # Build sub_to_tier lookup
        self.sub_to_tier: dict[str, int] = {}
        for tier_key, subs in config.get("subreddits", {}).items():
            tier_num = int(tier_key.replace("tier", ""))
            for sub in subs:
                self.sub_to_tier[sub.lower()] = tier_num

        kw = config.get("keywords", {})
        self.p1 = kw.get("priority1_cgt", {})
        self.p2 = kw.get("priority2_routing", {})
        self.p3 = kw.get("priority3_prior_auth", {})
        self.p4 = kw.get("priority4_general_navigation", {})

        excl = config.get("exclusions", {})
        self.skip_patterns = excl.get("skip_if_match", [])
        self.override_patterns = excl.get("override_exclusion_if", [])

    @staticmethod
    def _match_any(text: str, patterns: list) -> Optional[str]:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return pattern
        return None

    def evaluate(self, post) -> Optional[ScoredPost]:
        subreddit_name = post.subreddit.display_name
        tier = self.sub_to_tier.get(subreddit_name.lower())
        if tier is None:
            return None

        title = post.title or ""
        body = post.selftext or ""
        full_text = f"{title} {body}"

        # Check exclusions
        skip_hit = self._match_any(full_text, self.skip_patterns)
        if skip_hit:
            override_hit = self._match_any(full_text, self.override_patterns)
            if not override_hit:
                return None

        # P1: CGT — requires both match_any AND require_any
        p1_match = self._match_any(full_text, self.p1.get("match_any", []))
        if p1_match:
            p1_require = self._match_any(full_text, self.p1.get("require_any", []))
            if p1_require:
                return ScoredPost(
                    subreddit=subreddit_name,
                    tier=tier,
                    post_id=post.id,
                    title=title,
                    body=body,
                    url=f"https://reddit.com{post.permalink}",
                    author=str(post.author),
                    created_utc=post.created_utc,
                    score=5,
                    priority_label="P1 CGT",
                    reason=f"CGT match: '{p1_match}' + access context: '{p1_require}'",
                )

        # P2: Routing
        p2_match = self._match_any(full_text, self.p2.get("match_any", []))
        if p2_match:
            return ScoredPost(
                subreddit=subreddit_name,
                tier=tier,
                post_id=post.id,
                title=title,
                body=body,
                url=f"https://reddit.com{post.permalink}",
                author=str(post.author),
                created_utc=post.created_utc,
                score=4,
                priority_label="P2 Routing",
                reason=f"Routing barrier: '{p2_match}'",
            )

        # P3: Prior auth
        p3_match = self._match_any(full_text, self.p3.get("match_any", []))
        if p3_match:
            return ScoredPost(
                subreddit=subreddit_name,
                tier=tier,
                post_id=post.id,
                title=title,
                body=body,
                url=f"https://reddit.com{post.permalink}",
                author=str(post.author),
                created_utc=post.created_utc,
                score=3,
                priority_label="P3 Prior Auth",
                reason=f"Prior auth issue: '{p3_match}'",
            )

        # P4: General navigation — only for tier 1-2
        if tier <= 2:
            p4_match = self._match_any(full_text, self.p4.get("match_any", []))
            if p4_match:
                return ScoredPost(
                    subreddit=subreddit_name,
                    tier=tier,
                    post_id=post.id,
                    title=title,
                    body=body,
                    url=f"https://reddit.com{post.permalink}",
                    author=str(post.author),
                    created_utc=post.created_utc,
                    score=2,
                    priority_label="P4 General Navigation",
                    reason=f"Navigation need: '{p4_match}'",
                )

        return None
