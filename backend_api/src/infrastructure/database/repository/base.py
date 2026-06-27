import math
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from sqlalchemy import select, update, delete, func, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.sql.elements import BinaryExpression
from pydantic import BaseModel
from src.infrastructure.database.session import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class PaginationResult(Generic[ModelType]):
    def __init__(self, items: List[ModelType], total: int, page: int, size: int):
        self.items = items
        self.total = total
        self.page = page
        self.size = size
        self.pages = math.ceil(total / size) if size > 0 else 0
        self.has_next = page < self.pages
        self.has_prev = page > 1


class RepositoryException(Exception):
    pass


class EntityNotFoundError(RepositoryException):
    pass


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def _apply_sorting(self, query: Any, sort_by: str, sort_order: str) -> Any:
        if not hasattr(self.model, sort_by):
            return query

        column = getattr(self.model, sort_by)
        if sort_order.lower() == "desc":
            return query.order_by(desc(column))
        return query.order_by(asc(column))

    def _apply_eager_loading(self, query: Any, load_relations: List[str]) -> Any:
        for relation in load_relations:
            if hasattr(self.model, relation):
                query = query.options(selectinload(getattr(self.model, relation)))
        return query

    async def get(
        self, db: AsyncSession, id: Any, load_relations: Optional[List[str]] = None
    ) -> Optional[ModelType]:
        query = select(self.model).where(self.model.id == id)

        if hasattr(self.model, "is_deleted"):
            query = query.where(self.model.is_deleted == False)

        if load_relations:
            query = self._apply_eager_loading(query, load_relations)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_or_fail(
        self, db: AsyncSession, id: Any, load_relations: Optional[List[str]] = None
    ) -> ModelType:
        entity = await self.get(db, id, load_relations)
        if not entity:
            raise EntityNotFoundError(f"{self.model.__name__} with id {id} not found")
        return entity

    async def get_by_field(
        self,
        db: AsyncSession,
        field_name: str,
        value: Any,
        load_relations: Optional[List[str]] = None,
    ) -> Optional[ModelType]:
        if not hasattr(self.model, field_name):
            raise ValueError(
                f"Field {field_name} does not exist on {self.model.__name__}"
            )

        query = select(self.model).where(getattr(self.model, field_name) == value)

        if hasattr(self.model, "is_deleted"):
            query = query.where(self.model.is_deleted == False)

        if load_relations:
            query = self._apply_eager_loading(query, load_relations)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[List[BinaryExpression]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        load_relations: Optional[List[str]] = None,
    ) -> List[ModelType]:
        query = select(self.model)

        if hasattr(self.model, "is_deleted"):
            query = query.where(self.model.is_deleted == False)

        if filters:
            for condition in filters:
                query = query.where(condition)

        if sort_by:
            query = self._apply_sorting(query, sort_by, sort_order)

        if load_relations:
            query = self._apply_eager_loading(query, load_relations)

        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_paginated(
        self,
        db: AsyncSession,
        page: int = 1,
        size: int = 50,
        filters: Optional[List[BinaryExpression]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        load_relations: Optional[List[str]] = None,
    ) -> PaginationResult[ModelType]:
        count_query = select(func.count()).select_from(self.model)
        if hasattr(self.model, "is_deleted"):
            count_query = count_query.where(self.model.is_deleted == False)
        if filters:
            for condition in filters:
                count_query = count_query.where(condition)

        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        skip = (page - 1) * size
        items = await self.get_multi(
            db,
            skip=skip,
            limit=size,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            load_relations=load_relations,
        )

        return PaginationResult(items=items, total=total, page=page, size=size)

    async def create(
        self, db: AsyncSession, *, obj_in: Union[CreateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        obj_in_data = (
            obj_in.model_dump(exclude_unset=True)
            if isinstance(obj_in, BaseModel)
            else obj_in
        )
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def bulk_create(
        self,
        db: AsyncSession,
        *,
        objs_in: List[Union[CreateSchemaType, Dict[str, Any]]],
    ) -> List[ModelType]:
        db_objs = []
        for obj_in in objs_in:
            obj_in_data = (
                obj_in.model_dump(exclude_unset=True)
                if isinstance(obj_in, BaseModel)
                else obj_in
            )
            db_objs.append(self.model(**obj_in_data))

        db.add_all(db_objs)
        await db.flush()
        return db_objs

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]],
    ) -> ModelType:
        obj_data = {c.name: getattr(db_obj, c.name) for c in db_obj.__table__.columns}

        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])

        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def delete(
        self, db: AsyncSession, *, id: Any, hard_delete: bool = False
    ) -> ModelType:
        obj = await self.get_or_fail(db, id)

        if not hard_delete and hasattr(obj, "soft_delete"):
            obj.soft_delete()
            db.add(obj)
        else:
            await db.delete(obj)

        await db.flush()
        return obj

    async def count(
        self, db: AsyncSession, filters: Optional[List[BinaryExpression]] = None
    ) -> int:
        query = select(func.count()).select_from(self.model)

        if hasattr(self.model, "is_deleted"):
            query = query.where(self.model.is_deleted == False)

        if filters:
            for condition in filters:
                query = query.where(condition)

        result = await db.execute(query)
        return result.scalar_one()

    async def exists(self, db: AsyncSession, filters: List[BinaryExpression]) -> bool:
        count_val = await self.count(db, filters)
        return count_val > 0
