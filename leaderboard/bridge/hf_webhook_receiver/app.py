from __future__ import annotations

import json
import os
import hashlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib import error as urlerror
from urllib import request


def _build_dispatch_payload(*, body: dict, event_id: str) -> dict:
    event = body.get("event", {}) if isinstance(body, dict) else {}
    repo = event.get("repo", {}) if isinstance(event, dict) else {}
    discussion = event.get("discussion", {}) if isinstance(event, dict) else {}

    hf_repo = repo.get("name", "")
    hf_pr_number = discussion.get("num")
    hf_pr_url = discussion.get("url", "")

    return {
        "event_type": "hf_submission_event",
        "client_payload": {
            "event_id": event_id,
            "event_scope": event.get("scope"),
            "event_action": event.get("action"),
            "event_ts": event.get("createdAt"),
            "hf_repo": hf_repo,
            "hf_pr_number": hf_pr_number,
            "hf_head_sha": repo.get("headSha"),
            "hf_pr_url": hf_pr_url,
        },
    }


def _dispatch_to_github(*, payload: dict, token: str, repository: str) -> None:
    req = request.Request(
        url=f"https://api.github.com/repos/{repository}/dispatches",
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=30):
            return
    except urlerror.URLError as exc:
        raise RuntimeError(f"Failed to call GitHub dispatch API: {exc}") from exc


class HFWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/webhook/hf-submissions":
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return

        secret = os.environ.get("HF_WEBHOOK_SECRET", "")
        if not secret:
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.end_headers()
            return

        provided = self.headers.get("X-Webhook-Secret", "")
        if provided != secret:
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body_raw = self.rfile.read(content_length)
        try:
            body = json.loads(body_raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.end_headers()
            return

        event_id = (
            self.headers.get("X-Event-Id")
            or self.headers.get("X-Request-Id")
            or self.headers.get("X-Amzn-Trace-Id")
            or hashlib.sha256(body_raw).hexdigest()
        )
        dispatch_payload = _build_dispatch_payload(body=body, event_id=event_id)

        canonical_hf_repo = os.environ.get("HF_REPO_CANONICAL", "")
        if not canonical_hf_repo:
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.end_headers()
            return
        if dispatch_payload["client_payload"]["hf_repo"] != canonical_hf_repo:
            self.send_response(HTTPStatus.ACCEPTED)
            self.end_headers()
            return

        token = os.environ.get("GITHUB_DISPATCH_TOKEN", "")
        repository = os.environ.get("GITHUB_REPOSITORY", "")
        if not token or not repository:
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.end_headers()
            return

        try:
            _dispatch_to_github(payload=dispatch_payload, token=token, repository=repository)
        except RuntimeError:
            self.send_response(HTTPStatus.BAD_GATEWAY)
            self.end_headers()
            return

        self.send_response(HTTPStatus.ACCEPTED)
        self.end_headers()


def main() -> None:
    host = os.environ.get("HF_WEBHOOK_HOST", "0.0.0.0")
    port = int(os.environ.get("HF_WEBHOOK_PORT", "8080"))
    server = HTTPServer((host, port), HFWebhookHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
