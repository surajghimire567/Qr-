import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.admin.sites import AdminSite
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from cart.cart import Cart
from store.models import Category, Product

from .forms import CheckoutForm
from .admin import OrderAdmin, OrderItemInline
from .models import Order, OrderItem
from .services import (
    LifecycleError,
    OutOfStock,
    create_order_from_cart,
    release_unpaid,
)


class OrderServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="buyer", password="test-pass")
        category = Category.objects.create(name="Demo", slug="demo")
        cls.product = Product.objects.create(
            category=category,
            name="Demo product",
            slug="demo-product",
            price=Decimal("100.00"),
            stock=5,
        )

    def make_cart(self, quantity=2):
        request = RequestFactory().get("/")
        SessionMiddleware(lambda request: None).process_request(request)
        request.session.save()
        request.user = self.user
        cart = Cart(request)
        cart.add(self.product, quantity=quantity)
        return cart

    def make_form(self, key=None):
        form = CheckoutForm(data={
            "full_name": "Demo Buyer",
            "phone": "9841234567",
            "address": "Demo address",
            "checkout_key": str(key or uuid.uuid4()),
        })
        self.assertTrue(form.is_valid(), form.errors)
        return form

    def test_checkout_reserves_stock_and_snapshots_price(self):
        key = uuid.uuid4()
        order = create_order_from_cart(
            user=self.user,
            cart=self.make_cart(),
            form=self.make_form(key),
            checkout_key=key,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(order.total_amount, Decimal("200.00"))
        self.assertEqual(order.items.get().price, Decimal("100.00"))

        Product.objects.filter(pk=self.product.pk).update(price=Decimal("150.00"))
        self.assertEqual(order.items.get().subtotal, Decimal("200.00"))

    def test_duplicate_checkout_key_returns_the_original_order(self):
        key = uuid.uuid4()
        order = create_order_from_cart(
            user=self.user,
            cart=self.make_cart(),
            form=self.make_form(key),
            checkout_key=key,
        )
        repeated = create_order_from_cart(
            user=self.user,
            cart=self.make_cart(),
            form=self.make_form(key),
            checkout_key=key,
        )
        self.product.refresh_from_db()
        self.assertEqual(repeated.pk, order.pk)
        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)
        self.assertEqual(self.product.stock, 3)

    def test_insufficient_stock_rolls_back_order_and_items(self):
        cart = self.make_cart(quantity=2)
        Product.objects.filter(pk=self.product.pk).update(stock=1)
        with self.assertRaises(OutOfStock):
            create_order_from_cart(
                user=self.user,
                cart=cart,
                form=self.make_form(),
                checkout_key=uuid.uuid4(),
            )
        self.assertFalse(Order.objects.filter(user=self.user).exists())
        self.assertFalse(OrderItem.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)

    def test_release_unpaid_restocks_exactly_once(self):
        key = uuid.uuid4()
        order = create_order_from_cart(
            user=self.user,
            cart=self.make_cart(),
            form=self.make_form(key),
            checkout_key=key,
        )
        release_unpaid(order.pk, owner_id=self.user.pk)
        release_unpaid(order.pk, owner_id=self.user.pk)
        self.product.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertIsNotNone(order.stock_released_at)

    def test_paid_order_cannot_release_stock(self):
        order = Order.objects.create(
            user=self.user,
            full_name="Demo Buyer",
            phone="9841234567",
            address="Demo address",
            total_amount=Decimal("100.00"),
            status=Order.Status.PAID,
        )
        OrderItem.objects.create(order=order, product=self.product, price=Decimal("100.00"), quantity=1)
        with self.assertRaises(LifecycleError):
            release_unpaid(order.pk, owner_id=self.user.pk)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_started_payment_cannot_be_cancelled(self):
        order = Order.objects.create(
            user=self.user,
            full_name="Demo Buyer",
            phone="9841234567",
            address="Demo address",
            total_amount=Decimal("100.00"),
            payment_gateway=Order.Gateway.ESEWA,
            payment_starting=True,
        )
        OrderItem.objects.create(order=order, product=self.product, price=Decimal("100.00"), quantity=1)
        with self.assertRaises(LifecycleError):
            release_unpaid(order.pk, owner_id=self.user.pk)


class CheckoutAndOwnershipViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="buyer", password="test-pass")
        cls.other_user = get_user_model().objects.create_user(username="other", password="test-pass")
        category = Category.objects.create(name="Checkout", slug="checkout")
        cls.product = Product.objects.create(
            category=category,
            name="Checkout item",
            slug="checkout-item",
            price=Decimal("250.00"),
            stock=4,
        )
        cls.order = Order.objects.create(
            user=cls.user,
            full_name="Demo Buyer",
            phone="9841234567",
            address="Private demo address",
            total_amount=Decimal("250.00"),
        )

    def test_checkout_post_is_idempotent_for_the_session_key(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): {"quantity": 2}}
        session.save()
        checkout_url = reverse("orders:checkout")
        page = self.client.get(checkout_url)
        key = str(page.context["form"]["checkout_key"].value())
        data = {
            "full_name": "Demo Buyer",
            "phone": "9841234567",
            "address": "Demo address",
            "checkout_key": key,
        }

        first = self.client.post(checkout_url, data)
        second = self.client.post(checkout_url, data)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Order.objects.filter(user=self.user).count(), 2)  # one setup order + one checkout
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)

    def test_stale_cart_during_checkout_is_a_redirect_not_a_server_error(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {str(self.product.pk): {"quantity": 1}}
        session.save()
        checkout_url = reverse("orders:checkout")
        page = self.client.get(checkout_url)
        key = str(page.context["form"]["checkout_key"].value())
        Product.objects.filter(pk=self.product.pk).update(is_active=False)
        response = self.client.post(checkout_url, {
            "full_name": "Demo Buyer",
            "phone": "9841234567",
            "address": "Demo address",
            "checkout_key": key,
        })
        self.assertRedirects(response, reverse("cart:cart_detail"))
        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)

    def test_order_detail_is_private_and_anonymous_checkout_redirects(self):
        response = self.client.get(reverse("orders:order_detail", args=[self.order.pk]))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('orders:order_detail', args=[self.order.pk])}",
        )
        self.client.force_login(self.other_user)
        response = self.client.get(reverse("orders:order_detail", args=[self.order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_cancel_requires_post_and_csrf(self):
        self.client.force_login(self.user)
        cancel_url = reverse("orders:cancel_order", args=[self.order.pk])
        self.assertEqual(self.client.get(cancel_url).status_code, 405)

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(cancel_url).status_code, 403)

    def test_order_can_only_be_cancelled_by_its_owner(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse("orders:cancel_order", args=[self.order.pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 404)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)


class OrderAdminSafetyTests(TestCase):
    def test_financial_order_and_item_records_are_read_only(self):
        request = RequestFactory().get("/admin/")
        order_admin = OrderAdmin(Order, AdminSite())
        self.assertFalse(order_admin.has_add_permission(request))
        self.assertFalse(order_admin.has_delete_permission(request))
        self.assertIn("status", order_admin.readonly_fields)
        self.assertIn("total_amount", order_admin.readonly_fields)
        self.assertIn("payment_ref", order_admin.readonly_fields)

        item_inline = OrderItemInline(Order, AdminSite())
        self.assertFalse(item_inline.has_add_permission(request))
        self.assertFalse(item_inline.has_change_permission(request))
        self.assertFalse(item_inline.can_delete)
