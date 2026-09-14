#!/usr/bin/env bash
set -euo pipefail

url="${PAGES_ENDPOINT_URL:-https://rajon369963-del.github.io/sovereign-study-commons-india/}"
expected_title="${PAGES_EXPECTED_TITLE:-<title>सार्वजनिक अध्ययन महा-कॉकपिट | Universal Sovereign Study Lake</title>}"
body="$(mktemp)"
trap 'rm -f "$body"' EXIT

code="$(curl --silent --show-error --location --retry 3 --retry-delay 2 --connect-timeout 10 --max-time 30 --output "$body" --write-out '%{http_code}' "$url")"
digest="$(sha256sum "$body" | cut -d' ' -f1)"
printf 'event=%s ref=%s repo_sha=%s endpoint=%s http=%s bytes=%s sha256=%s\n' "${GITHUB_EVENT_NAME:-local}" "${GITHUB_REF:-local}" "${GITHUB_SHA:-local}" "$url" "$code" "$(wc -c < "$body")" "$digest"
grep -Eio '<title>[^<]*</title>|<h1[^>]*>[^<]*</h1>' "$body" | head -n 5 || true

test "$code" = '200'
grep -Fq "$expected_title" "$body"
if grep -Fq 'PASSED_PHYSICAL_VERIFICATION' "$body" || grep -Fq 'SUCCESS_PHYSICAL' "$body"; then
  echo 'stale unsafe verification marker detected on public endpoint' >&2
  exit 1
fi
printf 'PUBLIC_ENDPOINT_VERIFIED repo_sha=%s url=%s http=%s marker=%s sha256=%s\n' "${GITHUB_SHA:-local}" "$url" "$code" 'Universal Sovereign Study Lake title' "$digest"
