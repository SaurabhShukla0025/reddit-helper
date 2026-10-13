from datetime import date, timedelta
from types import SimpleNamespace

import pytest

import main
from src import lifecycle, policy, store
from src.config import Config, GeminiConfig, MatchRules, PolicyConfig, PostConfig, RedditCreds, Subreddit, _policy_config


def authorized():
    return Config(
        RedditCreds("id", "secret", "testapp", "password", "testapp/1"),
        [Subreddit("learnpython", "useful answers", MatchRules(), "approved scope",
                   "community permits app replies", True, date.today().isoformat())],
        "new", 10, GeminiConfig(), PostConfig(),
        PolicyConfig(api_approval_reference="test approval", app_registration_reference="test registration",
                     dedicated_app_username="testapp", privacy_policy_reviewed=True,
                     data_security_reviewed=True, deletion_contact="test@example.invalid",
                     external_ai_approval_reference="test AI authorization", provider_data_use_reviewed=True),
    )


def source(**overrides):
    values = dict(title="Question", selftext="Body", author="author", removed_by_category=None,
                  over_18=False, locked=False, archived=False,
                  subreddit=SimpleNamespace(display_name="learnpython", quarantine=False, subreddit_type="public"))
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def conn():
    connection = store.connect(":memory:")
    yield connection
    connection.close()


def seed(conn, **overrides):
    values = dict(post_id="abc", subreddit="learnpython", post_title="Question", post_url="url",
                  post_author="author", comment=policy.disclosed("Answer"), model="test-model",
                  status=store.STATUS_APPROVED, source_hash=lifecycle.fingerprint("Question", "Body"))
    values.update(overrides)
    return store.add_draft(conn, **values)


def test_default_permissions_block_before_client_creation(monkeypatch):
    config = authorized()
    config.policy = PolicyConfig()
    monkeypatch.setattr(main, "make_reddit", lambda _: pytest.fail("must not construct client"))
    with pytest.raises(SystemExit, match="blocked"):
        main._sign_in(config)


@pytest.mark.parametrize("field,value", [
    ("api_approval_reference", ""), ("app_registration_reference", ""),
    ("dedicated_app_username", "wrong"), ("privacy_policy_reviewed", False),
    ("data_security_reviewed", False), ("deletion_contact", ""),
])
def test_live_access_requires_each_prerequisite(field, value):
    config = authorized()
    setattr(config.policy, field, value)
    with pytest.raises(SystemExit):
        policy.require_api(config)


def test_actual_authenticated_account_is_checked(monkeypatch):
    monkeypatch.setattr(main, "make_reddit", lambda _: object())
    monkeypatch.setattr(main, "whoami", lambda _: "someoneelse")
    with pytest.raises(SystemExit, match="Authenticated account"):
        main._sign_in(authorized())


@pytest.mark.parametrize("field,value", [
    ("access_reference", ""), ("comments_reference", ""), ("ai_comments_allowed", False),
    ("rules_reviewed_on", "bad"),
    ("rules_reviewed_on", (date.today() - timedelta(days=31)).isoformat()),
    ("rules_reviewed_on", (date.today() + timedelta(days=1)).isoformat()),
])
def test_community_permission_and_current_rules_required(field, value):
    config = authorized()
    setattr(config.subreddits[0], field, value)
    with pytest.raises(SystemExit):
        policy.require_post(config, "learnpython")


def test_post_requires_external_processing_authorization():
    config = authorized()
    config.policy.external_ai_approval_reference = ""
    with pytest.raises(SystemExit):
        policy.require_post(config, "learnpython")


@pytest.mark.parametrize("raw", [{"privacy_policy_reviewed": "false"}, {"retention_days": 0},
                                  {"retention_days": 31}, {"typo": True}])
def test_policy_config_rejects_ambiguous_or_invalid_settings(raw):
    with pytest.raises(SystemExit):
        _policy_config(raw)


@pytest.mark.parametrize("overrides", [
    {"selftext": "[deleted]"}, {"author": None}, {"removed_by_category": "moderator"},
    {"selftext": "Changed body"}, {"title": "Changed title"}, {"over_18": True},
    {"subreddit": SimpleNamespace(display_name="learnpython", quarantine=True, subreddit_type="public")},
    {"subreddit": SimpleNamespace(display_name="learnpython", quarantine=False, subreddit_type="private")},
])
def test_unusable_sources_remove_drafts_and_score_history(conn, overrides):
    draft = seed(conn)
    store.record_karma(conn, draft.post_id, 3)
    reddit = SimpleNamespace(submission=lambda **_: source(**overrides))
    assert lifecycle.refresh(conn, reddit, [draft], authorized()) == []
    assert store.get_draft(conn, draft.post_id) is None
    assert store.karma_history(conn, draft.post_id) == []


