import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
from models import init_db, get_session, Employee, Event, Task, TaskStatus, Activity, activity_participants, EventType, ActivityType
from sqlalchemy import or_, and_
import re
from typing import List, Dict, Tuple, Optional
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize the AI models with better configuration
classifier = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli",
    device=0 if os.environ.get("CUDA_VISIBLE_DEVICES") else -1
)

# Define categories for classification with examples and synonyms
categories = [
    "поиск сотрудника",
    "информация о мероприятии",
    "информация о задаче",
    "социальные активности",
    "приветствие",
    "общая информация",
    "неопределенный запрос"
]

# Define example queries and synonyms for each category with improved patterns
category_patterns = {
    "приветствие": {
        "keywords": [
            'привет', 'здравствуй', 'добрый', 'начать', 'помощь', 'хеллоу',
            'хай', 'здорово', 'приветствую', 'доброе', 'добрый'
        ],
        "synonyms": [
            'здравствуйте', 'доброе утро', 'добрый день', 'добрый вечер',
            'хеллоу', 'хай', 'приветствую', 'здорово', 'добро пожаловать',
            'рад видеть', 'как дела', 'как жизнь'
        ],
        "examples": [
            "привет",
            "здравствуй",
            "добрый день",
            "начать",
            "помощь",
            "как пользоваться",
            "что умеешь",
            "как дела",
            "доброе утро",
            "добрый вечер",
            "рад тебя видеть",
            "как жизнь"
        ]
    },
    "поиск сотрудника": {
        "keywords": [
            'отдел', 'отделе', 'it', 'hr', 'sales', 'marketing', 'проект', 'project',
            'разработка', 'разработчик', 'менеджер', 'директор', 'руководитель',
            'специалист', 'инженер', 'аналитик', 'дизайнер', 'тестировщик',
            'кто', 'найти', 'показать', 'список', 'сотрудники', 'коллеги',
            'работает', 'трудится', 'занимается', 'отвечает', 'знает',
            'умеет', 'может', 'способен', 'опыт', 'навыки', 'умения'
        ],
        "synonyms": [
            'найти', 'показать', 'кто', 'какие', 'список', 'сотрудники', 'работники',
            'коллеги', 'люди', 'команда', 'группа', 'отдел', 'подразделение',
            'искать', 'поиск', 'найти', 'показать', 'вывести', 'отобразить',
            'работает', 'трудится', 'занимается', 'отвечает', 'знает',
            'умеет', 'может', 'способен', 'опыт', 'навыки', 'умения',
            'специалист', 'эксперт', 'профессионал', 'мастер', 'гуру'
        ],
        "examples": [
            "кто работает в отделе",
            "найти сотрудника",
            "кто из отдела",
            "покажи сотрудников",
            "кто работает над проектом",
            "список сотрудников",
            "какие люди работают",
            "кто в команде",
            "покажи команду разработки",
            "кто отвечает за проект",
            "найти специалиста по",
            "кто руководит отделом",
            "кто занимается разработкой",
            "покажи всех сотрудников отдела",
            "кто знает python",
            "кто умеет работать с базами данных",
            "найти эксперта по тестированию",
            "кто может помочь с проектом",
            "кто имеет опыт в маркетинге",
            "покажи специалистов по дизайну"
        ]
    },
    "информация о мероприятии": {
        "keywords": [
            'мероприятие', 'мероприятия', 'корпоратив', 'тренинг', 'встреча',
            'неделе', 'недели', 'месяц', 'месяца', 'день', 'дня', 'дата',
            'время', 'расписание', 'план', 'календарь', 'событие', 'события',
            'день рождения', 'дни рождения', 'праздник', 'праздники',
            'конференция', 'семинар', 'вебинар', 'презентация', 'доклад',
            'выступление', 'обучение', 'курс', 'лекция', 'мастер-класс'
        ],
        "synonyms": [
            'когда', 'расписание', 'план', 'календарь', 'дата', 'время',
            'запланировано', 'назначено', 'будет', 'пройдет', 'состоится',
            'организовано', 'подготовлено', 'устроено', 'праздновать',
            'отмечать', 'поздравлять', 'чествовать', 'проводить',
            'организовывать', 'планировать', 'готовить', 'устраивать'
        ],
        "examples": [
            "какие мероприятия",
            "когда корпоратив",
            "расписание мероприятий",
            "какие встречи",
            "когда тренинг",
            "что запланировано",
            "какие события",
            "что будет на неделе",
            "какие встречи запланированы",
            "расписание на месяц",
            "когда следующее мероприятие",
            "что готовится в отделе",
            "когда день рождения",
            "какие праздники",
            "когда конференция",
            "расписание тренингов",
            "какие семинары на этой неделе",
            "когда мастер-класс",
            "что запланировано на месяц",
            "какие мероприятия в офисе"
        ]
    },
    "информация о задаче": {
        "keywords": [
            'задача', 'задачи', 'дедлайн', 'проект', 'работа', 'поручение',
            'обязанность', 'функция', 'роль', 'ответственность', 'контроль',
            'проверка', 'тестирование', 'разработка', 'внедрение',
            'срок', 'статус', 'прогресс', 'выполнение', 'todo', 'in progress', 'done',
            'блокер', 'проблема', 'ошибка', 'баг', 'фича', 'улучшение',
            'оптимизация', 'рефакторинг', 'документация', 'отчет'
        ],
        "synonyms": [
            'сделать', 'выполнить', 'срок', 'статус', 'прогресс', 'ход',
            'продвижение', 'этап', 'стадия', 'фаза', 'процесс', 'работа',
            'дело', 'поручение', 'обязанность', 'контролировать',
            'проверять', 'отслеживать', 'мониторить', 'в работе',
            'текущие', 'к выполнению', 'сделано', 'выполнено',
            'заблокировано', 'проблема', 'ошибка', 'исправить',
            'улучшить', 'оптимизировать', 'переписать', 'документировать'
        ],
        "examples": [
            "какие задачи",
            "что нужно сделать",
            "какие дедлайны",
            "статус задачи",
            "когда сдать",
            "что в работе",
            "текущие задачи",
            "мои поручения",
            "что на контроле",
            "какие проекты в работе",
            "статус разработки",
            "ход выполнения",
            "что нужно сделать до",
            "какие задачи у",
            "покажи задачи к выполнению",
            "какие задачи в работе",
            "покажи выполненные задачи",
            "есть ли блокеры",
            "какие проблемы",
            "статус проекта"
        ]
    },
    "социальные активности": {
        "keywords": [
            'обед', 'игра', 'игры', 'встреча', 'встречи', 'общение',
            'команда', 'командный', 'вместе', 'совместно', 'активность',
            'активности', 'досуг', 'отдых', 'развлечение', 'развлечения',
            'йога', 'спорт', 'фитнес', 'танцы', 'музыка', 'кино',
            'театр', 'концерт', 'выставка', 'музей', 'парк', 'прогулка',
            'вечеринка', 'праздник', 'корпоратив', 'тимбилдинг'
        ],
        "synonyms": [
            'поиграть', 'пообедать', 'встретиться', 'познакомиться',
            'пообщаться', 'провести время', 'отдохнуть', 'развлечься',
            'командная игра', 'совместный обед', 'групповая активность',
            'заняться спортом', 'позаниматься йогой', 'потанцевать',
            'сходить в кино', 'посетить выставку', 'погулять в парке',
            'отпраздновать', 'провести тимбилдинг', 'организовать вечеринку'
        ],
        "examples": [
            "кто хочет поиграть",
            "кто идет на обед",
            "кто хочет встретиться",
            "найти партнера для игры",
            "кто свободен на обед",
            "кто хочет пообщаться",
            "найти компанию для",
            "кто хочет присоединиться",
            "кто готов поиграть",
            "кто хочет пообедать вместе",
            "кто занимается йогой",
            "кто хочет в кино",
            "кто идет на выставку",
            "кто хочет в парк",
            "кто готов к тимбилдингу",
            "кто хочет на вечеринку",
            "кто занимается спортом",
            "кто танцует",
            "кто любит музыку",
            "кто хочет в театр"
        ]
    },
    "общая информация": {
        "keywords": [
            'что', 'как', 'где', 'когда', 'почему', 'зачем',
            'информация', 'справка', 'помощь', 'подсказка',
            'правила', 'политика', 'процедуры', 'процессы',
            'структура', 'организация', 'компания', 'офис',
            'рабочее место', 'оборудование', 'ресурсы',
            'документы', 'файлы', 'база знаний', 'wiki'
        ],
        "synonyms": [
            'расскажи', 'объясни', 'покажи', 'найди', 'дай',
            'информацию', 'справку', 'помощь', 'подсказку',
            'правила', 'политику', 'процедуры', 'процессы',
            'структуру', 'организацию', 'компанию', 'офис',
            'рабочее место', 'оборудование', 'ресурсы',
            'документы', 'файлы', 'базу знаний', 'wiki'
        ],
        "examples": [
            "как работает",
            "где находится",
            "когда открыто",
            "что нужно знать",
            "какие правила",
            "как пользоваться",
            "где найти",
            "как получить доступ",
            "что делать если",
            "как решить проблему",
            "где посмотреть",
            "как узнать",
            "что нового",
            "какие изменения",
            "как обновить",
            "где документация",
            "как настроить",
            "что требуется",
            "как начать",
            "где справка"
        ]
    }
}

