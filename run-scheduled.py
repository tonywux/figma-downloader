#!/usr/bin/env python3
"""
Scheduled execution wrapper for figma-downloader.
This script runs the FigmaDownloader and updates the daily report.
Designed to be called by cron or the control script.
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
import traceback

# Add the current directory to Python path to import figma-downloader
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Import our FigmaDownloader
import importlib.util
spec = importlib.util.spec_from_file_location("figma_downloader", "figma-downloader.py")
figma_downloader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(figma_downloader)
FigmaDownloader = figma_downloader.FigmaDownloader


def format_duration(seconds):
    """Format duration in a human readable way"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def read_existing_report():
    """Read existing daily-report.md file"""
    report_file = Path("daily-report.md")
    if not report_file.exists():
        return None
    
    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Warning: Could not read existing report: {e}")
        return None


def parse_existing_history(report_content):
    """Parse existing history from report content"""
    if not report_content:
        return []
    
    # Look for the history table
    lines = report_content.split('\n')
    history = []
    in_table = False
    
    for line in lines:
        if ('| Date | Status | New Downloads | Total Found | Duration |' in line or 
            '| Timestamp | Status | New Downloads | Total Found | Duration |' in line):
            in_table = True
            continue
        elif in_table and line.startswith('|') and line.count('|') >= 5:
            # Parse table row
            parts = [p.strip() for p in line.split('|')[1:-1]]  # Remove empty first/last
            if len(parts) >= 5 and parts[0] != 'Date':  # Skip header
                # Skip invalid/dummy rows
                if (parts[0] == '------' or parts[0] == '-' or 
                    parts[1] == '--------' or parts[1] == '⏳ Waiting' or
                    not parts[0] or not parts[1]):
                    continue
                
                # Validate that the date/timestamp looks real (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS format)
                date_part = parts[0][:10] if len(parts[0]) >= 10 else parts[0]
                if not (len(date_part) == 10 and date_part.count('-') == 2):
                    continue
                
                # Validate that status contains expected emojis or text
                if not any(indicator in parts[1] for indicator in ['✅', '❌', 'Success', 'Failed', 'Error']):
                    continue
                
                try:
                    # Handle both old format (date only) and new format (timestamp)
                    date_or_timestamp = parts[0]
                    if len(date_or_timestamp) > 10:  # Looks like timestamp
                        timestamp = date_or_timestamp
                        date = date_or_timestamp[:10]
                    else:  # Just date
                        timestamp = date_or_timestamp
                        date = date_or_timestamp
                    
                    history.append({
                        'timestamp': timestamp,
                        'date': date,
                        'status': parts[1],
                        'new_downloads': parts[2],
                        'total_found': parts[3],
                        'duration': parts[4]
                    })
                except (IndexError, ValueError):
                    continue
        elif in_table and not line.strip().startswith('|'):
            # End of table
            break
    
    return history


