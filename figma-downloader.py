import requests
import os
import json
import hashlib

from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()


class FigmaDownloader:
    def __init__(self, token, file_key, download_dir="./downloads"):
        self.token = token
        self.file_key = file_key
        self.download_dir = Path(download_dir)
        self.headers = {"X-Figma-Token": token}
        self.state_file = self.download_dir / "download_state.json"
        
        # Create directories
        self.download_dir.mkdir(exist_ok=True)
        self.downloaded_items = self.load_state()
    
    def load_state(self):
        """Load previously downloaded items to avoid duplicates"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_state(self):
        """Save current download state"""
        with open(self.state_file, 'w') as f:
            json.dump(self.downloaded_items, f, indent=2)
    
    def get_file_data(self):
        """Get Figma file structure"""
        url = f"https://api.figma.com/v1/files/{self.file_key}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            raise Exception(f"Failed to get file data: {response.text}")
        
        return response.json()
    
    def find_image_nodes(self, node, nodes=None, path=""):
        """Recursively find all nodes that contain images"""
        if nodes is None:
            nodes = []
        
        # Check if node has fills with images or is an image node
        if hasattr(node, 'get'):
            node_type = node.get('type', '')
            node_name = node.get('name', 'Unnamed')
            node_id = node.get('id', '')
            
            # Look for frames/rectangles with image fills or actual image nodes
            should_export = False
            
            if node_type in ['FRAME', 'RECTANGLE', 'ELLIPSE']:
                fills = node.get('fills', [])
                for fill in fills:
                    if fill.get('type') == 'IMAGE':
                        should_export = True
                        break
            elif node_type == 'IMAGE':
                should_export = True
            
            if should_export:
                current_path = f"{path}/{node_name}" if path else node_name
                nodes.append({
                    'id': node_id,
                    'name': node_name,
                    'type': node_type,
                    'path': current_path
                })
            
            # Recursively check children
            children = node.get('children', [])
            for child in children:
                child_path = f"{path}/{node_name}" if path else node_name
                self.find_image_nodes(child, nodes, child_path)
        
        return nodes
    
    def export_images(self, node_ids):
        """Export images from Figma"""
        if not node_ids:
            return {}
        
        url = f"https://api.figma.com/v1/images/{self.file_key}"
        params = {
            'ids': ','.join(node_ids),
            'format': 'png',
            'scale': '2'  # Higher resolution
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code != 200:
            raise Exception(f"Failed to export images: {response.text}")
        
        return response.json()
    
    def download_image(self, url, filepath):
        """Download image from URL to file"""
        response = requests.get(url)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return True
        return False
    
    def generate_filename(self, node_info, timestamp):
        """Generate a clean filename"""
        # Clean the name for filesystem
        clean_name = "".join(c for c in node_info['name'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_name = clean_name.replace(' ', '_')
        
        # Create filename with timestamp
        filename = f"{timestamp}_{clean_name}_{node_info['id'][:8]}.png"
        return filename
    
    def create_item_hash(self, node_info):
        """Create hash to identify if item was already downloaded"""
        # Use node ID and name to create hash
        content = f"{node_info['id']}_{node_info['name']}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def run(self):
        """Main execution function"""
        print("🎨 Starting Figma screenshot download...")
        
        try:
            # Get file data
            print("📋 Getting file data...")
            file_data = self.get_file_data()
            
            # Find image nodes
            print("🔍 Finding images...")
            image_nodes = []
            
            # Check all pages
            for page in file_data['document']['children']:
                page_nodes = self.find_image_nodes(page, path=page.get('name', 'Page'))
                image_nodes.extend(page_nodes)
            
            if not image_nodes:
                print("✨ No images found in file")
                return
            
            print(f"📸 Found {len(image_nodes)} potential images")
            
            # Filter out already downloaded items
            new_nodes = []
            for node in image_nodes:
                item_hash = self.create_item_hash(node)
                if item_hash not in self.downloaded_items:
                    new_nodes.append(node)
            
            if not new_nodes:
                print("✅ No new images to download")
                return
            
            print(f"⬇️  Downloading {len(new_nodes)} new images...")
            
            # Export images
            node_ids = [node['id'] for node in new_nodes]
            export_data = self.export_images(node_ids)
            
            if 'images' not in export_data:
                print("❌ No export URLs received")
                return
            
            # Create today's folder
            today = datetime.now().strftime('%Y-%m-%d')
            today_dir = self.download_dir / today
            today_dir.mkdir(exist_ok=True)
            
            # Download each image
            timestamp = datetime.now().strftime('%H%M%S')
            downloaded_count = 0
            
            for node in new_nodes:
                node_id = node['id']
                if node_id in export_data['images']:
                    image_url = export_data['images'][node_id]
                    if image_url:  # Sometimes URLs can be null
                        filename = self.generate_filename(node, timestamp)
                        filepath = today_dir / filename
                        
                        if self.download_image(image_url, filepath):
                            print(f"✅ Downloaded: {filename}")
                            
                            # Mark as downloaded
                            item_hash = self.create_item_hash(node)
                            self.downloaded_items[item_hash] = {
                                'node_id': node_id,
                                'name': node['name'],
                                'downloaded_at': datetime.now().isoformat(),
                                'filepath': str(filepath)
                            }
                            downloaded_count += 1
                        else:
                            print(f"❌ Failed to download: {node['name']}")
                    else:
                        print(f"⚠️  No URL for: {node['name']}")
            
            # Save state
            self.save_state()
            print(f"🎉 Successfully downloaded {downloaded_count} images to {today_dir}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")

def main():
    # Configuration
    FIGMA_TOKEN = os.getenv('FIGMA_TOKEN')
    FILE_KEY = os.getenv('FILE_KEY')
    DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIR', './figma_downloads')
    
    if FIGMA_TOKEN == "YOUR_FIGMA_TOKEN_HERE" or FILE_KEY == "YOUR_FILE_KEY_HERE":
        print("❌ Please update the FIGMA_TOKEN and FILE_KEY in the script")
        return
    
    downloader = FigmaDownloader(FIGMA_TOKEN, FILE_KEY, DOWNLOAD_DIR)
    downloader.run()

if __name__ == "__main__":
    main()
