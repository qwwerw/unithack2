from sqlalchemy import create_engine, Column, Integer, String, Date, Time, DateTime, Boolean, ForeignKey, Enum, Text, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, time
import enum
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create database engine
engine = create_engine(os.getenv('DATABASE_URL', 'sqlite:///corporate_bot.db'))
Session = sessionmaker(bind=engine)
Base = declarative_base()

# Enums
class EventType(enum.Enum):
    CONFERENCE = "конференция"
    TRAINING = "тренинг"
    BIRTHDAY = "день рождения"
    CORPORATE = "корпоратив"
    MEETING = "встреча"
    SEMINAR = "семинар"

class ActivityType(enum.Enum):
    GAME = "игра"
    LUNCH = "обед"
    TRAINING = "тренинг"
    SPORT = "спорт"
    TEAM_BUILDING = "тимбилдинг"

class TaskStatus(enum.Enum):
    TODO = "к выполнению"
    IN_PROGRESS = "в работе"
    DONE = "выполнено"
    BLOCKED = "заблокировано"

# Association tables
event_participants = Table('event_participants', Base.metadata,
    Column('event_id', Integer, ForeignKey('events.id')),
    Column('employee_id', Integer, ForeignKey('employees.id'))
)

activity_participants = Table('activity_participants', Base.metadata,
    Column('activity_id', Integer, ForeignKey('activities.id')),
    Column('employee_id', Integer, ForeignKey('employees.id'))
)

# Models
class Employee(Base):
    __tablename__ = 'employees'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    position = Column(String(100))
    department = Column(String(50))
    email = Column(String(100))
    phone = Column(String(20))
    hire_date = Column(Date)
    birthday = Column(Date)
    skills = Column(Text)
    interests = Column(Text)
    bio = Column(Text)
    
    # Relationships
    tasks = relationship("Task", back_populates="assignee")
    events = relationship("Event", secondary=event_participants, back_populates="participants")
    activities = relationship("Activity", secondary=activity_participants, back_populates="participants")

class Event(Base):
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    type = Column(Enum(EventType))
    date = Column(Date)
    time = Column(Time)
    location = Column(String(200))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    participants = relationship("Employee", secondary=event_participants, back_populates="events")

class Task(Base):
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(Enum(TaskStatus), default=TaskStatus.TODO)
    priority = Column(String(20))
    deadline = Column(Date)
    tags = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Foreign keys
    assignee_id = Column(Integer, ForeignKey('employees.id'))
    
    # Relationships
    assignee = relationship("Employee", back_populates="tasks")

class Activity(Base):
    __tablename__ = 'activities'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    type = Column(Enum(ActivityType))
    date = Column(Date)
    time = Column(Time)
    location = Column(String(200))
    description = Column(Text)
    max_participants = Column(Integer)
    is_active = Column(Boolean, default=True)
    tags = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    participants = relationship("Employee", secondary=activity_participants, back_populates="activities")

def get_session():
    """Get a new database session."""
    return Session()

