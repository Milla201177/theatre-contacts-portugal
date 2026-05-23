#!/usr/bin/env python3
import html
import json
import os
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DATA_PATH = Path(__file__).with_name("artists-portugal-data.json")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
API_BASE = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""

ROLE_ALIASES = {
    "Бутафория / реквизит": "Сценография / декорации",
    "Детский театр": "Детский / кукольный театр",
    "Звук / запись": "Техника / звук / сцена",
    "Менеджмент / закулисье": "Продюсирование / организация",
    "Музыкальный театр": "Музыка / вокал",
    "Стрит-арт": "Перформанс / импровизация",
    "Строительство / реставрация": "Сценография / декорации",
    "Техника / сцена": "Техника / звук / сцена",
    "Театр кукол": "Детский / кукольный театр",
}


def load_artists():
    with DATA_PATH.open(encoding="utf-8") as file:
        return json.load(file)


ARTISTS = load_artists()
CATEGORIES = sorted({category for artist in ARTISTS for category in artist.get("categories", [])})
CITIES = sorted({city for artist in ARTISTS for city in artist.get("cities", [])})


def normalize(value):
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = value.lower().replace("ё", "е").replace("й", "и")
    return " ".join(
        "".join(char if char.isalnum() or char in "+@.- " else " " for char in value).split()
    )


def artist_alias_terms(artist):
    categories = set(artist.get("categories", []))
    return [alias for alias, category in ROLE_ALIASES.items() if category in categories]


def searchable_text(artist):
    contacts = " ".join(f"{item.get('label', '')} {item.get('value', '')}" for item in artist.get("contacts", []))
    return normalize(
        " ".join(
            [
                artist.get("name", ""),
                artist.get("about", ""),
                " ".join(artist.get("roles", [])),
                " ".join(artist.get("categories", [])),
                " ".join(artist_alias_terms(artist)),
                " ".join(artist.get("cities", [])),
                " ".join(artist.get("searchTerms", [])),
                contacts,
            ]
        )
    )


def find_artists(query):
    query = normalize(query)
    if not query:
        return ARTISTS

    exact_city = next((city for city in CITIES if normalize(city) == query), "")
    if exact_city:
        return [artist for artist in ARTISTS if exact_city in artist.get("cities", [])]

    exact_category = next((category for category in CATEGORIES if normalize(category) == query), "")
    if exact_category:
        return [artist for artist in ARTISTS if exact_category in artist.get("categories", [])]

    alias_category = ROLE_ALIASES.get(query) or next(
        (category for alias, category in ROLE_ALIASES.items() if normalize(alias) == query),
        "",
    )
    if alias_category:
        return [artist for artist in ARTISTS if alias_category in artist.get("categories", [])]

    parts = query.split()
    return [artist for artist in ARTISTS if all(part in searchable_text(artist) for part in parts)]


def telegram_request(method, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{API_BASE}/{method}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=35) as response:
        return json.loads(response.read().decode("utf-8"))


def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return telegram_request("sendMessage", payload)


def answer_callback(callback_query_id):
    return telegram_request("answerCallbackQuery", {"callback_query_id": callback_query_id})


def keyboard(items, prefix, columns=2):
    rows = []
    for index, label in enumerate(items):
        if index % columns == 0:
            rows.append([])
        rows[-1].append({"text": label, "callback_data": f"{prefix}:{index}"})
    return {"inline_keyboard": rows}


def format_contact(contact):
    label = html.escape(contact.get("label", "Контакт"))
    value = html.escape(contact.get("value", ""))
    url = contact.get("url", "")
    if url:
        return f'{label}: <a href="{html.escape(url, quote=True)}">{value}</a>'
    return f"{label}: {value}"


def format_artist(artist):
    cities = ", ".join(artist.get("cities", [])) or "город не указан"
    categories = ", ".join(artist.get("categories", []))
    roles = ", ".join(artist.get("roles", []))
    contacts = "\n".join(format_contact(contact) for contact in artist.get("contacts", []))

    return "\n".join(
        [
            f"<b>{html.escape(artist.get('name', 'Без имени'))}</b>",
            f"Город: {html.escape(cities)}",
            f"Направления: {html.escape(categories)}",
            f"Роли: {html.escape(roles)}",
            f"\n{html.escape(artist.get('about', ''))}",
            f"\n{contacts}",
        ]
    )


def send_results(chat_id, query, artists):
    if not artists:
        send_message(
            chat_id,
            "Ничего не нашлось. Попробуй другое слово: например, актёр, звук, Лиссабон, фотография.",
        )
        return

    title = f"Нашла {len(artists)} по запросу: <b>{html.escape(query)}</b>"
    send_message(chat_id, title)
    for artist in artists[:8]:
        send_message(chat_id, format_artist(artist))
    if len(artists) > 8:
        send_message(chat_id, f"Показала первые 8 из {len(artists)}. Уточни запрос, чтобы сузить выдачу.")


def handle_text(chat_id, text):
    text = (text or "").strip()
    if text in {"/start", "/help"}:
        send_message(
            chat_id,
            "Это поиск по театральным контактам в Португалии.\n\n"
            "Напиши имя, профессию, город или навык: актёр, звук, Лиссабон, фотография, танцор.\n\n"
            "Команды: /categories, /cities, /all",
        )
        return

    if text == "/categories":
        send_message(chat_id, "Выбери направление:", keyboard(CATEGORIES, "cat"))
        return

    if text == "/cities":
        send_message(chat_id, "Выбери город:", keyboard(CITIES, "city"))
        return

    if text == "/all":
        send_results(chat_id, "все контакты", ARTISTS)
        return

    send_results(chat_id, text, find_artists(text))


def handle_callback(callback):
    answer_callback(callback["id"])
    data = callback.get("data", "")
    chat_id = callback["message"]["chat"]["id"]
    try:
        prefix, raw_index = data.split(":", 1)
        index = int(raw_index)
    except ValueError:
        return

    if prefix == "cat" and 0 <= index < len(CATEGORIES):
        category = CATEGORIES[index]
        send_results(chat_id, category, find_artists(category))
    elif prefix == "city" and 0 <= index < len(CITIES):
        city = CITIES[index]
        send_results(chat_id, city, find_artists(city))


def poll():
    if not TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN first.")

    offset = 0
    print("Bot is running. Press Ctrl+C to stop.")
    while True:
        try:
            response = telegram_request(
                "getUpdates",
                {"timeout": 30, "offset": offset, "allowed_updates": ["message", "callback_query"]},
            )
            for update in response.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    handle_text(update["message"]["chat"]["id"], update["message"]["text"])
                elif "callback_query" in update:
                    handle_callback(update["callback_query"])
        except urllib.error.URLError as error:
            print(f"Network error: {error}. Retrying...")
            time.sleep(3)


if __name__ == "__main__":
    poll()
