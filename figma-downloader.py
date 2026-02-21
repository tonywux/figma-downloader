import argparse
import os
from datetime import datetime

from dotenv import load_dotenv

from detector import FigmaDetector
from downloader import FigmaDownloader
from notifications import NotificationManager

load_dotenv()


def format_summary(summary):
    end_time = summary.get("end_time")
    start_time = summary.get("start_time")
    duration = "N/A"
    if isinstance(start_time, datetime) and isinstance(end_time, datetime):
        duration = str(end_time - start_time).split(".")[0]

    return {
        "total_found": summary.get("total_found", 0),
        "new_downloaded": summary.get("new_downloaded", 0),
        "skipped": summary.get("skipped", 0),
        "errors": summary.get("errors", 0),
        "error_messages": summary.get("error_messages", []),
        "duration": duration,
    }


def run_detect(detector):
    start_time = datetime.now()
    manifest = detector.detect_images()
    end_time = datetime.now()
    return {
        "start_time": start_time,
        "end_time": end_time,
        "total_found": manifest.get("total_found", 0),
        "new_downloaded": 0,
        "skipped": manifest.get("total_found", 0) - manifest.get("new_items", 0),
        "errors": 0,
        "error_messages": [],
    }


def run_download(downloader):
    return downloader.download_from_manifest()


def run_both(detector, downloader):
    start_time = datetime.now()
    manifest = detector.detect_images()
    download_summary = downloader.download_from_nodes(manifest.get("items", []))
    download_summary["start_time"] = start_time
    return download_summary


def main():
    parser = argparse.ArgumentParser(description="Figma detector/downloader")
    parser.add_argument(
        "--mode",
        choices=["detect", "download", "both"],
        default=os.getenv("RUN_MODE", "both"),
        help="Run mode",
    )
    args = parser.parse_args()

    figma_token = os.getenv("FIGMA_TOKEN")
    file_key = os.getenv("FILE_KEY")
    download_dir = os.getenv("DOWNLOAD_DIR", "./figma_downloads")
    batch_size = int(os.getenv("BATCH_SIZE", 30))

    if not figma_token or not file_key:
        print("ERROR: Please set FIGMA_TOKEN and FILE_KEY environment variables")
        return 1

    notifier = NotificationManager()
    detector = FigmaDetector(figma_token, file_key, download_dir)
    downloader = FigmaDownloader(figma_token, file_key, download_dir, batch_size)

    summary = None
    should_notify = args.mode in {"download", "both"}
    if should_notify:
        notifier.send_run_started(args.mode)

    try:
        print(f"Starting Figma run in mode: {args.mode}")

        if args.mode == "detect":
            summary = run_detect(detector)
        elif args.mode == "download":
            summary = run_download(downloader)
        else:
            summary = run_both(detector, downloader)

        compact_summary = format_summary(summary)
        print("Run completed")
        print(f"Total found: {compact_summary['total_found']}")
        print(f"Downloaded: {compact_summary['new_downloaded']}")
        print(f"Skipped: {compact_summary['skipped']}")
        print(f"Errors: {compact_summary['errors']}")
        print(f"Duration: {compact_summary['duration']}")

        if should_notify:
            notifier.send_run_finished(args.mode, summary, success=True)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        if summary is None:
            summary = {
                "start_time": datetime.now(),
                "end_time": datetime.now(),
                "total_found": 0,
                "new_downloaded": 0,
                "skipped": 0,
                "errors": 1,
                "error_messages": [str(exc)],
            }
        else:
            summary["errors"] = summary.get("errors", 0) + 1
            summary.setdefault("error_messages", []).append(str(exc))
            summary["end_time"] = datetime.now()
        if should_notify:
            notifier.send_run_finished(args.mode, summary, success=False)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
