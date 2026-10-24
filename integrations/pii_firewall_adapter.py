import re
import hashlib
from typing import Tuple, List, Dict, Any


def validate_luhn(number_str: str) -> bool:
    """Validate numeric string using the Luhn (Mod-10) algorithm."""
    digits = re.sub(r"\D", "", number_str)
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    reverse_digits = digits[::-1]
    for i, char in enumerate(reverse_digits):
        d = int(char)
        if i % 2 == 1:
            d = d * 2
            if d > 9:
                d = d - 9
        total += d
    return total % 10 == 0


def validate_ssn(ssn_str: str) -> bool:
    """Validate US Social Security Number format and regulatory exclusion rules."""
    clean = re.sub(r"\D", "", ssn_str)
    if len(clean) != 9:
        return False
    area = int(clean[:3])
    group = int(clean[3:5])
    serial = int(clean[5:])
    if area == 0 or area == 666 or (900 <= area <= 999):
        return False
    if group == 0 or serial == 0:
        return False
    return True


CARD_PATTERN = re.compile(r"\b(?:\d[ \-]*?){13,19}\b")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
STRIPE_PATTERN = re.compile(r"\b(?:sk|pk)_(?:live|test)_[0-9a-zA-Z]{24,}\b")
AWS_KEY_PATTERN = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
)


class PIIFirewallAdapter:
    """Enterprise Data Loss Prevention (DLP) adapter guarding prompts, tools, and audit logs."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def sanitize_text(self, text: str, mode: str = "PARTIAL_MASK") -> Tuple[str, List[Dict[str, Any]]]:
        if not self.enabled or not text:
            return text, []

        findings = []
        occupied_spans = []

        # 1. Private Keys
        for m in PRIVATE_KEY_PATTERN.finditer(text):
            start, end = m.span()
            occupied_spans.append((start, end))
            findings.append({
                "type": "PRIVATE_KEY",
                "start": start,
                "end": end,
                "replacement": "[REDACTED_PRIVATE_KEY_BLOCK]"
            })

        # 2. Secret API Keys
        for m in STRIPE_PATTERN.finditer(text):
            start, end = m.span()
            occupied_spans.append((start, end))
            raw = m.group()
            findings.append({
                "type": "API_KEY_STRIPE",
                "start": start,
                "end": end,
                "replacement": raw[:8] + "XXXX...XXXX"
            })

        for m in AWS_KEY_PATTERN.finditer(text):
            start, end = m.span()
            occupied_spans.append((start, end))
            findings.append({
                "type": "API_KEY_AWS",
                "start": start,
                "end": end,
                "replacement": "AKIAXXXX...XXXX"
            })

        # 3. SSN
        for m in SSN_PATTERN.finditer(text):
            start, end = m.span()
            raw = m.group()
            if validate_ssn(raw):
                occupied_spans.append((start, end))
                digits = re.sub(r"\D", "", raw)
                findings.append({
                    "type": "SSN",
                    "start": start,
                    "end": end,
                    "replacement": f"XXX-XX-{digits[-4:]}"
                })

        # 4. PAN Card
        for m in CARD_PATTERN.finditer(text):
            start, end = m.span()
            raw = m.group()
            digits = re.sub(r"\D", "", raw)
            if 13 <= len(digits) <= 19 and validate_luhn(digits):
                occupied_spans.append((start, end))
                findings.append({
                    "type": "CREDIT_CARD",
                    "start": start,
                    "end": end,
                    "replacement": f"{digits[:4]}-XXXX-XXXX-{digits[-4:]}"
                })

        # Replace in reverse order so character offsets remain invariant
        findings.sort(key=lambda x: x["start"], reverse=True)
        sanitized = text
        for f in findings:
            sanitized = sanitized[:f["start"]] + f["replacement"] + sanitized[f["end"]:]

        findings.reverse()  # Return in natural reading order
        return sanitized, findings


pii_firewall = PIIFirewallAdapter(enabled=True)