def preprocess_query(query: str) -> str:
    """Preprocess the query for better classification."""
    # Convert to lowercase
    query = query.lower()
    
    # Remove punctuation but keep important symbols
    query = re.sub(r'[^\w\s\-]', ' ', query)
    
    # Remove extra spaces
    query = ' '.join(query.split())
    
    # Remove common stop words
    stop_words = {
        'и', 'в', 'на', 'с', 'по', 'для', 'не', 'ни', 'но', 'а', 'или',
        'что', 'как', 'когда', 'где', 'почему', 'зачем', 'кто', 'какой',
        'какая', 'какие', 'какое', 'каких', 'каким', 'какими', 'каком',
        'какой', 'какую', 'какого', 'какому', 'какою', 'какою', 'какою',
        'какою', 'какою', 'какою', 'какою', 'какою', 'какою', 'какою',
        'это', 'этот', 'эта', 'эти', 'этого', 'этой', 'этим', 'этими',
        'этом', 'эту', 'этою', 'этою', 'этою', 'этою', 'этою', 'этою',
        'этою', 'этою', 'этою', 'этою', 'этою', 'этою', 'этою', 'этою',
        'быть', 'был', 'была', 'были', 'было', 'быть', 'буду', 'будешь',
        'будет', 'будем', 'будете', 'будут', 'стать', 'стал', 'стала',
        'стали', 'стало', 'стать', 'стану', 'станешь', 'станет', 'станем',
        'станете', 'станут'
    }
    words = query.split()
    query = ' '.join(word for word in words if word not in stop_words)
    
    return query

