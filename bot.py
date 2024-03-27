import json
import logging

import telebot
from telebot.types import Message

import database
import gpt
from config import (
    ADMINS, LOGS_PATH, MAX_TOKENS_PER_SESSION, MAX_SESSIONS,
    MAX_USERS, MAX_MODEL_TOKENS, BOT_TOKEN, TOKENS_DATA_PATH
)
from gpt import ask_gpt, count_tokens_in_dialogue, get_system_content
from utils import create_keyboard

logging.basicConfig(
    filename=LOGS_PATH,
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
    filemode="w",
)

bot = telebot.TeleBot(BOT_TOKEN)

database.create_db()
database.create_table()


hero = {
    "Айлин Морвэн": "Айлин Морвэн - молодая воительница из фэнтезийного королевства Эландор. Она обладает невероятной силой и мастерски владеет мечом.",
    "Ганс Фишер": "Ханс - отважный пират из далекого морского мира Карибии. Он умелый стрелок и опытный моряк, который ищет сокровища и приключения на широких просторах океана",
    "Элизабет Старлинг": "Элизабет - молодая археолог из Лондона, специализирующаяся на исследовании древних культур",
    "Райан Стормборн": "Райан Стормборн - отважный викинг из скандинавского поселения на севере, который обладает необычными способностями контроля над стихиями. "
}

setting = {
    "Подводный город Атлантида": "В этом мире, скрытом под глубинами океана, живут существа с удивительными способностями и технологиями.",
    "Фантастический мир Лунной долины": "В этом мире, где луна всегда светит ярко, живут разнообразные фэнтезийные существа, такие как эльфы, драконы и гномы.",
    "Постапокалиптический мир Забытой Земли": "После катастрофы, которая изменила мир навсегда, осталась лишь разрушенная земля и редкие оазисы жизни.",
    "Магическая академия Волшебного университета": "В этом мире существуют талантливые маги и волшебницы, которые обучаются в университете, чтобы раскрыть свои магические способности."
}
hero_list = ["Айлин Морвэн", "Ганс Фишер", "Мира Сирион", "Райан Стормборн"]
genre_list = ["Ужасы", "Фэнтези", "Комедия", "Мелодрама", "Боевик", "Детектив"]
set_list = ["Подводный город Атлантида", "Фантастический мир Лунной долины", "Постапокалиптический мир Забытой Земли", "Магическая академия Волшебного университета"]


@bot.message_handler(commands=["start"])
def start(message):
    user_name = message.from_user.first_name
    user_id = message.from_user.id

    if not database.is_user_in_db(user_id):
        if len(database.get_all_users_data()) < MAX_USERS:
            database.add_new_user(user_id)
        else:

            bot.send_message(
                user_id,
                "К сожалению, лимит пользователей исчерпан. "
                "Вы не сможете воспользоваться ботом:("
            )
            return

    bot.send_message(
        user_id,
        f"Привет, {user_name}! Я бот-сценарист, который умеет писать истории!\n"
        f"Ты можешь выбрать главного героя, сеттинг и жанр, я помогу в написании истории\n"
        f"Чтобы узнать обо мне побольше - /about\n"
        f"А если возникнут вопросы - /help\n",
        reply_markup=create_keyboard(["/new_story"]),
    )


@bot.message_handler(commands=["help"])
def help_command(message):
    bot.send_message(message.from_user.id,
                     text="Я бот-сценарист, который умеет сочинять истории по выбранным вами параметрам!\n"
                          "/start - начало работы бота\n"
                          "/help - для помощи с ботом\n"
                          "/about - описание бота\n"
                          "/new_story - начать новую историю\n"
                          "/whole_story - вывести всю историю\n"
                          "/all_tokens - посмотреть все токены\n"
                          "/end - завершить историю"
                        )


@bot.message_handler(commands=["about"])
def about_command(message):
    bot.send_message(message.from_user.id,
                     text="Я бот-сценарист, который умеет сочинять истории по выбранным вами параметрам! "
                          "Тебе достаточно выбрать главного героя, сетттинг, жанр истории и ввести свои "
                          "правки и пожелания, а я сочиню!")


