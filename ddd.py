#!/usr/bin/env python3
"""Structure rules for digital data donation packages: extract, combine, compare, check, generate.

    python3 ddd.py add      <package.zip> --platform instagram --lang en [--date 2026-11-23]
    python3 ddd.py extract  <package.zip> --platform instagram -o snapshot.json
    python3 ddd.py diff     <a> <b>          # each a package zip, a snapshot .json or a structures/<platform> folder
    python3 ddd.py check    <package.zip> --platform instagram
    python3 ddd.py generate --platform instagram -o synthetic.zip [--lang en] [--records 5] [--seed 1]

`add` merges a package into structures/<platform>/ (files.yaml, schemas/, LIMITS.md).
Only the structure is stored: never the package, and never a value from it.
Needs Python 3.9 or newer and nothing else.
"""
import argparse
import json
import os
import sys

from dddtools.combined import Combined, as_snapshot, compare
from dddtools.extract import extract, package_date
from dddtools.generate import Generator

ROOT = os.path.dirname(os.path.abspath(__file__))


def structures(platform):
    return os.path.join(ROOT, "structures", platform)


def rules(combined):
    """The hand-edited extraction rules of a platform: its own wording and its personal keys."""
    return combined.meta["wording"], combined.meta["personal_keys"]


def platform_rules(platform):
    return rules(Combined(structures(platform), platform))


def load(target, platform=None):
    """A snapshot from a zip, a snapshot file or a structures folder."""
    if os.path.isdir(target):
        return as_snapshot(Combined(target))
    if target.endswith(".json"):
        with open(target, encoding="utf-8") as f:
            return json.load(f)
    if not platform:
        sys.exit("--platform is needed to read a package")
    return extract(target, platform, *platform_rules(platform))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add", help="merge a package into the platform's combined structure")
    p.add_argument("package")
    p.add_argument("--platform", required=True)
    p.add_argument("--lang", required=True, help="language of the package's field labels, e.g. en, de, nl")
    p.add_argument("--date", help="export date (YYYY-MM-DD); default: the newest entry date in the zip")

    p = sub.add_parser("extract", help="write one package's structure to a snapshot file (for review)")
    p.add_argument("package")
    p.add_argument("--platform", required=True)
    p.add_argument("-o", "--output", required=True)

    p = sub.add_parser("diff", help="show what differs between two packages, snapshots or structures")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--platform")

    p = sub.add_parser("check", help="show what a package has that the combined structure doesn't know yet")
    p.add_argument("package")
    p.add_argument("--platform", required=True)

    p = sub.add_parser("generate", help="build a synthetic package from the combined structure")
    p.add_argument("--platform", required=True)
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--lang", help="use only labels seen in this language")
    p.add_argument("--records", type=int, default=5, help="maximum items per list")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--date", help="export date of the synthetic package; default: newest package date")
    p.add_argument("--include-old", action="store_true", help="also files and keys marked 'not seen since'")

    a = ap.parse_args()
    if a.command == "add":
        date = a.date or package_date(a.package)
        if not date:
            sys.exit("the zip has no entry dates; pass --date")
        combined = Combined(structures(a.platform), a.platform)
        changes = combined.add(extract(a.package, a.platform, *rules(combined)), date, a.lang)
        combined.save()
        print("\n".join(changes) if changes else "no changes")
        print(combined.meta["last_change"]["summary"])
    elif a.command == "extract":
        with open(a.output, "w", encoding="utf-8") as f:
            json.dump(extract(a.package, a.platform, *platform_rules(a.platform)), f, indent=2, ensure_ascii=False, sort_keys=True)
            f.write("\n")
    elif a.command == "diff":
        lines = compare(load(a.a, a.platform), load(a.b, a.platform))
        print("\n".join(lines) if lines else "no differences")
    elif a.command == "check":
        combined = Combined(structures(a.platform), a.platform)
        known = as_snapshot(combined)
        snapshot = extract(a.package, a.platform, *rules(combined))
        lines = compare(known, snapshot, check=True)
        lines += [f"! {where}" for where in sorted(snapshot["left_out"]) if where.startswith("unreadable JSON")]
        print("\n".join(lines) if lines else "everything in this package is known")
        sys.exit(1 if lines else 0)
    elif a.command == "generate":
        combined = Combined(structures(a.platform))
        Generator(combined, a.seed, a.records, a.lang, a.date, include_old=a.include_old).build(a.output)
        print(a.output)


if __name__ == "__main__":
    main()
