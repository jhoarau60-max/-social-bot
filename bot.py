import os
import asyncio
import random
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx
from google import genai
from google.genai import types as genai_types
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
PROSPECTS_PER_DAY = 5

MESSAGE_PROSPECT = (
    "Bonjour {prenom} 👋 Je tombe sur votre profil et je vois qu'on partage "
    "le même intérêt pour l'investissement. Je travaille sur des projets qui "
    "génèrent des revenus passifs via l'immobilier digital et le trading IA — "
    "des choses concrètes qui fonctionnent en 2026. "
    "Ça vous dirait qu'on échange 5 minutes ?"
)

KEYWORDS_LINKEDIN  = ["investissement passif", "liberté financière", "crypto investissement", "immobilier", "revenus passifs"]
KEYWORDS_INSTAGRAM = ["investissement", "cryptofrancais", "immobilier", "libertefinanciere", "revenuspassifs"]
KEYWORDS_TWITTER   = ["investissement crypto", "liberté financière", "immobilier digital", "revenus passifs"]

CONTENT_TOPICS = [
    "L'immobilier tokenisé permet d'investir dans des propriétés mondiales dès 10$ — une révolution accessible à tous.",
    "Les bots de trading MEV génèrent des revenus passifs 24h/24 automatiquement sur la blockchain.",
    "En 2026, la liberté financière passe par les investissements passifs numériques. Voici comment.",
    "Saviez-vous qu'on peut acheter une fraction d'une villa à Miami pour 10$ ? L'immobilier tokenisé rend ça possible.",
    "Le trading algorithmique IA : comment des particuliers génèrent 1% par jour sans toucher aux marchés.",
    "Diversifier entre immobilier digital et trading IA : la stratégie des investisseurs intelligents en 2026.",
    "ArbCore, E-Estate, Smart Bot : 3 façons concrètes de créer des revenus passifs avec la technologie blockchain.",
]

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ─── NOTIFICATION TELEGRAM ───────────────────────────────────────────────────
async def notify_john(message: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        async with httpx.AsyncClient() as client:
            await client.post(url, json={
                "chat_id": JOHN_ID,
                "text": message,
                "parse_mode": "Markdown"
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
    response = await asyncio.to_thread(
        lambda: gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
    )
    return response.text.strip()

# ─── LINKEDIN ─────────────────────────────────────────────────────────────────
def get_linkedin_api():
    cookies_file = "/tmp/linkedin_cookies.json"
    try:
        if os.path.exists(cookies_file):
            api = Linkedin(LINKEDIN_EMAIL, LINKEDIN_PASSWORD, cookies=cookies_file)
        else:
            api = Linkedin(LINKEDIN_EMAIL, LINKEDIN_PASSWORD)
        return api
    except Exception:
        return Linkedin(LINKEDIN_EMAIL, LINKEDIN_PASSWORD)

LINKEDIN_CONNECTIONS_FILE = "/tmp/linkedin_connections.json"

def load_known_connections():
    import json
    try:
        if os.path.exists(LINKEDIN_CONNECTIONS_FILE):
            with open(LINKEDIN_CONNECTIONS_FILE, 'r') as f:
                return set(json.load(f))
    except Exception:
        pass
    return set()

def save_known_connections(conn_set):
    import json
    try:
        with open(LINKEDIN_CONNECTIONS_FILE, 'w') as f:
            json.dump(list(conn_set), f)
    except Exception as e:
        logger.error(f"Erreur sauvegarde connexions: {e}")

async def linkedin_check_new_connections():
    try:
        api = await asyncio.to_thread(get_linkedin_api)
        connections = await asyncio.to_thread(api.get_connections, limit=50)
        known = load_known_connections()
        new_connections = []
        current_ids = set()
        for c in connections:
            uid = c.get("public_id", "") or str(c.get("entityUrn", ""))
            if not uid:
                continue
            current_ids.add(uid)
            if uid not in known:
                new_connections.append(c)
        if not known:
            save_known_connections(current_ids)
            logger.info(f"LinkedIn: {len(current_ids)} connexions initiales sauvegardées")
            return
        for c in new_connections:
            try:
                prenom = c.get("firstName", "vous")
                uid = c.get("public_id", "") or str(c.get("entityUrn", ""))
                message = MESSAGE_PROSPECT.format(prenom=prenom)
                recipients = [{"entityUrn": c.get("entityUrn", f"urn:li:member:{uid}")}]
                await asyncio.to_thread(api.send_message, message, recipients)
                logger.info(f"LinkedIn message envoyé à {prenom} (nouvelle connexion)")
                await notify_john(f"🤝 *LinkedIn* — Nouvelle connexion acceptée !\n👤 {prenom}\n💬 Message de prospection envoyé automatiquement")
                await asyncio.sleep(random.uniform(30, 60))
            except Exception as e:
                logger.error(f"Erreur message nouvelle connexion LinkedIn: {e}")
        save_known_connections(current_ids)
    except Exception as e:
        logger.error(f"Erreur vérification connexions LinkedIn: {e}")

async def linkedin_post():
    try:
        content = await generate_post("LinkedIn")
        api = await asyncio.to_thread(get_linkedin_api)
        await asyncio.to_thread(api.post, content)
        logger.info("LinkedIn post publié")
        await notify_john(f"✅ *LinkedIn* — Post publié :\n\n{content[:300]}")
    except Exception as e:
        logger.error(f"Erreur LinkedIn post: {e}")
        await notify_john(f"❌ *LinkedIn* post erreur: {str(e)[:200]}")

async def linkedin_prospect():
    try:
        api = await asyncio.to_thread(get_linkedin_api)
        keyword = random.choice(KEYWORDS_LINKEDIN)
        people = await asyncio.to_thread(api.search_people, keyword, PROSPECTS_PER_DAY * 2)
        count = 0
        for person in people:
            if count >= PROSPECTS_PER_DAY:
                break
            try:
                profile_id = person.get("public_id", "")
                prenom = person.get("firstName", "vous")
                if not profile_id:
                    continue
                api.add_connection(profile_id)
                count += 1
                logger.info(f"LinkedIn invitation envoyée à {prenom}")
                await asyncio.sleep(random.uniform(40, 90))
            except Exception as e:
                logger.error(f"LinkedIn prospect individuel: {e}")
        await notify_john(f"✅ *LinkedIn* — {count} invitations envoyées (mot-clé: {keyword})")
    except Exception as e:
        logger.error(f"Erreur LinkedIn prospecting: {e}")
        await notify_john(f"❌ *LinkedIn* prospecting erreur: {str(e)[:200]}")

# ─── INSTAGRAM ────────────────────────────────────────────────────────────────
async def instagram_post():
    try:
        content = await generate_post("Instagram")
        cl = InstaClient()
        cl.login(INSTA_USERNAME, INSTA_PASSWORD)
        # Crée une image simple avec Pillow
        from PIL import Image, ImageDraw, ImageFont
        import io
        img = Image.new("RGB", (1080, 1080), color=(10, 20, 50))
        draw = ImageDraw.Draw(img)
        # Texte centré
        lines = content.split("\n")
        y = 300
        for line in lines[:8]:
            draw.text((50, y), line[:60], fill=(255, 255, 255))
            y += 80
        img_path = "/tmp/insta_post.jpg"
        img.save(img_path, format="JPEG", quality=95)
        cl.photo_upload(img_path, content)
        logger.info("Instagram post publié")
        await notify_john(f"✅ *Instagram* — Post publié :\n\n{content[:300]}")
    except Exception as e:
        logger.error(f"Erreur Instagram post: {e}")
        await notify_john(f"❌ *Instagram* post erreur: {str(e)[:200]}")

async def instagram_prospect():
    try:
        cl = InstaClient()
        cl.login(INSTA_USERNAME, INSTA_PASSWORD)
        hashtag = random.choice(KEYWORDS_INSTAGRAM)
        medias = cl.hashtag_medias_top(hashtag, amount=30)
        count = 0
        done_users = set()
        for media in medias:
            if count >= PROSPECTS_PER_DAY:
                break
            try:
                user_id = media.user.pk
                if user_id in done_users:
                    continue
                done_users.add(user_id)
                user_info = cl.user_info(user_id)
                prenom = user_info.full_name.split()[0] if user_info.full_name else "vous"
                message = MESSAGE_PROSPECT.format(prenom=prenom)
                cl.direct_send(message, [user_id])
                count += 1
                logger.info(f"Instagram DM envoyé à {prenom}")
                await asyncio.sleep(random.uniform(90, 180))
            except Exception as e:
                logger.error(f"Instagram prospect individuel: {e}")
        await notify_john(f"✅ *Instagram* — {count} DMs envoyés (#{hashtag})")
    except Exception as e:
        logger.error(f"Erreur Instagram prospecting: {e}")
        await notify_john(f"❌ *Instagram* prospecting erreur: {str(e)[:200]}")

# ─── TWITTER/X ────────────────────────────────────────────────────────────────
async def twitter_post():
    try:
        content = await generate_post("Twitter")
        client = twikit.Client("fr-FR")
        await client.login(
            auth_info_1=TWITTER_USERNAME,
            auth_info_2=TWITTER_EMAIL,
            password=TWITTER_PASSWORD
        )
        await client.create_tweet(text=content[:280])
        logger.info("Twitter post publié")
        await notify_john(f"✅ *Twitter/X* — Tweet publié :\n\n{content[:200]}")
    except Exception as e:
        logger.error(f"Erreur Twitter post: {e}")
        await notify_john(f"❌ *Twitter/X* post erreur: {str(e)[:200]}")

async def twitter_prospect():
    try:
        client = twikit.Client("fr-FR")
        await client.login(
            auth_info_1=TWITTER_USERNAME,
            auth_info_2=TWITTER_EMAIL,
            password=TWITTER_PASSWORD
        )
        keyword = random.choice(KEYWORDS_TWITTER)
        users = await client.search_user(keyword, count=PROSPECTS_PER_DAY * 2)
        count = 0
        for user in users:
            if count >= PROSPECTS_PER_DAY:
                break
            try:
                prenom = user.name.split()[0] if user.name else "vous"
                message = MESSAGE_PROSPECT.format(prenom=prenom)
                await client.send_dm(user.id, message)
                count += 1
                logger.info(f"Twitter DM envoyé à {prenom}")
                await asyncio.sleep(random.uniform(60, 120))
            except Exception as e:
                logger.error(f"Twitter prospect individuel: {e}")
        await notify_john(f"✅ *Twitter/X* — {count} DMs envoyés (mot-clé: {keyword})")
    except Exception as e:
        logger.error(f"Erreur Twitter prospecting: {e}")
        await notify_john(f"❌ *Twitter/X* prospecting erreur: {str(e)[:200]}")

# ─── MAIN ─────────────────────────────────────────────────────────────────────
async def main():
    scheduler = AsyncIOScheduler(timezone=PARIS_TZ)

    # Publications quotidiennes
    scheduler.add_job(linkedin_post,    'cron', hour=8,  minute=0)
    scheduler.add_job(instagram_post,   'cron', hour=12, minute=0)
    scheduler.add_job(twitter_post,     'cron', hour=18, minute=0)

    # Prospecting tous les 3 jours
    scheduler.add_job(linkedin_prospect,  'interval', days=3, start_date='2026-04-25 09:30:00')
    scheduler.add_job(instagram_prospect, 'interval', days=3, start_date='2026-04-25 14:00:00')
    scheduler.add_job(twitter_prospect,   'interval', days=3, start_date='2026-04-25 16:00:00')

    # Vérification nouvelles connexions LinkedIn toutes les 6h
    scheduler.add_job(linkedin_check_new_connections, 'interval', hours=6)

    scheduler.start()
    logger.info("✅ Bot Réseaux Sociaux Project Inves'T démarré !")
    await notify_john("🚀 *Bot Réseaux Sociaux* démarré !\n\nPublications et prospecting actifs sur LinkedIn, Instagram et Twitter/X.")

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