def generate_report(summary, existing_history=None):
    """Generate the daily report markdown content"""
    timestamp = datetime.now()
    
    # Determine status
    if summary.get('errors', 0) > 0:
        status_emoji = "❌"
        status_text = "Failed"
    else:
        status_emoji = "✅"
        status_text = "Success"
    
    # Format duration
    duration_str = "N/A"
    if summary.get('duration_formatted'):
        duration_str = summary['duration_formatted']
    elif summary.get('duration_seconds'):
        duration_str = format_duration(summary['duration_seconds'])
    
    # Prepare current run data
    current_run = {
        'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'date': timestamp.strftime('%Y-%m-%d'),
        'status': f"{status_emoji} {status_text}",
        'new_downloads': str(summary.get('new_downloaded', 0)),
        'total_found': str(summary.get('total_found', 0)),
        'duration': duration_str
    }
    
    # Combine with existing history
    if existing_history is None:
        existing_history = []
    
    # Add the new run to the beginning (keep all runs, don't remove same-day entries)
    history = [current_run] + existing_history
    
    # Keep only runs from the last N days based on date, not count
    retention_days = int(os.getenv('REPORT_RETENTION_DAYS', 30))
    cutoff_date = (timestamp - timedelta(days=retention_days)).strftime('%Y-%m-%d')
    history = [h for h in history if h.get('date', h.get('timestamp', '')[:10]) >= cutoff_date]
    
    # Calculate statistics
    total_runs = len(history)
    successful_runs = len([h for h in history if '✅' in h['status']])
    success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0
    total_downloads = sum(int(h['new_downloads']) for h in history if h['new_downloads'].isdigit())
    avg_per_day = total_downloads / total_runs if total_runs > 0 else 0
    
    # Error details for current run
    error_section = ""
    if summary.get('error_messages'):
        error_section = f"""
### Errors This Run
```
{chr(10).join(summary['error_messages'])}
```
"""
    
    # Generate report content
    report_content = f"""# Figma Downloader Daily Reports

## Latest Run: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

- **Status**: {status_emoji} {status_text}
- **New Images**: {summary.get('new_downloaded', 0)} downloaded
- **Total Images Found**: {summary.get('total_found', 0)}
- **Skipped (Already Downloaded)**: {summary.get('skipped', 0)}
- **Execution Time**: {duration_str}
- **Download Directory**: {summary.get('download_dir', 'N/A')}
{error_section}
### Recent History
| Timestamp | Status | New Downloads | Total Found | Duration |
|-----------|--------|---------------|-------------|----------|
"""
    
    # Add history rows
    for entry in history:
        timestamp_display = entry.get('timestamp', entry.get('date', ''))
        report_content += f"| {timestamp_display} | {entry['status']} | {entry['new_downloads']} | {entry['total_found']} | {entry['duration']} |\n"
    
    # Add summary statistics
    report_content += f"""
### Last {len(history)} Days Summary
- **Total Runs**: {total_runs}
- **Success Rate**: {success_rate:.1f}% ({successful_runs}/{total_runs})
- **Total Images Downloaded**: {total_downloads}
- **Average per Day**: {avg_per_day:.1f} images

---
*Last updated: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}*
"""
    
    return report_content


def update_daily_report(summary):
    """Update the daily-report.md file with latest run information"""
    try:
        # Read existing report
        existing_content = read_existing_report()
        existing_history = parse_existing_history(existing_content)
        
        # Generate new report
        new_content = generate_report(summary, existing_history)
        
        # Write updated report
        with open("daily-report.md", 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"📊 Updated daily-report.md")
        
    except Exception as e:
        print(f"⚠️  Failed to update report: {e}")
        traceback.print_exc()


def main():
    """Main execution function"""
    print(f"🕐 Scheduled run started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Configuration
        FIGMA_TOKEN = os.getenv('FIGMA_TOKEN')
        FILE_KEY = os.getenv('FILE_KEY')
        DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIR', './figma_downloads')
        BATCH_SIZE = int(os.getenv('BATCH_SIZE', 10))
        
        # Validate configuration
        if not FIGMA_TOKEN or not FILE_KEY:
            raise Exception("FIGMA_TOKEN and FILE_KEY environment variables must be set")
        
        if FIGMA_TOKEN == "your_figma_personal_access_token" or FILE_KEY == "your_figma_file_key":
            raise Exception("Please update FIGMA_TOKEN and FILE_KEY with actual values")
        
        # Create downloader with logging enabled
        downloader = FigmaDownloader(
            token=FIGMA_TOKEN,
            file_key=FILE_KEY,
            download_dir=DOWNLOAD_DIR,
            batch_size=BATCH_SIZE,
            enable_logging=True
        )
        
        # Run with summary tracking
        summary = downloader.run_with_summary()
        
        # Add additional info to summary
        summary['download_dir'] = DOWNLOAD_DIR
        summary['figma_file_key'] = FILE_KEY
        
        # Update daily report
        update_daily_report(summary)
        
        # Print summary
        print(f"✅ Scheduled run completed successfully")
        print(f"📊 Downloaded {summary.get('new_downloaded', 0)} new images")
        print(f"📁 Total found: {summary.get('total_found', 0)}")
        print(f"⏱️  Duration: {summary.get('duration_formatted', 'N/A')}")
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Scheduled run failed: {error_msg}")
        
        # Still try to update report with error
        error_summary = {
            'start_time': datetime.now(),
            'end_time': datetime.now(),
            'total_found': 0,
            'new_downloaded': 0,
            'skipped': 0,
            'errors': 1,
            'error_messages': [error_msg],
            'duration_formatted': '0s',
            'download_dir': os.getenv('DOWNLOAD_DIR', './figma_downloads'),
            'figma_file_key': os.getenv('FILE_KEY', 'N/A')
        }
        
        try:
            update_daily_report(error_summary)
        except Exception as report_error:
            print(f"⚠️  Could not update report: {report_error}")
        
        # Re-raise the original error
        raise e


if __name__ == "__main__":
    main()
