import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

from exceptions import IsNot200Error, RepeatSendError

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s'
)
handler_rotating = RotatingFileHandler(
    'main.log',
    maxBytes=50000000,
    backupCount=5
)
handler_rotating.setFormatter(formatter)
handler_streaming = logging.StreamHandler(sys.stdout)
handler_streaming.setFormatter(formatter)
logger.addHandler(handler_rotating)
logger.addHandler(handler_streaming)
load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 5
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def sent_message_do_not_repeat(message, bot):
    """Preventing send_message func from repeating."""
    try:
        send_message(bot, message)
        logger.info('Message does not repeat')
        return message
    except RepeatSendError:
        raise RepeatSendError('Message is sent again')


def send_message(bot, message):
    """Sends message to telegram."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info('Message is sent')
    except telegram.error.TelegramError:
        raise telegram.error.TelegramError('Message is not sent')


def get_api_answer(current_timestamp):
    """Gets response from yandex API in dict."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise IsNot200Error('Response status code is not 200')
    except IsNot200Error:
        raise IsNot200Error('Response status code is not 200')
    except Exception:
        raise Exception('Api error')
    else:
        return response.json()


def check_response(response):
    """Gets value from dict with the key 'homeworks'."""
    if not isinstance(response, dict):
        raise TypeError('Response must be dict')
    try:
        homework = response.get('homeworks')
        if type(homework) != list:
            raise AttributeError('Homework must be list')
        if homework is None:
            raise KeyError('There is no homework key')
    except KeyError:
        raise KeyError('There is no homework key')
    except AttributeError:
        raise AttributeError('Homework must be list')
    except Exception:
        raise Exception('Check response error')
    else:
        return homework


def parse_status(homework):
    """Parsing some values from homework and returns HW status."""
    try:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
        if homework_name is None or homework_status is None:
            raise KeyError('Key error in during parsing')
        verdict = HOMEWORK_STATUSES[homework_status]
    except KeyError:
        raise KeyError('Key error')
    except Exception:
        raise Exception('Parse status error')
    else:
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Cheking that keys exist."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Main logic of bot-program."""
    if check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())
        sent_message = ''
        while True:
            try:
                response = get_api_answer(current_timestamp)
                homework = check_response(response)
                if homework:
                    message = parse_status(homework[0])
                    if sent_message != message:
                        sent_message = sent_message_do_not_repeat(message, bot)
                else:
                    logger.debug('There are no new statuses')
                current_timestamp = int(time.time())
                time.sleep(RETRY_TIME)
            except Exception as error:
                message = f'Program crash: {error}'
                logger.error(message)
                if sent_message != message:
                    try:
                        sent_message = sent_message_do_not_repeat(message, bot)
                    except telegram.error.TelegramError:
                        raise telegram.error.TelegramError(
                            'Message is not sent'
                        )
                time.sleep(RETRY_TIME)
            else:
                logger.info('There are no errors')
    else:
        logger.critical('Environment variables error')


if __name__ == '__main__':
    main()
