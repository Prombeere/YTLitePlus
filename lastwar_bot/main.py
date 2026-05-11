"""
Entry point. Run with: python main.py
Requires Windows + Python 3.10+ + pywin32
"""

import logging
import sys

from bot import LastWarBot
from config import BotConfig


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("lastwar_bot.log", encoding="utf-8"),
        ],
    )

    cfg = BotConfig()
    bot = LastWarBot(cfg)
    bot.start()


if __name__ == "__main__":
    main()
