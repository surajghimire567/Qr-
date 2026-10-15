from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending payment"
        PAID = "paid", "Paid"
        FAILED = "failed", "Payment failed"
        CANCELLED = "cancelled", "Cancelled"

    class Gateway(models.TextChoices):
        KHALTI = "khalti", "Khalti"
        ESEWA = "esewa", "eSewa"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    address = models.CharField(max_length=255)
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    # payment_ref is the immutable provider initiation ID (Khalti pidx / eSewa UUID).
    payment_gateway = models.CharField(max_length=10, choices=Gateway.choices, blank=True)
    payment_ref = models.CharField(max_length=100, blank=True)
    gateway_transaction_id = models.CharField(max_length=100, blank=True)
    payment_starting = models.BooleanField(default=False)
    stock_released_at = models.DateTimeField(null=True, blank=True)
    checkout_key = models.UUIDField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(total_amount__gte=Decimal("0.00")),
                name="order_total_nonnegative",
            ),
            models.UniqueConstraint(
                fields=["user", "checkout_key"],
                name="order_checkout_key_user_unique",
            ),
        ]

    def __str__(self):
        return f"Order #{self.pk} ({self.get_status_display()})"

    def calculate_total(self):
        return sum((item.subtotal for item in self.items.all()), Decimal("0.00"))


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "store.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=Decimal("0.00")),
                name="order_item_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name="order_item_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product}"

    @property
    def subtotal(self):
        return self.price * self.quantity
