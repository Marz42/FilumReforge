"""Failure-injection regressions for the developer/CI/release gate."""
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from check_release import Checks, validate_junit, redact
from check_schema import EXPECTED_NULLABLE, classify_diffs
from paradigma_adapter import install


@pytest.mark.parametrize("module", ["pytest", "alembic"])
def test_missing_required_python_module_fails(tmp_path, module):
    checks = Checks(tmp_path)
    assert not checks.command("missing-" + module, [sys.executable, "-S", "-c", f"import {module}"])


def test_missing_executable_is_failure(tmp_path):
    assert not Checks(tmp_path).command("missing", [str(tmp_path / "nonexistent")])


@pytest.mark.parametrize("name", ["lint", "build", "postgres", "migration"])
def test_nonzero_without_error_word_is_failure(tmp_path, name):
    assert not Checks(tmp_path).command(name, [sys.executable, "-c", "print('finished'); raise SystemExit(3)"])


def test_stale_junit_cannot_satisfy_a_noop(tmp_path):
    report = tmp_path / "tests.xml"
    report.write_text('<testsuite><testcase name="old"/></testsuite>')
    assert not Checks(tmp_path).command("noop", [sys.executable, "-c", "pass"], junit=report)
    assert not report.exists()


@pytest.mark.parametrize("xml", ["<testsuite/>", "<testsuite><testcase><failure/></testcase></testsuite>",
    '<testsuite><testcase><skipped message="database unavailable"/></testcase></testsuite>'])
def test_junit_missing_tests_failure_or_skip_is_rejected(tmp_path, xml):
    path = tmp_path / "result.xml"
    path.write_text(xml)
    with pytest.raises(ValueError):
        validate_junit(path, postgres=True)


def test_only_documented_legacy_skips_are_permitted_outside_pg(tmp_path):
    path = tmp_path / "result.xml"
    path.write_text('<testsuite><testcase classname="tests.test_services"><skipped '
                    'message="B-12: Legacy E task template runtime removed"/></testcase></testsuite>')
    assert validate_junit(path) == 1
    with pytest.raises(ValueError):
        validate_junit(path, postgres=True)


def test_logs_do_not_include_connection_credentials(tmp_path):
    checks = Checks(tmp_path, env={"POSTGRES_DSN": "postgresql://user:private@host/db"})
    checks.command("safe", [sys.executable, "-c", "print('postgresql://user:private@host/db')"])
    assert "private" not in (tmp_path / "safe.log").read_text()
    assert "private" not in redact("postgresql+asyncpg://user:private@host/db", {})


def compatible_diffs():
    return [[("modify_nullable", None, table, column, {}, True, False)]
            for table, column in EXPECTED_NULLABLE]


def test_compatibility_exception_is_exact_and_revision_bound():
    diffs = compatible_diffs()
    result = classify_diffs(diffs, "20260827_01", True)
    assert result["passed"] and not result["schema_clean"]
    assert not classify_diffs(diffs, "20260827_01", False)["passed"]
    assert not classify_diffs(diffs, "different", True)["passed"]
    assert not classify_diffs(diffs[:-1], "20260827_01", True)["passed"]
    assert not classify_diffs(diffs + [("remove_table", "unexpected")], "20260827_01", True)["passed"]
    assert not classify_diffs(diffs + [[("modify_type", None, "tasks", "status", {}, "a", "b")]], "20260827_01", True)["passed"]
    assert classify_diffs([], "future-contract", False)["schema_clean"]


@pytest.fixture
def version_root(tmp_path):
    root = tmp_path
    (root / ".paradigma/schemas").mkdir(parents=True)
    (root / "VERSION").write_text("0.93.0-rc.1")
    (root / ".paradigma/VERSION").write_text("0.7.0")
    (root / ".paradigma/config.yaml").write_text('filum_paradigma_version_file: .paradigma/VERSION\n'
        'installed_distribution_version: 0.7.0\nconfig_schema_version: 0.5\nokf_version: 0.1\n')
    (root / ".paradigma/schemas/paradigma-types.schema.yaml").write_text('document_schema_version: 0.3\n')
    return root


def test_version_adapter_keeps_product_and_protocol_separate(version_root):
    install()
    from paradigma.application.versioning import read_version_info, validate_version_info
    info = read_version_info(version_root)
    assert not validate_version_info(info)
    assert (version_root / "VERSION").read_text() == "0.93.0-rc.1"
    (version_root / ".paradigma/VERSION").write_text("0.8.0")
    assert any(d.code == "PD_VERSION_DISTRIBUTION_DRIFT" for d in validate_version_info(read_version_info(version_root)))


