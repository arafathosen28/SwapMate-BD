from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    username = Column(String, nullable=True)
    send_type = Column(String)
    receive_type = Column(String)
    send_amount = Column(Float)
    fee = Column(Float, default=0.0)
    receive_amount = Column(Float)
    receive_address = Column(String)
    payment_to = Column(String, nullable=True)  # e.g. personal number
    status = Column(String, default="Pending")  # Pending, Completed, Rejected
    admin_note = Column(Text, nullable=True)
    tx_id = Column(String, nullable=True)
    proof_file_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
