import asyncio
import pickle
from datetime import datetime
from typing import TypeVar, Type, List

from sqlalchemy import select

from . import Session, Base, RedisSession

T = TypeVar('T', bound='BaseAdapter')


class BaseAdapterMeta(type):
    def __new__(mcs, name, bases, dct):
        cls = super().__new__(mcs, name, bases, dct)
        cls._db_model = dct.get('_db_model')
        return cls


class BaseAdapter(metaclass=BaseAdapterMeta):
    _db_model: Type[Base]
    _enable_caching: bool = True

    id: int = None

    created_at: datetime = datetime.now()
    changed_at: datetime = datetime.now()

    async def save(self):
        await self.before_save()
        self.changed_at = datetime.now()

        async with Session() as session:
            db_instance = await session.get(self._db_model, self.id)

            if db_instance is None:
                db_instance = self._db_model()
                session.add(db_instance)

            for field, value in self.to_dict().items():
                setattr(db_instance, field, value)

            await session.flush()
            await session.refresh(db_instance)
            self.id = db_instance.id

            await self.after_save()
            await session.commit()

        if self._enable_caching:
            asyncio.create_task(RedisSession.hset(f"{self._db_model.__tablename__}_db", str(self.id), pickle.dumps(self.to_dict())))

    @classmethod
    async def load_by_id(cls: Type[T], id: int) -> T:  # match_type: ignore
        if cls._enable_caching and (params := await RedisSession.hget(f"{cls._db_model.__tablename__}_db", str(id))) is not None:
            return await cls.from_dict(pickle.loads(params))
        async with Session() as session:
            db_instance = await session.get(cls._db_model, id)
            if db_instance:
                return await cls.from_db_instance(db_instance)

        assert Exception('Object is not exists.')

    @classmethod
    async def load_one_by(cls: Type[T], query_class, query) -> T:  # match_type: ignore
        async with Session() as session:
            db_instance = (await session.execute(select(cls._db_model).where(query_class == query))).scalar_one_or_none()
            if db_instance:
                return await cls.from_db_instance(db_instance)

        assert Exception('Object is not exists.')

    @classmethod
    async def load_all_by(cls: Type[T], query_class, query) -> List[T]:  # match_type: ignore
        async with Session() as session:
            db_instances = (await session.execute(select(cls._db_model).where(query_class == query))).scalars().all()
            return [await cls.from_db_instance(db_instance) for db_instance in db_instances]

    @classmethod
    async def load_all(cls: Type[T]) -> List[T]:
        if cls._enable_caching and (objects := await RedisSession.hgetall(f"{cls._db_model.__tablename__}_db")) != {}:
            return [await cls.from_dict(pickle.loads(params)) for params in objects.values()]
        async with Session() as session:
            result = await session.execute(select(cls._db_model))
            db_instances = result.scalars().all()
            return [await cls.from_db_instance(db_instance) for db_instance in db_instances]

    @classmethod
    async def from_db_instance(cls: Type[T], db_instance) -> T:
        instance = cls()
        for field in cls._db_model.__table__.columns.keys():
            setattr(instance, field, getattr(db_instance, field))
        await instance.on_load_complete()

        if cls._enable_caching:
            asyncio.create_task(RedisSession.hset(f"{cls._db_model.__tablename__}_db", str(instance.id), pickle.dumps(instance.to_dict())))

        return instance

    def to_dict(self):
        return {field: getattr(self, field) for field in self._db_model.__table__.columns.keys()}

    @classmethod
    async def from_dict(cls: Type[T], params: dict):
        instance = cls()
        for field, value in params.items():
            setattr(instance, field, value)
        await instance.on_load_complete()
        return instance

    async def remove(self):
        async with Session() as session:
            db_instance = await session.get(self._db_model, self.id)
            if db_instance:
                await session.delete(db_instance)
                await session.commit()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self.save()

    def __repr__(self):
        fvars = ', '.join([f'{k}={repr(v)}' for k, v in vars(self).items()])
        return f"{self.__class__.__name__}({fvars})"

    def __str_(self):
        fvars = ', '.join([f'{k}={repr(v)}' for k, v in vars(self).items()])
        return f"{self.__class__.__name__}({fvars})"

    async def on_load_complete(self):
        return

    async def after_save(self):
        return

    async def before_save(self):
        return
