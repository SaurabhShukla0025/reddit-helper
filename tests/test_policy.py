"""Offline safety and workflow tests for manual single-comment publishing."""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

import main
from src import lifecycle, policy, poster, store
from src.config import Config, PolicyConfig, PostConfig, RedditCreds, Subreddit, _policy_config, load_config


def authorized():
    return Config(
        RedditCreds("id", "secret", "testapp", "password", "helper/1 by u/testapp"),
        [Subreddit("learnpython", "Helpful answers", "scope", "replies allowed", date.today().isoformat())],
        PostConfig(3),
        PolicyConfig(
            api_approval_reference="approval",
            app_registration_reference="registration",
            dedicated_app_username="testapp",
            privacy_policy_reviewed=True,
            data_security_reviewed=True,
            deletion_contact="test@example.invalid",
            approved_purpose="Human-written replies",
            operator_identity="u/testapp",
            app_profile_label_reference="label",
            terms_accepted_on=date.today().isoformat(),
            devvit_assessment_reference="assessment",
            external_api_exception_reference="test exception",
            storage_security_reference="test security",
            backup_deletion_procedure_reference="test procedure",
            cleanup_schedule_reference="test schedule",
            privacy_notice_sha256=policy.privacy_digest(),
        ),
    )


def source(**overrides):
    values = dict(
        title="Question",
        selftext="Body",
        author="someone",
        removed_by_category=None,
        over_18=False,
        locked=False,
        archived=False,
        subreddit=SimpleNamespace(display_name="learnpython", quarantine=False, subreddit_type="public"),
    )
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def conn():
    connection = store.connect(":memory:")
    yield connection
    connection.close()


def seed(conn, **overrides):
    values = dict(
        post_id="abc",
        subreddit="learnpython",
        post_title="Question",
        post_url="url",
        post_author="",
        comment="A human-written useful answer",
        model="human",
        status=store.STATUS_APPROVED,
        source_hash=lifecycle.fingerprint("Question", "Body"),
    )
    values.update(overrides)
    return store.add_draft(conn, **values)


def reddit_for(**overrides):
    return SimpleNamespace(submission=lambda **_: source(**overrides))


@pytest.mark.parametrize(
    "field,value",
    [
        ("api_approval_reference", ""),
        ("app_registration_reference", ""),
        ("dedicated_app_username", "wrong"),
        ("approved_purpose", ""),
        ("privacy_policy_reviewed", False),
        ("data_security_reviewed", False),
        ("deletion_contact", ""),
        ("approval_expires_on", "bad"),
        ("approval_expires_on", (date.today() - timedelta(days=1)).isoformat()),
    ],
)
def test_live_access_requires_real_prerequisites(field, value):
    config = authorized()
    setattr(config.policy, field, value)
    with pytest.raises(SystemExit):
        policy.require_api(config)


def test_default_permissions_block_before_client_creation(monkeypatch):
    config = authorized()
    config.policy = PolicyConfig()
    monkeypatch.setattr(main, "make_reddit", lambda _: pytest.fail("no client"))
    with pytest.raises(SystemExit, match="blocked"):
        main._sign_in(config)


def test_authenticated_identity_checked(monkeypatch):
    monkeypatch.setattr(main, "make_reddit", lambda _: object())
    monkeypatch.setattr(main, "whoami", lambda _: "different")
    with pytest.raises(SystemExit, match="Authenticated account"):
        main._sign_in(authorized())


@pytest.mark.parametrize(
    "field,value",
    [
        ("access_reference", ""),
        ("comments_reference", ""),
        ("rules_reviewed_on", "bad"),
        ("rules_reviewed_on", (date.today() - timedelta(days=31)).isoformat()),
    ],
)
def test_community_permission_required(field, value):
    config = authorized()
    setattr(config.subreddits[0], field, value)
    with pytest.raises(SystemExit):
        policy.require_post(config, "learnpython")


