"""
CLI Runner: Convert YouTube Channel Data (live handle/URL or exported HTML/JSON) to structured JSON.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

# Ensure src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from youtube_parser import YouTubeChannelConverter, YouTubeChannelParser


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert YouTube channel data to structured JSON."
    )
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        "--url",
        "--handle",
        dest="query",
        type=str,
        default=None,
        help="YouTube channel handle (e.g. '@veritasium') or full URL.",
    )
    group.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to local HTML or JSON file containing YouTube channel data.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path for output JSON file.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation spaces (default: 2).",
    )
    args = parser.parse_args()

    yt_parser = YouTubeChannelParser()
    converter = YouTubeChannelConverter(parser=yt_parser)

    # Default to sample channel if no arguments provided
    if not args.query and not args.input:
        default_sample = PROJECT_ROOT / "sample_youtube" / "sample_channel.html"
        print(f"[INFO] No input specified. Defaulting to sample channel: {default_sample}")
        args.input = str(default_sample)

    print("\n=======================================================")
    print("  YouTube Channel Data to JSON Converter")
    print("=======================================================\n")

    if args.query:
        print(f"  Fetching Live Channel: {args.query} ...")
        result = converter.convert_url(
            query_or_url=args.query,
            output_json_path=args.output,
            indent=args.indent,
        )
        default_out = (
            PROJECT_ROOT / "sample_youtube" / f"{result.channel_info.handle.lstrip('@')}.json"
            if result.channel_info.handle
            else PROJECT_ROOT / "sample_youtube" / "youtube_channel.json"
        )
    else:
        in_path = Path(args.input)
        if not in_path.exists():
            print(f"[ERROR] Input file does not exist: {in_path}")
            sys.exit(1)
        print(f"  Parsing Local File: {in_path} ...")
        result = converter.convert_file(
            file_path=in_path,
            output_json_path=args.output,
            indent=args.indent,
        )
        default_out = in_path.with_suffix(".json")

    final_out = Path(args.output) if args.output else default_out
    if not args.output:
        converter._write_output(result, final_out, indent=args.indent)

    info = result.channel_info
    print("[SUCCESS] Conversion completed!")
    print(f"  Channel:          {info.channel_name} ({info.handle or 'No handle'})")
    print(f"  Subscribers:      {info.subscriber_count_text or 'N/A'}")
    print(f"  Total Videos:     {result.total_videos}")
    print(f"  Verified:         {'Yes' if info.is_verified else 'No'}")
    print(f"  Output File:      {final_out.resolve()}\n")

    if result.videos:
        print("  Sample Videos:")
        for v in result.videos[:3]:
            print(f"    - [{v.duration_text or 'Short'}] {v.title} ({v.view_count_text or '0 views'})")
        if len(result.videos) > 3:
            print(f"    ... and {len(result.videos) - 3} more videos.")
    print()


if __name__ == "__main__":
    main()