@bot.message_handler(commands=["debug"])
def send_logs(message):
    user_id = message.from_user.id
    if user_id in ADMINS:
        with open(LOGS_PATH, "rb") as f:
            bot.send_document(message.from_user.id, f)


@bot.message_handler(commands=["all_tokens"])
def send_tokens(message):
    user_id = message.from_user.id
    if database.is_user_in_db(user_id):
        with open(TOKENS_DATA_PATH, "r") as f:
            bot.send_message(user_id,
                             f"За всё время израсходовано: {json.load(f)["tokens_count"]}, токенов"
                             )


@bot.message_handler(commands=["new_story"])
def registration(message):
    bot.send_message(message.chat.id,
                     f"Давай начнем писать, для начала выбери своего героя:",
                     reply_markup=create_keyboard(["Выбрать героя"]))
    bot.register_next_step_handler(message, choose_hero)


def filter_choose_hero(message: Message) -> bool:
    user_id = message.from_user.id
    if database.is_user_in_db(user_id):
        return message.text in ["Выбрать героя", "Выбрать другого героя", "Начать новую сессию"]


@bot.message_handler(func=filter_choose_hero)
def choose_hero(message: Message):
    user_id = message.from_user.id
    sessions = database.get_user_data(user_id)["sessions"]
    if sessions < MAX_SESSIONS:
        database.update_row(user_id, "sessions", sessions + 1)
        database.update_row(user_id, "tokens", MAX_TOKENS_PER_SESSION)
        bot.send_message(
            user_id,
            "Выбери главного героя твоей истории:",
            reply_markup=create_keyboard(hero_list),
        )
        bot.register_next_step_handler(message, hero_selection)

    else:
        bot.send_message(
            user_id,
            "К сожалению, лимит твоих вопросов исчерпан:("
        )


def hero_selection(message: Message):
    user_id = message.from_user.id
    user_choice = message.text
    if user_choice in hero_list:
        database.update_row(user_id, "hero", user_choice)
        bot.send_message(
            user_id,
            f"Отлично, {message.from_user.first_name}, теперь твой главный герой - {user_choice}\n"
            f"Давай узнаем о нем побольше. {hero[user_choice]}\n"
            f"\n"
            f"Давай теперь жанр твоей истории:",
            reply_markup=create_keyboard(["Изменить жанр истории"]),
        )
        bot.register_next_step_handler(message, genre_selection)

    else:
        bot.send_message(
            user_id,
            "К сожалению, такого героя нет, выбери один из предложенных в меню",
            reply_markup=create_keyboard(hero_list),
        )
        bot.register_next_step_handler(message, hero_selection)


def filter_choose_genre(message: Message) -> bool:
    user_id = message.from_user.id
    if database.is_user_in_db(user_id):
        return message.text == "Изменить жанр истории"


@bot.message_handler(func=filter_choose_genre)
def choose_genre(message: Message):
    bot.send_message(
        message.from_user.id,
        "Какой жанр тебе нужен:",
        reply_markup=create_keyboard(genre_list),
    )
    bot.register_next_step_handler(message, genre_selection)


def genre_selection(message: Message):
    user_id = message.from_user.id
    user_choice = message.text
    if user_choice in genre_list:
        database.update_row(user_id, "genre", user_choice)
        bot.send_message(
            user_id,
            f"Принято, {message.from_user.first_name}! Теперь твоя история будет в стиле {user_choice}. "
            f"А теперь приступим к выбору сеттинга.",
            reply_markup=create_keyboard(["Изменить сеттинг истории"])
        )
        bot.register_next_step_handler(message, set_selection)
    else:
        bot.send_message(
            user_id,
            "Пожалуйста, выбери жанр из предложенных:",
            reply_markup=create_keyboard(genre_list),
        )
        bot.register_next_step_handler(message, genre_selection)


def filter_choose_set(message: Message) -> bool:
    user_id = message.from_user.id
    if database.is_user_in_db(user_id):
        return message.text == "Изменить сеттинг истории"


