#!/usr/bin/env python3
"""
Manage cron jobs for figma-downloader detect/download modes.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()


CRON_BLOCK_BEGIN = "# FIGMA_DOWNLOADER_CRON_BEGIN"
CRON_BLOCK_END = "# FIGMA_DOWNLOADER_CRON_END"


def project_dir():
    return Path(__file__).resolve().parent


def python_command():
    venv_python = project_dir() / "venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def detect_schedule():
    return os.getenv("CRON_DETECT_SCHEDULE", "0 * * * *")


def download_schedule():
    return os.getenv("CRON_DOWNLOAD_SCHEDULE", "5 12,18,22 * * *")


def cron_log_file():
    return os.getenv("CRON_LOG_FILE", "logs/scheduler.log")


def get_current_crontab():
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout


def strip_existing_block(crontab_content):
    lines = crontab_content.splitlines()
    cleaned = []
    in_block = False

    for line in lines:
        if line.strip() == CRON_BLOCK_BEGIN:
            in_block = True
            continue
        if line.strip() == CRON_BLOCK_END:
            in_block = False
            continue
        if not in_block:
            cleaned.append(line)

    cleaned_content = "\n".join(cleaned).strip()
    return f"{cleaned_content}\n" if cleaned_content else ""


def build_cron_block():
    cwd = str(project_dir())
    py = python_command()
    log_path = cron_log_file().replace('"', '\\"')
    detect = (
        f"{detect_schedule()} cd \"{cwd}\" && "
        f"{py} figma-downloader.py --mode detect >> \"{log_path}\" 2>&1"
    )
    download = (
        f"{download_schedule()} cd \"{cwd}\" && "
        f"{py} figma-downloader.py --mode download >> \"{log_path}\" 2>&1"
    )

    return "\n".join(
        [
            CRON_BLOCK_BEGIN,
            "# Detect job",
            detect,
            "# Download job",
            download,
            CRON_BLOCK_END,
            "",
        ]
    )


def install_crontab(content):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".cron", delete=False) as temp:
        temp.write(content)
        temp_path = temp.name

    try:
        result = subprocess.run(["crontab", temp_path], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or "Unknown crontab error")
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def is_active(crontab_content):
    return CRON_BLOCK_BEGIN in crontab_content and CRON_BLOCK_END in crontab_content


def start():
    current = get_current_crontab()
    base = strip_existing_block(current)
    new_content = base + build_cron_block()
    install_crontab(new_content)
    print("Cron jobs installed")
    print(f"Detect schedule:   {detect_schedule()}")
    print(f"Download schedule: {download_schedule()}")
    print(f"Log file:          {cron_log_file()}")


def stop():
    current = get_current_crontab()
    if not current.strip():
        print("No crontab entries found")
        return

    base = strip_existing_block(current).strip()
    if base:
        install_crontab(base + "\n")
    else:
        subprocess.run(["crontab", "-r"], check=False)

    print("Cron jobs removed")


def status():
    current = get_current_crontab()
    active = is_active(current)
    print("Figma cron manager status")
    print(f"Active: {'yes' if active else 'no'}")
    print(f"Detect schedule (env):   {detect_schedule()}")
    print(f"Download schedule (env): {download_schedule()}")
    print(f"Log file (env):          {cron_log_file()}")
    if active:
        print("")
        print("Installed cron block:")
        for line in current.splitlines():
            if (
                line.strip() == CRON_BLOCK_BEGIN
                or line.strip() == CRON_BLOCK_END
                or "figma-downloader.py --mode detect" in line
                or "figma-downloader.py --mode download" in line
                or line.strip() in {"# Detect job", "# Download job"}
            ):
                print(line)


def show_help():
    print("Usage: python cron-manager.py [start|stop|status|help]")
    print("")
    print("Commands:")
    print("  start   Install or update detect/download cron jobs")
    print("  stop    Remove detect/download cron jobs")
    print("  status  Show cron manager status and installed block")
    print("  help    Show this help")
    print("")
    print("Environment variables:")
    print("  CRON_DETECT_SCHEDULE   (default: 0 * * * *)")
    print("  CRON_DOWNLOAD_SCHEDULE (default: 5 12,18,22 * * *)")
    print("  CRON_LOG_FILE          (default: logs/scheduler.log)")


def main():
    if len(sys.argv) < 2:
        show_help()
        return 0

    command = sys.argv[1].lower()
    if command == "start":
        start()
        return 0
    if command == "stop":
        stop()
        return 0
    if command == "status":
        status()
        return 0
    if command == "help":
        show_help()
        return 0

    print(f"Unknown command: {command}")
    show_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