def calculate_category_score(query: str, category: str) -> float:
    """Calculate a score for how well the query matches a category."""
    score = 0.0
    patterns = category_patterns[category]
    
    # Проверяем наличие ключевых слов
    for keyword in patterns["keywords"]:
        if keyword in query:
            score += 0.4
        elif any(word.startswith(keyword) or keyword.startswith(word) for word in query.split()):
            score += 0.2
    
    # Проверяем синонимы
    for synonym in patterns["synonyms"]:
        if synonym in query:
            score += 0.3
        elif any(word.startswith(synonym) or synonym.startswith(word) for word in query.split()):
            score += 0.15
    
    # Проверяем примеры
    for example in patterns["examples"]:
        if example in query:
            score += 0.6
        elif any(word in example for word in query.split()):
            score += 0.3
    
    # Дополнительные проверки для поиска сотрудников
    if category == "поиск сотрудника":
        # Проверяем навыки
        tech_skills = {
            'python': ['python', 'питон'],
            'java': ['java', 'джава'],
            'javascript': ['javascript', 'js', 'джаваскрипт'],
            'react': ['react', 'реакт'],
            'django': ['django', 'джанго'],
            'docker': ['docker', 'докер'],
            'postgresql': ['postgresql', 'postgres', 'постгрес'],
            'mongodb': ['mongodb', 'монго'],
            'selenium': ['selenium', 'селениум'],
            'pytest': ['pytest', 'питест'],
            'postman': ['postman', 'постман'],
            'jira': ['jira', 'джира'],
            'agile': ['agile', 'аджайл'],
            'scrum': ['scrum', 'скрам'],
            'fastapi': ['fastapi', 'фастапи']
        }
        
        for skill, keywords in tech_skills.items():
            if any(keyword in query for keyword in keywords):
                score += 1.0
        
        # Проверяем роли и должности
        roles = {
            'разработчик': ['разработчик', 'программист', 'developer', 'coder'],
            'тестировщик': ['тестировщик', 'qa', 'tester'],
            'менеджер': ['менеджер', 'manager', 'руководитель'],
            'дизайнер': ['дизайнер', 'designer', 'ui/ux'],
            'аналитик': ['аналитик', 'analyst']
        }
        
        for role, keywords in roles.items():
            if any(keyword in query for keyword in keywords):
                score += 0.8
        
        # Проверяем отделы
        departments = {
            'it': ['it', 'айти', 'разработка'],
            'hr': ['hr', 'эйчар', 'кадры'],
            'sales': ['sales', 'продажи'],
            'marketing': ['marketing', 'маркетинг']
        }
        
        for dept, keywords in departments.items():
            if any(keyword in query for keyword in keywords):
                score += 0.8
    
    # Дополнительные проверки для мероприятий
    if category == "информация о мероприятии":
        # Проверяем временные периоды
        time_periods = {
            'сегодня': ['сегодня', 'сейчас', 'в данный момент'],
            'завтра': ['завтра', 'на следующий день'],
            'неделя': ['неделе', 'недели', 'на этой неделе', 'в течение недели'],
            'месяц': ['месяце', 'месяца', 'в этом месяце', 'в течение месяца']
        }
        
        for period, keywords in time_periods.items():
            if any(keyword in query for keyword in keywords):
                score += 1.0
        
        # Проверяем типы мероприятий
        event_types = {
            'встреча': ['встреча', 'meeting', 'митинг'],
            'тренинг': ['тренинг', 'training', 'обучение'],
            'конференция': ['конференция', 'conference', 'конф'],
            'семинар': ['семинар', 'seminar', 'вебинар'],
            'корпоратив': ['корпоратив', 'party', 'вечеринка']
        }
        
        for event_type, keywords in event_types.items():
            if any(keyword in query for keyword in keywords):
                score += 0.8
    
    # Дополнительные проверки для задач
    if category == "информация о задаче":
        # Проверяем статусы
        statuses = {
            'todo': ['todo', 'сделать', 'выполнить', 'к выполнению'],
            'in_progress': ['в работе', 'текущие', 'выполняются'],
            'done': ['done', 'сделано', 'выполнено', 'завершено'],
            'blocked': ['blocked', 'блокер', 'заблокировано']
        }
        
        for status, keywords in statuses.items():
            if any(keyword in query for keyword in keywords):
                score += 1.0
        
        # Проверяем приоритеты
        priorities = {
            'high': ['высокий', 'высокая', 'срочно', 'срочная', 'критично', 'критичная'],
            'medium': ['средний', 'средняя', 'обычный', 'обычная'],
            'low': ['низкий', 'низкая', 'не срочно', 'не срочная']
        }
        
        for priority, keywords in priorities.items():
            if any(keyword in query for keyword in keywords):
                score += 0.8
    
    # Дополнительные проверки для социальных активностей
    if category == "социальные активности":
        # Проверяем типы активностей
        activity_types = {
            'игры': ['игра', 'игры', 'настольные', 'board games'],
            'спорт': ['спорт', 'фитнес', 'йога', 'танцы'],
            'обед': ['обед', 'пообедать', 'lunch'],
            'развлечения': ['кино', 'театр', 'концерт', 'выставка']
        }
        
        for activity_type, keywords in activity_types.items():
            if any(keyword in query for keyword in keywords):
                score += 0.8
    
    return score

def classify_query(query: str) -> Tuple[str, float]:
    """Classify the user query into one of the predefined categories with confidence score."""
    query = preprocess_query(query)
    logger.info(f"Processing query: {query}")
    
    # Calculate scores for each category
    category_scores = {
        category: calculate_category_score(query, category)
        for category in categories if category != "неопределенный запрос"
    }
    
    # Get the category with the highest score
    max_score_category = max(category_scores.items(), key=lambda x: x[1])
    
    # If the highest score is too low, use the AI model
    if max_score_category[1] < 0.3:
        logger.info("Using AI model for classification")
        result = classifier(query, categories)
        max_score_index = result['scores'].index(max(result['scores']))
        category = result['labels'][max_score_index]
        confidence = result['scores'][max_score_index]
        logger.info(f"AI model classified as: {category} with confidence {confidence:.2f}")
    else:
        category = max_score_category[0]
        confidence = max_score_category[1]
        logger.info(f"Rule-based classification: {category} with confidence {confidence:.2f}")
    
    # If confidence is too low, return "неопределенный запрос"
    if confidence < 0.2:
        return "неопределенный запрос", confidence
    
    return category, confidence

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    welcome_message = (
        "👋 Добро пожаловать в корпоративный бот!\n\n"
        "Я помогу вам с:\n\n"
        "🔍 Поиском сотрудников:\n"
        "• По имени, отделу, проекту\n"
        "• По навыкам и опыту\n"
        "• По интересам и увлечениям\n\n"
        "📅 HR-активностями:\n"
        "• Календарь мероприятий\n"
        "• Дни рождения коллег\n"
        "• Корпоративные события\n\n"
        "✅ Рабочими задачами:\n"
        "• Календарь занятости\n"
        "• Напоминания и дедлайны\n"
        "• Статусы и приоритеты\n\n"
        "🎮 Социальными активностями:\n"
        "• Организация мероприятий\n"
        "• Поиск коллег для игр/обедов\n"
        "• Групповые активности\n\n"
        "💡 Просто задайте вопрос в свободной форме!\n\n"
        "Примеры вопросов:\n"
        "• Кто работает в IT отделе?\n"
        "• Какие мероприятия на этой неделе?\n"
        "• Какие задачи у Ивана Петрова?\n"
        "• Кто хочет поиграть в настольные игры?\n"
        "• Когда день рождения у Марии?\n"
        "• Какие срочные задачи в работе?\n"
        "• Кто знает Python и Docker?\n"
        "• Какие активности запланированы на месяц?"
    )
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = (
        "🤖 Как пользоваться ботом:\n\n"
        "1. Поиск сотрудников:\n"
        "   • 'Кто работает в IT отделе?'\n"
        "   • 'Найти разработчика Python'\n"
        "   • 'Кто знает Docker?'\n"
        "   • 'Показать всех из отдела продаж'\n\n"
        "2. HR-активности:\n"
        "   • 'Какие мероприятия на неделе?'\n"
        "   • 'Когда день рождения у Анны?'\n"
        "   • 'Показать календарь событий'\n"
        "   • 'Какие тренинги запланированы?'\n\n"
        "3. Рабочие задачи:\n"
        "   • 'Какие задачи у Ивана?'\n"
        "   • 'Показать срочные задачи'\n"
        "   • 'Что в работе на этой неделе?'\n"
        "   • 'Есть ли блокеры?'\n\n"
        "4. Социальные активности:\n"
        "   • 'Кто хочет поиграть в настольные игры?'\n"
        "   • 'Найти партнера для обеда'\n"
        "   • 'Какие активности на этой неделе?'\n"
        "   • 'Кто занимается йогой?'\n\n"
        "5. Комбинированные запросы:\n"
        "   • 'Какие срочные задачи в работе у Ивана?'\n"
        "   • 'Кто из IT отдела занимается йогой?'\n"
        "   • 'Какие мероприятия и активности на месяц?'\n\n"
        "Команды:\n"
        "   /start - Начать работу с ботом\n"
        "   /help - Показать это сообщение\n\n"
        "💡 Бот понимает вопросы в свободной форме и старается найти наиболее релевантную информацию."
    )
    await update.message.reply_text(help_text)