def test_legacy_rows_are_removed(conn):
    draft = seed(conn, source_hash=None)
    reddit = SimpleNamespace(submission=lambda **_: source())
    assert lifecycle.refresh(conn, reddit, [draft], authorized()) == []


def test_source_error_blocks_use_without_deleting_unverified_data(conn):
    draft = seed(conn)
    def unavailable(**_):
        raise RuntimeError("network error")
    with pytest.raises(RuntimeError, match="verification failed"):
        lifecycle.refresh(conn, SimpleNamespace(submission=unavailable), [draft], authorized())
    assert store.get_draft(conn, draft.post_id) is not None


@pytest.mark.parametrize("status", [403, 404])
def test_confirmed_unavailable_source_response_purges_local_data(conn, status):
    draft = seed(conn)
    store.record_karma(conn, draft.post_id, 1)
    def unavailable(**_):
        error = RuntimeError("unavailable")
        error.response = SimpleNamespace(status_code=status)
        raise error
    reddit = SimpleNamespace(submission=unavailable)
    assert lifecycle.refresh(conn, reddit, [draft], authorized()) == []
    assert store.get_draft(conn, draft.post_id) is None
    assert store.karma_history(conn, draft.post_id) == []


def test_legacy_database_migrates_and_expired_records_are_pruned(tmp_path):
    import sqlite3
    db = tmp_path / "legacy.db"
    with sqlite3.connect(db) as old:
        old.execute(store._SCHEMA)
        old.execute("INSERT INTO drafts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("old", "learnpython", "Question", "url", "author", "Answer", "pending", "model",
                     "2000-01-01T00:00:00+00:00", "2000-01-01T00:00:00+00:00", None))
    upgraded = store.connect(db)
    assert "source_hash" in {row["name"] for row in upgraded.execute("PRAGMA table_info(drafts)")}
    assert store.list_drafts(upgraded) == []
    assert upgraded.execute("PRAGMA secure_delete").fetchone()[0] == 1
    upgraded.close()


def test_post_rechecks_source_and_never_submits_deleted_content(conn):
    draft = seed(conn)
    reddit = SimpleNamespace(submission=lambda **_: source(selftext="[deleted]"))
    with pytest.raises(RuntimeError, match="unavailable"):
        lifecycle.submit_checked(conn, reddit, draft, draft.comment, authorized(),
                                 lambda *_: pytest.fail("must not post"))


def test_valid_post_reaches_submission(conn):
    draft = seed(conn)
    calls = []
    reddit = SimpleNamespace(submission=lambda **_: source())
    result = lifecycle.submit_checked(conn, reddit, draft, draft.comment, authorized(),
                                     lambda *args: calls.append(args) or "posted-url")
    assert result == "posted-url"
    assert calls[0][1:] == (draft.post_id, draft.comment)


@pytest.mark.parametrize("overrides", [{"locked": True}, {"archived": True}])
def test_locked_archived_posts_are_blocked(conn, overrides):
    draft = seed(conn)
    reddit = SimpleNamespace(submission=lambda **_: source(**overrides))
    with pytest.raises(RuntimeError, match="locked or archived"):
        lifecycle.submit_checked(conn, reddit, draft, draft.comment, authorized(), lambda *_: pytest.fail("must not post"))


def test_changed_approval_and_missing_disclosure_block_post(conn):
    draft = seed(conn)
    reddit = SimpleNamespace(submission=lambda **_: pytest.fail("no source read needed"))
    with pytest.raises(RuntimeError, match="disclosure"):
        lifecycle.submit_checked(conn, reddit, draft, "Answer", authorized(), lambda *_: None)
    store.set_status(conn, draft.post_id, store.STATUS_REJECTED)
    with pytest.raises(RuntimeError, match="no longer approved"):
        lifecycle.submit_checked(conn, reddit, draft, draft.comment, authorized(), lambda *_: None)


