import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import requests


class FigmaDetector:
    def __init__(self, token, file_key, download_dir):
        self.token = token
        self.file_key = file_key
        self.download_dir = Path(download_dir)
        self.headers = {"X-Figma-Token": token}
        self.state_file = self.download_dir / "download_state.json"
        self.manifest_file = self.download_dir / "detected_images.json"
        self.manifest_csv_file = self.download_dir / "detected_images.csv"

        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.downloaded_items = self.load_state()

    def load_state(self):
        if self.state_file.exists():
            with open(self.state_file, "r") as f:
                return json.load(f)
        return {}

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

    def get_file_data(self):
        url = f"https://api.figma.com/v1/files/{self.file_key}"
        response = requests.get(url, headers=self.headers, timeout=30)

        if response.status_code != 200:
            raise Exception(f"Failed to get file data: {response.text}")

        return response.json()

    def find_image_nodes(self, node, nodes=None, path=""):
        if nodes is None:
            nodes = []

        if hasattr(node, "get"):
            node_type = node.get("type", "")
            node_name = node.get("name", "Unnamed")
            node_id = node.get("id", "")

            should_export = False
            if node_type in ["FRAME", "RECTANGLE", "ELLIPSE"]:
                fills = node.get("fills", [])
                for fill in fills:
                    if fill.get("type") == "IMAGE":
                        should_export = True
                        break
            elif node_type == "IMAGE":
                should_export = True

            if should_export:
                current_path = f"{path}/{node_name}" if path else node_name
                nodes.append(
                    {
                        "id": node_id,
                        "name": node_name,
                        "type": node_type,
                        "path": current_path,
                    }
                )

            children = node.get("children", [])
            for child in children:
                child_path = f"{path}/{node_name}" if path else node_name
                self.find_image_nodes(child, nodes, child_path)

        return nodes

    def save_detection_manifest(self, image_nodes):
        detected_at = datetime.now().isoformat()
        manifest_items = []
        new_count = 0

        for node in image_nodes:
            already_downloaded = self.is_already_downloaded(node)
            if not already_downloaded:
                new_count += 1

            manifest_items.append(
                {
                    "id": node["id"],
                    "name": node["name"],
                    "type": node["type"],
                    "path": node["path"],
                    "status": "downloaded" if already_downloaded else "new",
                    "detected_at": detected_at,
                }
            )

        manifest_data = {
            "detected_at": detected_at,
            "file_key": self.file_key,
            "total_found": len(manifest_items),
            "new_items": new_count,
            "items": manifest_items,
        }

        with open(self.manifest_file, "w") as f:
            json.dump(manifest_data, f, indent=2)

        with open(self.manifest_csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["id", "name", "type", "path", "status", "detected_at"]
            )
            writer.writeheader()
            for item in manifest_items:
                writer.writerow(item)

        return manifest_data

    def detect_images(self):
        print("Getting file data...")
        file_data = self.get_file_data()

        print("Finding images...")
        image_nodes = []
        for page in file_data["document"]["children"]:
            page_nodes = self.find_image_nodes(page, path=page.get("name", "Page"))
            image_nodes.extend(page_nodes)

        if not image_nodes:
            print("No images found in file")
            return self.save_detection_manifest([])

        print(f"Found {len(image_nodes)} potential images")
        manifest = self.save_detection_manifest(image_nodes)
        print(f"Manifest saved: {self.manifest_file}")
        print(f"CSV saved: {self.manifest_csv_file}")
        print(f"New items pending download: {manifest['new_items']}")
        return manifest
