"""Tool builds, MINT's Go checks, syntax and executable bits, required files, flake evaluation."""

from __future__ import annotations

import os
import py_compile
import shutil

from .core import Context

BASH_SCRIPTS = (
    "scripts/abora-app-catalog.sh",
    "scripts/abora-apps.sh",
    "scripts/abora-custom-packages.sh",
    "scripts/abora.sh",
    "scripts/abora-adopt-nixos.sh",
    "scripts/abora-adopt-bootstrap.sh",
    "scripts/abora-boot.sh",
    "scripts/abora-build.sh",
    "scripts/abora-check-full.sh",
    "scripts/abora-config.sh",
    "scripts/abora-desktop.sh",
    "scripts/abora-desktop-profiles.sh",
    "scripts/abora-dotfiles-import.sh",
    "scripts/abora-doctor.sh",
    "scripts/abora-gaming.sh",
    "scripts/abora-hardware-test.sh",
    "scripts/abora-installer.sh",
    "scripts/abora-repair-flake-purity.sh",
    "scripts/abora-recovery.sh",
    "scripts/abora-session-setup.sh",
    "scripts/abora-setup-launcher.sh",
    "scripts/abora-support-report.sh",
    "scripts/abora-ui.sh",
    "scripts/abora-welcome.sh",
    "scripts/anix.sh",
    "scripts/abora-theme-sync.sh",
    "scripts/abora-update.sh",
    "scripts/abora-desktop-preview.sh",
)

NIX_FILES = (
    "flake.nix",
    "nix/modules/abora-options.nix",
    "nix/modules/anix.nix",
    "nix/modules/branding.nix",
    "nix/modules/installed-base.nix",
    "nix/profiles/live.nix",
    "nix/pkgs/desktop-preview.nix",
    "nix/pkgs/hardware-test.nix",
)

PYTHON_SCRIPTS = (
    "scripts/check-scripts.py",
    "scripts/release/check_scripts/__init__.py",
    "scripts/release/check_scripts/core.py",
    "scripts/release/check_scripts/setup.py",
    "scripts/release/check_scripts/static_checks.py",
    "scripts/release/check_scripts/static_manual.py",
    "scripts/release/check_scripts/gui.py",
    "scripts/release/check_scripts/release.py",
    "scripts/release/check_scripts/suites.py",
    "scripts/release-metadata.py",
    "scripts/release/abora_release.py",
    "scripts/release/tarball.py",
    "scripts/package-anix.py",
    "scripts/build-tinypm-image.py",
    "scripts/package-tinypm.py",
    "scripts/preflight.py",
    "scripts/check-release-files.py",
    "scripts/release/abora_ui.py",
    "scripts/build-iso.py",
    "scripts/rebuild-vm.py",
    "scripts/run-qemu.py",
    "scripts/dev-doctor.py",
    "scripts/check-all-files.py",
    "scripts/check-desktops.py",
    "scripts/abora-config-gui.py",
    "scripts/abora-welcome-gui.py",
    "scripts/abora-gaming-welcome-gui.py",
)

REQUIRED_FILES = (
    "scripts/abora-check-full.sh",
    "scripts/abora-setup.desktop",
    "docs/wiki/ANIX-V1.md",
    "docs/wiki/ANIX-V2-Languages.md",
    "docs/wiki/TinyPM.md",
    "docs/wiki/Abora-Tools.md",
    "docs/wiki/Abora-Gaming.md",
    "docs/wiki/Recovery.md",
    "docs/wiki/Updating-Abora.md",
    "docs/bug-report-template.md",
    "vendor/tinypm/Cargo.toml",
    "vendor/tinypm/src/main.rs",
    "vendor/tinypm/src/bin/grab.rs",
)

NIX_UNAVAILABLE = (
    ("/nix/var/nix/db/big-lock.*Permission denied", "nix store unavailable (flake eval skipped)"),
    ("/nix/var/nix/daemon-socket/socket.*Connection refused", "nix daemon unavailable (flake eval skipped)"),
    ("remote store 'daemon' previously failed", "nix daemon unavailable (flake eval skipped)"),
)