def test_scope_enforced():
    with pytest.raises(SystemExit, match="outside"):
        policy.require_post(authorized(), "other")


@pytest.mark.parametrize(
    "raw",
    [
        {"privacy_policy_reviewed": "false"},
        {"retention_days": 0},
        {"retention_days": 31},
        {"retention_days": True},
        {"gemini": True},
    ],
)
def test_invalid_policy_config_rejected(raw):
    with pytest.raises(SystemExit):
        _policy_config(raw)


@pytest.mark.parametrize(
    "overrides",
    [
        {"selftext": "[deleted]"},
        {"author": None},
        {"removed_by_category": "moderator"},
        {"selftext": "Changed"},
        {"title": "Changed"},
        {"over_18": True},
        {"subreddit": SimpleNamespace(display_name="other", quarantine=False, subreddit_type="public")},
        {"subreddit": SimpleNamespace(display_name="learnpython", quarantine=True, subreddit_type="public")},
    ],
)
def test_unusable_source_purged(conn, overrides):
    draft = seed(conn)
    assert lifecycle.refresh(conn, reddit_for(**overrides), [draft], authorized()) == []
    assert store.get_draft(conn, draft.post_id) is None


def test_network_error_blocks_use_without_purge(conn):
    draft = seed(conn)

    def fail(**_):
        raise RuntimeError("offline")

    with pytest.raises(RuntimeError, match="verification failed"):
        lifecycle.refresh(conn, SimpleNamespace(submission=fail), [draft], authorized())
    assert store.get_draft(conn, draft.post_id)


@pytest.mark.parametrize("overrides", [{"locked": True}, {"archived": True}])
def test_locked_archived_blocked(conn, overrides):
    draft = seed(conn)
    with pytest.raises(RuntimeError, match="locked or archived"):
        lifecycle.submit_checked(
            conn, reddit_for(**overrides), draft, draft.comment, authorized(), lambda *_: pytest.fail("no publish")
        )


def test_reviewed_text_required(conn):
    draft = seed(conn)
    with pytest.raises(RuntimeError, match="differs"):
        lifecycle.submit_checked(conn, reddit_for(), draft, "different", authorized(), lambda *_: None)


def test_manual_reply_published_without_ai_disclosure(conn):
    draft = seed(conn)
    assert (
        lifecycle.submit_checked(conn, reddit_for(), draft, draft.comment, authorized(), lambda *_: "published-url")
        == "published-url"
    )
    assert store.get_draft(conn, draft.post_id).status == store.STATUS_POSTED


def test_edit_invalidates_approval(conn):
    seed(conn)
    store.update_comment(conn, "abc", "Edited answer")
    assert store.get_draft(conn, "abc").status == store.STATUS_PENDING


@pytest.mark.parametrize(
    "text",
    [
        "A human-written useful answer",
        "A human-written useful answer!",
    ],
)
def test_duplicate_and_similar_replies_blocked(conn, text):
    seed(conn, post_id="previous", status=store.STATUS_POSTED)
    draft = seed(conn, comment=text)
    with pytest.raises(RuntimeError, match="Duplicate"):
        lifecycle.submit_checked(conn, reddit_for(), draft, draft.comment, authorized(), lambda *_: None)


def test_attempt_cap_survives_reopening_and_deletion(tmp_path):
    path = tmp_path / "queue.db"
    first = store.connect(path)
    draft = seed(first)
    config = authorized()
    config.post.max_posts_per_day = 1
    lifecycle.submit_checked(first, reddit_for(), draft, draft.comment, config, lambda *_: "url")
    store.forget(first, draft.post_id)
    first.close()
    second = store.connect(path)
    draft = seed(second, post_id="def", comment="A completely distinct practical solution")
    with pytest.raises(RuntimeError, match="Daily"):
        lifecycle.submit_checked(second, reddit_for(), draft, draft.comment, config, lambda *_: None)
    second.close()


