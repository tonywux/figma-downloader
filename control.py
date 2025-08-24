#!/usr/bin/env python3
"""
Control script for managing the Figma downloader scheduler.
Provides simple commands to start, stop, check status, and run the scheduler.
"""

import os
import sys
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_cron_command():
    """Get the cron command for this project"""
    current_dir = os.path.abspath(os.path.dirname(__file__))
    schedule = os.getenv('SCHEDULE_CRON', '*/10 * * * *')  # Default: every 10 minutes for testing
    
    # Use full path to Python executable (either venv or system python3)
    venv_python = os.path.join(current_dir, 'venv', 'bin', 'python')
    if os.path.exists(venv_python):
        python_cmd = venv_python
    else:
        python_cmd = '/usr/bin/python3'  # Fallback to system python3
    
    # Cron command that runs our scheduled script
    cron_command = f'{schedule} cd "{current_dir}" && {python_cmd} run-scheduled.py >> logs/scheduler.log 2>&1'
    return cron_command


def get_current_crontab():
    """Get current crontab content"""
    try:
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            # No crontab exists yet
            return ""
    except Exception as e:
        print(f"Error reading crontab: {e}")
        return ""


def is_scheduler_active():
    """Check if the figma scheduler is active in crontab"""
    crontab_content = get_current_crontab()
    return "run-scheduled.py" in crontab_content and "figma" in crontab_content.lower()


