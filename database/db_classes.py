from ctypes.wintypes import SHORT
from datetime import datetime

from sqlalchemy import *
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


###################### -------    BASE    ------- ######################


class Base(AsyncAttrs, DeclarativeBase):
    created_at = Column(TIMESTAMP(), nullable=False, default=datetime.now())
    changed_at = Column(TIMESTAMP(), nullable=False, default=datetime.now())


@event.listens_for(Base, 'before_update')
def receive_before_update(mapper, connection, target):
    target.changed_at = datetime.now()


###################### -------    USER    ------- ######################

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    username = Column(String, nullable=False, default="")
    password = Column(String, nullable=False, default="")
    login_type = Column(String, nullable=False, default="")
    game_id = Column(Integer, nullable=False, default=1)
    lang = Column(String, nullable=False, default="idk")
    country = Column(String, nullable=True)
    created_from_ip = Column(String, nullable=True, default=None)
    created_from_device = Column(String, nullable=True, default=None)
    rights = Column(ARRAY(VARCHAR(25)), nullable=False, default=[])


class UserLoginDB(Base):
    __tablename__ = "user_logins"
    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    user_id = Column(Integer, nullable=False, default=0)
    ip_addr = Column(String, nullable=False, default="")
    device_model = Column(String, nullable=True, default="")
    device_vendor = Column(String, nullable=True, default="")
    device_id = Column(String, nullable=True, default="")
    os_version = Column(String, nullable=True, default="")
    platform = Column(String, nullable=True, default="")


###################### -------    SOCIALS    ------- ######################


class TelegramUserDB(Base):
    __tablename__ = "telegram_users"

    id = Column(BIGINT(), primary_key=True, unique=True, nullable=False)

    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    role = Column(String, nullable=False, default='nobody')


class TelegramBindingsDB(Base):
    __tablename__ = "telegram_bindings"

    telegram_id = Column(BIGINT(), primary_key=True, nullable=False)
    game_id = Column(Integer, primary_key=True, nullable=False)
    user_id = Column(Integer, nullable=False)