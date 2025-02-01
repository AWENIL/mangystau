from openai import OpenAI
import shelve
from dotenv import load_dotenv
import os
import time
import logging

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")

client = OpenAI()  # API ключ подтянется автоматически из переменной окружения


def upload_file(file_path):
    """ Загружает файл на OpenAI """
    with open(file_path, "rb") as f:
        file = client.files.create(file=f, purpose="assistants")
    return file


def create_assistant(file):
    """ Создаёт ассистента с файлом в базе знаний """
    assistant = client.beta.assistants.create(
        name="WhatsApp AirBnb Assistant",
        instructions=(
            "You're a helpful WhatsApp assistant that can assist guests that are staying in our Paris AirBnb. "
            "Use your knowledge base to best respond to customer queries. "
            "If you don't know the answer, say simply that you cannot help with question and advise to contact the host directly. "
            "Be friendly and funny."
        ),
        tools=[{"type": "retrieval"}],
        model="gpt-4o-mini",
        file_ids=[file.id],
    )
    return assistant


def check_if_thread_exists(wa_id):
    """ Проверяет, есть ли уже тред для данного wa_id """
    with shelve.open("threads_db") as threads_shelf:
        return threads_shelf.get(wa_id, None)


def store_thread(wa_id, thread_id):
    """ Сохраняет тред для пользователя """
    with shelve.open("threads_db", writeback=True) as threads_shelf:
        threads_shelf[wa_id] = thread_id


def run_assistant(thread, name):
    """ Запускает ассистента и дожидается завершения работы """
    assistant = client.beta.assistants.retrieve(OPENAI_ASSISTANT_ID)

    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id,
    )

    # Ждем завершения работы ассистента
    while True:
        time.sleep(0.5)
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run.status == "completed":
            break
        elif run.status in ["failed", "cancelled"]:
            logging.error(f"Run failed or was cancelled: {run.status}")
            return "Ошибка при обработке запроса."

    # Получаем последнее сообщение
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    new_message = messages.data[0].content[0].text.value
    logging.info(f"Generated message: {new_message}")
    return new_message


def generate_response(message_body, wa_id, name):
    """ Генерирует ответ ассистента на сообщение """
    thread_id = check_if_thread_exists(wa_id)

    if thread_id is None:
        logging.info(f"Creating new thread for {name} with wa_id {wa_id}")
        thread = client.beta.threads.create()
        store_thread(wa_id, thread.id)
        thread_id = thread.id
    else:
        logging.info(f"Retrieving existing thread for {name} with wa_id {wa_id}")
        thread = client.beta.threads.retrieve(thread_id)

    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=message_body,
    )

    return run_assistant(thread, name)