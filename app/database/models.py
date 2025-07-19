from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    phone = Column(String(20))
    is_admin = Column(Boolean, default=False)
    is_moderator = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    short_description = Column(Text)
    full_description = Column(Text)
    date = Column(DateTime, nullable=False)
    location = Column(String(255))
    speakers = Column(Text)  # JSON string
    image_path = Column(String(255))
    registration_required = Column(Boolean, default=True)
    max_participants = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    registrations = relationship("Registration", back_populates="event")

class Registration(Base):
    __tablename__ = "registrations"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_id = Column(Integer, ForeignKey("events.id"))
    registered_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")
    event = relationship("Event", back_populates="registrations")