def build_dotnet_tool(ctx: Context, label: str, project: str, dll: str):
    """A plain Debug build (not the slower AOT publish the Nix package uses) is enough for
    behavioural tests. The tools are called as single executables, so wrap `dotnet <dll>`."""
    if not shutil.which("dotnet"):
        ctx.ok(f"dotnet unavailable ({label} runtime tests skipped)")
        return None
    built = ctx.run(["dotnet", "build", str(ctx.repo / project), "-c", "Debug"], env={"MSBuildEnableWorkloadResolver": "false"}, quiet=True)
    if built.returncode != 0:
        ctx.fail(f"{label}: dotnet build failed")
        return None
    wrapper = ctx.tmp / label
    wrapper.write_text(f"#!/usr/bin/env python3\nimport os, sys\nos.execvp('dotnet', ['dotnet', {str(ctx.repo / dll)!r}, *sys.argv[1:]])\n")
    wrapper.chmod(0o755)
    ctx.ok(f"{label}: built for runtime tests")
    return wrapper


def run(ctx: Context) -> None:
    # The updater and ANIX suites need real resolver/plan-tool binaries: there is no Bash fallback.
    ctx.resolver_bin = build_dotnet_tool(
        ctx, "abora-update-resolver", "tools/abora-update-resolver/AboraUpdateResolver.csproj",
        "tools/abora-update-resolver/bin/Debug/net10.0/abora-update-resolver.dll",
    )
    ctx.plan_tool_bin = build_dotnet_tool(
        ctx, "abora-plan-tool", "tools/abora-plan-tool/AboraPlanTool.csproj",
        "tools/abora-plan-tool/bin/Debug/net10.0/abora-plan-tool.dll",
    )

    # vendor/mint had no automated verification before: only the manual `make
    # test-installer*` targets. go vet/test are its baseline safety net.
    if shutil.which("go"):
        for step in ("build", "vet", "test"):
            done = ctx.run(["go", step, "./..."], cwd=ctx.repo / "vendor/mint", quiet=True)
            ctx.result(done.returncode == 0, f"vendor/mint: go {step}")
    else:
        ctx.ok("go unavailable (vendor/mint build/vet/test skipped)")

    for file in BASH_SCRIPTS:
        path = ctx.path(file)
        if not path.is_file():
            ctx.fail(f"Missing file: {file}")
            continue
        ctx.result(ctx.run(["bash", "-n", file]).returncode == 0, f"syntax (bash): {file}")
        if os.access(path, os.X_OK):
            ctx.ok(f"executable: {file}")
        else:
            ctx.fail(f"not executable: {file}")

    for file in PYTHON_SCRIPTS:
        path = ctx.path(file)
        if not path.is_file():
            ctx.fail(f"Missing file: {file}")
            continue
        try:
            py_compile.compile(str(path), doraise=True)
            ctx.ok(f"syntax (python): {file}")
        except py_compile.PyCompileError as exc:
            ctx.fail(f"syntax (python): {file}")
            ctx.detail(str(exc))

    if shutil.which("shellcheck"):
        # -S error matches CI's "ShellCheck scripts" step; warning-level style nits
        # belong to check-all-files' warning tier, not a hard gate here.
        linted = ctx.run(["shellcheck", "-S", "error", "scripts/abora-update.sh", "scripts/abora-repair-flake-purity.sh"])
        ctx.result(linted.returncode == 0, "shellcheck: updater and repair scripts")
    else:
        ctx.ok("shellcheck unavailable (updater lint skipped)")

    for file in (*NIX_FILES, *REQUIRED_FILES):
        if ctx.path(file).is_file():
            ctx.ok(f"exists: {file}")
        else:
            ctx.fail(f"Missing file: {file}")

    if ctx.run(["git", "rev-parse", "--is-inside-work-tree"], quiet=True).returncode == 0:
        for file in REQUIRED_FILES:
            if not ctx.path(file).is_file():
                continue
            if ctx.run(["git", "ls-files", "--error-unmatch", file], quiet=True).returncode == 0:
                ctx.ok(f"tracked by git: {file}")
            else:
                ctx.fail(f"untracked source file: {file}")

    if not shutil.which("nix"):
        ctx.ok("nix command unavailable (flake eval skipped)")
        return
    shown = ctx.run(["nix", "--extra-experimental-features", "nix-command flakes", "flake", "show", "--no-write-lock-file", str(ctx.repo)], capture=True)
    if shown.returncode == 0:
        ctx.ok("nix flake evaluation")
        return
    for pattern, message in NIX_UNAVAILABLE:
        if ctx.grep("-q", pattern, stdin=shown.stdout):
            ctx.ok(message)
            return
    ctx.fail("nix flake evaluation")
    ctx.detail(shown.stdout)
