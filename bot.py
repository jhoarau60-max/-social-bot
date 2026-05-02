import os
import asyncio
import random
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from instagrapi import Client as InstaClient
from linkedin_api import Linkedin
import twikit

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── CONFIG ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN     = os.environ.get("TELEGRAM_TOKEN")
LINKEDIN_EMAIL     = os.environ.get("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD  = os.environ.get("LINKEDIN_PASSWORD")
INSTA_USERNAME     = os.environ.get("INSTA_USERNAME")
INSTA_PASSWORD     = os.environ.get("INSTA_PASSWORD")
TWITTER_USERNAME   = os.environ.get("TWITTER_USERNAME")
TWITTER_EMAIL      = os.environ.get("TWITTER_EMAIL")
TWITTER_PASSWORD   = os.environ.get("TWITTER_PASSWORD")

JOHN_ID        = 7385702412
PARIS_TZ       = ZoneInfo("Europe/Paris")


CONTENT_TOPICS = [
    "L'immobilier tokenisé permet d'investir dans des propriétés mondiales dès 10$ — une révolution accessible à tous.",
    "Les bots de trading MEV génèrent des revenus passifs 24h/24 automatiquement sur la blockchain.",
    "En 2026, la liberté financière passe par les investissements passifs numériques. Voici comment.",
    "Saviez-vous qu'on peut acheter une fraction d'une villa à Miami pour 10$ ? L'immobilier tokenisé rend ça possible.",
    "Le trading algorithmique IA : comment des particuliers génèrent 1% par jour sans toucher aux marchés.",
    "Diversifier entre immobilier digital et trading IA : la stratégie des investisseurs intelligents en 2026.",
    "ArbCore, E-Estate, Smart Bot : 3 façons concrètes de créer des revenus passifs avec la technologie blockchain.",
]

async def call_gemini(prompt: str, system_instruction: str = None) -> str:
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    if system_instruction:
        payload["system_instruction"] = {"parts": [{"text": system_instruction}]}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{GEMINI_URL}?key={GEMINI_API_KEY}", json=payload)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


# ─── CLIENTS GLOBAUX (login une seule fois) ───────────────────────────────────
INSTA_SESSION_FILE   = "/home/johnny/-social-bot/insta_session.json"
TWITTER_COOKIES_FILE = "/home/johnny/-social-bot/twitter_cookies.json"
insta_client: InstaClient = None
twitter_client: twikit.Client = None

async def init_instagram():
    global insta_client
    cl = InstaClient()
    proxy = os.environ.get("INSTAGRAM_PROXY")
    if proxy:
        cl.set_proxy(proxy)
    try:
        session_id = os.environ.get("INSTA_SESSION_ID")
        if session_id:
            cl.login_by_sessionid(session_id)
        else:
            if os.path.exists(INSTA_SESSION_FILE):
                cl.load_settings(INSTA_SESSION_FILE)
            cl.login(INSTA_USERNAME, INSTA_PASSWORD)
            cl.dump_settings(INSTA_SESSION_FILE)
        insta_client = cl
        logger.info("✅ Instagram connecté")
    except Exception as e:
        logger.error(f"❌ Instagram login: {e}")
        await notify_john(f"❌ *Instagram* login échoué: {str(e)[:200]}")

async def init_twitter():
    global twitter_client
    cl = twikit.Client("fr-FR")
    try:
        import json as _json
        auth_token = os.environ.get("TWITTER_AUTH_TOKEN")
        ct0 = os.environ.get("TWITTER_CT0")
        if auth_token and ct0:
            with open(TWITTER_COOKIES_FILE, 'w') as f:
                _json.dump({"auth_token": auth_token, "ct0": ct0}, f)
        if os.path.exists(TWITTER_COOKIES_FILE):
            cl.load_cookies(TWITTER_COOKIES_FILE)
            twitter_client = cl
            logger.info("✅ Twitter connecté (cookies)")
        else:
            await cl.login(auth_info_1=TWITTER_USERNAME, auth_info_2=TWITTER_EMAIL, password=TWITTER_PASSWORD)
            cl.save_cookies(TWITTER_COOKIES_FILE)
            twitter_client = cl
            logger.info("✅ Twitter connecté (login)")
    except Exception as e:
        logger.error(f"❌ Twitter login: {e}")
        await notify_john(f"❌ *Twitter/X* login échoué: {str(e)[:200]}")

# ─── NOTIFICATION TELEGRAM ───────────────────────────────────────────────────
async def notify_john(message: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={
                "chat_id": JOHN_ID,
                "text": message,
                "parse_mode": "Markdown"
            })
            if resp.status_code == 400:
                await client.post(url, json={
                    "chat_id": JOHN_ID,
                    "text": message
                })
    except Exception as e:
        logger.error(f"Erreur notification Telegram: {e}")

# ─── GÉNÉRATION DE CONTENU ────────────────────────────────────────────────────
async def generate_post(platform: str) -> str:
    topic = random.choice(CONTENT_TOPICS)
    if platform == "LinkedIn":
        prompt = (
            f"Écris un post LinkedIn professionnel et accrocheur en français sur ce sujet : {topic}\n"
            "3-4 phrases maximum. Ajoute 3-4 hashtags pertinents à la fin.\n"
            "Hashtags obligatoires : #InvestissementPassif #LiberteFinanciere #ProjectInvestT\n"
            "Ton : expert, inspirant, sans jargon technique."
        )
    elif platform == "Instagram":
        prompt = (
            f"Écris une légende Instagram en français sur ce sujet : {topic}\n"
            "2-3 phrases percutantes. Ajoute 8-10 hashtags populaires à la fin.\n"
            "Inclus : #investissement #crypto #immobilier #libertefinanciere #revenuspassifs #trading #blockchain #ProjectInvestT\n"
            "Ton : dynamique, motivant, accessible."
        )
    else:  # Twitter
        prompt = (
            f"Écris un tweet en français sur ce sujet : {topic}\n"
            "Maximum 250 caractères. 2-3 hashtags max.\n"
            "Hashtags : #Investissement #LiberteFinanciere\n"
            "Ton : direct, percutant, inspirant."
        )
    return await call_gemini(prompt)

# ─── LINKEDIN ─────────────────────────────────────────────────────────────────
LINKEDIN_CHALLENGE_MSG = (
    "⚠️ *LinkedIn — Vérification manuelle requise*\n\n"
    "LinkedIn a bloqué la connexion automatique (CHALLENGE détecté).\n\n"
    "*👉 Actions à faire :*\n"
    "1. Va sur linkedin.com et connecte-toi manuellement\n"
    "2. Complète la vérification (email / SMS / captcha)\n"
    "3. Redémarre le bot (pkill -f bot.py puis relance)\n\n"
    "_Le bot reprendra automatiquement après le redémarrage._"
)

def get_linkedin_api():
    li_at = os.environ.get("LINKEDIN_COOKIE")
    jsessionid = os.environ.get("LINKEDIN_JSESSIONID", "")
    try:
        if li_at:
            cookies = {"li_at": li_at}
            if jsessionid:
                cookies["JSESSIONID"] = jsessionid
            api = Linkedin(LINKEDIN_EMAIL, LINKEDIN_PASSWORD, authenticate=False, cookies=cookies)
        else:
            api = Linkedin(LINKEDIN_EMAIL, LINKEDIN_PASSWORD)
        return api
    except Exception as e:
        if "CHALLENGE" in str(e).upper():
            raise Exception("LINKEDIN_CHALLENGE")
        raise


async def linkedin_post():
    try:
        content = await generate_post("LinkedIn")
        api = await asyncio.to_thread(get_linkedin_api)
        await asyncio.to_thread(api.post, content)
        logger.info("LinkedIn post publié")
        await notify_john(f"✅ *LinkedIn* — Post publié :\n\n{content[:300]}")
    except Exception as e:
        logger.error(f"Erreur LinkedIn post: {e}")
        if "LINKEDIN_CHALLENGE" in str(e):
            await notify_john(LINKEDIN_CHALLENGE_MSG)
        else:
            await notify_john(f"❌ *LinkedIn* post erreur: {str(e)[:200]}")


# ─── INSTAGRAM ────────────────────────────────────────────────────────────────
async def instagram_post():
    if not insta_client:
        await notify_john("⚠️ *Instagram* — Client non connecté, post ignoré")
        return
    try:
        content = await generate_post("Instagram")
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (1080, 1080), color=(10, 20, 50))
        draw = ImageDraw.Draw(img)
        lines = content.split("\n")
        y = 300
        for line in lines[:8]:
            draw.text((50, y), line[:60], fill=(255, 255, 255))
            y += 80
        img_path = "/tmp/insta_post.jpg"
        img.save(img_path, format="JPEG", quality=95)
        insta_client.photo_upload(img_path, content)
        logger.info("Instagram post publié")
        await notify_john(f"✅ *Instagram* — Post publié :\n\n{content[:300]}")
    except Exception as e:
        logger.error(f"Erreur Instagram post: {e}")
        await notify_john(f"❌ *Instagram* post erreur: {str(e)[:200]}")


