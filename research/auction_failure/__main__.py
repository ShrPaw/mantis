"""
Auction Failure Research — Module Entry Point

Usage:
  python -m research.auction_failure --replay <jsonl_path>
  python -m research.auction_failure --live
"""

from .runner import main

if __name__ == "__main__":
    main()
