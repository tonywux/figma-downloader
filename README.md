# Figma Downloader

A Python service that automatically downloads images from Figma files with smart batching, duplicate detection, and retry logic.

## Features

- 🎨 **Automatic Image Detection**: Finds all image nodes (frames with image fills, rectangles, ellipses, and image components)
- 📦 **Intelligent Batching**: Processes images in configurable batches to avoid API timeouts
- 🔄 **Retry Logic**: Handles timeouts and failures with exponential backoff
- 🚫 **Duplicate Prevention**: Tracks downloaded items to avoid re-downloading
- 📁 **Organized Storage**: Creates date-based folders for downloads
- ⚡ **High Resolution**: Downloads images at 2x scale for crisp quality
- 🛡️ **Error Handling**: Graceful handling of API failures and network issues

## Requirements

- Python 3.6+
- A Figma account with API access
- Required Python packages:
  - `requests`
  - `python-dotenv`

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd figma-downloader
```

2. Install dependencies:
```bash
pip install requests python-dotenv
```

3. Create a `.env` file in the project root:
```bash
touch .env
```

## Configuration

Add the following environment variables to your `.env` file:

```env
# Required
FIGMA_TOKEN=your_figma_personal_access_token
FILE_KEY=your_figma_file_key

# Optional
DOWNLOAD_DIR=./figma_downloads
BATCH_SIZE=10
```

### Getting Your Figma Token

1. Go to [Figma Account Settings](https://www.figma.com/settings)
2. Scroll down to "Personal access tokens"
3. Click "Create new token"
4. Give it a name and copy the token
5. Add it to your `.env` file

### Getting the File Key

The file key is found in your Figma file URL:
```
https://www.figma.com/design/FILE_KEY_HERE/Your-File-Name
```

## Usage

### Basic Usage

```bash
python figma-downloader.py
```

### Configuration Options

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `FIGMA_TOKEN` | Required | Your Figma personal access token |
| `FILE_KEY` | Required | The Figma file key from the URL |
| `DOWNLOAD_DIR` | `./figma_downloads` | Directory to save downloaded images |
| `BATCH_SIZE` | `10` | Number of images to process per batch |

## How It Works

1. **File Analysis**: Connects to Figma API and retrieves the file structure
2. **Image Detection**: Recursively searches for:
   - Frames with image fills
   - Rectangles with image fills  
   - Ellipses with image fills
   - Image components
3. **Duplicate Check**: Compares against previously downloaded items using MD5 hashes
4. **Batch Processing**: Groups images into batches to avoid API timeouts
5. **Download**: Exports images as PNG at 2x resolution and saves them locally
6. **State Tracking**: Maintains a `download_state.json` file to track progress

## File Organization

Downloads are organized in the following structure:

```
figma_downloads/
├── download_state.json          # Tracks downloaded items
├── 2024-01-15/                 # Date-based folders
│   ├── 143022_button_primary_a1b2c3d4.png
│   ├── 143025_icon_search_e5f6g7h8.png
│   └── ...
└── 2024-01-16/
    └── ...
```

### Filename Format

Files are named using the pattern:
```
{timestamp}_{cleaned_name}_{node_id_prefix}.png
```

- `timestamp`: HHMMSS format when the download started
- `cleaned_name`: Sanitized version of the Figma component name
- `node_id_prefix`: First 8 characters of the Figma node ID

## Error Handling

The service includes robust error handling:

- **API Timeouts**: Automatic retry with exponential backoff
- **Batch Timeouts**: Automatically splits large batches into smaller ones
- **Network Failures**: Retries failed downloads up to 3 times
- **Invalid Responses**: Graceful handling of malformed API responses

## State Management

The service maintains state in `download_state.json` to:
- Avoid re-downloading existing images
- Track download history
- Resume interrupted downloads

Example state file:
```json
{
  "a1b2c3d4e5f6g7h8": {
    "node_id": "123:456",
    "name": "Button Primary",
    "downloaded_at": "2024-01-15T14:30:22.123456",
    "filepath": "figma_downloads/2024-01-15/143022_button_primary_a1b2c3d4.png"
  }
}
```

## Troubleshooting

### Common Issues

**"Failed to get file data"**
- Check your `FIGMA_TOKEN` is valid
- Ensure the `FILE_KEY` is correct
- Verify you have access to the Figma file

**"No images found in file"**
- The file may not contain any image components
- Images might be embedded as fills in components
- Check if the file has multiple pages

**"Batch timeout"**
- Reduce the `BATCH_SIZE` environment variable
- Check your internet connection
- Some complex images may take longer to export

### Debug Mode

For additional debugging information, you can modify the script to add more verbose logging or run with Python's debug flags:

```bash
python -v figma-downloader.py
```

## API Rate Limits

The service includes built-in rate limiting:
- 3-second delay between batches
- Exponential backoff on retries
- Configurable batch sizes to stay within API limits

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Changelog

### v1.0.0
- Initial release
- Batch processing with retry logic
- Duplicate detection
- Date-based organization
- High-resolution image export