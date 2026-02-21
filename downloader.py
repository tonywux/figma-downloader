import hashlib
import json
import math
import time
from datetime import datetime
from pathlib import Path

import requests


class FigmaDownloader:
    def __init__(self, token, file_key, download_dir, batch_size=30):
        self.token = token
        self.file_key = file_key
        self.download_dir = Path(download_dir)
        self.batch_size = batch_size
        self.headers = {"X-Figma-Token": token}
        self.state_file = self.download_dir / "download_state.json"
        self.manifest_file = self.download_dir / "detected_images.json"

        self.rate_limit_requests_per_minute = 10
        self.rate_limit_window = 60
        self.request_timestamps = []

        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.downloaded_items = self.load_state()

    def load_state(self):
        if self.state_file.exists():
            with open(self.state_file, "r") as f:
                return json.load(f)
        return {}

    def save_state(self):
        with open(self.state_file, "w") as f:
            json.dump(self.downloaded_items, f, indent=2)

    def create_item_hash(self, node_info):
        content = f"{self.file_key}_{node_info['id']}"
        return hashlib.md5(content.encode()).hexdigest()

    def create_legacy_item_hash(self, node_info):
        content = f"{node_info['id']}_{node_info['name']}"
        return hashlib.md5(content.encode()).hexdigest()

    def is_already_downloaded(self, node_info):
        item_hash = self.create_item_hash(node_info)
        legacy_hash = self.create_legacy_item_hash(node_info)
        return item_hash in self.downloaded_items or legacy_hash in self.downloaded_items

    def wait_for_rate_limit(self):
        current_time = time.time()
        self.request_timestamps = [
            ts
            for ts in self.request_timestamps
            if current_time - ts < self.rate_limit_window
        ]

        if len(self.request_timestamps) >= self.rate_limit_requests_per_minute:
            oldest_request = min(self.request_timestamps)
            wait_time = self.rate_limit_window - (current_time - oldest_request)
            if wait_time > 0:
                print(f"Rate limit reached. Waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time + 0.1)

        self.request_timestamps.append(current_time)

    def export_images_batch(self, node_ids, retry_count=3):
        if not node_ids:
            return {}

        url = f"https://api.figma.com/v1/images/{self.file_key}"
        params = {"ids": ",".join(node_ids), "format": "png", "scale": "2"}
        response = None

        for attempt in range(retry_count):
            try:
                self.wait_for_rate_limit()
                response = requests.get(
                    url, headers=self.headers, params=params, timeout=30
                )

                if response.status_code == 200:
                    return response.json()
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    rate_limit_type = response.headers.get(
                        "X-Figma-Rate-Limit-Type", "unknown"
                    )
                    plan_tier = response.headers.get("X-Figma-Plan-Tier", "unknown")
                    print(
                        f"WARNING: Rate limited (attempt {attempt + 1}): "
                        f"{rate_limit_type} limit on {plan_tier} plan"
                    )
                    if attempt < retry_count - 1:
                        print(f"Waiting {retry_after} seconds before retry...")
                        time.sleep(retry_after)
                    else:
                        raise Exception(
                            f"Rate limited after {retry_count} attempts. "
                            f"Retry after {retry_after} seconds."
                        )
                elif response.status_code == 400:
                    error_data = response.json()
                    if "timeout" in error_data.get("err", "").lower():
                        print(
                            f"WARNING: Batch timeout on attempt {attempt + 1}, "
                            "retrying with smaller batch..."
                        )
                        if attempt == retry_count - 1:
                            raise Exception(
                                f"Batch timeout after {retry_count} attempts"
                            )
                    else:
                        raise Exception(f"Failed to export images: {response.text}")
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")

            except requests.exceptions.Timeout:
                print(f"WARNING: Request timeout on attempt {attempt + 1}")
                if attempt == retry_count - 1:
                    raise Exception("Request timeout after multiple attempts")

            if response is None or response.status_code != 429:
                time.sleep(2**attempt)

        return {}

    def download_image(self, url, filepath, retry_count=3):
        for attempt in range(retry_count):
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    with open(filepath, "wb") as f:
                        f.write(response.content)
                    return True
            except Exception as exc:
                print(f"WARNING: Download attempt {attempt + 1} failed: {exc}")
                if attempt < retry_count - 1:
                    time.sleep(1)
        return False

    def generate_filename(self, node_info, timestamp):
        clean_name = "".join(
            c for c in node_info["name"] if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        clean_name = clean_name.replace(" ", "_")
        if len(clean_name) > 50:
            clean_name = clean_name[:50]
        return f"{timestamp}_{clean_name}_{node_info['id'][:8]}.png"

    def load_detection_manifest(self):
        if not self.manifest_file.exists():
            return None
        with open(self.manifest_file, "r") as f:
            return json.load(f)

    def process_batch(self, batch_nodes, batch_num, total_batches, timestamp, today_dir):
        print(f"Processing batch {batch_num}/{total_batches} ({len(batch_nodes)} images)")
        node_ids = [node["id"] for node in batch_nodes]

        try:
            export_data = self.export_images_batch(node_ids)
            if "images" not in export_data:
                print(f"ERROR: No export URLs received for batch {batch_num}")
                return 0

            downloaded_count = 0
            for node in batch_nodes:
                node_id = node["id"]
                if node_id in export_data["images"]:
                    image_url = export_data["images"][node_id]
                    if image_url:
                        filename = self.generate_filename(node, timestamp)
                        filepath = today_dir / filename
                        if self.download_image(image_url, filepath):
                            print(f"  OK: {filename}")
                            item_hash = self.create_item_hash(node)
                            self.downloaded_items[item_hash] = {
                                "node_id": node_id,
                                "name": node["name"],
                                "downloaded_at": datetime.now().isoformat(),
                                "filepath": str(filepath),
                            }
                            downloaded_count += 1
                        else:
                            print(f"  ERROR: Failed to download: {node['name']}")
                    else:
                        print(f"  WARNING: No URL for: {node['name']}")
                else:
                    print(f"  WARNING: No export data for: {node['name']}")

            self.save_state()
            return downloaded_count

        except Exception as exc:
            error_msg = str(exc)
            print(f"ERROR: Batch {batch_num} failed: {error_msg}")

            if len(batch_nodes) > 1 and (
                "timeout" in error_msg.lower() or "rate limited" in error_msg.lower()
            ):
                print(f"Retrying by splitting batch {batch_num} into smaller pieces...")
                mid = len(batch_nodes) // 2

                count1 = self.process_batch(
                    batch_nodes[:mid], f"{batch_num}a", total_batches, timestamp, today_dir
                )
                delay = 5 if "rate limited" in error_msg.lower() else 2
                time.sleep(delay)
                count2 = self.process_batch(
                    batch_nodes[mid:], f"{batch_num}b", total_batches, timestamp, today_dir
                )
                return count1 + count2

            return 0

    def download_from_nodes(self, candidate_nodes):
        start_time = datetime.now()
        summary = {
            "start_time": start_time,
            "end_time": None,
            "total_found": len(candidate_nodes),
            "new_downloaded": 0,
            "skipped": 0,
            "errors": 0,
            "error_messages": [],
        }

        try:
            new_nodes = [
                node for node in candidate_nodes if not self.is_already_downloaded(node)
            ]
            summary["skipped"] = len(candidate_nodes) - len(new_nodes)

            if not new_nodes:
                print("No new images to download")
                summary["end_time"] = datetime.now()
                return summary

            print(f"Downloading {len(new_nodes)} new images...")
            print(f"Processing in batches of {self.batch_size}")

            today = datetime.now().strftime("%Y-%m-%d")
            today_dir = self.download_dir / today
            today_dir.mkdir(exist_ok=True)

            total_downloaded = 0
            timestamp = datetime.now().strftime("%H%M%S")
            total_batches = math.ceil(len(new_nodes) / self.batch_size)

            for i in range(0, len(new_nodes), self.batch_size):
                batch_nodes = new_nodes[i : i + self.batch_size]
                batch_num = (i // self.batch_size) + 1
                batch_downloaded = self.process_batch(
                    batch_nodes, batch_num, total_batches, timestamp, today_dir
                )
                total_downloaded += batch_downloaded
                if batch_num < total_batches:
                    print("Waiting 20 seconds before next batch...")
                    time.sleep(20)

            summary["new_downloaded"] = total_downloaded
            print(
                f"Successfully downloaded {total_downloaded}/{len(new_nodes)} images to {today_dir}"
            )
            summary["end_time"] = datetime.now()
            return summary

        except Exception as exc:
            summary["errors"] += 1
            summary["error_messages"].append(str(exc))
            summary["end_time"] = datetime.now()
            raise

    def download_from_manifest(self):
        manifest = self.load_detection_manifest()
        if not manifest:
            raise Exception(
                f"Manifest not found at {self.manifest_file}. Run detect mode first."
            )
        print(
            f"Loaded manifest from {manifest.get('detected_at', 'unknown time')} "
            f"with {len(manifest.get('items', []))} items"
        )
        return self.download_from_nodes(manifest.get("items", []))