def search_employees(query: str) -> str:
    """Search for employees based on the query."""
    session = get_session()
    query_lower = query.lower()
    logger.info(f"Searching employees with query: {query_lower}")
    
    try:
        # Определяем ключевые слова для поиска (русские и английские)
        role_keywords = {
            'разработка': [
                'разработка', 'разработчик', 'программист', 'код', 'кодить',
                'developer', 'programmer', 'coder', 'software', 'engineer'
            ],
            'руководство': [
                'руководитель', 'директор', 'менеджер', 'глава', 'начальник',
                'manager', 'director', 'head', 'lead', 'chief', 'senior'
            ],
            'тестирование': [
                'тестирование', 'тестировщик', 'qa', 'контроль качества',
                'tester', 'qa engineer', 'quality', 'testing'
            ],
            'дизайн': [
                'дизайн', 'дизайнер', 'ui', 'ux', 'интерфейс',
                'designer', 'ui/ux', 'interface', 'frontend'
            ],
            'аналитика': [
                'аналитик', 'анализ', 'исследование', 'исследователь',
                'analyst', 'researcher', 'research', 'analysis'
            ]
        }
        
        # Определяем отделы (русские и английские названия)
        departments = {
            'it': ['it', 'айти', 'информационные технологии', 'разработка', 'development'],
            'hr': ['hr', 'эйчар', 'кадры', 'персонал', 'human resources'],
            'sales': ['sales', 'продажи', 'сейлз', 'коммерция'],
            'marketing': ['marketing', 'маркетинг', 'реклама', 'продвижение']
        }
        
        # Извлекаем поисковые термины
        search_terms = []
        search_roles = []
        search_departments = []
        search_skills = []
        search_interests = []
        
        # Проверяем навыки (расширенный список)
        tech_skills = {
            'python': ['python', 'питон'],
            'java': ['java', 'джава'],
            'javascript': ['javascript', 'js', 'джаваскрипт'],
            'react': ['react', 'реакт'],
            'django': ['django', 'джанго'],
            'docker': ['docker', 'докер'],
            'postgresql': ['postgresql', 'postgres', 'постгрес'],
            'mongodb': ['mongodb', 'монго'],
            'selenium': ['selenium', 'селениум'],
            'pytest': ['pytest', 'питест'],
            'postman': ['postman', 'постман'],
            'jira': ['jira', 'джира'],
            'agile': ['agile', 'аджайл'],
            'scrum': ['scrum', 'скрам'],
            'fastapi': ['fastapi', 'фастапи']
        }
        
        # Проверяем навыки
        for skill, keywords in tech_skills.items():
            if any(keyword in query_lower for keyword in keywords):
                search_skills.append(skill)
                logger.info(f"Found skill: {skill}")
        
        # Проверяем интересы
        if 'йога' in query_lower:
            search_interests.append('йога')
        if 'игра' in query_lower or 'игры' in query_lower:
            search_interests.append('настольные игры')
        if 'путешествия' in query_lower:
            search_interests.append('путешествия')
        if 'танцы' in query_lower:
            search_interests.append('танцы')
        if 'теннис' in query_lower:
            search_interests.append('теннис')
        
        # Проверяем роли
        for role, keywords in role_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                search_roles.append(role)
                logger.info(f"Found role: {role}")
        
        # Проверяем отделы
        for dept, keywords in departments.items():
            if any(keyword in query_lower for keyword in keywords):
                search_departments.append(dept)
                logger.info(f"Found department: {dept}")
        
        # Формируем запрос
        query_filters = []
        
        # Если найдены навыки
        if search_skills:
            skill_conditions = []
            for skill in search_skills:
                skill_conditions.append(Employee.skills.ilike(f'%{skill}%'))
            query_filters.append(or_(*skill_conditions))
        
        # Если найдены интересы
        if search_interests:
            interest_conditions = []
            for interest in search_interests:
                interest_conditions.append(Employee.interests.ilike(f'%{interest}%'))
            query_filters.append(or_(*interest_conditions))
        
        # Если найдены роли
        if search_roles:
            role_conditions = []
            for role in search_roles:
                role_keywords_list = role_keywords[role]
                role_conditions.append(or_(
                    *[Employee.position.ilike(f'%{keyword}%') for keyword in role_keywords_list]
                ))
            query_filters.append(or_(*role_conditions))
        
        # Если найдены отделы
        if search_departments:
            dept_conditions = []
            for dept in search_departments:
                dept_keywords_list = departments[dept]
                dept_conditions.append(or_(
                    *[Employee.department.ilike(f'%{keyword}%') for keyword in dept_keywords_list]
                ))
            query_filters.append(or_(*dept_conditions))
        
        # Если запрос содержит "все" или "всех", показываем всех сотрудников
        if 'все' in query_lower or 'всех' in query_lower:
            employees = session.query(Employee).all()
        # Если нет конкретных критериев, ищем по всему тексту
        elif not query_filters:
            employees = session.query(Employee).filter(or_(
                Employee.name.ilike(f'%{query}%'),
                Employee.position.ilike(f'%{query}%'),
                Employee.department.ilike(f'%{query}%'),
                Employee.interests.ilike(f'%{query}%'),
                Employee.skills.ilike(f'%{query}%')
            )).all()
        else:
            # Выполняем поиск с фильтрами
            employees = session.query(Employee).filter(and_(*query_filters)).all()
        
        if employees:
            # Группируем сотрудников по отделам
            dept_employees = {}
            for emp in employees:
                if emp.department not in dept_employees:
                    dept_employees[emp.department] = []
                dept_employees[emp.department].append(emp)
            
            # Формируем ответ
            response = "Найдены следующие сотрудники:\n\n"
            for dept, emps in dept_employees.items():
                response += f"📌 {dept}:\n"
                for emp in emps:
                    response += f"• {emp.name} - {emp.position}\n"
                    if emp.skills:
                        response += f"  🛠️ Навыки: {emp.skills}\n"
                    if emp.interests:
                        response += f"  🎯 Интересы: {emp.interests}\n"
                    if emp.bio:
                        response += f"  📝 О себе: {emp.bio}\n"
                    if emp.email:
                        response += f"  📧 Email: {emp.email}\n"
                    if emp.phone:
                        response += f"  📱 Телефон: {emp.phone}\n"
                    if emp.hire_date:
                        response += f"  📅 В компании с: {emp.hire_date}\n"
                    if emp.birthday:
                        response += f"  🎂 День рождения: {emp.birthday}\n"
                response += "\n"
            return response
        
        return "Сотрудники не найдены. Попробуйте уточнить критерии поиска."
    finally:
        session.close()