def test_duplicate_comment_blocked(conn):
    draft = seed(conn)
    seed(conn, post_id="previous", status=store.STATUS_POSTED)
    reddit = SimpleNamespace(submission=lambda **_: source())
    with pytest.raises(RuntimeError, match="Duplicate"):
        lifecycle.submit_checked(conn, reddit, draft, draft.comment, authorized(), lambda *_: pytest.fail("must not post"))


def test_disclosed_but_unreviewed_submission_text_is_blocked(conn):
    draft = seed(conn)
    reddit = SimpleNamespace(submission=lambda **_: pytest.fail("must not access source"))
    with pytest.raises(RuntimeError, match="differs from the approved"):
        lifecycle.submit_checked(conn, reddit, draft, policy.disclosed("Unreviewed text"),
                                 authorized(), lambda *_: pytest.fail("must not post"))


def test_post_confirmation_declined_never_submits(conn, monkeypatch):
    seed(conn)
    monkeypatch.setattr(main, "load_config", authorized)
    monkeypatch.setattr(main, "_queue", lambda: conn)
    monkeypatch.setattr(main, "_sign_in", lambda _: (SimpleNamespace(submission=lambda **_: source()), "testapp"))
    monkeypatch.setattr(main, "_confirm", lambda _: False)
    monkeypatch.setattr(main.poster, "run_posts", lambda *args, **kwargs: pytest.fail("must not publish"))
    main.cmd_post([])
    assert store.list_drafts(conn)[0].status == store.STATUS_APPROVED


def test_post_cli_cannot_raise_configured_cap(conn, monkeypatch):
    for index in range(3):
        seed(conn, post_id=str(index), comment=policy.disclosed(f"Answer {index}"))
    config = authorized()
    config.post.max_posts_per_run = 1
    monkeypatch.setattr(main, "load_config", lambda: config)
    monkeypatch.setattr(main, "_queue", lambda: conn)
    monkeypatch.setattr(main, "_sign_in", lambda _: (SimpleNamespace(submission=lambda **_: source()), "testapp"))
    monkeypatch.setattr(main, "_confirm", lambda _: True)
    calls = []
    monkeypatch.setattr(main.poster, "submit_comment", lambda *args: calls.append(args) or "posted-url")
    main.cmd_post(["--limit", "100"])
    assert len(calls) == 1
    assert len(store.list_drafts(conn, store.STATUS_POSTED)) == 1


def test_retention_deletes_old_data_without_extending_on_score_update(conn):
    draft = seed(conn)
    old = (date.today() - timedelta(days=31)).isoformat()
    conn.execute("UPDATE drafts SET created_at = ? WHERE post_id = ?", (old, draft.post_id))
    conn.commit()
    store.record_karma(conn, draft.post_id, 5)
    assert store.prune(conn) == 1
    assert store.list_drafts(conn) == []
    assert store.karma_history(conn, draft.post_id) == []


def test_noninteractive_post_flag_rejected_before_loading_config(monkeypatch):
    monkeypatch.setattr(main, "load_config", lambda: pytest.fail("no config or network needed"))
    with pytest.raises(SystemExit, match="human confirmation"):
        main.cmd_post(["--yes"])


def test_offline_preview_hides_unverified_source_content(conn, monkeypatch, capsys):
    seed(conn)
    monkeypatch.setattr(main, "load_config", authorized)
    monkeypatch.setattr(main, "_queue", lambda: conn)
    monkeypatch.setattr(main, "_sign_in", lambda _: pytest.fail("must stay offline"))
    main.cmd_post(["--dry-run"])
    output = capsys.readouterr().out
    assert "Dry run" in output
    assert "Question" not in output and "Answer" not in output


def test_drafting_limit_counts_declines_and_cannot_exceed_config(conn, monkeypatch):
    from src.fetch import Post
    config = authorized()
    config.gemini.max_drafts_per_run = 2
    posts = [Post(str(i), "learnpython", "Question", "author", 1, 0, "url", "Body", 1) for i in range(5)]
    monkeypatch.setattr(main, "load_config", lambda: config)
    monkeypatch.setattr(main, "_sign_in", lambda _: (object(), "testapp"))
    monkeypatch.setattr(main, "make_client", lambda: object())
    monkeypatch.setattr(main, "_queue", lambda: conn)
    monkeypatch.setattr(main, "fetch_all", lambda *_: {"learnpython": posts})
    calls = []
    monkeypatch.setattr(main, "draft_comment", lambda *args, **kwargs: calls.append(args) or None)
    main.cmd_draft(["--limit", "100"])
    assert len(calls) == 2
