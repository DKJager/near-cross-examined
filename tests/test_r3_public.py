import sys, os, shutil, subprocess, tempfile, pathlib, re

_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_R, os.path.join(_R, "src")]

def test_forbidden_strings_in_public_files():
    """Check that public files do not contain forbidden strings."""
    root = pathlib.Path(_R)
    public_files = []

    # top-level markdown and other files
    for p in ["README.md", "THESIS.md", "TRIPWIRES.md", "WEAKNESSES.md", "Makefile", "forecasts.json"]:
        public_files.append(root / p)

    # out/index.html and optional docs/index.html
    public_files.append(root / "out" / "index.html")
    docs_index = root / "docs" / "index.html"
    if docs_index.is_file():
        public_files.append(docs_index)

    # *.py files directly in root
    for f in root.glob("*.py"):
        public_files.append(f)

    # data/MANIFEST.json
    public_files.append(root / "data" / "MANIFEST.json")

    # sql/*.sql
    sql_dir = root / "sql"
    if sql_dir.is_dir():
        for f in sql_dir.glob("*.sql"):
            public_files.append(f)

    forbidden = [
        ("openrouter", lambda txt: "openrouter" in txt.lower()),
        ("XXL", lambda txt: "XXL" in txt),
        ("6 of 6", lambda txt: "6 of 6" in txt),
    ]

    offenders = []
    for f in public_files:
        if not f.is_file():
            continue
        try:
            txt = f.read_text(encoding="utf-8")
        except Exception:
            continue
        for name, check in forbidden:
            if check(txt):
                offenders.append(f"{f}: contains '{name}'")

    assert not offenders, f"Public files contain forbidden strings: {', '.join(offenders)}"

def _copy_regular(src_root: pathlib.Path, dst_root: pathlib.Path):
    # copy data, out, docs directories
    for sub in ["data", "out", "docs", "sql"]:
        s = src_root / sub
        d = dst_root / sub
        if s.is_dir():
            # what a fresh clone holds: the source files are not shipped (data/RAW_NOT_COMMITTED.txt)
            skip = set()
            rn = src_root / "data" / "RAW_NOT_COMMITTED.txt"
            if sub == "data" and rn.is_file():
                skip = {ln.strip() for ln in rn.read_text().splitlines() if ln.strip() and not ln.startswith("#")}
            shutil.copytree(s, d, ignore=lambda _dir, names: [n for n in names if n in skip])

    # copy regular files at root: Makefile, LICENSE, *.py, *.md, *.json
    for item in src_root.iterdir():
        if item.is_file() and (item.name in {"Makefile", "LICENSE"} or item.suffix in {".py", ".md", ".json"}):
            shutil.copy2(item, dst_root / item.name)

    # copy tests folder without this file
    tests_src = src_root / "tests"
    tests_dst = dst_root / "tests"
    tests_dst.mkdir(exist_ok=True)
    for item in tests_src.iterdir():
        if item.is_file() and item.name != "test_r3_public.py":
            shutil.copy2(item, tests_dst / item.name)

def test_install_steps_fresh_venv():
    """Validate the four install steps run correctly in a fresh venv."""
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td) / "repo"
        repo.mkdir()
        _copy_regular(pathlib.Path(_R), repo)

        readme_path = repo / "README.md"
        assert readme_path.is_file(), "README.md missing in copy"
        readme_text = readme_path.read_text(encoding="utf-8")
        # extract fenced block under ## Install
        install_section = re.search(r"## Install\s+```sh\n(.*?)```", readme_text, re.DOTALL)
        assert install_section, "Install fenced block not found"
        lines = [ln.strip() for ln in install_section.group(1).splitlines() if ln.strip()]
        expected = [
            "python3 -m venv .venv",
            ". .venv/bin/activate",
            "pip install pytest",
            "make verify",
        ]
        assert lines == expected, f"Install steps differ: {lines!r} vs {expected!r}"

        # run the four lines as one script
        script = "set -e\n" + "\n".join(lines) + "\n"
        env = {"PATH": os.getenv("PATH", ""), "HOME": str(pathlib.Path(td))}
        result = subprocess.run(
            ["sh", "-c", script],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        out = result.stdout + result.stderr
        assert result.returncode == 0, f"Install script failed with rc={result.returncode}"
        assert "VERIFY OK" in out, "VERIFY OK not in install output"
        assert "VERIFY OK (offline)" in out, "a fresh clone must verify in offline mode"
        assert "DOCS OK" in out, "DOCS OK not in install output"

def test_make_verify_without_pytest():
    """Check that make verify aborts cleanly when pytest is unavailable."""
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td) / "repo"
        repo.mkdir()
        _copy_regular(pathlib.Path(_R), repo)

        # create venv without pip
        venv_dir = repo / "venv_nopip"
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv_dir)], check=True)

        py_bin = venv_dir / "bin" / "python"
        cmd = ["make", "verify", f"PY={py_bin}"]
        result = subprocess.run(
            cmd,
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=600,
        )
        out = result.stdout + result.stderr
        assert result.returncode != 0, "make verify should exit non‑zero without pytest"
        assert "needs pytest" in out.lower(), "Missing message about needing pytest"
        assert "pip install pytest" in out.lower(), "Missing pip install suggestion"
        assert "Traceback" not in out, "Unexpected traceback in output"

if __name__ == "__main__":
    for fn in [obj for name, obj in globals().items() if name.startswith("test_")]:
        fn()
    print("PASS")