def search_events(query: str) -> str:
    """Search for events based on the query."""
    session = get_session()
    query_lower = query.lower()
    logger.info(f"Searching events with query: {query_lower}")
    
    try:
        from datetime import datetime, timedelta
        
        # Определяем временной период
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        month_end = today + timedelta(days=30)
        
        # Проверяем, есть ли в запросе упоминание сотрудника
        employee_name = None
        for word in query_lower.split():
            if len(word) > 3:  # Игнорируем короткие слова
                employee = session.query(Employee).filter(
                    Employee.name.ilike(f'%{word}%')
                ).first()
                if employee:
                    employee_name = employee.name
                    break
        
        # Формируем запрос
        if employee_name:
            # Если найден сотрудник, ищем мероприятия, связанные с ним
            events = session.query(Event).join(
                event_participants
            ).join(
                Employee
            ).filter(
                Employee.name == employee_name
            ).all()
        elif 'неделе' in query_lower or 'недели' in query_lower:
            # Если запрос о неделе, показываем мероприятия на текущую неделю
            events = session.query(Event).filter(
                Event.date >= week_start,
                Event.date <= week_end
            ).all()
        elif 'месяц' in query_lower or 'месяца' in query_lower:
            # Если запрос о месяце, показываем мероприятия на ближайший месяц
            events = session.query(Event).filter(
                Event.date >= today,
                Event.date <= month_end
            ).all()
        elif 'семинар' in query_lower or 'тренинг' in query_lower:
            # Если запрос о семинарах или тренингах
            events = session.query(Event).filter(
                Event.type == EventType.TRAINING
            ).all()
        elif 'день рождения' in query_lower:
            # Если запрос о днях рождения
            events = session.query(Event).filter(
                Event.type == EventType.BIRTHDAY
            ).all()
        else:
            # Поиск по названию или типу
            events = session.query(Event).filter(
                or_(
                    Event.name.ilike(f'%{query}%'),
                    Event.type.ilike(f'%{query}%'),
                    Event.description.ilike(f'%{query}%')
                )
            ).all()
        
        if events:
            # Группируем мероприятия по датам
            date_events = {}
            for event in events:
                if event.date not in date_events:
                    date_events[event.date] = []
                date_events[event.date].append(event)
            
            # Формируем ответ
            response = "Найдены следующие мероприятия:\n\n"
            for date, evts in sorted(date_events.items()):
                response += f"📅 {date}:\n"
                for event in evts:
                    response += f"• {event.name} ({event.type.value})\n"
                    if event.time:
                        response += f"  🕒 {event.time}\n"
                    if event.description:
                        response += f"  {event.description}\n"
                    if event.location:
                        response += f"  📍 {event.location}\n"
                    if event.participants:
                        response += f"  👥 Участники: {', '.join(p.name for p in event.participants)}\n"
                    if event.tags:
                        response += f"  🏷️ Теги: {event.tags}\n"
                    response += "\n"
            return response
        
        return "Мероприятия не найдены."
    finally:
        session.close()

