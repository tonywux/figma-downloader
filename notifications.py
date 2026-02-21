import os
import html
from datetime import datetime

import requests


class NotificationManager:
    def __init__(self):
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        self.service_label = os.getenv("NOTIFICATION_SERVICE_LABEL", "Figma Downloader").strip()

    def is_configured(self):
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    def _send_telegram(self, message_html):
        if not (self.telegram_bot_token and self.telegram_chat_id):
            return
        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": message_html,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code != 200:
            raise Exception(f"Telegram notification failed: {response.text}")

    def send(self, message_html):
        if not self.is_configured():
            return
        try:
            self._send_telegram(message_html)
        except Exception as exc:
            print(f"WARNING: Notification failed: {exc}")

    def send_run_started(self, mode):
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        service_label = html.escape(self.service_label)
        mode_label = html.escape(mode.capitalize())
        started_at_safe = html.escape(started_at)
        message = (
            f"<b>[{service_label}] Run Started</b>\n"
            f"<b>Mode:</b> {mode_label}\n"
            f"<b>Started:</b> <code>{started_at_safe}</code>\n"
            f"<b>Status:</b> In progress"
        )
        self.send(message)

    def send_run_finished(self, mode, summary, success=True):
        end_time = summary.get("end_time")
        if isinstance(end_time, datetime):
            end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            end_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        start_time = summary.get("start_time")
        if isinstance(start_time, datetime):
            start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            start_time_str = "N/A"

        status = "Success" if success else "Failed"
        status_safe = html.escape(status)
        service_label = html.escape(self.service_label)
        mode_label = html.escape(mode.capitalize())
        start_time_safe = html.escape(start_time_str)
        end_time_safe = html.escape(end_time_str)
        duration = "N/A"
        if isinstance(start_time, datetime) and isinstance(end_time, datetime):
            duration = str(end_time - start_time).split(".")[0]
        duration_safe = html.escape(duration)

        lines = [
            f"<b>[{service_label}] Run Finished</b>",
            f"<b>Result:</b> {status_safe}",
            f"<b>Mode:</b> {mode_label}",
            f"<b>Started:</b> <code>{start_time_safe}</code>",
            f"<b>Finished:</b> <code>{end_time_safe}</code>",
            f"<b>Duration:</b> <code>{duration_safe}</code>",
            "",
            "<b>Summary</b>",
            f"- Total found: <b>{summary.get('total_found', 0)}</b>",
            f"- Downloaded: <b>{summary.get('new_downloaded', 0)}</b>",
            f"- Skipped: <b>{summary.get('skipped', 0)}</b>",
            f"- Errors: <b>{summary.get('errors', 0)}</b>",
        ]

        error_messages = summary.get("error_messages", [])
        if error_messages:
            lines.append("")
            lines.append("<b>Error details</b>")
            for msg in error_messages[:5]:
                lines.append(f"- <code>{html.escape(str(msg))}</code>")

        self.send("\n".join(lines))
