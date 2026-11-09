"""
CLI Runner: Convert Telegram Desktop HTML export (messages.html) to JSON.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

# Ensure src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from telegram_parser import TelegramChatConverter, TelegramHTMLParser


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Telegram Desktop messages.html to structured JSON.")
    parser.add_argument(
        "--input",
        type=str,
        default="telegram_msg_html/messages.html",
        help="Path to Telegram exported messages.html file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path for output JSON file (default: messages.json in same folder as input).",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation spaces (default: 2).",
    )
    parser.add_argument(
        "--no-service",
        action="store_true",
        help="Exclude service/system messages from output.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input file does not exist: {input_path}")
        sys.exit(1)

    html_parser = TelegramHTMLParser(include_service_messages=not args.no_service)
    converter = TelegramChatConverter(parser=html_parser)

    print(f"\n=======================================================")
    print(f"  Telegram Chat HTML to JSON Converter")
    print(f"  Input: {input_path}")
    print(f"=======================================================\n")

    chat = converter.convert(
        input_html_path=input_path,
        output_json_path=args.output,
        indent=args.indent,
    )

    out_file = Path(args.output) if args.output else input_path.with_name("messages.json")

    # Display summary statistics
    reactions_count = sum(m.reaction_count for m in chat.messages)
    media_count = sum(1 for m in chat.messages if m.media is not None)
    replies_count = sum(1 for m in chat.messages if m.reply_to_message_id is not None)

    print("[SUCCESS] Conversion completed!")
    print(f"  Chat Title:       {chat.chat_title}")
    print(f"  Total Messages:   {chat.total_messages}")
    print(f"  With Media:       {media_count}")
    print(f"  With Replies:     {replies_count}")
    print(f"  Total Reactions:  {reactions_count}")
    print(f"  Output File:      {out_file.resolve()}\n")


if __name__ == "__main__":
    main()

