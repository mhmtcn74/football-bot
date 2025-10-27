import os
import requests
import telebot
from telebot import types
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

# Read tokens from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
API_KEY = os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY")

if not BOT_TOKEN:
    raise SystemExit("Error: BOT_TOKEN environment variable is missing.")
if not API_KEY:
    raise SystemExit("Error: FOOTBALL_API_KEY environment variable is missing.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

HELP_TEXT = (
    "⚽ Maç Analiz Botu (İstatistik tabanlı)\n\n"
    "Komutlar:\n"
    "/start - Hoş geldin mesajı\n"
    "/match <takım adı> - Takım bilgilerini getirir (ülke, kuruluş, logo)\n"
    "/form <takım adı> - Takımın son 5 maçlık formunu gösterir (W/D/L)\n"
)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, HELP_TEXT)

def api_get(path, params=None):
    base = "https://v3.football.api-sports.io"
    headers = {"x-apisports-key": API_KEY}
    r = requests.get(base + path, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def find_team(team_name):
    data = api_get("/teams", params={"search": team_name})
    resp = data.get("response", [])
    if not resp:
        return None
    return resp[0]["team"]

@bot.message_handler(commands=['match'])
def cmd_match(message):
    text = message.text.partition(' ')[2].strip()
    if not text:
        bot.reply_to(message, "Kullanım: /match <takım adı>  örn: /match galatasaray")
        return
    team = find_team(text)
    if not team:
        bot.reply_to(message, "Takım bulunamadı. Lütfen tam adı veya popüler kısa adıyla tekrar deneyin.")
        return
    name = team.get("name")
    country = team.get("country", "Bilinmiyor")
    founded = team.get("founded") or "Bilinmiyor"
    logo = team.get("logo") or ""
    msg = f"🏟️ *{name}*\nÜlke: {country}\nKuruluş: {founded}\n"
    if logo:
        msg += f"Logo: {logo}\n"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['form'])
def cmd_form(message):
    text = message.text.partition(' ')[2].strip()
    if not text:
        bot.reply_to(message, "Kullanım: /form <takım adı>  örn: /form fenerbahçe")
        return
    team = find_team(text)
    if not team:
        bot.reply_to(message, "Takım bulunamadı. Lütfen tam adı veya popüler kısa adıyla tekrar deneyin.")
        return
    team_id = team.get("id")
    try:
        data = api_get("/fixtures", params={"team": team_id, "last": 5})
    except requests.HTTPError as e:
        bot.reply_to(message, f"API isteğinde hata: {e}")
        return
    fixtures = data.get("response", [])
    if not fixtures:
        bot.reply_to(message, "Son 5 maç bilgisi bulunamadı.")
        return
    form = []
    details = []
    for f in fixtures:
        home = f["teams"]["home"]
        away = f["teams"]["away"]
        goals = f.get("goals", {})
        home_goals = goals.get("home")
        away_goals = goals.get("away")
        if home_goals is None or away_goals is None:
            res = "?"
        else:
            if team_id == home["id"]:
                if home_goals > away_goals:
                    res = "W"
                elif home_goals < away_goals:
                    res = "L"
                else:
                    res = "D"
            else:
                if away_goals > home_goals:
                    res = "W"
                elif away_goals < home_goals:
                    res = "L"
                else:
                    res = "D"
        form.append(res)
        match_str = f"{home['name']} {home_goals if home_goals is not None else '-'} - {away_goals if away_goals is not None else '-'} {away['name']} ({f['fixture']['date'][:10]}) -> {res}"
        details.append(match_str)
    form_text = " ".join(form)
    reply = f"📋 *{team.get('name')}* son {len(fixtures)} maç formu: {form_text}\n\nDetaylar:\n" + "\n".join(details)
    bot.send_message(message.chat.id, reply, parse_mode="Markdown")

# --- Health server for Render Web Service ---
def run_health_server():
    port = int(os.getenv("PORT", "8000"))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    print(f"Health server listening on 0.0.0.0:{port}")
    server.serve_forever()

t = threading.Thread(target=run_health_server, daemon=True)
t.start()

if __name__ == '__main__':
    print("Bot başlatılıyor...")
    bot.infinity_polling()
