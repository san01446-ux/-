import os
from dotenv import load_dotenv

load_dotenv()

from apocalypse_bot.core.bot import bot


def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN이 없습니다. .env 파일에 "
            "DISCORD_TOKEN=봇토큰 형식으로 입력하세요."
        )
    bot.run(token)


if __name__ == "__main__":
    main()
