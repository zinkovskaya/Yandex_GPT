import logging

import json
import time
from config import IAM_TOKEN_ENDPOINT, IAM_TOKEN_PATH, MODEL_TEMPERATURE, TOKENS_DATA_PATH

import requests

from config import LOGS_PATH, MAX_MODEL_TOKENS, FOLDER_ID, GPT_MODEL

logging.basicConfig(
    filename=LOGS_PATH,
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
    filemode="w",
)


def get_system_content(setting_user, hero_user, genre):
    return (f"Ты талантливый сценарист с большим опытом. Сочини историю в жанре {genre},"
            f"главный герой {hero_user}, место событий - {setting_user}")


def count_tokens_in_dialogue(messages: list) -> int:
    token = get_iam_token()
    folder_id = FOLDER_ID
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    data = {
        "modelUri": f"gpt://{folder_id}/yandexgpt/latest",
        "maxTokens": MAX_MODEL_TOKENS,
        "messages": []
    }

    for row in messages:
        data["messages"].append(
            {
                "role": row["role"],
                "text": row["content"]
            }
        )

    return len(
        requests.post(
            "https://llm.api.cloud.yandex.net/foundationModels/v1/tokenizeCompletion",
            json=data,
            headers=headers
        ).json()["tokens"]
    )


def increment_tokens_by_request(messages: list[dict]):
    try:
        with open(TOKENS_DATA_PATH, "r") as token_file:
            tokens_count = json.load(token_file)["tokens_count"]

    except FileNotFoundError:
        tokens_count = 0

    current_tokens_used = count_tokens_in_dialogue(messages)
    tokens_count += current_tokens_used

    with open(TOKENS_DATA_PATH, "w") as token_file:
        json.dump({"tokens_count": tokens_count}, token_file)


def ask_gpt(messages):
    iam_token = get_iam_token()

    url = f"https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        'Authorization': f'Bearer {iam_token}',
        'Content-Type': 'application/json'
    }

    data = {
        "modelUri": f"gpt://{FOLDER_ID}/{GPT_MODEL}/latest",
        "completionOptions": {
            "stream": False,
            "temperature": MODEL_TEMPERATURE,
            "maxTokens": MAX_MODEL_TOKENS
        },
        "messages": []
    }

    for row in messages:
        data["messages"].append(
            {
                "role": row["role"],
                "text": row["content"]
            }
        )

    try:
        response = requests.post(url, headers=headers, json=data)

    except Exception as e:
        print("Произошла непредвиденная ошибка.", e)

    else:
        if response.status_code != 200:
            print("Ошибка при получении ответа:", response.status_code)
        else:
            result = response.json()['result']['alternatives'][0]['message']['text']
            messages.append({"role": "assistant", "content": result})
            increment_tokens_by_request(messages)
            return result


def create_new_iam_token():

    headers = {"Metadata-Flavor": "Google"}

    try:
        response = requests.get(IAM_TOKEN_ENDPOINT, headers=headers)

    except Exception as e:
        print("Не удалось выполнить запрос:", e)
        print("Токен не получен")

    else:
        if response.status_code == 200:
            token_data = {
                "access_token": response.json().get("access_token"),
                "expires_at": response.json().get("expires_in") + time.time()
            }

            with open(IAM_TOKEN_PATH, "w") as token_file:
                json.dump(token_data, token_file)

        else:
            print("Ошибка при получении ответа:", response.status_code)
            print("Токен не получен")


def get_iam_token() -> str:

    try:
        with open(IAM_TOKEN_PATH, "r") as token_file:
            token_data = json.load(token_file)

        expires_at = token_data.get("expires_at")

        if expires_at <= time.time():
            create_new_iam_token()

    except FileNotFoundError:
        create_new_iam_token()

    with open(IAM_TOKEN_PATH, "r") as token_file:
        token_data = json.load(token_file)

    return token_data.get("access_token")

