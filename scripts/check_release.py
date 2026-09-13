"""Portable fail-closed engineering checks; success never grants production approval."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LEGACY_REASON = "B-12: Legacy E task template runtime removed"


def validate_junit(path, *, postgres=False):
    cases = list(ET.parse(path).getroot().iter("testcase"))
    if not cases:
        raise ValueError("no test cases recorded")
    if postgres:
        required = set(json.loads((ROOT / "scripts/required_postgres_tests.json").read_text(encoding="utf-8")))
        observed = {f"{case.get('classname')}::{case.get('name')}" for case in cases}
        if not required or not required.issubset(observed):
            raise ValueError("required PostgreSQL test coverage is missing")
    for case in cases:
        if case.find("failure") is not None or case.find("error") is not None:
            raise ValueError("test failure recorded")
        skipped = case.find("skipped")
        if skipped is not None and (postgres or skipped.get("message") != LEGACY_REASON
                or not case.get("classname", "").endswith("test_services")):
            raise ValueError("required test skipped")
    return len(cases)


def redact(text, env):
    for key, value in env.items():
        if value and any(token in key.upper() for token in ("SECRET", "PASSWORD", "TOKEN", "DSN", "API_KEY")):
            text = text.replace(value, "[REDACTED]")
    return re.sub(r"([a-z][a-z0-9+.-]*://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", text, flags=re.I)


class Checks:
    def __init__(self, output, env=None):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / "summary.json").unlink(missing_ok=True)
        self.env = dict(os.environ if env is None else env)
        self.results = []

    def command(self, name, args, cwd=ROOT, *, junit=None, postgres=False):
        start = time.monotonic()
        passed = False
        if junit:
            Path(junit).unlink(missing_ok=True)
        try:
            result = subprocess.run(args, cwd=cwd, env=self.env, capture_output=True,
                                    text=True, encoding="utf-8", errors="replace", timeout=1200)
            log = redact(result.stdout + result.stderr, self.env)
            passed = result.returncode == 0
            if passed and junit:
                validate_junit(junit, postgres=postgres)
        except (OSError, subprocess.TimeoutExpired, ValueError, ET.ParseError) as exc:
            log = f"Required check failed: {type(exc).__name__}"
            passed = False
        if junit and Path(junit).exists():
            report = Path(junit)
            report.write_text(redact(report.read_text(encoding="utf-8"), self.env), encoding="utf-8")
        (self.output / f"{name}.log").write_text(log, encoding="utf-8")
        self.results.append({"name": name, "passed": passed, "seconds": round(time.monotonic()-start, 2)})
        print(f"{name}: {'PASS' if passed else 'FAIL'}", flush=True)
        return passed

    def requirement(self, name, passed):
        self.results.append({"name": name, "passed": bool(passed)})
        print(f"{name}: {'PASS' if passed else 'FAIL'}", flush=True)
        return bool(passed)


def production_settings_valid():
    sys.path.insert(0, str(ROOT / "backend"))
    from app.core.config import Settings
    try:
        settings = Settings(_env_file=ROOT / "backend/.env")
        storage = Path(settings.storage_base_path)
        if not storage.is_absolute():
            storage = ROOT / "backend" / storage
        return (settings.app_env == "production" and settings.postgres_dsn.startswith("postgresql+asyncpg://")
                and storage.is_dir())
    except Exception:
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["developer", "isolated-ci", "release"], default="release")
    parser.add_argument("--suite", choices=["all", "backend", "frontend", "governance", "smoke"], default="all")
    parser.add_argument("--output", type=Path, default=ROOT / "verification-runs/release-check")
    args = parser.parse_args(argv)
    if args.mode == "release" and args.suite != "all":
        parser.error("release mode requires --suite all")
    checks = Checks(args.output.resolve())
    env = checks.env
    env["JWT_SECRET_KEY"] = "isolated-check-only-jwt-key-never-for-production"
    env["APP_ENV"] = "development"
    env["POSTGRES_DSN"] = "sqlite+aiosqlite:///:memory:"
    env["REDIS_DSN"] = env.get("REDIS_TEST_DSN", "redis://127.0.0.1:1/0")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or "npm"
    py = sys.executable
    backend, frontend = ROOT / "backend", ROOT / "frontend"
    if args.suite in ("all", "backend"):
        if checks.command("backend-tools", [py, "-c", "import pytest, alembic, asyncpg, sqlalchemy"]):
            unit = checks.output / "backend-unit.xml"
            checks.command("backend-unit", [py, "-m", "pytest", "-m", "not postgres", f"--junitxml={unit}"], backend, junit=unit)
            if args.mode != "developer":
                if checks.requirement("explicit-test-database", bool(env.get("POSTGRES_TEST_ADMIN_DSN"))):
                    env["FILUM_REQUIRE_POSTGRES_TESTS"] = "true"
                    pg = checks.output / "backend-postgres.xml"
                    checks.command("backend-postgres", [py, "-m", "pytest", "-m", "postgres", f"--junitxml={pg}"], backend, junit=pg, postgres=True)
                    checks.command("isolated-schema", [py, str(ROOT / "scripts/check_schema.py"), "--isolated", "--allow-ki014-compatibility"])
                if checks.requirement("explicit-test-redis", bool(env.get("REDIS_TEST_DSN"))):
                    checks.command("redis", [py, "-c", "import os, redis; assert redis.Redis.from_url(os.environ['REDIS_TEST_DSN'], socket_connect_timeout=5).ping()"])
        checks.command("syntax", [py, "-m", "compileall", "-q", "app", "tests"], backend)
    if args.suite in ("all", "frontend"):
        for name, script in (("typecheck", "type-check"), ("lint", "lint:check"), ("build", "build-only")):
            checks.command(name, [npm, "run", script], frontend)
        junit = checks.output / "frontend.xml"
        checks.command("frontend-unit", [npm, "run", "test:unit", "--", "--run", "--reporter=junit", f"--outputFile={junit}"], frontend, junit=junit)
    if args.suite in ("all", "smoke"):
        checks.command("browser-smoke", [npm, "run", "test:e2e", "--", "e2e/login.spec.ts", "e2e/shell.spec.ts", "e2e/session-races.spec.ts"], frontend)
    if args.suite in ("all", "governance"):
        checks.command("governance", [py, str(ROOT / "scripts/pd.py"), "compliance", "check", "--profile", "strict", "--format", "json"])
    if args.mode == "release":
        checks.requirement("production-settings", production_settings_valid())
        if checks.requirement("explicit-target-database", bool(os.environ.get("POSTGRES_DSN"))):
            env["POSTGRES_DSN"] = os.environ["POSTGRES_DSN"]
            checks.command("target-schema-clean", [py, str(ROOT / "scripts/check_schema.py")])
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL))
    except (OSError, subprocess.CalledProcessError):
        sha = "unknown"
        dirty = True
    if args.mode == "release":
        checks.requirement("release-source-identity", sha != "unknown" and not dirty)
    passed = bool(checks.results) and all(result["passed"] for result in checks.results)
    status = f"{args.mode.upper()}_CHECKS_PASSED" if passed else "CHECKS_FAILED"
    summary = {"status": status, "mode": args.mode, "suite": args.suite, "sha": sha,
               "dirty_worktree": dirty, "human_gates_required": True, "production_ready": False, "checks": checks.results}
    (checks.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"{status}; HUMAN_GATES_REQUIRED; production_ready=false")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
