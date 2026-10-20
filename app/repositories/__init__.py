"""Repository layer enforcing tenant (student_id) isolation for all database operations."""
import uuid
from typing import List, Optional, Type, TypeVar, Generic
from sqlalchemy import select, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.student import Student
from app.config.logging_config import logger

T = TypeVar("T", bound=Base)


class StudentScopedRepository(Generic[T]):
    """
    Generic repository that enforces student_id scoping on all queries.
    Prevents cross-tenant data access by requiring student_id for all operations.
    """

    def __init__(self, model_class: Type[T], session: AsyncSession):
        self.model_class = model_class
        self.session = session

    def _get_student_id_column(self):
        """Returns the student_id column for the model, or raises if not present."""
        if not hasattr(self.model_class, "student_id"):
            raise ValueError(f"Model {self.model_class.__name__} does not have student_id column")
        return self.model_class.student_id

    async def get_by_id(self, id: uuid.UUID, student_id: uuid.UUID) -> Optional[T]:
        """Gets a single record by ID, scoped to student_id."""
        stmt = select(self.model_class).where(
            and_(
                self.model_class.id == id,
                self._get_student_id_column() == student_id,
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_all(
        self,
        student_id: uuid.UUID,
        limit: Optional[int] = None,
        offset: int = 0,
        order_by: Optional[str] = None,
    ) -> List[T]:
        """Gets all records for a student, with optional pagination and ordering."""
        stmt = select(self.model_class).where(
            self._get_student_id_column() == student_id
        )

        if order_by and hasattr(self.model_class, order_by):
            stmt = stmt.order_by(getattr(self.model_class, order_by))
        elif hasattr(self.model_class, "created_at"):
            stmt = stmt.order_by(self.model_class.created_at.desc())

        if limit:
            stmt = stmt.limit(limit)
        if offset:
            stmt = stmt.offset(offset)

        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def count(self, student_id: uuid.UUID) -> int:
        """Counts records for a student."""
        stmt = select(func.count(self.model_class.id)).where(
            self._get_student_id_column() == student_id
        )
        res = await self.session.execute(stmt)
        return res.scalar() or 0

    async def create(self, student_id: uuid.UUID, **kwargs) -> T:
        """Creates a new record scoped to student_id."""
        obj = self.model_class(student_id=student_id, **kwargs)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def delete(self, id: uuid.UUID, student_id: uuid.UUID) -> bool:
        """Deletes a record by ID, scoped to student_id."""
        stmt = delete(self.model_class).where(
            and_(
                self.model_class.id == id,
                self._get_student_id_column() == student_id,
            )
        )
        res = await self.session.execute(stmt)
        return res.rowcount > 0

    async def delete_all(self, student_id: uuid.UUID) -> int:
        """Deletes all records for a student."""
        stmt = delete(self.model_class).where(
            self._get_student_id_column() == student_id
        )
        res = await self.session.execute(stmt)
        return res.rowcount

    async def exists(self, id: uuid.UUID, student_id: uuid.UUID) -> bool:
        """Checks if a record exists for the given student."""
        stmt = select(func.count(self.model_class.id)).where(
            and_(
                self.model_class.id == id,
                self._get_student_id_column() == student_id,
            )
        )
        res = await self.session.execute(stmt)
        return (res.scalar() or 0) > 0


class StudentRepository:
    """Specialized repository for Student model (uses id instead of student_id)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: uuid.UUID) -> Optional[Student]:
        stmt = select(Student).where(Student.id == id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_phone(self, phone_number: str) -> Optional[Student]:
        stmt = select(Student).where(Student.phone_number == phone_number)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create(self, phone_number: str, **kwargs) -> Student:
        student = Student(phone_number=phone_number, **kwargs)
        self.session.add(student)
        await self.session.flush()
        return student

    async def update(self, id: uuid.UUID, **kwargs) -> Optional[Student]:
        student = await self.get_by_id(id)
        if student:
            for key, value in kwargs.items():
                setattr(student, key, value)
            await self.session.flush()
        return student

    async def delete(self, id: uuid.UUID) -> bool:
        stmt = delete(Student).where(Student.id == id)
        res = await self.session.execute(stmt)
        return res.rowcount > 0