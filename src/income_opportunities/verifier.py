"""
Online Income Opportunities Verification & Safety Analysis.
Hard-rejection rules for scams and non-work content, caution signals, platform
trust tiers matched by exact domain, and link checks for alert candidates.

Statuses: 'verified_source' (known platform or your own entry), 'needs_review'
(unknown source), 'risk_flagged' (caution signals) and 'rejected'.
"""

from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from src.config import LinkVerificationConfig
from src.income_opportunities.models import (
    OnlineIncomeOpportunity,
    OpportunityStatus,
    SourceTrustTier,
)
from src.verifier import LinkVerifier

# Established platforms, matched on the registered domain of the listing or application URL.
# Names alone are not trusted: any listing can call itself "Outlier" or put "review" in a URL.
KNOWN_PLATFORM_DOMAINS: Dict[str, SourceTrustTier] = {
    "dataannotation.tech": SourceTrustTier.TIER_1_HIGHEST,
    "outlier.ai": SourceTrustTier.TIER_1_HIGHEST,
    "remotasks.com": SourceTrustTier.TIER_1_HIGHEST,
    "oneforma.com": SourceTrustTier.TIER_1_HIGHEST,
    "centific.com": SourceTrustTier.TIER_1_HIGHEST,
    "telusinternational.com": SourceTrustTier.TIER_1_HIGHEST,
    "telusinternational.ai": SourceTrustTier.TIER_1_HIGHEST,
    "telusdigital.com": SourceTrustTier.TIER_1_HIGHEST,
    "appen.com": SourceTrustTier.TIER_1_HIGHEST,
    "proofreading.org": SourceTrustTier.TIER_1_HIGHEST,
    "cambridgeproofreading.com": SourceTrustTier.TIER_1_HIGHEST,
    "scribbr.com": SourceTrustTier.TIER_1_HIGHEST,
    "enago.com": SourceTrustTier.TIER_1_HIGHEST,
    "academicpositions.com": SourceTrustTier.TIER_1_HIGHEST,
    "usertesting.com": SourceTrustTier.TIER_2_GOOD,
    "testbirds.com": SourceTrustTier.TIER_2_GOOD,
    "respondent.io": SourceTrustTier.TIER_2_GOOD,
    "prolific.com": SourceTrustTier.TIER_2_GOOD,
    "prolific.co": SourceTrustTier.TIER_2_GOOD,
    "preply.com": SourceTrustTier.TIER_2_GOOD,
    "cambly.com": SourceTrustTier.TIER_2_GOOD,
    "rev.com": SourceTrustTier.TIER_2_GOOD,
    "gotranscript.com": SourceTrustTier.TIER_2_GOOD,
    "modsquad.com": SourceTrustTier.TIER_2_GOOD,
    "belaysolutions.com": SourceTrustTier.TIER_2_GOOD,
    "timeetc.com": SourceTrustTier.TIER_2_GOOD,
}


def platform_for_url(url: Optional[str]) -> Optional[Tuple[str, SourceTrustTier]]:
    """(domain, tier) when the URL's host is a known platform domain or one of its subdomains."""
    host = urlparse(url or "").netloc.lower().split(":")[0]
    for domain, tier in KNOWN_PLATFORM_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return domain, tier
    return None