@bot.message_handler(func=filter_choose_genre)
def choose_set(message: Message):
    bot.send_message(
        message.from_user.id,
        "Какой сеттинг истории тебе нужен:",
        reply_markup=create_keyboard(set_list),
    )
    bot.register_next_step_handler(message, set_selection)


def set_selection(message: Message):
    user_id = message.from_user.id
    user_choice = message.text
    if user_choice in set_list:
        database.update_row(user_id, "setting", user_choice)
        bot.send_message(
            user_id,
            f"Принято, {message.from_user.first_name}! Теперь твоя история будет разворачиваться в {user_choice}.\n"
            f"Описание мира: {setting[user_choice]}.\n Если хочешь что-то добавить к своей истории, то напиши сейчас.")

        bot.register_next_step_handler(message, story_information)
    else:
        bot.send_message(
            user_id,
            "Пожалуйста, выбери сеттинг из предложенных:",
            reply_markup=create_keyboard(set_list),
        )
        bot.register_next_step_handler(message, set_selection)


@bot.message_handler(content_types=['text'])
def story_information(message):
    user_id = message.from_user.id
    message_text = message.text
    if message_text == "Написать историю":
        give_answer(message)

    if database.is_user_in_db(user_id):
        database.update_row(user_id, "info", message_text)
        bot.send_message(user_id,
                         text="Дополнение к истории принято! Скорее жми кнопку!",
                         reply_markup=create_keyboard(["Написать историю"]))


@bot.message_handler(commands=['end'])
def end_story(message):
    user_id = message.chat.id
    if not database.is_user_in_db(user_id):
        bot.send_message(user_id,
                         "Не уверен как так получилось, но вроде как ты еще не начал историю..",
                         reply_markup=create_keyboard(['/start']))

    else:
        bot.send_message(user_id,
                         f"С тобой весело писать историю, что делаем дальше?",
                         reply_markup=create_keyboard(['/whole_story', '/start', '/all_tokens', '/debug']))


def filter_story(message) -> bool:
    user_id = message.from_user.id
    if database.is_user_in_db(user_id):
        return message.text == "Написать историю"


@bot.message_handler(func=filter_story)
def solve_task(message):
    user_id = message.from_user.id
    bot.send_message(user_id, "Приступаю!")


def give_answer(message: Message):
    user_id = message.from_user.id
    user_tokens = database.get_user_data(user_id)["tokens"]
    setting_user = database.get_user_data(user_id)["setting"]
    hero_user = database.get_user_data(user_id)["hero"]
    genre = database.get_user_data(user_id)["genre"]
    user_content = database.get_user_data(user_id)["info"]

    system_content = get_system_content(setting_user, hero_user, genre)

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content}
    ]
    tokens_messages = count_tokens_in_dialogue(messages)

    if tokens_messages + MAX_MODEL_TOKENS <= user_tokens:
        bot.send_message(message.from_user.id, "Решаю...")
        answer = ask_gpt(messages)
        messages.append({"role": "assistant", "content": answer})
        user_tokens -= count_tokens_in_dialogue([{"role": "assistant", "content": answer}])
        database.update_row(user_id, "tokens", user_tokens)

        json_string = json.dumps(messages, ensure_ascii=False)
        database.update_row(user_id, "messages", json_string)

        if answer is None:
            bot.send_message(
                user_id,
                "Не могу получить ответ от GPT :(",
                reply_markup=create_keyboard(["/start"]),
            )
        elif answer == "":
            bot.send_message(
                user_id,
                "Не могу сформулировать решение :(",
                reply_markup=create_keyboard(["/start"])
            )
            logging.info(
                f"Отправлено: {message.text}\nПолучена ошибка: нейросеть вернула пустую строку"
            )
        else:
            bot.send_message(
                user_id,
                answer,
                reply_markup=create_keyboard(
                    [
                        "Продолжить историю",
                        "/new_story",
                        "Начать новую сессию",
                    ]
                ),
            )

    else:
        bot.send_message(
            message.from_user.id,
            "Токенов на ответ может не хватить:( Начни новую сессию",
            reply_markup=create_keyboard(["Начать новую сессию"])
        )
        logging.info(
            f"Отправлено: {message.text}\nПолучено: Предупреждение о нехватке токенов"
        )


