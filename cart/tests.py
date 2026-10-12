from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from store.models import Category, Product


class CartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        phones = Category.objects.create(name="Phones", slug="phones")
        cls.redmi = Product.objects.create(
            category=phones,
            name="Redmi 13",
            slug="redmi-13",
            price=Decimal("21999.00"),
            stock=5,
        )
        cls.case = Product.objects.create(
            category=phones,
            name="Phone Case",
            slug="case",
            price=Decimal("499.50"),
            stock=10,
        )
        cls.sold_out = Product.objects.create(
            category=phones,
            name="Sold Out",
            slug="sold-out",
            price=Decimal("100.00"),
            stock=0,
        )
        cls.hidden = Product.objects.create(
            category=phones,
            name="Hidden",
            slug="hidden",
            price=Decimal("100.00"),
            stock=5,
            is_active=False,
        )

    def add(self, product, qty=1, override=False):
        data = {"quantity": qty}
        if override:
            data["override"] = "on"
        return self.client.post(reverse("cart:cart_add", args=[product.id]), data)

    def session_qty(self, product):
        return self.client.session.get("cart", {}).get(str(product.id), {}).get("quantity")

    def test_empty_cart_page(self):
        response = self.client.get(reverse("cart:cart_detail"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your cart is empty")
        self.assertNotIn("cart", self.client.session)  # Nothing written yet.

    def test_add_stores_id_and_quantity_only(self):
        response = self.add(self.redmi, 2)
        self.assertRedirects(response, reverse("cart:cart_detail"))
        self.assertEqual(self.client.session["cart"], {str(self.redmi.id): {"quantity": 2}})

    def test_add_twice_accumulates_and_override_replaces(self):
        self.add(self.redmi, 1)
        self.add(self.redmi, 2)
        self.assertEqual(self.session_qty(self.redmi), 3)
        self.add(self.redmi, 1, override=True)
        self.assertEqual(self.session_qty(self.redmi), 1)

    def test_quantity_capped_at_stock(self):
        self.add(self.redmi, 9)  # Stock is 5.
        self.assertEqual(self.session_qty(self.redmi), 5)

    def test_invalid_quantity_rejected(self):
        for bad_quantity in (0, -1, 21, "abc"):
            self.add(self.case, bad_quantity)
            self.assertIsNone(self.session_qty(self.case))

    def test_out_of_stock_and_inactive_not_added(self):
        self.add(self.sold_out)
        self.assertIsNone(self.session_qty(self.sold_out))
        response = self.add(self.hidden)
        self.assertEqual(response.status_code, 404)

    def test_get_cannot_change_cart(self):
        response = self.client.get(reverse("cart:cart_add", args=[self.redmi.id]))
        self.assertEqual(response.status_code, 405)

    def test_remove(self):
        self.add(self.redmi, 2)
        self.client.post(reverse("cart:cart_remove", args=[self.redmi.id]))
        self.assertIsNone(self.session_qty(self.redmi))

    def test_totals_use_database_price(self):
        self.add(self.redmi, 2)
        self.add(self.case, 3)
        response = self.client.get(reverse("cart:cart_detail"))
        self.assertEqual(response.context["total"], Decimal("45496.50"))  # 2*21999 + 3*499.50
        self.assertContains(response, "Cart (5)")  # Context processor.

    def test_deactivated_product_pruned_from_cart(self):
        self.add(self.case, 1)
        Product.objects.filter(pk=self.case.pk).update(is_active=False)
        response = self.client.get(reverse("cart:cart_detail"))
        self.assertContains(response, "Your cart is empty")
        self.assertIsNone(self.session_qty(self.case))

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            reverse("cart:cart_add", args=[self.redmi.id]),
            {"quantity": 1},
        )
        self.assertEqual(response.status_code, 403)
