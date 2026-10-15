from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from orders.models import Order


class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="shopper",
            password="correct-password",
        )

    def test_logout_requires_post(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("logout"))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_logout_post_redirects_and_clears_session(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("store:product_list"))
        self.assertNotIn("_auth_user_id", self.client.session)


class OrderHistoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(username="history-owner", password="test-pass")
        cls.other_user = user_model.objects.create_user(username="history-other", password="test-pass")
        cls.orders = [
            Order.objects.create(
                user=cls.user,
                full_name="History buyer",
                phone="9841234567",
                address="Owner address",
                total_amount="10.00",
            )
            for _ in range(11)
        ]
        Order.objects.create(
            user=cls.other_user,
            full_name="Other buyer",
            phone="9800000000",
            address="Other private address",
            total_amount="99.00",
        )

    def test_history_requires_login(self):
        response = self.client.get(reverse("accounts:order_history"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_history_is_owner_filtered_and_paginated_newest_first(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:order_history"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 11)
        self.assertContains(response, f"#{self.orders[-1].pk}")
        self.assertNotContains(response, "Other private address")
        self.assertContains(response, "Page 1 of 2")

        last_page = self.client.get(reverse("accounts:order_history"), {"page": 2})
        self.assertEqual(list(last_page.context["orders"])[0].pk, self.orders[0].pk)
        self.assertContains(last_page, "Page 2 of 2")

    def test_history_page_boundaries_for_zero_one_ten_and_eleven_orders(self):
        self.client.force_login(self.user)
        for count in (0, 1, 10, 11):
            with self.subTest(count=count):
                Order.objects.filter(user=self.user).delete()
                for number in range(count):
                    Order.objects.create(
                        user=self.user,
                        full_name="Boundary buyer",
                        phone="9841234567",
                        address="Demo address",
                        total_amount="10.00",
                    )
                response = self.client.get(reverse("accounts:order_history"))
                page_obj = response.context["page_obj"]
                self.assertEqual(page_obj.paginator.count, count)
                self.assertEqual(page_obj.paginator.num_pages, 1 if count <= 10 else 2)
                self.assertEqual(len(page_obj.object_list), min(count, 10))
                if count == 0:
                    self.assertContains(response, "Browse products")

    def test_invalid_negative_and_too_large_page_values_are_safe(self):
        self.client.force_login(self.user)
        for page in ("invalid", "-1", "999999"):
            with self.subTest(page=page):
                response = self.client.get(reverse("accounts:order_history"), {"page": page})
                self.assertEqual(response.status_code, 200)
                expected_page = 1 if page == "invalid" else 2
                self.assertEqual(response.context["page_obj"].number, expected_page)


class SeparateAdminSessionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username="store-admin",
            password="admin-pass",
            is_staff=True,
            is_superuser=True,
        )
        self.customer = user_model.objects.create_user(
            username="store-customer",
            password="customer-pass",
        )

    def test_customer_and_admin_sessions_and_post_logouts_are_separate(self):
        admin_login = self.client.post(reverse("admin:login"), {
            "username": "store-admin",
            "password": "admin-pass",
            "next": reverse("admin:index"),
        })
        self.assertEqual(admin_login.status_code, 302)
        self.assertIn("adminsessionid", self.client.cookies)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

        self.client.post(reverse("login"), {
            "username": "store-customer",
            "password": "customer-pass",
        })
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

        self.client.post(reverse("login"), {
            "username": "store-customer",
            "password": "customer-pass",
        })
        admin_logout = self.client.post(reverse("admin:logout"))
        self.assertIn(admin_logout.status_code, {200, 302})
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

    def test_staff_identity_is_logged_out_of_the_storefront(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("store:product_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