def filter_continue_story(message: Message) -> bool:
    user_id = message.from_user.id
    if database.is_user_in_db(user_id):
        return message.text == "Продолжить историю"


@bot.message_handler(func=filter_continue_story)
def continue_explaining(message):
    user_id = message.from_user.id
    hero_user = database.get_user_data(user_id)["hero"]
    if not hero_user:
        bot.send_message(
            user_id,
            "Кажется ты не выбрал героя..",
            reply_markup=create_keyboard(
                [
                    "Выбрать героя",
                    "Начать новую сессию"]),
        )
        return

    json_string_messages = database.get_user_data(user_id)["messages"]
    messages = json.loads(json_string_messages)
    user_tokens = database.get_user_data(user_id)["tokens"]
    tokens_messages = count_tokens_in_dialogue(messages)

    if tokens_messages + MAX_MODEL_TOKENS <= user_tokens:
        bot.send_message(user_id, "Формулирую продолжение...")
        answer = ask_gpt(messages)
        messages.append({"role": "assistant", "content": answer})
        user_tokens -= count_tokens_in_dialogue([{"role": "assistant", "content": answer}])
        database.update_row(user_id, "tokens", user_tokens)

        json_string_messages = json.dumps(messages, ensure_ascii=False)
        database.update_row(user_id, "messages", json_string_messages)

        if answer is None:
            bot.send_message(
                user_id,
                "Не могу получить ответ от GPT :(",
                reply_markup=create_keyboard(
                    [
                        "/new_story",
                        "/start",
                        "Начать новую сессию"
                    ]
                ),
            )

        else:
            bot.send_message(
                user_id,
                answer,
                reply_markup=create_keyboard(
                    [
                        "Продолжить историю",
                        "Начать новую сессию",
                        "/whole_story"
                    ]
                ),
            )
    else:
        bot.send_message(
            message.from_user.id,
            "Токенов на ответ может не хватить:( Пожалуйста, попробуй укоротить вопрос. "
            "или задай новый",
            reply_markup=create_keyboard(["/start"]),
        )
        logging.info(
            f"Отправлено: {message.text}\nПолучено: Предупреждение о нехватке токенов"
        )


@bot.message_handler(commands=["whole_story"])
def get_whole_story(message):
    user_id = message.chat.id

    if not database.is_user_in_db(user_id):
        bot.send_message(user_id, "Не уверен как так получилось, но вроде как ты еще не начал историю..")
        return

    if database.is_user_in_db(user_id):
        json_string_messages = database.get_user_data(user_id)["content"]
        messages = json.loads(json_string_messages)
        whole_story = " "
        for row in messages:
            whole_story += row["content"]

        bot.send_message(user_id, f"История которая у нас получается:\n{whole_story}")


def is_tokens_limit(user_id, chat_id, bot):
    if not database.is_user_in_db(user_id):
        return

    tokens_of_session = gpt.count_tokens_in_dialogue(user_id)

    if tokens_of_session >= MAX_TOKENS_PER_SESSION:
        bot.send_message(
            chat_id,
            f'Вы израсходовали все токены в этой сессии. Вы можете начать новую, введя help_with')

    elif tokens_of_session + 50 >= MAX_TOKENS_PER_SESSION:
        bot.send_message(
            chat_id,
            f'Вы приближаетесь к лимиту в {MAX_TOKENS_PER_SESSION} токенов в этой сессии. '
            f'Ваш запрос содержит суммарно {tokens_of_session} токенов.')

    elif tokens_of_session / 2 >= MAX_TOKENS_PER_SESSION:
        bot.send_message(
            chat_id,
            f'Вы использовали больше половины токенов в этой сессии. '
            f'Ваш запрос содержит суммарно {tokens_of_session} токенов.'
        )


bot.polling()