# ─── INSTAGRAM STORIES ───────────────────────────────────────────────────────

STORY_QUIZ_LIST = [
    {"question": "Tu veux des revenus passifs ?",      "oui": "Absolument !",       "non": "Pas encore"},
    {"question": "Tu connais l'immobilier tokenisé ?", "oui": "Oui j'investis",     "non": "Non c'est quoi ?"},
    {"question": "Tu investis déjà en crypto ?",       "oui": "Oui régulièrement",  "non": "Non j'hésite"},
    {"question": "Objectif : liberté financière ?",    "oui": "C'est mon but !",    "non": "J'ai d'autres priorités"},
    {"question": "Tu veux un revenu automatique ?",    "oui": "Oui montrez-moi !",  "non": "J'ai des questions"},
]

STORY_PROJECTS_LIST = [
    {"nom": "E-Estate",       "desc": "Immobilier tokenisé dès 10$\n0.41% à 1% par jour 💰",   "lien": "https://www.e-estate.co/agent/953277721577",    "bg": (10, 40, 120)},
    {"nom": "Smart MEV Bot",  "desc": "Trading IA automatique 24h/24\nBot accessible dès 49$ 🤖", "lien": "https://xmev.ai?inviteCode=QVKB8JNC",           "bg": (50, 10, 120)},
    {"nom": "ArbCore",        "desc": "Arbitrage crypto automatique\n1.07% par jour dès 50 USDT ⚡", "lien": "https://arbcore.app/?frenID=IFK2MAN6",       "bg": (10, 90, 50)},
    {"nom": "Artena",         "desc": "Club DeFi privé exclusif\nPass dès 50$ 🔥",               "lien": "https://artena.pro/r/jonas05",                  "bg": (110, 40, 10)},
]

