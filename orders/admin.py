from django.contrib import admin
from .models import Order, OrderItem
class OrderItemInline(admin.TabularInline): # edit items inside the order page
 model = OrderItem
 extra = 0
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
 list_display = ["id", "user", "status", "total_amount", "created_at"]
 list_filter = ["status"]
 lines = [OrderItemInline]