def search_tasks(query: str) -> str:
    """Search for tasks based on the query."""
    session = get_session()
    query_lower = query.lower()
    logger.info(f"Searching tasks with query: {query_lower}")
    
    try:
        # Определяем ключевые слова для статусов задач
        status_keywords = {
            TaskStatus.TODO: [
                'todo', 'сделать', 'выполнить', 'к выполнению', 'новые',
                'ожидает', 'ожидающие', 'в очереди', 'в планах'
            ],
            TaskStatus.IN_PROGRESS: [
                'в работе', 'текущие', 'выполняются', 'активные',
                'in progress', 'разработка', 'разрабатывается'
            ],
            TaskStatus.DONE: [
                'done', 'сделано', 'выполнено', 'завершено', 'готово',
                'завершенные', 'выполненные', 'готовые'
            ],
            TaskStatus.BLOCKED: [
                'blocked', 'блокер', 'блокеры', 'заблокировано',
                'проблема', 'проблемы', 'ошибка', 'ошибки',
                'препятствие', 'препятствия'
            ]
        }
        
        # Определяем ключевые слова для приоритетов
        priority_keywords = {
            'high': ['высокий', 'высокая', 'срочно', 'срочная', 'критично', 'критичная'],
            'medium': ['средний', 'средняя', 'обычный', 'обычная'],
            'low': ['низкий', 'низкая', 'не срочно', 'не срочная']
        }
        
        # Формируем запрос
        query_filters = []
        
        # Проверяем, есть ли в запросе упоминание сотрудника
        employee_name = None
        for word in query_lower.split():
            if len(word) > 3:  # Игнорируем короткие слова
                employee = session.query(Employee).filter(
                    Employee.name.ilike(f'%{word}%')
                ).first()
                if employee:
                    employee_name = employee.name
                    logger.info(f"Found employee: {employee_name}")
                    query_filters.append(Task.assignee.has(Employee.name == employee_name))
                    break
        
        # Проверяем статусы задач
        for status, keywords in status_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                logger.info(f"Found status: {status}")
                query_filters.append(Task.status == status)
        
        # Проверяем приоритеты
        for priority, keywords in priority_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                logger.info(f"Found priority: {priority}")
                query_filters.append(Task.priority == priority)
        
        # Проверяем сроки
        today = datetime.now().date()
        if 'сегодня' in query_lower:
            logger.info("Filtering for today's tasks")
            query_filters.append(Task.deadline == today)
        elif 'завтра' in query_lower:
            tomorrow = today + timedelta(days=1)
            logger.info("Filtering for tomorrow's tasks")
            query_filters.append(Task.deadline == tomorrow)
        elif 'неделе' in query_lower or 'недели' in query_lower:
            week_end = today + timedelta(days=6)
            logger.info(f"Filtering for tasks until {week_end}")
            query_filters.append(Task.deadline <= week_end)
        elif 'месяц' in query_lower or 'месяца' in query_lower:
            month_end = today + timedelta(days=30)
            logger.info(f"Filtering for tasks until {month_end}")
            query_filters.append(Task.deadline <= month_end)
        
        # Проверяем теги
        if 'тег' in query_lower or 'теги' in query_lower:
            tag = query_lower.split('тег')[-1].strip()
            if tag:
                logger.info(f"Filtering by tag: {tag}")
                query_filters.append(Task.tags.ilike(f'%{tag}%'))
        
        # Если нет конкретных фильтров, ищем по всему тексту
        if not query_filters:
            logger.info("No specific filters found, searching in all fields")
            query_filters.append(or_(
                Task.title.ilike(f'%{query}%'),
                Task.description.ilike(f'%{query}%'),
                Task.tags.ilike(f'%{query}%')
            ))
        
        # Выполняем поиск с фильтрами
        logger.info(f"Applying filters: {query_filters}")
        tasks = session.query(Task).filter(and_(*query_filters)).all()
        logger.info(f"Found {len(tasks)} tasks")
        
        if tasks:
            # Группируем задачи по статусу
            status_tasks = {}
            for task in tasks:
                if task.status not in status_tasks:
                    status_tasks[task.status] = []
                status_tasks[task.status].append(task)
            
            # Формируем ответ
            response = "Найдены следующие задачи:\n\n"
            for status, tsk in status_tasks.items():
                response += f"📌 {status.value}:\n"
                for task in tsk:
                    response += f"• {task.title}\n"
                    if task.description:
                        response += f"  {task.description}\n"
                    response += f"  📅 Срок: {task.deadline}\n"
                    response += f"  👤 Исполнитель: {task.assignee.name}\n"
                    if task.priority:
                        response += f"  ⚡ Приоритет: {task.priority}\n"
                    if task.tags:
                        response += f"  🏷️ Теги: {task.tags}\n"
                    if task.created_at:
                        response += f"  📝 Создана: {task.created_at}\n"
                    if task.updated_at:
                        response += f"  🔄 Обновлена: {task.updated_at}\n"
                    response += "\n"
            return response
        
        return "Задачи не найдены."
    finally:
        session.close()

def search_activities(query: str) -> str:
    """Search for social activities based on the query."""
    session = get_session()
    query_lower = query.lower()
    logger.info(f"Searching activities with query: {query_lower}")
    
    try:
        from datetime import datetime, timedelta
        
        # Определяем временной период
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        month_end = today + timedelta(days=30)
        
        # Проверяем, есть ли в запросе упоминание сотрудника
        employee_name = None
        for word in query_lower.split():
            if len(word) > 3:  # Игнорируем короткие слова
                employee = session.query(Employee).filter(
                    Employee.name.ilike(f'%{word}%')
                ).first()
                if employee:
                    employee_name = employee.name
                    break
        
        # Формируем запрос
        if employee_name:
            # Если найден сотрудник, ищем активности, связанные с ним
            activities = session.query(Activity).join(
                activity_participants
            ).join(
                Employee
            ).filter(
                Employee.name == employee_name,
                Activity.is_active == True
            ).all()
        elif 'все' in query_lower or 'всех' in query_lower:
            # Показываем все активные активности
            activities = session.query(Activity).filter(
                Activity.is_active == True
            ).all()
        elif 'неделе' in query_lower or 'недели' in query_lower:
            # Если запрос о неделе, показываем активности на текущую неделю
            activities = session.query(Activity).filter(
                Activity.date >= week_start,
                Activity.date <= week_end,
                Activity.is_active == True
            ).all()
        elif 'месяц' in query_lower or 'месяца' in query_lower:
            # Если запрос о месяце, показываем активности на ближайший месяц
            activities = session.query(Activity).filter(
                Activity.date >= today,
                Activity.date <= month_end,
                Activity.is_active == True
            ).all()
        elif 'йога' in query_lower:
            # Если запрос о йоге
            activities = session.query(Activity).filter(
                Activity.type == ActivityType.TRAINING,
                Activity.name.ilike('%йога%'),
                Activity.is_active == True
            ).all()
        elif 'игра' in query_lower or 'игры' in query_lower:
            # Если запрос об играх
            activities = session.query(Activity).filter(
                Activity.type == ActivityType.GAME,
                Activity.is_active == True
            ).all()
        elif 'обед' in query_lower:
            # Если запрос об обедах
            activities = session.query(Activity).filter(
                Activity.type == ActivityType.LUNCH,
                Activity.is_active == True
            ).all()
        else:
            # Поиск по названию, типу или описанию
            activities = session.query(Activity).filter(
                and_(
                    Activity.is_active == True,
                    or_(
                        Activity.name.ilike(f'%{query}%'),
                        Activity.description.ilike(f'%{query}%'),
                        Activity.type.ilike(f'%{query}%'),
                        Activity.tags.ilike(f'%{query}%')
                    )
                )
            ).all()
        
        if activities:
            # Группируем активности по датам
            date_activities = {}
            for activity in activities:
                if activity.date not in date_activities:
                    date_activities[activity.date] = []
                date_activities[activity.date].append(activity)
            
            # Формируем ответ
            response = "Найдены следующие активности:\n\n"
            for date, acts in sorted(date_activities.items()):
                response += f"📅 {date}:\n"
                for activity in acts:
                    response += f"• {activity.name} ({activity.type.value})\n"
                    if activity.time:
                        response += f"  🕒 {activity.time}\n"
                    if activity.description:
                        response += f"  {activity.description}\n"
                    if activity.location:
                        response += f"  📍 {activity.location}\n"
                    if activity.max_participants:
                        response += f"  👥 Максимум участников: {activity.max_participants}\n"
                    if activity.participants:
                        response += f"  👥 Участники: {', '.join(p.name for p in activity.participants)}\n"
                    if activity.tags:
                        response += f"  🏷️ Теги: {activity.tags}\n"
                    if activity.created_at:
                        response += f"  📝 Создана: {activity.created_at}\n"
                    if activity.updated_at:
                        response += f"  🔄 Обновлена: {activity.updated_at}\n"
                    response += "\n"
            return response
        
        return "Активности не найдены."
    finally:
        session.close()

