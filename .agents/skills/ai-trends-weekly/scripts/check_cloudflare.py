#!/usr/bin/env python3
"""Detect whether HTML content is a Cloudflare challenge page.

Reads HTML from stdin. Exit codes:
  0 - Normal page (not a Cloudflare challenge)
  1 - Cloudflare JS challenge detected
  2 - Error reading input
"""
import sys

CF_SIGNATURES = [
    "_cf_chl_opt",
    "cf_chl_",
    "cf_chl_props",
    "challenge-error",
    "__cf_chl",
    "cdn-cgi/challenge-platform",
    "cloudflare challenge",
    "Enable JavaScript and cookies to continue",
    "checking your browser before accessing",
]


def is_cloudflare(html: str) -> bool:
    lower = html.lower()
    return any(sig.lower() in lower for sig in CF_SIGNATURES)


def main():
    try:
        content = sys.stdin.read()
    except Exception as e:
        print(f"Error reading stdin: {e}", file=sys.stderr)
        sys.exit(2)

    if not content.strip():
        print("Empty input", file=sys.stderr)
        sys.exit(2)

    if is_cloudflare(content):
        print("CLOUDFLARE_DETECTED")
        sys.exit(1)
    else:
        print("NORMAL_PAGE")
        sys.exit(0)


if __name__ == "__main__":
    main()
