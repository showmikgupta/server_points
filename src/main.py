from dotenv import load_dotenv  # used for getting environment vars

import bot


def main():
    load_dotenv()
    bot.run()


if __name__ == "__main__":
    main()
