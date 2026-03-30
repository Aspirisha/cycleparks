from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Request(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=False), nullable=False)
    user_id = Column(BigInteger, nullable=False)
    command = Column(Text, nullable=False)


class CommandStat(Base):
    __tablename__ = "command_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    command = Column(Text, nullable=False)
    count = Column(Integer, nullable=False)


class SendFailure(Base):
    __tablename__ = "send_failures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_type = Column(Text, nullable=False)
    error_message = Column(Text, nullable=False)
    count = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class Error(Base):
    __tablename__ = "errors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    exception_type = Column(Text, nullable=False)
    error_message = Column(Text, nullable=False)
    update_str = Column(Text, nullable=False)


class CyclePark(Base):
    __tablename__ = "cycleparks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feature_id = Column(String(50), nullable=False, unique=True)
    svdate = Column(Date, nullable=True)
    prk_carr = Column(Boolean, nullable=False)
    prk_cover = Column(Boolean, nullable=False)
    prk_secure = Column(Boolean, nullable=False)
    prk_locker = Column(Boolean, nullable=False)
    prk_sheff = Column(Boolean, nullable=False)
    prk_mstand = Column(Boolean, nullable=False)
    prk_pstand = Column(Boolean, nullable=False)
    prk_hoop = Column(Boolean, nullable=False)
    prk_post = Column(Boolean, nullable=False)
    prk_buterf = Column(Boolean, nullable=False)
    prk_wheel = Column(Boolean, nullable=False)
    prk_hangar = Column(Boolean, nullable=False)
    prk_tier = Column(Boolean, nullable=False)
    prk_other = Column(Boolean, nullable=False)
    prk_provis = Column(Integer, nullable=True)
    prk_cpt = Column(Integer, nullable=True)
    borough = Column(String(100), nullable=True)
    photo1_url = Column(Text, nullable=True)
    photo2_url = Column(Text, nullable=True)
    longitude = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)


class CycleParkSubmission(Base):
    __tablename__ = "cyclepark_submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    photo1_file_id = Column(Text, nullable=False)
    photo2_file_id = Column(Text, nullable=False)
    status = Column(
        String(20), nullable=False, default="pending"
    )  # pending, approved, rejected
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(BigInteger, nullable=True)
