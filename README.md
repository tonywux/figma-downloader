# Figma Downloader

Minimal Python tool to detect and download image assets from a Figma file.

## Quick Start

1. Install dependencies:

```bash
pip install requests python-dotenv
```

2. Create `.env` in the project root:

```env
FIGMA_TOKEN=your_figma_personal_access_token
FILE_KEY=your_figma_file_key
DOWNLOAD_DIR=./figma_downloads
BATCH_SIZE=30
```

3. Run detect + download:

```bash
python figma-downloader.py --mode both
```

## Run Modes

- `detect`: scan the Figma file and write `detected_images.json` / `detected_images.csv`
- `download`: download from existing manifest
- `both`: detect first, then download (default)

Examples:

```bash
python figma-downloader.py --mode detect
python figma-downloader.py --mode download
python figma-downloader.py --mode both
```

## Cron Scheduler (Optional)

Use `cron-manager.py` to install jobs for detect/download:

```bash
python cron-manager.py start
python cron-manager.py status
python cron-manager.py stop
```

Optional env vars:

```env
CRON_DETECT_SCHEDULE=0 * * * *
CRON_DOWNLOAD_SCHEDULE=5 12,18,22 * * *
CRON_LOG_FILE=logs/scheduler.log
```

## Notifications (Optional)

Telegram notifications are sent when these values are set:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
NOTIFICATION_SERVICE_LABEL=Figma Downloader
```

## Output

- Downloaded files are saved under `DOWNLOAD_DIR` in date-based folders.
- State is stored in `download_state.json` to prevent duplicates.

## License

MIT. See `LICENSE`.