def test_failed_attempt_is_uncertain_and_cannot_retry(conn):
    draft = seed(conn)

    def fail(*_):
        raise RuntimeError("unknown outcome")

    with pytest.raises(RuntimeError, match="unknown"):
        lifecycle.submit_checked(conn, reddit_for(), draft, draft.comment, authorized(), fail)
    assert store.get_draft(conn, "abc").status == store.STATUS_UNCERTAIN
    with pytest.raises(RuntimeError, match="no longer approved"):
        lifecycle.submit_checked(
            conn, reddit_for(), draft, draft.comment, authorized(), lambda *_: pytest.fail("no retry")
        )
    assert conn.execute("SELECT attempts FROM daily_attempts").fetchone()[0] == 1


def test_repeated_reservation_is_blocked_across_connections(tmp_path):
    path = tmp_path / "queue.db"
    first = store.connect(path)
    draft = seed(first)
    second = store.connect(path)
    stale = store.get_draft(second, "abc")
    store.reserve_publish(first, draft, 3)
    with pytest.raises(RuntimeError, match="no longer approved"):
        store.reserve_publish(second, stale, 3)
    assert second.execute("SELECT attempts FROM daily_attempts").fetchone()[0] == 1
    first.close()
    second.close()


def test_retention_uses_creation_not_edit_time(conn):
    seed(conn)
    old = (date.today() - timedelta(days=31)).isoformat()
    conn.execute("UPDATE drafts SET created_at = ?", (old,))
    conn.commit()
    store.update_comment(conn, "abc", "new text")
    assert store.prune(conn, 7) == 1
    assert not store.list_drafts(conn)


def test_legacy_ai_and_author_metadata_removed(tmp_path):
    path = tmp_path / "legacy.db"
    old = store.connect(path)
    seed(old, post_id="ai", model="gemini", post_author="someone")
    seed(old, post_id="human", post_author="someone")
    old.execute("CREATE TABLE karma (score INTEGER)")
    old.execute("INSERT INTO karma VALUES (4)")
    old.commit()
    old.close()
    upgraded = store.connect(path)
    assert not store.has_draft(upgraded, "ai")
    assert store.get_draft(upgraded, "human").post_author == ""
    assert not upgraded.execute("SELECT name FROM sqlite_master WHERE name='karma'").fetchall()
    upgraded.close()


def test_single_publish_confirmation_decline(tmp_path, monkeypatch):
    path = tmp_path / "queue.db"
    connection = store.connect(path)
    seed(connection)
    connection.close()
    monkeypatch.setattr(main, "_queue", lambda: store.connect(path))
    monkeypatch.setattr(main, "load_config", authorized)
    monkeypatch.setattr(main, "_sign_in", lambda _: (reddit_for(), "testapp"))
    monkeypatch.setattr(main, "_confirm", lambda _: False)
    monkeypatch.setattr(main.poster, "submit_comment", lambda *_: pytest.fail("no publish"))
    main.cmd_post("abc")
    with store.connect(path) as connection:
        assert store.get_draft(connection, "abc").status == store.STATUS_APPROVED


def test_manual_selection_only_creates_requested_draft(tmp_path, monkeypatch):
    path = tmp_path / "queue.db"
    reply = tmp_path / "reply.txt"
    reply.write_text("A useful manually written answer", encoding="utf-8")
    calls = []

    def selected(**kwargs):
        calls.append(kwargs)
        return source()

    monkeypatch.setattr(main, "_queue", lambda: store.connect(path))
    monkeypatch.setattr(main, "load_config", authorized)
    monkeypatch.setattr(main, "_sign_in", lambda _: (SimpleNamespace(submission=selected), "testapp"))
    main.cmd_draft("abc", str(reply))
    connection = store.connect(path)
    draft = store.get_draft(connection, "abc")
    assert calls == [{"id": "abc"}]
    assert draft.comment == reply.read_text() and draft.model == "human" and draft.post_author == ""
    connection.close()


