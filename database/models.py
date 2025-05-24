from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey

Base = declarative_base()

class Portfolio(Base):
    __tablename__ = "portfolios"
    portfolio_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    channel_id = Column(String(50))  # Discord channel_id stored as string

class Task(Base):
    __tablename__ = "tasks"
    task_id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    description = Column(Text)
    status = Column(String(50), default="Not Started")
    priority = Column(String(10), default="Low")
    deadline = Column(TIMESTAMP, nullable=False)
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP)
    portfolio_id = Column(Integer)
    parent_task_id = Column(Integer, ForeignKey('tasks.task_id'))
    source_meeting_id = Column(Integer)
