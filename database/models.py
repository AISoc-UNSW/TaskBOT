from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, Date, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship

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

class MeetingRecord(Base):
    __tablename__ = "meeting_records"
    
    meeting_id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_date = Column(Date, nullable=False)
    meeting_name = Column(String(255), nullable=False)
    recording_file_link = Column(Text, nullable=True)
    auto_caption = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    portfolio_id = Column(Integer, ForeignKey('portfolios.portfolio_id', ondelete='CASCADE'), nullable=False)
    
    portfolio = relationship("Portfolio", back_populates="meeting_records")