def test_offline_preview_hides_source(tmp_path, monkeypatch, capsys):
    path = tmp_path / "queue.db"
    connection = store.connect(path)
    seed(connection)
    connection.close()
    monkeypatch.setattr(main, "_queue", lambda: store.connect(path))
    monkeypatch.setattr(main, "_sign_in", lambda _: pytest.fail("no network"))
    main.cmd_post("abc", dry_run=True)
    output = capsys.readouterr().out
    assert "Dry run" in output and "Question" not in output and "answer" not in output


@pytest.mark.parametrize(
    "args",
    [
        ["post"],
        ["post", "abc", "--yes"],
        ["karma"],
        ["fetch"],
        ["match"],
        ["draft", "--limit", "10"],
        ["post", "abc", "--limit", "10"],
    ],
)
def test_automation_cli_removed(args):
    with pytest.raises(SystemExit):
        main._build_parser().parse_args(args)


def test_credentials_from_environment_and_single_community(tmp_path, monkeypatch):
    import yaml

    example = yaml.safe_load(main.Path("config.example.yaml").read_text(encoding="utf-8-sig"))
    example["reddit"]["username"] = "testapp"
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(example))
    for key in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_PASSWORD"):
        monkeypatch.setenv(key, "test")
    config = load_config(path)
    assert config.reddit.password == "test"
    example["subreddits"].append(dict(example["subreddits"][0]))
    path.write_text(yaml.safe_dump(example))
    with pytest.raises(SystemExit, match="exactly one"):
        load_config(path)


def test_poster_does_not_retry_uncertain_error():
    calls = []

    def fail(body):
        calls.append(body)
        raise RuntimeError("timeout")

    reddit = SimpleNamespace(submission=lambda **_: SimpleNamespace(reply=fail))
    with pytest.raises(RuntimeError, match="unknown"):
        poster.submit_comment(reddit, "abc", "body")
    assert calls == ["body"]


def test_cleanup_runs_without_credentials_and_preserves_unrelated_files(tmp_path, monkeypatch):
    from src import applog

    log = tmp_path / "reddit-helper.log"
    log.write_text("legacy")
    backup = tmp_path / "reddit-helper.log.1"
    backup.write_text("legacy")
    unrelated = tmp_path / "notes.log"
    unrelated.write_text("keep")
    applog.cleanup_logs(log)
    assert not log.exists() and not backup.exists() and unrelated.read_text() == "keep"


def test_maintenance_repeats_local_cleanup_until_stopped(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "cmd_cleanup", lambda: calls.append("cleanup"))

    def stop(_):
        raise KeyboardInterrupt

    monkeypatch.setattr(main.time, "sleep", stop)
    main.cmd_maintenance()
    assert calls == ["cleanup"]


@pytest.mark.parametrize("status", [store.STATUS_POSTED, store.STATUS_UNCERTAIN])
def test_terminal_drafts_cannot_be_reapproved_or_edited(conn, status):
    draft = seed(conn, status=status)
    store.set_status(conn, draft.post_id, store.STATUS_APPROVED)
    store.update_comment(conn, draft.post_id, "changed")
    current = store.get_draft(conn, draft.post_id)
    assert current.status == status and current.comment == draft.comment


def test_draft_expiring_during_confirmation_is_not_published(conn):
    draft = seed(conn)
    conn.execute("UPDATE drafts SET created_at = '2000-01-01' WHERE post_id = 'abc'")
    conn.commit()
    with pytest.raises(RuntimeError, match="no longer approved"):
        lifecycle.submit_checked(
            conn, reddit_for(), draft, draft.comment, authorized(), lambda *_: pytest.fail("no publication")
        )
    assert not store.has_draft(conn, "abc")