def parse_date(date_str):
    """Parse date string to datetime object."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()

def parse_time(time_str):
    """Parse time string to time object."""
    return datetime.strptime(time_str, "%H:%M").time()

def init_db():
    """Initialize the database with test data."""
    # Drop all tables and recreate them
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    
    session = Session()
    
    try:
        # Create test employees
        employees = [
            Employee(
                name="Иван Петров",
                position="Senior Developer",
                department="IT",
                email="ivan@company.com",
                phone="+7 (999) 123-45-67",
                hire_date=parse_date("2020-01-15"),
                birthday=parse_date("1985-05-20"),
                skills="Python, Django, PostgreSQL, Docker",
                interests="настольные игры, программирование, путешествия",
                bio="Опытный разработчик с 10-летним стажем"
            ),
            Employee(
                name="Анна Сидорова",
                position="HR Manager",
                department="HR",
                email="anna@company.com",
                phone="+7 (999) 234-56-78",
                hire_date=parse_date("2019-03-10"),
                birthday=parse_date("1990-08-15"),
                skills="HR, рекрутинг, обучение персонала",
                interests="йога, танцы, психология",
                bio="HR специалист с опытом в IT компаниях"
            ),
            Employee(
                name="Дмитрий Козлов",
                position="Developer",
                department="IT",
                email="dmitry@company.com",
                phone="+7 (999) 345-67-89",
                hire_date=parse_date("2021-06-01"),
                birthday=parse_date("1995-03-25"),
                skills="Python, FastAPI, MongoDB, React",
                interests="настольные игры, спорт, музыка",
                bio="Full-stack разработчик"
            ),
            Employee(
                name="Мария Иванова",
                position="QA Engineer",
                department="IT",
                email="maria@company.com",
                phone="+7 (999) 456-78-90",
                hire_date=parse_date("2022-02-15"),
                birthday=parse_date("1992-11-10"),
                skills="Python, Selenium, Pytest, Postman",
                interests="тестирование, танцы, йога, путешествия",
                bio="QA инженер с опытом автоматизации тестирования"
            ),
            Employee(
                name="Алексей Смирнов",
                position="Project Manager",
                department="IT",
                email="alexey@company.com",
                phone="+7 (999) 567-89-01",
                hire_date=parse_date("2018-09-01"),
                birthday=parse_date("1988-07-05"),
                skills="Agile, Scrum, Jira, Python",
                interests="настольные игры, теннис, чтение",
                bio="Опытный проект-менеджер в IT"
            )
        ]
        
        # Add employees to session
        session.add_all(employees)
        session.flush()  # Flush to get IDs
        
        # Create test events
        events = [
            Event(
                name="Python Meetup",
                type=EventType.CONFERENCE,
                date=parse_date("2025-05-20"),
                time=parse_time("15:00"),
                location="Конференц-зал",
                description="Встреча Python-разработчиков компании",
                participants=employees[:3]  # Иван, Анна, Дмитрий
            ),
            Event(
                name="Тренинг по Agile",
                type=EventType.TRAINING,
                date=parse_date("2025-05-22"),
                time=parse_time("10:00"),
                location="Тренинг-зал",
                description="Обучение методологии Agile",
                participants=employees[1:]  # Все кроме Ивана
            ),
            Event(
                name="День рождения Анны",
                type=EventType.BIRTHDAY,
                date=parse_date("2025-08-15"),
                time=parse_time("12:00"),
                location="Офис",
                description="Празднование дня рождения",
                participants=employees
            )
        ]
        
        # Add events to session
        session.add_all(events)
        session.flush()
        
        # Create test tasks
        tasks = [
            Task(
                title="Рефакторинг API",
                description="Оптимизация существующего API",
                status=TaskStatus.IN_PROGRESS,
                deadline=parse_date("2025-05-25"),
                assignee=employees[0],  # Иван
                tags="python, api, optimization"
            ),
            Task(
                title="Написание тестов",
                description="Автоматизация тестирования",
                status=TaskStatus.TODO,
                deadline=parse_date("2025-05-30"),
                assignee=employees[3],  # Мария
                tags="testing, automation, python"
            ),
            Task(
                title="Исправление бага в авторизации",
                description="Критический баг в системе авторизации",
                status=TaskStatus.BLOCKED,
                deadline=parse_date("2025-05-18"),
                assignee=employees[2],  # Дмитрий
                tags="bug, auth, critical"
            )
        ]
        
        # Add tasks to session
        session.add_all(tasks)
        session.flush()
        
        # Create test activities
        activities = [
            Activity(
                name="Настольные игры",
                type=ActivityType.GAME,
                date=parse_date("2025-05-21"),
                time=parse_time("18:00"),
                location="Игровая комната",
                description="Еженедельные настольные игры",
                max_participants=8,
                is_active=True,
                participants=employees[:3],  # Иван, Анна, Дмитрий
                tags="games, team building"
            ),
            Activity(
                name="Йога в офисе",
                type=ActivityType.TRAINING,
                date=parse_date("2025-05-23"),
                time=parse_time("09:00"),
                location="Тренинг-зал",
                description="Утренняя йога для сотрудников",
                max_participants=10,
                is_active=True,
                participants=[employees[1], employees[3]],  # Анна, Мария
                tags="yoga, health, morning"
            ),
            Activity(
                name="Совместный обед",
                type=ActivityType.LUNCH,
                date=parse_date("2025-05-24"),
                time=parse_time("13:00"),
                location="Столовая",
                description="Еженедельный обед команды",
                max_participants=6,
                is_active=True,
                participants=employees,
                tags="lunch, team building"
            )
        ]
        
        # Add activities to session
        session.add_all(activities)
        
        # Commit all changes
        session.commit()
        
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