STORY_INSPIRATIONS = [
    "En 2026, ne pas investir c'est perdre chaque jour avec l'inflation 💡",
    "La liberté financière n'est pas un rêve — c'est une stratégie 🚀",
    "Pendant que tu dors, ton argent peut travailler pour toi 💤💰",
    "On peut acheter une part d'immeuble à Miami pour 10$ — l'immobilier tokenisé change tout 🏙️",
    "Le meilleur moment pour investir c'était hier. Le deuxième meilleur : maintenant ⏰",
    "Immobilier digital + Trading IA = la stratégie des investisseurs modernes 🧩",
    "Chaque jour sans revenus passifs = dépendre uniquement de ton salaire. Changeons ça 💪",
]

def create_story_image(title: str, subtitle: str, tag: str = "", bg_color: tuple = (10, 20, 50), accent_color: tuple = (255, 200, 0)) -> str:
    from PIL import Image, ImageDraw, ImageFont
    import textwrap
    img = Image.new("RGB", (1080, 1920), color=bg_color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (1080, 10)], fill=accent_color)
    draw.rectangle([(0, 1910), (1080, 1920)], fill=accent_color)
    try:
        font_brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 68)
        font_sub   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 46)
    except Exception:
        font_brand = font_title = font_sub = ImageFont.load_default()
    draw.text((60, 80),  "Project Inves'T",           font=font_brand, fill=accent_color)
    draw.text((60, 140), "@projectinvest_officiel",   font=font_brand, fill=(150, 150, 150))
    if tag:
        w = len(tag) * 26 + 40
        draw.rectangle([(60, 220), (60 + w, 290)], fill=accent_color)
        draw.text((80, 228), tag, font=font_sub, fill=(0, 0, 0))
    y = 680
    for line in textwrap.wrap(title, width=18):
        draw.text((60, y), line, font=font_title, fill=(255, 255, 255))
        y += 95
    y += 30
    for line in textwrap.wrap(subtitle, width=26):
        draw.text((60, y), line, font=font_sub, fill=(200, 200, 200))
        y += 65
    path = "/tmp/story.jpg"
    img.save(path, format="JPEG", quality=95)
    return path

async def instagram_story_quiz():
    if not insta_client:
        await notify_john("⚠️ *Instagram* — Client non connecté, story ignorée")
        return
    try:
        quiz = random.choice(STORY_QUIZ_LIST)
        img_path = create_story_image(
            title=quiz["question"], subtitle="Vote ci-dessous ! 👇",
            bg_color=(10, 20, 80), accent_color=(100, 200, 255)
        )
        try:
            from instagrapi.types import StoryPoll
            poll = StoryPoll(
                x=0.5, y=0.75, width=0.9, height=0.14, rotation=0,
                question=quiz["question"],
                tallies=[
                    {"text": quiz["oui"], "count": 0, "font_size": 35.0},
                    {"text": quiz["non"], "count": 0, "font_size": 35.0}
                ]
            )
            insta_client.photo_upload_to_story(img_path, stickers=[poll])
        except Exception:
            insta_client.photo_upload_to_story(img_path)
        logger.info(f"Instagram story quiz: {quiz['question']}")
        await notify_john(f"✅ *Instagram Story* — Quiz :\n\n❓ {quiz['question']}")
    except Exception as e:
        logger.error(f"Erreur Instagram story quiz: {e}")
        await notify_john(f"❌ *Instagram Story* quiz erreur: {str(e)[:200]}")

