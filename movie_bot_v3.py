import telebot
from telebot import types
import requests

TELEGRAM_TOKEN = "8736298609:AAGfNDC9RR09n02eCusGgwlpJjlZ9m7tJn8"
TMDB_TOKEN     = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJlMDRiODEzNWM4NzE2OGQ0MGNhOGU5MzVkMTY1YWM1OCIsIm5iZiI6MTc3NzAyMjE1NS4wOSwic3ViIjoiNjllYjM0Y2I1OTU4YzQ5YzExYjRlMDFjIiwic2NvcGVzIjpbImFwaV9yZWFkIl0sInZlcnNpb24iOjF9.c9xEr9571sMVgH-lyzpwdatPsq_v2KBF0epjLmK1LmI"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

TMDB_BASE    = "https://api.themoviedb.org/3"
TMDB_IMG     = "https://image.tmdb.org/t/p/w500"
TMDB_HEADERS = {
    "Authorization": f"Bearer {TMDB_TOKEN}",
    "accept": "application/json"
}

GENRE_IDS = {
    "Drama":     18,
    "Sci-Fi":    878,
    "Action":    28,
    "Comedy":    35,
    "Animation": 16,
    "Horror":    27,
    "Romance":   10749,
    "Thriller":  53,
}

user_sessions = {}

PAGE_SIZE = 3   # movies shown per page

def tmdb_get(endpoint: str, params: dict = {}) -> dict:
    url = f"{TMDB_BASE}/{endpoint}"
    response = requests.get(url, headers=TMDB_HEADERS, params=params)
    return response.json()


def format_movie(m: dict) -> str:
    title  = m.get("title", "Unknown")
    year   = m.get("release_date", "????")[:4]
    rating = round(m.get("vote_average", 0), 1)
    votes  = m.get("vote_count", 0)
    plot   = m.get("overview", "No description available.")
    return (
        f"🎬 *{title}* ({year})\n"
        f"⭐ Rating: {rating}/10  ({votes} votes)\n"
        f"📖 {plot[:280]}{'...' if len(plot) > 280 else ''}"
    )


def send_movie_card(chat_id, m: dict):
    poster_path = m.get("poster_path")
    text = format_movie(m)
    if poster_path:
        try:
            bot.send_photo(chat_id, f"{TMDB_IMG}{poster_path}",
                           caption=text, parse_mode="Markdown")
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, parse_mode="Markdown")


def pagination_keyboard(chat_id: int) -> types.InlineKeyboardMarkup:
    """Build ◀️ page X/Y ▶️ navigation keyboard."""
    session = user_sessions.get(chat_id, {})
    results = session.get("results", [])
    page    = session.get("page", 0)
    total   = len(results)
    pages   = (total + PAGE_SIZE - 1) // PAGE_SIZE  # ceiling division

    markup = types.InlineKeyboardMarkup(row_width=3)
    prev_btn = types.InlineKeyboardButton(
        "◀️", callback_data="page_prev" if page > 0 else "page_noop")
    page_btn = types.InlineKeyboardButton(
        f"{page + 1} / {pages}", callback_data="page_noop")
    next_btn = types.InlineKeyboardButton(
        "▶️", callback_data="page_next" if (page + 1) < pages else "page_noop")
    markup.add(prev_btn, page_btn, next_btn)
    markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="back_main"))
    return markup


def show_page(chat_id: int, send_new: bool = False):
    """Send (or edit) the current page of results."""
    session = user_sessions.get(chat_id)
    if not session:
        return

    results = session["results"]
    page    = session["page"]
    label   = session.get("label", "Results")
    total   = len(results)
    pages   = (total + PAGE_SIZE - 1) // PAGE_SIZE

    start = page * PAGE_SIZE
    chunk = results[start: start + PAGE_SIZE]

    # Header message
    header = (f"*{label}*\n"
              f"Showing {start + 1}–{min(start + PAGE_SIZE, total)} of {total}")

    if send_new:
        # Delete old nav message if exists, then send fresh cards
        for m in chunk:
            send_movie_card(chat_id, m)
        bot.send_message(chat_id, header,
                         parse_mode="Markdown",
                         reply_markup=pagination_keyboard(chat_id))
        return

    # For page turns: delete old cards and send new ones
    # We re-send cards and update the nav message
    for m in chunk:
        send_movie_card(chat_id, m)
    bot.send_message(chat_id, header,
                     parse_mode="Markdown",
                     reply_markup=pagination_keyboard(chat_id))