# ==============================================================================
# HARD REJECTION RULES: NON-WORK, SCHEMES, SCAMS, & ARTICLE NOISE
# ==============================================================================
HARD_REJECTION_RULES = [
    # 1. Non-Work Content / Advice / SEO Side-Hustle Articles / Listicles
    (
        r"\b(\d+\s+(?:best\s+)?ways\s+to\s+make\s+money|how\s+to\s+make\s+money\s+online|side\s+hustle\s+ideas|how\s+to\s+start\s+a\s+side\s+hustle|passive\s+income\s+(?:ideas|guide|streams|blueprint)|monetize\s+your\s+blog|freelance\s+tips|best\s+websites\s+to\s+earn|top\s+\d+\s+ways\s+to\s+earn|how\s+i\s+made\s+\$\d+)\b",
        "Non-work article, guide, or SEO listicle (not a concrete paid work opportunity)"
    ),
    # 2. Affiliate Marketing / Dropshipping / E-Commerce / Social Influencer
    (
        r"\b(affiliate\s+marketing|affiliate\s+commissions?|dropshipping|e-?commerce\s+(?:store|business)|shopify\s+store\s+builder|amazon\s+fba\s+business|influencer\s+brand\s+deal|youtube\s+monetization|tiktok\s+shop|blogging\s+for\s+profit)\b",
        "E-commerce, dropshipping, affiliate marketing, or social influencer monetization"
    ),
    # 3. Courses, Coaching Programs, Paid Starter Packages & Upfront Fees
    (
        r"\b(buy\s+(?:our|this)\s+course|paid\s+masterclass|mentorship\s+program|coaching\s+package|starter\s+kit\s+fee|upfront\s+fee|registration\s+fee|pay\s+\$\d+\s+to\s+start|training\s+deposit|starter\s+package|purchase\s+a\s+license)\b",
        "Requires paid course, coaching, upfront registration fee, or starter kit"
    ),
    # 4. Multi-Level Marketing (MLM) & Recruitment Pyramids
    (
        r"\b(recruit\s+(?:\d+|others|friends)|downline\s+commission|multi-?level\s+marketing|mlm|pyramid\s+scheme|matrix\s+marketing|referral\s+downline|build\s+your\s+team)\b",
        "Multi-Level Marketing (MLM) or team recruitment scheme"
    ),
    # 5. Crypto, Trading, Staking, Forex & Gambling
    (
        r"\b(crypto\s+trading|forex\s+trading|forex\s+signals|binary\s+options|bitcoin\s+deposit|invest\s+and\s+earn|high-yield\s+investment|sports\s+betting|casino\s+payout|gambling\s+bot|yield\s+farming|crypto\s+wallet\s+deposit|trade\s+crypto\s+for\s+profit)\b",
        "Cryptocurrency trading, Forex, binary options, staking, or gambling/betting"
    ),
    # 6. Check Cashing, Wire Transfers, Money Forwarding & Mystery Shopper Scams
    (
        r"\b(receive\s+funds|transfer\s+money|cash\s+(?:a\s+)?check|deposit\s+(?:a\s+)?check|mystery\s+shopper\s+check|wire\s+funds|forward\s+payments|package\s+mule|send\s+your\s+bvn|send\s+banking\s+pin)\b",
        "Suspicious money forwarding, check cashing, or financial credential request"
    ),
    # 7. Guaranteed Wealth / Get Rich Quick Claims
    (
        r"\b(make\s+\$\d{3,}\s+(?:a|per)\s+day\s+guaranteed|guaranteed\s+(?:\$\d+|\d+k\s+monthly)|get\s+rich\s+quick|easy\s+passive\s+wealth|earn\s+\$\d{4,}\s+weekly\s+from\s+home\s+guaranteed)\b",
        "Unrealistic guaranteed income or get-rich-quick claim"
    ),
    # 8. "Start Your Own Business" / Commission-Only Schemes
    (
        r"\b(start\s+your\s+own\s+business|be\s+your\s+own\s+boss\s+today|100%\s+commission\s+only\s+opportunity|commission-only\s+sales\s+rep)\b",
        "Vague business-opportunity pitch or commission-only scheme"
    ),
]

# Mild Risk / Cautionary Signatures
CAUTION_SIGNATURES = [
    (r"\b(telegram\s+only|contact\s+via\s+whatsapp\s+only|inbox\s+for\s+details|dm\s+on\s+instagram)\b", "Communication restricted to Telegram/WhatsApp/Social DM"),
    (r"\b(no\s+skills\s+required\s+\$\d{2,}\/hr)\b", "High hourly claim with zero requirements"),
    (r"\b(gift\s+cards?\s+only)\b", "Payment offered exclusively in gift cards"),
]


class HardRejectionClassifier:
    """Classifies whether an opportunity is a scam, a scheme or non-work advice."""

    @staticmethod
    def evaluate(opp: OnlineIncomeOpportunity) -> Tuple[bool, List[str]]:
        """Scans title, organization, description, URL and tags. Returns (is_rejected, reasons)."""
        text_to_scan = f"{opp.title} {opp.organization} {opp.description} {opp.url} {' '.join(opp.tags)}".lower()
        reasons = [reason for pattern, reason in HARD_REJECTION_RULES if re.search(pattern, text_to_scan, re.IGNORECASE)]
        return bool(reasons), reasons


