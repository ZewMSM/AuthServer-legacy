from sqlalchemy import select

from database import UserDB, UserLoginDB, Session
from database.base_adapter import BaseAdapter


class User(BaseAdapter):
    _db_model = UserDB

    username: str = ''
    password: str = ''
    login_type: str = ''
    game_id: int = -1
    lang: str = 'en'
    country: str = None
    created_from_ip: str = None
    created_from_device: str = None
    rights: list[str] = []

    @staticmethod
    async def load_by_game_and_username(username: str, game_id: int) -> 'User':
        async with Session() as session:
            db_instances = (await session.execute(select(UserDB).where(UserDB.game_id == game_id).where(UserDB.username == username))).scalars()
            for db_instance in db_instances:
                return await User.from_db_instance(db_instance)

    async def add_login(self, ip_addr, model, vendor, os, devid, platform):
        async with UserLogin() as login:
            login.user = self
            login.ip_addr = ip_addr
            login.device_model = model
            login.device_vendor = vendor
            login.os_version = os
            login.device_id = devid
            login.platform = platform
        return login


class UserLogin(BaseAdapter):
    _db_model = UserLoginDB

    user_id: int
    ip_addr: str
    device_model: str
    device_vendor: str
    device_id: str
    os_version: str
    platform: str

    user: 'User'

    async def on_load_complete(self):
        self.user = await User.load_by_id(self.user_id)

    async def before_save(self):
        if self.user is not None:
            self.user_id = self.user.id