def test_missing_protocol_version_still_fails(version_root):
    install()
    from paradigma.application.versioning import read_version_info, VersionModelError
    (version_root / ".paradigma/VERSION").unlink()
    with pytest.raises(VersionModelError):
        read_version_info(version_root)


def test_unconfigured_upstream_version_behavior_is_unchanged(version_root):
    install()
    from paradigma.application.versioning import read_distribution_version
    (version_root / ".paradigma/config.yaml").write_text('installed_distribution_version: 0.7.0\n')
    assert read_distribution_version(version_root) == "0.93.0-rc.1"


def test_ci_without_explicit_services_cannot_pass(tmp_path, monkeypatch):
    import check_release
    monkeypatch.delenv("POSTGRES_TEST_ADMIN_DSN", raising=False)
    monkeypatch.delenv("REDIS_TEST_DSN", raising=False)
    monkeypatch.setenv("POSTGRES_DSN", "postgresql+asyncpg://target:private@production/db")
    observed = []
    def success(self, name, args, *a, **kw):
        observed.append(self.env["POSTGRES_DSN"])
        self.results.append({"name": name, "passed": True})
        return True
    monkeypatch.setattr(Checks, "command", success)
    assert check_release.main(["--mode", "isolated-ci", "--suite", "backend", "--output", str(tmp_path)]) == 1
    assert set(observed) == {"sqlite+aiosqlite:///:memory:"}


def test_multiple_migration_heads_fail_before_any_connection(monkeypatch):
    import check_schema
    from alembic.script import ScriptDirectory
    class MultipleHeads:
        def get_heads(self):
            return ["one", "two"]
    monkeypatch.setattr(ScriptDirectory, "from_config", lambda _: MultipleHeads())
    with pytest.raises(RuntimeError, match="exactly one head"):
        check_schema.run(True, True)


def test_unreachable_isolated_pg_fails_without_credentials_in_output(tmp_path):
    import os
    env = {**os.environ, "POSTGRES_TEST_ADMIN_DSN": "postgresql://test:private-pass@127.0.0.1:1/postgres"}
    result = subprocess.run([sys.executable, str(SCRIPTS / "check_schema.py"), "--isolated"],
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert "private-pass" not in result.stdout + result.stderr


def test_pg_subset_cannot_replace_full_required_coverage(tmp_path):
    import json
    import xml.etree.ElementTree as ET
    names = json.loads((SCRIPTS / "required_postgres_tests.json").read_text())
    root = ET.Element("testsuite")
    for entry in names:
        classname, name = entry.split("::")
        ET.SubElement(root, "testcase", classname=classname, name=name)
    path = tmp_path / "pg.xml"
    ET.ElementTree(root).write(path)
    assert validate_junit(path, postgres=True) == len(names)
    skipped = ET.SubElement(root[0], "skipped", message="unavailable")
    ET.ElementTree(root).write(path)
    with pytest.raises(ValueError, match="skipped"):
        validate_junit(path, postgres=True)
    root[0].remove(skipped)
    root.remove(root[0])
    ET.ElementTree(root).write(path)
    with pytest.raises(ValueError, match="coverage"):
        validate_junit(path, postgres=True)


def test_new_run_cannot_leave_an_old_success_summary(tmp_path):
    path = tmp_path / "summary.json"
    path.write_text('{"status":"ISOLATED-CI_CHECKS_PASSED"}')
    Checks(tmp_path)
    assert not path.exists()


def test_default_mode_requires_full_release_checks():
    import check_release
    with pytest.raises(SystemExit) as result:
        check_release.main(["--suite", "backend"])
    assert result.value.code == 2


@pytest.mark.parametrize("state", ["dirty", "unknown"])
def test_release_requires_identifiable_clean_source(tmp_path, monkeypatch, state):
    import check_release
    for key in ("POSTGRES_TEST_ADMIN_DSN", "REDIS_TEST_DSN", "POSTGRES_DSN"):
        monkeypatch.setenv(key, "test-only-unused-by-stub")
    monkeypatch.setattr(check_release, "production_settings_valid", lambda: True)
    def success(self, name, *a, **kw):
        self.results.append({"name": name, "passed": True})
        return True
    monkeypatch.setattr(Checks, "command", success)
    def git_output(args, **kw):
        if state == "unknown":
            raise OSError("git unavailable")
        return "abc123" if "rev-parse" in args else " M changed.py"
    monkeypatch.setattr(subprocess, "check_output", git_output)
    assert check_release.main(["--mode", "release", "--output", str(tmp_path)]) == 1