def start_session(chat_id: int, results: list, label: str):
    """Save results to session and show first page."""
    user_sessions[chat_id] = {"results": results, "page": 0, "label": label}
    show_page(chat_id, send_new=True)

def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎭 By Genre",     callback_data="menu_genre"),
        types.InlineKeyboardButton("🔥 Popular Now",  callback_data="menu_popular"),
        types.InlineKeyboardButton("⭐ Top Rated",    callback_data="menu_top"),
        types.InlineKeyboardButton("📅 By Year",      callback_data="menu_year"),
        types.InlineKeyboardButton("🔍 Search Title", callback_data="menu_search"),
    )
    return markup


def genre_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name in GENRE_IDS:
        markup.add(types.InlineKeyboardButton(
            name, callback_data=f"genre_{name}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back"))
    return markup


def year_menu():
    markup = types.InlineKeyboardMarkup(row_width=3)
    for label, year in [("90s", 1990), ("2000s", 2000), ("2010s", 2010),
                         ("2015+", 2015), ("2020+", 2020), ("2023+", 2023)]:
        markup.add(types.InlineKeyboardButton(
            label, callback_data=f"year_{year}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back"))
    return markup

@bot.message_handler(commands=["start"])
def start(message):
    name = message.from_user.first_name
    bot.send_message(
        message.chat.id,
        f"👋 Hi, *{name}*! I'm your *Movie Guide Bot* 🎬\n\n"
        "Connected to thousands of real movies via TMDB.\n"
        "Use the menu below or just type any movie title!",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


@bot.message_handler(commands=["help"])
def help_cmd(message):
    bot.send_message(
        message.chat.id,
        "📋 *How to use me:*\n\n"
        "• 🎭 *By Genre* — pick a genre, browse top films\n"
        "• 🔥 *Popular Now* — what people watch today\n"
        "• ⭐ *Top Rated* — all-time best films\n"
        "• 📅 *By Year* — filter by era\n"
        "• 🔍 *Search* — type any movie name\n\n"
        "Use ◀️ ▶️ buttons to flip through results 3 at a time!\n"
        "Type /start for the main menu.",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    cid = call.message.chat.id
    mid = call.message.message_id

    # Pagination
    if call.data == "page_next":
        session = user_sessions.get(cid)
        if session:
            total = len(session["results"])
            pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
            if session["page"] + 1 < pages:
                session["page"] += 1
                bot.answer_callback_query(call.id)
                show_page(cid, send_new=True)
        return

    elif call.data == "page_prev":
        session = user_sessions.get(cid)
        if session and session["page"] > 0:
            session["page"] -= 1
            bot.answer_callback_query(call.id)
            show_page(cid, send_new=True)
        return

    elif call.data == "page_noop":
        bot.answer_callback_query(call.id)
        return

    elif call.data == "back_main":
        bot.send_message(cid, "🎬 *Main Menu*",
                         parse_mode="Markdown", reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return

    # Navigation
    elif call.data == "back":
        bot.edit_message_text("🎬 *Main Menu* — choose an option:",
                              cid, mid, parse_mode="Markdown",
                              reply_markup=main_menu())

    elif call.data == "menu_genre":
        bot.edit_message_text("🎭 *Choose a genre:*", cid, mid,
                              parse_mode="Markdown", reply_markup=genre_menu())

    elif call.data == "menu_year":
        bot.edit_message_text("📅 *Choose an era:*", cid, mid,
                              parse_mode="Markdown", reply_markup=year_menu())

    elif call.data == "menu_search":
        bot.edit_message_text(
            "🔍 *Type a movie title and I'll search for you!*",
            cid, mid, parse_mode="Markdown")
        bot.register_next_step_handler(call.message, do_search)

    # Popular
    elif call.data == "menu_popular":
        bot.answer_callback_query(call.id, "Loading...")
        data = tmdb_get("movie/popular", {"language": "en-US", "page": 1})
        results = data.get("results", [])
        bot.edit_message_text("🔥 *Popular Right Now:*", cid, mid,
                              parse_mode="Markdown")
        start_session(cid, results, "🔥 Popular Now")
        bot.answer_callback_query(call.id)
        return

    # Top rated
    elif call.data == "menu_top":
        bot.answer_callback_query(call.id, "Loading...")
        data = tmdb_get("movie/top_rated", {"language": "en-US", "page": 1})
        results = data.get("results", [])
        bot.edit_message_text("⭐ *All-Time Top Rated:*", cid, mid,
                              parse_mode="Markdown")
        start_session(cid, results, "⭐ Top Rated")
        bot.answer_callback_query(call.id)
        return

    # Genre
    elif call.data.startswith("genre_"):
        genre_name = call.data.replace("genre_", "")
        genre_id   = GENRE_IDS.get(genre_name)
        bot.answer_callback_query(call.id, f"Loading {genre_name}...")
        data = tmdb_get("discover/movie", {
            "with_genres":    genre_id,
            "sort_by":        "vote_average.desc",
            "vote_count.gte": 500,
            "language":       "en-US",
            "page":           1
        })
        results = data.get("results", [])
        bot.edit_message_text(f"🎭 *{genre_name} Movies:*", cid, mid,
                              parse_mode="Markdown")
        start_session(cid, results, f"🎭 {genre_name}")
        bot.answer_callback_query(call.id)
        return

    # Year
    elif call.data.startswith("year_"):
        year = int(call.data.replace("year_", ""))
        bot.answer_callback_query(call.id, f"Loading {year}+...")
        data = tmdb_get("discover/movie", {
            "primary_release_date.gte": f"{year}-01-01",
            "sort_by":                  "vote_average.desc",
            "vote_count.gte":           300,
            "language":                 "en-US",
            "page":                     1
        })
        results = data.get("results", [])
        bot.edit_message_text(f"📅 *Best movies from {year}+:*", cid, mid,
                              parse_mode="Markdown")
        start_session(cid, results, f"📅 From {year}")
        bot.answer_callback_query(call.id)
        return

    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    text = message.text.lower().strip()

    if text in ("hi", "hello", "hey", "привет", "сәлем"):
        name = message.from_user.first_name
        bot.send_message(message.chat.id,
                         f"👋 Hey *{name}*! Ready to find a great film?",
                         parse_mode="Markdown", reply_markup=main_menu())
        return

    if text in ("bye", "goodbye", "пока", "сау бол"):
        bot.send_message(message.chat.id,
                         "🍿 Enjoy your movie! Come back anytime. 👋")
        return

    do_search(message)


def do_search(message):
    """Search TMDB and show paginated results."""
    query = message.text.strip()
    if not query:
        return

    bot.send_message(message.chat.id,
                     f"🔍 Searching for *{query}*...",
                     parse_mode="Markdown")

    data    = tmdb_get("search/movie", {"query": query, "language": "en-US"})
    results = data.get("results", [])
    total   = data.get("total_results", 0)

    if not results:
        bot.send_message(message.chat.id,
                         "😕 Nothing found. Try different spelling or browse by genre!",
                         reply_markup=main_menu())
        return

    bot.send_message(message.chat.id,
                     f"🎯 Found *{total}* results — use ◀️ ▶️ to browse!",
                     parse_mode="Markdown")
    start_session(message.chat.id, results, f'🔍 "{query}"')

if __name__ == "__main__":
    print("🎬 Movie Guide Bot v3 (TMDB + Pagination) is running...")
    bot.polling(none_stop=True)
