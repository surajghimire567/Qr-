

from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
class Order(models.Model):
 class Status(models.TextChoices):
  PENDING = "pending", "Pending payment"
  PAID = "paid", "Paid"
  FAILED = "failed", "Payment failed"
  CANCELLED = "cancelled", "Cancelled"
 user = models.ForeignKey(
  settings.AUTH_USER_MODEL,
  on_delete=models.PROTECT, # keep financial records
  related_name="orders", # request.user.orders.all() (Day 6 history page)
 )
 full_name = models.CharField(max_length=150)
 phone = models.CharField(max_length=20)
 address = models.CharField(max_length=255)
 total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
 status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
 # Set on Day 5 ONLY after server-side verification with the gateway
 # (Khalti pidx / eSewa transaction_uuid)
 payment_ref = models.CharField(max_length=100, blank=True)
 paid_at = models.DateTimeField(null=True, blank=True)
 created_at = models.DateTimeField(auto_now_add=True)
 updated_at = models.DateTimeField(auto_now=True)
 class Meta:
  ordering = ["-created_at"]
 def __str__(self):
  return f"Order #{self.pk} ({self.get_status_display()})"
 def calculate_total(self):
  return sum((item.subtotal for item in self.items.all()), Decimal("0.00"))
class OrderItem(models.Model):
 order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
 product = models.ForeignKey(
 "store.Product", on_delete=models.PROTECT, related_name="order_items"
 )
 price = models.DecimalField(max_digits=10, decimal_places=2) # snapshot at purchase
 quantity = models.PositiveIntegerField(
 default=1, validators=[MinValueValidator(1)]
 )
 def __str__(self):
  return f"{self.quantity} x {self.product}"
 @property
 def subtotal(self):
  return self.price * self.quantity
