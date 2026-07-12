from __future__ import annotations

import json
import urllib.request
from http.cookiejar import CookieJar

ORIGIN = "http://127.0.0.1:3000"
API_BASE_URL = "http://127.0.0.1:8000"


def main() -> None:
    cookies = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    bootstrap_request = urllib.request.Request(
        f"{API_BASE_URL}/api/v1/demo/session-bootstrap",
        headers={"Origin": ORIGIN},
    )
    with opener.open(bootstrap_request) as response:
        bootstrap = json.load(response)

    mint_request = urllib.request.Request(
        f"{API_BASE_URL}/api/v1/demo/sessions",
        data=json.dumps({"demo_actor": "advisor"}).encode(),
        headers={
            "Content-Type": "application/json",
            "Origin": ORIGIN,
            "X-CSRF-Token": bootstrap["csrf_token"],
        },
        method="POST",
    )
    with opener.open(mint_request) as response:
        minted = json.load(response)

    if minted.get("role") != "advisor" or minted.get("proof_mode") != "synthetic-demo":
        raise SystemExit("demo identity probe returned an unexpected public response")
    if not minted.get("csrf_token"):
        raise SystemExit("demo identity probe did not return session CSRF")
    if not any(cookie.name == "night_voyager_session" for cookie in cookies):
        raise SystemExit("demo identity probe did not receive the session cookie")
    print("compose-proof: bootstrap and synthetic session mint passed")


if __name__ == "__main__":
    main()
