from __future__ import annotations

from models import Project
from services.slack_notifier import SlackNotifier, create_portable_ssl_context


def test_portable_ssl_context_contains_trusted_ca_certificates() -> None:
    assert create_portable_ssl_context().get_ca_certs()


def test_polished_compact_block_layout() -> None:
    project = Project(
        platform="lancers", category_key="lancers_web", category_name="Web",
        project_id="42", project_url="https://example.test/projects/42",
        title="Build <website>", price="100,000円", client_name="A & B",
        scraped_at="2026-10-07T15:55:59+09:00",
    )

    payload = SlackNotifier(True, "https://hooks.slack.test/services/test").format_payload(project)

    assert [block["type"] for block in payload["blocks"]] == ["section", "section", "divider"]
    assert "2026-10-07 15:55:59" not in str(payload)
    assert "New Project" not in str(payload)
    assert "🕒" not in str(payload)
    details = payload["blocks"][0]["text"]["text"]
    assert details.splitlines() == [
        "*Platform:* Lancers   •   *Category:* Web",
        "*Title:* Build &lt;website&gt;",
        "*Price:* 100,000円",
        "*Client:* A &amp; B",
    ]
    url_block = payload["blocks"][1]
    assert url_block["text"]["text"] == "*URL:*\nhttps://example.test/projects/42"
    assert url_block["accessory"]["url"] == project.project_url
    assert url_block["accessory"]["text"]["text"] == "Open URL"
