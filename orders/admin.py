from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ("product", "price", "quantity", "subtotal")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "status", "total_amount", "payment_gateway",
        "created_at", "paid_at",
    )
    list_filter = ("status", "payment_gateway", "created_at")
    search_fields = (
        "=id", "user__username", "full_name", "phone", "payment_ref",
        "gateway_transaction_id",
    )
    list_select_related = ("user",)
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-pk")
    readonly_fields = (
        "user", "full_name", "phone", "address", "total_amount", "status",
        "payment_gateway", "payment_ref", "gateway_transaction_id",
        "payment_starting", "stock_released_at", "checkout_key", "paid_at",
        "created_at", "updated_at",
    )
    inlines = (OrderItemInline,)
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