def analyze_opportunity_safety(opp: OnlineIncomeOpportunity) -> OnlineIncomeOpportunity:
    """Assigns trust tier, legitimacy and risk indicators, and the verification status."""
    text_to_scan = f"{opp.title} {opp.organization} {opp.description} {opp.url}".lower()
    legitimacy_points: List[str] = []
    risk_points: List[str] = []

    platform = platform_for_url(opp.application_url) or platform_for_url(opp.url)
    if platform:
        domain, tier = platform
        opp.source_trust_tier = tier
        opp.source_type = "official_portal" if tier == SourceTrustTier.TIER_1_HIGHEST else "verified_platform"
        legitimacy_points.append(f"Known platform ({domain})")
    elif opp.source == "custom":
        opp.source_trust_tier = SourceTrustTier.TIER_2_GOOD
        legitimacy_points.append(f"Added by you ({opp.organization})")
    else:
        opp.source_trust_tier = SourceTrustTier.TIER_3_REVIEW

    if opp.url.startswith("https://"):
        legitimacy_points.append("Secure HTTPS application link")
    if opp.last_reviewed:
        legitimacy_points.append(f"Catalogue entry, last reviewed {opp.last_reviewed}")

    is_rejected, rejection_reasons = HardRejectionClassifier.evaluate(opp)
    if is_rejected:
        risk_points.extend(rejection_reasons)
        opp.rejection_reasons = rejection_reasons

    for pattern, reason in CAUTION_SIGNATURES:
        if re.search(pattern, text_to_scan, re.IGNORECASE):
            risk_points.append(reason)
    if opp.review_overdue:
        risk_points.append(f"Catalogue entry overdue for review (last reviewed {opp.last_reviewed or 'never'})")

    opp.legitimacy_indicators = legitimacy_points
    opp.scam_risk_indicators = risk_points

    if is_rejected:
        opp.verification_status = "rejected"
        opp.status = OpportunityStatus.REJECTED
        opp.is_verified = False
    elif risk_points:
        opp.verification_status = "risk_flagged"
        opp.status = OpportunityStatus.NEEDS_REVIEW
    elif opp.source_trust_tier in (SourceTrustTier.TIER_1_HIGHEST, SourceTrustTier.TIER_2_GOOD):
        opp.verification_status = "verified_source"
        opp.status = OpportunityStatus.VERIFIED
    else:
        opp.verification_status = "needs_review"
        opp.status = OpportunityStatus.NEEDS_REVIEW
    return opp


class IncomeOpportunityVerifier:
    """Safety screening for every opportunity and link checks for alert candidates."""

    def __init__(self, link_verifier: Optional[LinkVerifier] = None):
        self.link_verifier = link_verifier if link_verifier is not None else LinkVerifier()

    @staticmethod
    def screen(opportunities: List[OnlineIncomeOpportunity]) -> Tuple[List[OnlineIncomeOpportunity], List[OnlineIncomeOpportunity]]:
        """(accepted, rejected) after safety analysis. No network access."""
        accepted: List[OnlineIncomeOpportunity] = []
        rejected: List[OnlineIncomeOpportunity] = []
        for opp in opportunities:
            analyze_opportunity_safety(opp)
            (rejected if opp.verification_status == "rejected" else accepted).append(opp)
        return accepted, rejected

    async def check_links(self, opportunities: List[OnlineIncomeOpportunity], config: Optional[LinkVerificationConfig] = None) -> Dict[str, str]:
        """Checks application links. Marks dead ones expired; returns {fingerprint: link status}."""
        targets = {opp.fingerprint: (opp.application_url or opp.url) for opp in opportunities}
        results = await self.link_verifier.verify_many(targets.values(), config)
        statuses: Dict[str, str] = {}
        for opp in opportunities:
            result = results.get(targets[opp.fingerprint])
            if result is None:
                continue
            statuses[opp.fingerprint] = result.status
            opp.link_verification_status = result.reason
            if result.is_dead:
                opp.is_verified = False
                opp.status = OpportunityStatus.EXPIRED
                opp.scam_risk_indicators.append(f"Link closed or missing ({result.reason})")
                if opp.verification_status == "verified_source":
                    opp.verification_status = "needs_review"
        return statuses