async def instagram_story_projet():
    if not insta_client:
        await notify_john("⚠️ *Instagram* — Client non connecté, story ignorée")
        return
    try:
        projet = random.choice(STORY_PROJECTS_LIST)
        img_path = create_story_image(
            title=projet["nom"], subtitle=projet["desc"],
            tag="PROJET", bg_color=projet["bg"], accent_color=(255, 200, 0)
        )
        try:
            from instagrapi.types import StoryLink
            insta_client.photo_upload_to_story(img_path, stickers=[StoryLink(webUri=projet["lien"])])
        except Exception:
            insta_client.photo_upload_to_story(img_path)
        logger.info(f"Instagram story projet: {projet['nom']}")
        await notify_john(f"✅ *Instagram Story* — Projet :\n\n🏦 {projet['nom']}\n🔗 {projet['lien']}")
    except Exception as e:
        logger.error(f"Erreur Instagram story projet: {e}")
        await notify_john(f"❌ *Instagram Story* projet erreur: {str(e)[:200]}")

async def instagram_story_inspiration():
    if not insta_client:
        await notify_john("⚠️ *Instagram* — Client non connecté, story ignorée")
        return
    try:
        text = random.choice(STORY_INSPIRATIONS)
        img_path = create_story_image(
            title=text, subtitle="Project Inves'T — Investis intelligemment",
            bg_color=(10, 10, 30), accent_color=(255, 160, 0)
        )
        try:
            insta_client.photo_upload_to_story(img_path)
        except Exception as e:
            if "media payload" not in str(e).lower():
                raise
        logger.info("Instagram story inspiration publiée")
        await notify_john(f"✅ *Instagram Story* — Inspiration :\n\n💡 {text[:150]}")
    except Exception as e:
        logger.error(f"Erreur Instagram story inspiration: {e}")
        await notify_john(f"❌ *Instagram Story* inspiration erreur: {str(e)[:200]}")

async def instagram_post_story():
    story_type = random.choices(["quiz", "projet", "inspiration"], weights=[30, 40, 30])[0]
    if story_type == "quiz":
        await instagram_story_quiz()
    elif story_type == "projet":
        await instagram_story_projet()
    else:
        await instagram_story_inspiration()

# ─── TWITTER/X ────────────────────────────────────────────────────────────────
async def twitter_post():
    if not twitter_client:
        await notify_john("⚠️ *Twitter/X* — Client non connecté, tweet ignoré")
        return
    try:
        content = await generate_post("Twitter")
        await twitter_client.create_tweet(text=content[:280])
        logger.info("Twitter post publié")
        await notify_john(f"✅ *Twitter/X* — Tweet publié :\n\n{content[:200]}")
    except Exception as e:
        logger.error(f"Erreur Twitter post: {e}")
        await notify_john(f"❌ *Twitter/X* post erreur: {str(e)[:200]}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────
async def main():
    scheduler = AsyncIOScheduler(timezone=PARIS_TZ)

    # Publications quotidiennes
    scheduler.add_job(linkedin_post,    'cron', hour=8,  minute=0)
    scheduler.add_job(instagram_post,   'cron', hour=12, minute=0)
    scheduler.add_job(twitter_post,     'cron', hour=18, minute=0)

    # Stories Instagram 3x/jour
    scheduler.add_job(instagram_post_story, 'cron', hour=9,  minute=0)
    scheduler.add_job(instagram_post_story, 'cron', hour=13, minute=30)
    scheduler.add_job(instagram_post_story, 'cron', hour=19, minute=0)

    logger.info("🔄 Initialisation Instagram...")
    try:
        await asyncio.wait_for(init_instagram(), timeout=30)
    except asyncio.TimeoutError:
        logger.error("❌ Instagram timeout (30s) — bot continue sans Instagram")
        await notify_john("⚠️ *Instagram* — timeout connexion, bot continue sans Instagram")

    logger.info("🔄 Initialisation Twitter...")
    try:
        await asyncio.wait_for(init_twitter(), timeout=30)
    except asyncio.TimeoutError:
        logger.error("❌ Twitter timeout (30s) — bot continue sans Twitter")
        await notify_john("⚠️ *Twitter/X* — timeout connexion, bot continue sans Twitter")

    scheduler.start()
    logger.info("✅ Bot Réseaux Sociaux Project Inves'T démarré !")
    await notify_john("🚀 *Bot Réseaux Sociaux* démarré !\n\nPublications automatiques actives sur LinkedIn, Instagram et Twitter/X.")

    await asyncio.Event().wait()

if __name__ == "__main__":
    print("Démarrage du bot...", flush=True)
    asyncio.run(main())
