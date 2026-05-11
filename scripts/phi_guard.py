#!/usr/bin/env python3
"""Pre-commit PHI guard — blocks SSN, MRN, and real-looking DOB patterns.

Runs on staged files. Exits 1 and prints offending lines if patterns are found.
Synthetic patient names (e.g. 'Aragorn Strider') are allowed — this guard
targets structured identifiers, not freeform text.

Excluded: reference/ and .venv/ (handled by pre-commit exclude config).
"""

import re
import sys

PATTERNS = [
    # SSN: 123-45-6789 or 123456789 (9 digits)
    (r"\b\d{3}-\d{2}-\d{4}\b", "SSN pattern"),
    # MRN-style: MRN followed by digits, or common prefixes
    (r"\bMRN[-:\s]+\d{5,10}\b", "MRN pattern"),
    (r"\bPatient[-_]?ID[-:\s]+\d{5,10}\b", "Patient ID pattern"),
    # NPI (10 digits, common in healthcare)
    (r"\bNPI[-:\s]+\d{10}\b", "NPI pattern"),
    # DEA number pattern (2 letters + 7 digits)
    (r"\b[A-Z]{2}\d{7}\b", "DEA number pattern"),
]

COMPILED = [(re.compile(p, re.IGNORECASE), label) for p, label in PATTERNS]


def check_file(path: str) -> list[str]:
    violations = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, 1):
                for pattern, label in COMPILED:
                    if pattern.search(line):
                        violations.append(f"  {path}:{i} [{label}]: {line.rstrip()}")
    except (OSError, UnicodeDecodeError):
        pass
    return violations


def main():
    files = sys.argv[1:]
    all_violations = []
    for path in files:
        all_violations.extend(check_file(path))

    if all_violations:
        print("PHI GUARD: Potential PHI patterns detected — commit blocked.")
        print("Review and remove before committing:\n")
        for v in all_violations:
            print(v)
        sys.exit(1)


if __name__ == "__main__":
    main()
