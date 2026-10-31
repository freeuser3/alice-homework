import json

from keenetic_skill.probe import redact, report, write_record


def test_redact_nested_secrets():
    data = {
        "session": {
            "user": {"user_id": "u1", "access_token": "secret"},
        },
        "items": [
            {"authorization": "Bearer secret"},
            {"oauth_token": "secret"},
        ],
    }
    result = redact(data)
    assert result["session"]["user"]["user_id"] == "u1"
    assert result["session"]["user"]["access_token"] == "***"
    assert result["items"][0]["authorization"] == "***"
    assert result["items"][1]["oauth_token"] == "***"


def test_write_record_appends_jsonl(tmp_path):
    path = tmp_path / "keenetic.log"
    write_record(path, {"a": 1})
    write_record(path, {"b": 2})
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [{"a": 1}, {"b": 2}]


def test_report_groups_users_and_apps(tmp_path, capsys):
    path = tmp_path / "keenetic.log"
    records = [
        {
            "ts": "t1",
            "body": {
                "session": {
                    "user": {"user_id": "u1"},
                    "application": {"application_id": "a1"},
                },
                "meta": {"client_id": "c1"},
                "request": {"command": "cmd1"},
            },
        },
        {
            "ts": "t2",
            "body": {
                "session": {
                    "user": {"user_id": "u2"},
                    "application": {"application_id": "a1"},
                },
                "meta": {"client_id": "c1"},
                "request": {"command": "cmd2"},
            },
        },
    ]
    for record in records:
        write_record(path, record)
    assert report(path) == 0
    out = capsys.readouterr().out
    assert "u1" in out
    assert "u2" in out
    assert "Различных комбинаций" in out


def test_report_skips_invalid_lines(tmp_path, capsys):
    path = tmp_path / "keenetic.log"
    path.write_text(
        "not json\n"
        + json.dumps({
            "ts": "t1",
            "body": {
                "session": {"user": {"user_id": "u1"}},
                "request": {"command": "cmd1"},
            },
        })
        + "\n",
        encoding="utf-8",
    )
    assert report(path) == 0
    out = capsys.readouterr().out
    assert "u1" in out


def test_report_missing_log(tmp_path, capsys):
    assert report(tmp_path / "missing.log") == 1
    assert "лог не найден" in capsys.readouterr().out
