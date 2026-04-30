import asyncio
import twikit
import os

TWITTER_USERNAME = os.environ.get("TWITTER_USERNAME", "hoarauj1")
TWITTER_EMAIL    = os.environ.get("TWITTER_EMAIL", "jhoarau60@gmail.com")
TWITTER_PASSWORD = os.environ.get("TWITTER_PASSWORD", "Hoaraujohnny.1@")
COOKIES_FILE     = "/home/johnny/-social-bot/twitter_cookies.json"

async def main():
    client = twikit.Client("fr-FR")
    print("Connexion à Twitter...")
    await client.login(
        auth_info_1=TWITTER_USERNAME,
        auth_info_2=TWITTER_EMAIL,
        password=TWITTER_PASSWORD
    )
    client.save_cookies(COOKIES_FILE)
    print(f"✅ Cookies sauvegardés dans {COOKIES_FILE}")

asyncio.run(main())