@pytest.fixture(autouse=True)
def privacy_notice(monkeypatch, tmp_path):
    notice = tmp_path / "privacy.txt"
    notice.write_text("Operator u/testapp; deletion contact test@example.invalid; test-only notice.")
    monkeypatch.setattr(policy, "PRIVACY_PATH", notice)


@pytest.mark.parametrize(
    "field",
    [
        "operator_identity",
        "app_profile_label_reference",
        "terms_accepted_on",
        "devvit_assessment_reference",
        "external_api_exception_reference",
        "storage_security_reference",
        "backup_deletion_procedure_reference",
        "cleanup_schedule_reference",
        "privacy_notice_sha256",
    ],
)
def test_new_setup_evidence_blocks_live_access(field):
    config = authorized()
    setattr(config.policy, field, "")
    with pytest.raises(SystemExit, match="blocked"):
        policy.require_api(config)


def test_privacy_edits_invalidate_review():
    config = authorized()
    policy.PRIVACY_PATH.write_text("changed operator u/testapp contact test@example.invalid")
    with pytest.raises(SystemExit, match="privacy notice"):
        policy.require_api(config)


def test_privacy_placeholder_blocked_even_with_matching_hash():
    policy.PRIVACY_PATH.write_text("Operator u/testapp contact test@example.invalid [REQUIRED: encryption]")
    config = authorized()
    with pytest.raises(SystemExit, match="privacy notice"):
        policy.require_api(config)


def test_readiness_never_loads_credentials_or_calls_reddit(tmp_path, monkeypatch, capsys):
    from src import config as config_module
    from src import readiness

    path = tmp_path / "config.yaml"
    readiness.initialize("testapp", "learnpython", path)
    monkeypatch.setattr(config_module, "load_secrets", lambda: pytest.fail("must not load secrets"))
    assert not readiness.report(path)
    assert "MISSING" in capsys.readouterr().out


def test_setup_does_not_fabricate_permissions(tmp_path):
    import yaml

    from src import readiness

    path = tmp_path / "config.yaml"
    readiness.initialize("saurabhimapro", "learnpython", path)
    data = yaml.safe_load(path.read_text())
    assert data["reddit"]["username"] == "saurabhimapro"
    assert data["subreddits"][0]["name"] == "learnpython"
    assert not data["policy"]["api_approval_reference"]
    assert not data["policy"]["dedicated_app_username"]
    assert not data["policy"]["privacy_policy_reviewed"]
    with pytest.raises(SystemExit, match="already exists"):
        readiness.initialize("different", "other", path)


def test_credentials_environment_skips_decryption(tmp_path, monkeypatch):
    from src import credentials

    path = tmp_path / "credentials.bin"
    path.write_bytes(b"encrypted")
    for key in credentials.KEYS:
        monkeypatch.setenv(key, "testvalue")
    monkeypatch.setattr(credentials, "_crypt", lambda *_args, **_kwargs: pytest.fail("no decrypt needed"))
    assert all(credentials.load_secrets(path).values())


def test_credentials_decryption_failure_has_no_plaintext_fallback(tmp_path, monkeypatch):
    from src import credentials

    path = tmp_path / "credentials.bin"
    path.write_bytes(b"bad")
    for key in credentials.KEYS:
        monkeypatch.delenv(key, raising=False)

    def fail(*_args, **_kwargs):
        raise SystemExit("decrypt failed")

    monkeypatch.setattr(credentials, "_crypt", fail)
    with pytest.raises(SystemExit, match="decrypt failed"):
        credentials.load_secrets(path)


def test_windows_dpapi_round_trip_dummy_payload():
    import os

    from src.credentials import _crypt

    if os.name != "nt":
        pytest.skip("Windows-only DPAPI")
    payload = b"offline-dummy-data-no-real-secrets"
    encrypted = _crypt(payload)
    assert payload not in encrypted
    assert _crypt(encrypted, decrypt=True) == payload