def get_next_run_time():
    """Get a simple estimation of next run time (works for every N minutes)"""
    schedule = os.getenv('SCHEDULE_CRON', '*/10 * * * *')
    
    # Simple parsing for */N * * * * format
    if schedule.startswith('*/') and schedule.count('*') == 4:
        try:
            minutes = int(schedule.split('/')[1].split()[0])
            now = datetime.now()
            next_run = now.replace(second=0, microsecond=0)
            
            # Find next interval
            current_minute = now.minute
            next_minute = ((current_minute // minutes) + 1) * minutes
            
            if next_minute >= 60:
                next_run = next_run.replace(hour=next_run.hour + 1, minute=next_minute - 60)
            else:
                next_run = next_run.replace(minute=next_minute)
            
            return next_run.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
    
    # For other formats, just show the cron expression
    return f"Based on schedule: {schedule}"


def start_scheduler():
    """Add the scheduler to crontab"""
    if is_scheduler_active():
        print("✅ Scheduler is already ACTIVE")
        return True
    
    cron_command = get_cron_command()
    current_crontab = get_current_crontab()
    
    # Add our command to crontab
    new_crontab = current_crontab
    if new_crontab and not new_crontab.endswith('\n'):
        new_crontab += '\n'
    
    new_crontab += f"# Figma Downloader Scheduler\n"
    new_crontab += f"{cron_command}\n"
    
    try:
        # Write to temporary file and load into crontab
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cron', delete=False) as f:
            f.write(new_crontab)
            temp_file = f.name
        
        result = subprocess.run(['crontab', temp_file], capture_output=True, text=True)
        os.unlink(temp_file)  # Clean up temp file
        
        if result.returncode == 0:
            print("✅ Scheduler STARTED successfully")
            print(f"📅 Schedule: {os.getenv('SCHEDULE_CRON', '*/10 * * * *')}")
            print(f"📅 Next run: {get_next_run_time()}")
            print(f"📁 Logs: {os.path.abspath('logs/scheduler.log')}")
            return True
        else:
            print(f"❌ Failed to start scheduler: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error starting scheduler: {e}")
        return False


def stop_scheduler():
    """Remove the scheduler from crontab"""
    if not is_scheduler_active():
        print("🛑 Scheduler is already STOPPED")
        return True
    
    current_crontab = get_current_crontab()
    
    # Remove lines related to figma downloader
    lines = current_crontab.split('\n')
    new_lines = []
    skip_next = False
    
    for line in lines:
        if skip_next:
            skip_next = False
            continue
        
        if "# Figma Downloader Scheduler" in line:
            skip_next = True  # Skip the next line (the actual cron command)
            continue
        elif "run-scheduled.py" in line and "figma" in line.lower():
            continue  # Skip this line
        else:
            new_lines.append(line)
    
    new_crontab = '\n'.join(new_lines).strip()
    
    try:
        if new_crontab:
            # Write updated crontab
            with tempfile.NamedTemporaryFile(mode='w', suffix='.cron', delete=False) as f:
                f.write(new_crontab + '\n')
                temp_file = f.name
            
            result = subprocess.run(['crontab', temp_file], capture_output=True, text=True)
            os.unlink(temp_file)
        else:
            # Remove entire crontab if empty
            result = subprocess.run(['crontab', '-r'], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("🛑 Scheduler STOPPED successfully")
            print("❌ Daily downloads are now disabled")
            return True
        else:
            print(f"❌ Failed to stop scheduler: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error stopping scheduler: {e}")
        return False


def show_status():
    """Show current scheduler status"""
    print("📊 Figma Downloader Scheduler Status")
    print("=" * 40)
    
    if is_scheduler_active():
        print("✅ Scheduler is ACTIVE")
        print(f"📅 Schedule: {os.getenv('SCHEDULE_CRON', '*/10 * * * *')}")
        print(f"📅 Next run: {get_next_run_time()}")
    else:
        print("❌ Scheduler is INACTIVE")
        print("💡 Run 'python control.py start' to activate")
    
    # Check log file
    log_file = Path("logs/scheduler.log")
    if log_file.exists():
        try:
            stat = log_file.stat()
            print(f"📁 Log file: {log_file.absolute()}")
            print(f"📊 Log size: {stat.st_size} bytes")
            print(f"📅 Last modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            print(f"📁 Log file exists but couldn't read stats: {e}")
    else:
        print("📁 No log file found (will be created on first run)")
    
    # Check report file
    report_file = Path("daily-report.md")
    if report_file.exists():
        try:
            stat = report_file.stat()
            print(f"📊 Report file: {report_file.absolute()}")
            print(f"📅 Last updated: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            print(f"📊 Report file exists but couldn't read stats: {e}")
    else:
        print("📊 No report file found (will be created on first run)")


def run_now():
    """Run the scheduler immediately for testing"""
    print("🚀 Running Figma downloader now...")
    print("-" * 40)
    
    try:
        # Run the scheduled script directly
        result = subprocess.run([sys.executable, 'run-scheduled.py'], 
                              capture_output=False, text=True)
        
        if result.returncode == 0:
            print("-" * 40)
            print("✅ Manual run completed successfully")
        else:
            print("-" * 40)
            print(f"❌ Manual run failed with exit code {result.returncode}")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Error running scheduler: {e}")
        return False


def show_logs():
    """Show recent log entries"""
    log_file = Path("logs/scheduler.log")
    
    if not log_file.exists():
        print("📁 No log file found")
        return
    
    try:
        print("📋 Recent log entries (last 20 lines):")
        print("-" * 50)
        
        # Read last 20 lines
        with open(log_file, 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-20:] if len(lines) > 20 else lines
            
            for line in recent_lines:
                print(line.rstrip())
                
    except Exception as e:
        print(f"❌ Error reading log file: {e}")


def show_help():
    """Show usage information"""
    print("📖 Figma Downloader Scheduler Control")
    print("=" * 40)
    print("Usage: python control.py [command]")
    print()
    print("Commands:")
    print("  start     - Start the scheduler (adds to crontab)")
    print("  stop      - Stop the scheduler (removes from crontab)")
    print("  status    - Show current scheduler status")
    print("  run-now   - Run the downloader immediately")
    print("  logs      - Show recent log entries")
    print("  help      - Show this help message")
    print()
    print("Configuration:")
    print("  Set environment variables in .env file:")
    print("  - FIGMA_TOKEN: Your Figma personal access token")
    print("  - FILE_KEY: Your Figma file key")
    print("  - SCHEDULE_CRON: Cron schedule (default: */10 * * * * - every 10 minutes)")
    print("  - DOWNLOAD_DIR: Download directory (default: ./figma_downloads)")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == "start":
        start_scheduler()
    elif command == "stop":
        stop_scheduler()
    elif command == "status":
        show_status()
    elif command == "run-now":
        run_now()
    elif command == "logs":
        show_logs()
    elif command == "help":
        show_help()
    else:
        print(f"❌ Unknown command: {command}")
        print("💡 Run 'python control.py help' for usage information")
        sys.exit(1)


if __name__ == "__main__":
    main()
