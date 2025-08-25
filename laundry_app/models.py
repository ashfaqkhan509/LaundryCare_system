import enum
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import (
    Integer, String, DateTime, ForeignKey,
    Numeric, Enum, CheckConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from laundry_app import db


class UserRole(enum.Enum):
    CUSTOMER = "customer"
    WORKER = "worker"
    ADMIN = "admin"


class OrderStatus(enum.Enum):
    CREATED = "created"
    ACCEPTED = "accepted"
    PICKED_UP = "picked_up"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    worker_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # relationships
    worker: Mapped["User"] = relationship(
        "User",
        remote_side=[id],
        back_populates="customers",
        foreign_keys=[worker_id],
    )
    customers: Mapped[list["User"]] = relationship(
        "User",
        back_populates="worker",
        foreign_keys="User.worker_id",
    )

    addresses: Mapped[list["Address"]] = relationship(back_populates="user")
    customer_orders: Mapped[list["Order"]] = relationship(
        back_populates="customer", foreign_keys="Order.customer_id"
    )
    worker_orders: Mapped[list["Order"]] = relationship(
        back_populates="worker", foreign_keys="Order.worker_id"
    )
    created_orders: Mapped[list["Order"]] = relationship(
        back_populates="creator", foreign_keys="Order.created_by"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self, include_worker=False, include_customers=False):
        data = {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "role": self.role.value if self.role else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
        if include_worker and self.worker:
            data["worker"] = {
                "id": self.worker.id,
                "name": self.worker.name,
                "email": self.worker.email
            }
        if include_customers:
            data["customers"] = [
                {"id": c.id, "name": c.name, "email": c.email} for c in self.customers
            ]
        return data


class Address(db.Model):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    street: Mapped[str] = mapped_column(String)
    area: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String, nullable=False, default="Lahore")
    postal_code: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint("city = 'Lahore'", name="check_city_lahore"),
    )

    user: Mapped["User"] = relationship(back_populates="addresses")
    orders: Mapped[list["Order"]] = relationship(back_populates="address")

    def to_dict(self):
        return {
            "id": self.id,
            "street": self.street,
            "area": self.area,
            "city": self.city,
            "postal_code": self.postal_code,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Order(db.Model):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    worker_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    address_id: Mapped[int] = mapped_column(ForeignKey("addresses.id"), nullable=False)

    total_price: Mapped[float] = mapped_column(Numeric)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.CREATED)
    pickup_time: Mapped[datetime] = mapped_column(DateTime)
    delivery_time: Mapped[datetime] = mapped_column(DateTime)
    cancellation_fee: Mapped[float] = mapped_column(Numeric, default=0.00)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    customer: Mapped["User"] = relationship(back_populates="customer_orders", foreign_keys=[customer_id])
    worker: Mapped["User"] = relationship(back_populates="worker_orders", foreign_keys=[worker_id])
    creator: Mapped["User"] = relationship(back_populates="created_orders", foreign_keys=[created_by])
    address: Mapped["Address"] = relationship(back_populates="orders")

    def to_dict(self):
        return {
            "id": self.id,
            "total_price": float(self.total_price) if self.total_price else 0.0,
            "status": self.status.value if self.status else None,
            "pickup_time": self.pickup_time.isoformat() if self.pickup_time else None,
            "delivery_time": self.delivery_time.isoformat() if self.delivery_time else None,
            "cancellation_fee": float(self.cancellation_fee) if self.cancellation_fee else 0.0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "customer": self.customer.to_dict() if self.customer else None,
            "worker": self.worker.to_dict() if self.worker else None,
            "creator": self.creator.to_dict() if self.creator else None,
            "address": self.address.to_dict() if self.address else None,
        }


class TokenBlocklist(db.Model):
    __tablename__ = "token_blocklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jti: Mapped[str] = mapped_column(String, nullable=False, index=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<TokenBlocklist jti={self.jti}>"