def search_general_info(query: str) -> str:
    """Search for general information based on the query."""
    query_lower = query.lower()
    
    # База знаний
    if 'база знаний' in query_lower or 'wiki' in query_lower:
        return (
            "📚 База знаний доступна по адресу: wiki.company.com\n\n"
            "Для доступа используйте ваши корпоративные учетные данные.\n"
            "Если у вас нет доступа, обратитесь к вашему руководителю или в IT-отдел."
        )
    
    # Офис
    if 'офис' in query_lower or 'находится' in query_lower:
        return (
            "🏢 Офис находится по адресу:\n"
            "г. Москва, ул. Примерная, д. 123\n\n"
            "Ближайшее метро: Примерная (5 минут пешком)\n"
            "Вход через главный вход, предъявите пропуск на ресепшене."
        )
    
    # Правила
    if 'правила' in query_lower or 'политика' in query_lower:
        return (
            "📋 Основные правила компании:\n\n"
            "1. Рабочий день с 9:00 до 18:00\n"
            "2. Обед с 13:00 до 14:00\n"
            "3. Дресс-код: business casual\n"
            "4. Обязательное использование корпоративной почты\n"
            "5. Соблюдение политики информационной безопасности\n\n"
            "Полные правила доступны в базе знаний."
        )
    
    # IT поддержка
    if 'it' in query_lower or 'поддержка' in query_lower or 'помощь' in query_lower:
        return (
            "🖥️ IT поддержка:\n\n"
            "• Email: support@company.com\n"
            "• Внутренний номер: 1234\n"
            "• Часы работы: 9:00 - 18:00\n\n"
            "Для срочных вопросов звоните на внутренний номер."
        )
    
    return "Информация не найдена."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages and respond accordingly."""
    query = update.message.text
    logger.info(f"Received message: {query}")
    
    # Проверяем на приветствие
    if any(word in query.lower() for word in ['привет', 'здравствуй', 'добрый', 'хай', 'хеллоу']):
        await update.message.reply_text(
            "👋 Привет! Я корпоративный бот, готовый помочь вам с поиском информации о сотрудниках, "
            "мероприятиях, задачах и социальных активностях. Просто задайте вопрос в свободной форме!"
        )
        return
    
    category, confidence = classify_query(query)
    logger.info(f"Classified as: {category} with confidence {confidence:.2f}")
    
    if category == "неопределенный запрос":
        # Пробуем найти ответ в общей информации
        response = search_general_info(query)
        if response == "Информация не найдена.":
            response = (
                "Извините, я не совсем понял ваш вопрос. Попробуйте переформулировать или используйте /help для получения подсказок.\n\n"
                "Примеры вопросов:\n"
                "• Кто работает в IT отделе?\n"
                "• Какие мероприятия запланированы на этой неделе?\n"
                "• Какие задачи у Ивана Петрова?\n"
                "• Кто хочет поиграть в настольные игры?\n"
                "• Когда день рождения у Марии?\n"
                "• Какие срочные задачи в работе?\n"
                "• Кто знает Python и Docker?\n"
                "• Какие активности запланированы на месяц?"
            )
    elif category == "поиск сотрудника":
        response = search_employees(query)
    elif category == "информация о мероприятии":
        response = search_events(query)
    elif category == "информация о задаче":
        response = search_tasks(query)
    elif category == "социальные активности":
        response = search_activities(query)
    elif category == "общая информация":
        response = search_general_info(query)
    else:
        response = "Извините, я не совсем понял ваш вопрос. Попробуйте переформулировать или используйте /help для получения подсказок."
    
    logger.info(f"Sending response: {response}")
    await update.message.reply_text(response)

async def create_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a new social activity."""
    try:
        # Parse activity details from message
        message_text = update.message.text
        activity_data = parse_activity_data(message_text)
        
        if not activity_data:
            await update.message.reply_text(
                "Пожалуйста, укажите детали активности в формате:\n"
                "Создать активность: [название]\n"
                "Тип: [игра/обед/тренинг]\n"
                "Дата: [дд.мм.гггг]\n"
                "Время: [чч:мм]\n"
                "Место: [место]\n"
                "Описание: [описание]\n"
                "Макс. участников: [число]"
            )
            return
        
        session = get_session()
        try:
            # Create new activity
            activity = Activity(
                name=activity_data['name'],
                type=activity_data['type'],
                date=activity_data['date'],
                time=activity_data['time'],
                location=activity_data['location'],
                description=activity_data['description'],
                max_participants=activity_data['max_participants'],
                is_active=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Add creator as first participant
            activity.participants.append(update.effective_user)
            
            session.add(activity)
            session.commit()
            
            await update.message.reply_text(
                f"✅ Активность '{activity.name}' успешно создана!\n\n"
                f"📅 Дата: {activity.date}\n"
                f"🕒 Время: {activity.time}\n"
                f"📍 Место: {activity.location}\n"
                f"👥 Макс. участников: {activity.max_participants}\n\n"
                f"Присоединяйтесь к активности!"
            )
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error creating activity: {e}")
        await update.message.reply_text("Произошла ошибка при создании активности. Попробуйте позже.")

def parse_activity_data(message: str) -> Optional[Dict]:
    """Parse activity details from message text."""
    try:
        lines = message.split('\n')
        activity_data = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if 'название' in key:
                    activity_data['name'] = value
                elif 'тип' in key:
                    activity_data['type'] = value
                elif 'дата' in key:
                    activity_data['date'] = datetime.strptime(value, '%d.%m.%Y').date()
                elif 'время' in key:
                    activity_data['time'] = value
                elif 'место' in key:
                    activity_data['location'] = value
                elif 'описание' in key:
                    activity_data['description'] = value
                elif 'макс' in key:
                    activity_data['max_participants'] = int(value)
        
        # Validate required fields
        required_fields = ['name', 'type', 'date', 'time', 'location']
        if all(field in activity_data for field in required_fields):
            return activity_data
        return None
    except Exception as e:
        logger.error(f"Error parsing activity data: {e}")
        return None

async def join_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Join an existing activity."""
    try:
        activity_id = context.args[0] if context.args else None
        if not activity_id:
            await update.message.reply_text("Пожалуйста, укажите ID активности.")
            return
        
        session = get_session()
        try:
            activity = session.query(Activity).filter(
                Activity.id == activity_id,
                Activity.is_active == True
            ).first()
            
            if not activity:
                await update.message.reply_text("Активность не найдена или уже неактивна.")
                return
            
            if len(activity.participants) >= activity.max_participants:
                await update.message.reply_text("К сожалению, все места уже заняты.")
                return
            
            if update.effective_user in activity.participants:
                await update.message.reply_text("Вы уже участвуете в этой активности.")
                return
            
            activity.participants.append(update.effective_user)
            session.commit()
            
            await update.message.reply_text(
                f"✅ Вы успешно присоединились к активности '{activity.name}'!\n\n"
                f"📅 Дата: {activity.date}\n"
                f"🕒 Время: {activity.time}\n"
                f"📍 Место: {activity.location}\n"
                f"👥 Участников: {len(activity.participants)}/{activity.max_participants}"
            )
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error joining activity: {e}")
        await update.message.reply_text("Произошла ошибка при присоединении к активности. Попробуйте позже.")

async def create_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a new task."""
    try:
        # Parse task details from message
        message_text = update.message.text
        task_data = parse_task_data(message_text)
        
        if not task_data:
            await update.message.reply_text(
                "Пожалуйста, укажите детали задачи в формате:\n"
                "Создать задачу: [название]\n"
                "Описание: [описание]\n"
                "Исполнитель: [имя]\n"
                "Срок: [дд.мм.гггг]\n"
                "Приоритет: [высокий/средний/низкий]\n"
                "Теги: [тег1, тег2]"
            )
            return
        
        session = get_session()
        try:
            # Find assignee
            assignee = session.query(Employee).filter(
                Employee.name.ilike(f"%{task_data['assignee']}%")
            ).first()
            
            if not assignee:
                await update.message.reply_text("Исполнитель не найден.")
                return
            
            # Create new task
            task = Task(
                title=task_data['title'],
                description=task_data['description'],
                assignee=assignee,
                deadline=task_data['deadline'],
                priority=task_data['priority'],
                status=TaskStatus.TODO,
                tags=task_data['tags'],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            session.add(task)
            session.commit()
            
            await update.message.reply_text(
                f"✅ Задача '{task.title}' успешно создана!\n\n"
                f"📝 Описание: {task.description}\n"
                f"👤 Исполнитель: {task.assignee.name}\n"
                f"📅 Срок: {task.deadline}\n"
                f"⚡ Приоритет: {task.priority}\n"
                f"🏷️ Теги: {task.tags}"
            )
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        await update.message.reply_text("Произошла ошибка при создании задачи. Попробуйте позже.")

def parse_task_data(message: str) -> Optional[Dict]:
    """Parse task details from message text."""
    try:
        lines = message.split('\n')
        task_data = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if 'название' in key:
                    task_data['title'] = value
                elif 'описание' in key:
                    task_data['description'] = value
                elif 'исполнитель' in key:
                    task_data['assignee'] = value
                elif 'срок' in key:
                    task_data['deadline'] = datetime.strptime(value, '%d.%m.%Y').date()
                elif 'приоритет' in key:
                    task_data['priority'] = value
                elif 'теги' in key:
                    task_data['tags'] = value
        
        # Validate required fields
        required_fields = ['title', 'assignee', 'deadline']
        if all(field in task_data for field in required_fields):
            return task_data
        return None
    except Exception as e:
        logger.error(f"Error parsing task data: {e}")
        return None

async def update_task_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update task status."""
    try:
        task_id = context.args[0] if context.args else None
        new_status = context.args[1] if len(context.args) > 1 else None
        
        if not task_id or not new_status:
            await update.message.reply_text(
                "Пожалуйста, укажите ID задачи и новый статус.\n"
                "Пример: /update_task 123 in_progress"
            )
            return
        
        session = get_session()
        try:
            task = session.query(Task).filter(Task.id == task_id).first()
            
            if not task:
                await update.message.reply_text("Задача не найдена.")
                return
            
            # Update status
            task.status = TaskStatus(new_status)
            task.updated_at = datetime.now()
            session.commit()
            
            await update.message.reply_text(
                f"✅ Статус задачи '{task.title}' обновлен на {task.status.value}!"
            )
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error updating task status: {e}")
        await update.message.reply_text("Произошла ошибка при обновлении статуса задачи. Попробуйте позже.")

def main():
    """Start the bot."""
    # Initialize database
    init_db()
    
    # Create the Application
    application = Application.builder().token("8181926764:AAE0RsZomH3bdhLnGqatSi5W7HH3fwjiEQQ").build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("create_activity", create_activity))
    application.add_handler(CommandHandler("join_activity", join_activity))
    application.add_handler(CommandHandler("create_task", create_task))
    application.add_handler(CommandHandler("update_task", update_task_status))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 