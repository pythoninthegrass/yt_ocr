#!/usr/bin/env python3

import csv
import os
import sys
import argparse
import time
import json
import re
from dataclasses import dataclass, asdict
from decouple import config
from firecrawl import FirecrawlApp
from typing import Dict, List, Optional, Tuple


"""
YouTube Channel ID Scraper using Firecrawl
Automatically finds YouTube channel IDs using Firecrawl for reliable scraping

Configuration via .env file:
    FIRECRAWL_API_KEY=your_api_key_here
    FIRECRAWL_DELAY=1.0  # Optional delay between requests

Usage:
    python channel_finder.py ../extracted_usernames.csv
"""


try:
    from rich.console import Console
    from rich.progress import (
        Progress,
        BarColumn,
        TextColumn,
        TimeElapsedColumn,
        SpinnerColumn,
    )
    from rich.table import Table
    from rich.panel import Panel

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


@dataclass
class ChannelResult:
    username: str
    channel_id: str = ""
    url: str = ""
    status: str = "pending"  # pending, found, not_found, error
    error_msg: str = ""


class FirecrawlYouTubeScraper:
    def __init__(self, csv_file: str):
        self.csv_file = csv_file
        self.api_key = config("FIRECRAWL_API_KEY", default=None)
        self.output_file = csv_file.replace(".csv", "_scraped.csv")
        self.delay = config("FIRECRAWL_DELAY", default=1.0, cast=float)
        self.channels: Dict[str, ChannelResult] = {}
        self.console = Console() if RICH_AVAILABLE else None

        if not self.api_key:
            self.print_error("❌ Firecrawl API key required!")
            self.print_info(
                "Set FIRECRAWL_API_KEY in .env file, environment variable, or use --api-key"
            )
            self.print_info("Get your API key at: https://firecrawl.dev")
            sys.exit(1)

        # Initialize Firecrawl
        try:
            self.firecrawl = FirecrawlApp(api_key=self.api_key)
            self.print_info("✅ Firecrawl initialized successfully")
        except Exception as e:
            self.print_error(f"Failed to initialize Firecrawl: {e}")
            sys.exit(1)

    def load_csv(self) -> bool:
        """Load CSV file and initialize channel data"""
        try:
            with open(self.csv_file, "r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    username = row.get("username", "").strip()
                    existing_channel = row.get("channel", "").strip()
                    existing_url = row.get("url", "").strip()

                    if username:
                        if existing_channel and existing_channel.startswith("UC"):
                            # Already has channel ID - mark as found
                            self.channels[username] = ChannelResult(
                                username=username,
                                channel_id=existing_channel,
                                url=existing_url
                                or f"https://www.youtube.com/channel/{existing_channel}",
                                status="found",
                            )
                        else:
                            # Need to scrape
                            self.channels[username] = ChannelResult(username=username)
            return True
        except FileNotFoundError:
            self.print_error(f"File {self.csv_file} not found!")
            return False
        except Exception as e:
            self.print_error(f"Error loading CSV: {e}")
            return False

    def save_csv(self) -> bool:
        """Save results to CSV"""
        try:
            with open(self.output_file, "w", encoding="utf-8", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["username", "url", "channel"])

                for channel in self.channels.values():
                    writer.writerow([channel.username, channel.url, channel.channel_id])
            return True
        except Exception as e:
            self.print_error(f"Error saving CSV: {e}")
            return False

    def save_progress(self, filename: str = None):
        """Save progress to JSON file for resuming"""
        progress_file = filename or self.csv_file.replace(".csv", "_progress.json")
        try:
            with open(progress_file, "w", encoding="utf-8") as f:
                json.dump({k: asdict(v) for k, v in self.channels.items()}, f, indent=2)
        except Exception as e:
            self.print_error(f"Error saving progress: {e}")

    def load_progress(self, filename: str = None) -> bool:
        """Load progress from JSON file"""
        progress_file = filename or self.csv_file.replace(".csv", "_progress.json")
        try:
            if os.path.exists(progress_file):
                with open(progress_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for username, channel_data in data.items():
                        self.channels[username] = ChannelResult(**channel_data)
                self.print_info(f"📂 Loaded progress from {progress_file}")
                return True
        except Exception as e:
            self.print_error(f"Error loading progress: {e}")
        return False

    def extract_channel_id_from_content(self, content: str) -> Optional[str]:
        """Extract channel ID from Firecrawl content"""
        # Try multiple patterns to find channel ID
        patterns = [
            r'"externalId":"(UC[a-zA-Z0-9_-]{22})"',
            r'"channelId":"(UC[a-zA-Z0-9_-]{22})"',
            r"/channel/(UC[a-zA-Z0-9_-]{22})",
            r'"browse_id":"(UC[a-zA-Z0-9_-]{22})"',
            r'"browseEndpoint":{"browseId":"(UC[a-zA-Z0-9_-]{22})"',
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1)

        return None

    def scrape_channel_id(self, username: str) -> ChannelResult:
        """
        Scrape channel ID for a username using Firecrawl.
        
        Prioritizes /about endpoints as they're more reliable and consistently successful.
        Falls back to base URLs if /about endpoints fail.
        """
        result = ChannelResult(username=username)

        # Try different URL formats, prioritizing /about endpoints as they're more reliable
        urls_to_try = [
            f"https://www.youtube.com/{username}/about",
            f"https://www.youtube.com/c/{username.replace('@', '')}/about",
            f"https://www.youtube.com/user/{username.replace('@', '')}/about",
            f"https://www.youtube.com/{username}",
            f"https://www.youtube.com/c/{username.replace('@', '')}",
            f"https://www.youtube.com/user/{username.replace('@', '')}",
        ]

        for url in urls_to_try:
            try:
                self.print_info(f"🔍 Trying {url}")

                # Use Firecrawl to scrape the page
                scrape_result = self.firecrawl.scrape_url(url, formats=['html'])
                
                # Debug: Print what we got back
                if not scrape_result:
                    self.print_error(f"No result returned from {url}")
                    continue
                
                # Check if scraping was successful
                if hasattr(scrape_result, 'success') and not scrape_result.success:
                    error_msg = getattr(scrape_result, 'error', 'Unknown error')
                    self.print_error(f"Scraping failed for {url}: {error_msg}")
                    continue
                
                # Handle ScrapeResponse object
                if scrape_result and hasattr(scrape_result, 'html') and scrape_result.html:
                    html_content = scrape_result.html
                    
                    if html_content:
                        channel_id = self.extract_channel_id_from_content(html_content)

                        if channel_id:
                            result.channel_id = channel_id
                            result.url = f"https://www.youtube.com/channel/{channel_id}"
                            result.status = "found"
                            return result

                # Rate limiting
                time.sleep(self.delay)

            except Exception as e:
                error_msg = str(e) if str(e) != "None" else "HTTP Error"
                result.error_msg = error_msg
                self.print_error(f"Error scraping {url}: {error_msg}")
                # Shorter delay for failed attempts, especially for non-/about URLs
                delay = 0.2 if "/about" not in url else 0.5
                time.sleep(delay)
                continue

        # If we get here, channel wasn't found
        result.status = "not_found"
        result.error_msg = "Channel not found with any URL format"
        return result

    def get_pending_channels(self) -> List[str]:
        """Get list of usernames that need scraping"""
        return [
            username
            for username, channel in self.channels.items()
            if channel.status == "pending"
        ]

    def get_stats(self) -> Tuple[int, int, int, int]:
        """Get statistics: total, found, pending, not_found"""
        total = len(self.channels)
        found = sum(1 for c in self.channels.values() if c.status == "found")
        pending = sum(1 for c in self.channels.values() if c.status == "pending")
        not_found = sum(1 for c in self.channels.values() if c.status == "not_found")
        return total, found, pending, not_found

    def print_stats(self):
        """Print current statistics"""
        total, found, pending, not_found = self.get_stats()

        if RICH_AVAILABLE:
            stats_text = f"Found: {found}/{total} ({found / total * 100:.1f}%)"
            if pending > 0:
                stats_text += f" | Pending: {pending}"
            if not_found > 0:
                stats_text += f" | Not Found: {not_found}"

            self.console.print(Panel(stats_text, title="📊 Progress", style="blue"))
        else:
            print(f"\n📊 Progress: {found}/{total} found ({found / total * 100:.1f}%)")
            if pending > 0:
                print(f"   Pending: {pending}")
            if not_found > 0:
                print(f"   Not found: {not_found}")

    def print_results_table(self, limit: int = 20, status_filter: str = None):
        """Print results in table format"""
        channels = list(self.channels.values())

        if status_filter:
            channels = [c for c in channels if c.status == status_filter]

        if limit:
            channels = channels[:limit]

        if RICH_AVAILABLE:
            table = Table(
                title=f"Results {f'({status_filter})' if status_filter else ''}"
            )
            table.add_column("Username", style="cyan")
            table.add_column("Status", style="bold")
            table.add_column("Channel ID", style="green")
            table.add_column("Error", style="red", max_width=30)

            for channel in channels:
                status_emoji = {
                    "found": "✅",
                    "pending": "⏳",
                    "not_found": "❌",
                    "error": "🔥",
                }.get(channel.status, "❓")

                table.add_row(
                    channel.username,
                    f"{status_emoji} {channel.status}",
                    channel.channel_id,
                    channel.error_msg[:27] + "..."
                    if len(channel.error_msg) > 30
                    else channel.error_msg,
                )

            self.console.print(table)
        else:
            print(f"\n{'Username':<20} {'Status':<12} {'Channel ID':<30}")
            print("-" * 62)
            for channel in channels:
                status_emoji = {"found": "✅", "pending": "⏳", "not_found": "❌"}.get(
                    channel.status, "❓"
                )
                print(
                    f"{channel.username:<20} {status_emoji} {channel.status:<10} {channel.channel_id}"
                )

    def scrape_all_channels(self, resume: bool = False):
        """Scrape all pending channels"""
        if resume:
            self.load_progress()

        pending = self.get_pending_channels()

        if not pending:
            self.print_success("✅ No channels need scraping!")
            self.print_stats()
            return

        self.print_info(f"🚀 Starting to scrape {len(pending)} channels...")
        self.print_info(f"⏱️  Delay between requests: {self.delay} seconds")

        if RICH_AVAILABLE:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self.console,
            ) as progress:
                task = progress.add_task("Scraping channels...", total=len(pending))

                for i, username in enumerate(pending):
                    progress.update(task, description=f"Scraping {username}")

                    result = self.scrape_channel_id(username)
                    self.channels[username] = result

                    # Print result
                    if result.status == "found":
                        self.console.print(f"✅ {username} -> {result.channel_id}")
                    else:
                        self.console.print(f"❌ {username} -> {result.status}")

                    progress.advance(task)

                    # Save progress every 5 channels
                    if (i + 1) % 5 == 0:
                        self.save_progress()
                        self.save_csv()

        else:
            for i, username in enumerate(pending, 1):
                print(f"[{i}/{len(pending)}] Scraping {username}...")

                result = self.scrape_channel_id(username)
                self.channels[username] = result

                if result.status == "found":
                    print(f"✅ Found: {result.channel_id}")
                else:
                    print(f"❌ {result.status}: {result.error_msg}")

                # Save progress every 5 channels
                if i % 5 == 0:
                    self.save_progress()
                    self.save_csv()

        # Final save
        self.save_csv()
        self.save_progress()

        self.print_success("🎉 Scraping completed!")
        self.print_stats()

    def export_glance_config(self):
        """Export found channels to Glance YAML format"""
        found_channels = [
            c for c in self.channels.values() if c.status == "found" and c.channel_id
        ]

        if not found_channels:
            self.print_error("No channels found to export!")
            return

        config_text = "- type: videos\n  channels:\n"
        for channel in found_channels:
            config_text += f"    - {channel.channel_id}  # {channel.username}\n"

        config_file = self.output_file.replace(".csv", "_glance.yml")
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                f.write(config_text)

            self.print_success(f"📤 Glance config exported to {config_file}")
            self.print_info(f"Found {len(found_channels)} channels ready for Glance!")

        except Exception as e:
            self.print_error(f"Error exporting config: {e}")

    def print_error(self, message: str):
        if RICH_AVAILABLE:
            self.console.print(f"❌ {message}", style="red")
        else:
            print(f"❌ {message}")

    def print_success(self, message: str):
        if RICH_AVAILABLE:
            self.console.print(f"✅ {message}", style="green")
        else:
            print(f"✅ {message}")

    def print_info(self, message: str):
        if RICH_AVAILABLE:
            self.console.print(f"ℹ️  {message}", style="blue")
        else:
            print(f"ℹ️  {message}")


def main():
    parser = argparse.ArgumentParser(
        description="YouTube Channel ID Scraper with Firecrawl"
    )
    parser.add_argument("csv_file", help="Path to CSV file with usernames")

    args = parser.parse_args()

    if not os.path.exists(args.csv_file):
        print(f"❌ File {args.csv_file} not found!")
        sys.exit(1)

    scraper = FirecrawlYouTubeScraper(args.csv_file)

    if not scraper.load_csv():
        sys.exit(1)

    # Always resume from previous progress for unattended runs
    scraper.load_progress()

    # Main scraping operation
    try:
        scraper.scrape_all_channels(resume=True)
        scraper.export_glance_config()
    except KeyboardInterrupt:
        scraper.print_info("\n⏹️  Scraping interrupted. Progress saved.")
        scraper.save_progress()
        scraper.save_csv()


if __name__ == "__main__":
    main()
