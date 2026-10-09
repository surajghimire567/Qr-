from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Category, Product


class CatalogViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # runs once for the whole class; each test is rolled back
        cls.phones = Category.objects.create(name="Phones", slug="phones")
        cls.laptops = Category.objects.create(name="Laptops", slug="laptops")

        cls.redmi = Product.objects.create(
            category=cls.phones, name="Redmi 13", slug="redmi-13",
            price=Decimal("21999.00"), stock=5,
        )
        cls.hidden = Product.objects.create(
            category=cls.phones, name="Old Phone", slug="old-phone",
            price=Decimal("5000.00"), is_active=False,
        )
        cls.mac = Product.objects.create(
            category=cls.laptops, name="MacBook Air", slug="macbook-air",
            price=Decimal("150000.00"), stock=2,
        )

    def test_list_shows_only_active_products(self):
        r = self.client.get(reverse("store:product_list"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Redmi 13")
        self.assertNotContains(r, "Old Phone")

    def test_category_filter(self):
        r = self.client.get(self.phones.get_absolute_url())
        self.assertContains(r, "Redmi 13")
        self.assertNotContains(r, "MacBook Air")

    def test_unknown_category_is_404(self):
        r = self.client.get(
            reverse("store:product_list_by_category", args=["nope"])
        )
        self.assertEqual(r.status_code, 404)

    def test_detail_page(self):
        r = self.client.get(self.redmi.get_absolute_url())
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "store/product_detail.html")
        self.assertContains(r, "21999.00")

    def test_inactive_product_detail_is_404(self):
        r = self.client.get(reverse("store:product_detail", args=["old-phone"]))
        self.assertEqual(r.status_code, 404)

    def test_list_query_count(self):
        # select_related keeps this flat (no N+1)
        with self.assertNumQueries(2):  # 1 categories + 1 products JOIN category
            self.client.get(reverse("store:product_list"))