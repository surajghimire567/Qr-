import base64
import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from orders.models import Order
from orders.services import LifecycleError, release_unpaid

from . import gateways as gw
from .services import claim_payment_start, mark_paid, record_payment_reference


class PaymentServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="pay-buyer", password="test-pass")
        self.order = Order.objects.create(
            user=self.user,
            full_name="Demo Buyer",
            phone="9841234567",
            address="Demo address",
            total_amount=Decimal("100.00"),
        )

    def test_payment_start_claim_is_single_and_reference_is_recorded_once(self):
        claim_payment_start(self.order.pk, owner_id=self.user.pk, gateway=Order.Gateway.KHALTI)
        with self.assertRaises(LifecycleError):
            claim_payment_start(self.order.pk, owner_id=self.user.pk, gateway=Order.Gateway.ESEWA)
        record_payment_reference(
            self.order.pk,
            gateway=Order.Gateway.KHALTI,
            reference="pidx-demo",
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_ref, "pidx-demo")
        self.assertEqual(self.order.payment_gateway, Order.Gateway.KHALTI)
        self.assertFalse(self.order.payment_starting)

        with self.assertRaises(LifecycleError):
            record_payment_reference(
                self.order.pk,
                gateway=Order.Gateway.KHALTI,
                reference="replacement-pidx",
            )

    def test_mark_paid_preserves_initiation_reference_and_is_idempotent(self):
        self.order.payment_gateway = Order.Gateway.KHALTI
        self.order.payment_ref = "pidx-demo"
        self.order.save(update_fields=["payment_gateway", "payment_ref"])
        paid = mark_paid(
            self.order.pk,
            expected_ref="pidx-demo",
            gateway=Order.Gateway.KHALTI,
            receipt="receipt-demo",
        )
        paid_at = paid.paid_at
        repeated = mark_paid(
            self.order.pk,
            expected_ref="pidx-demo",
            gateway=Order.Gateway.KHALTI,
            receipt="receipt-demo",
        )
        self.assertEqual(repeated.status, Order.Status.PAID)
        self.assertEqual(repeated.payment_ref, "pidx-demo")
        self.assertEqual(repeated.gateway_transaction_id, "receipt-demo")
        self.assertEqual(repeated.paid_at, paid_at)

    def test_conflicting_receipt_and_paid_after_release_are_rejected(self):
        self.order.payment_gateway = Order.Gateway.KHALTI
        self.order.payment_ref = "pidx-demo"
        self.order.save(update_fields=["payment_gateway", "payment_ref"])
        mark_paid(
            self.order.pk,
            expected_ref="pidx-demo",
            gateway=Order.Gateway.KHALTI,
            receipt="receipt-demo",
        )
        with self.assertRaises(LifecycleError):
            mark_paid(
                self.order.pk,
                expected_ref="pidx-demo",
                gateway=Order.Gateway.KHALTI,
                receipt="different-receipt",
            )

        unpaid = Order.objects.create(
            user=self.user,
            full_name="Demo Buyer",
            phone="9841234567",
            address="Demo address",
            total_amount=Decimal("50.00"),
            payment_gateway=Order.Gateway.KHALTI,
            payment_ref="pidx-closed",
        )
        release_unpaid(
            unpaid.pk,
            expected_ref="pidx-closed",
            terminal=Order.Status.FAILED,
        )
        with self.assertRaises(LifecycleError):
            mark_paid(
                unpaid.pk,
                expected_ref="pidx-closed",
                gateway=Order.Gateway.KHALTI,
                receipt="late-receipt",
            )


class KhaltiReturnTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="khalti-buyer", password="test-pass")
        self.order = Order.objects.create(
            user=self.user,
            full_name="Buyer",
            phone="9841234567",
            address="Demo",
            total_amount=Decimal("100.00"),
            payment_gateway=Order.Gateway.KHALTI,
            payment_ref="pidx-demo",
        )
        self.client.force_login(self.user)
        self.url = reverse("payments:khalti_return")

    @patch("payments.gateways.khalti_lookup")
    def test_verified_success_and_repeat_keep_original_reference(self, lookup):
        lookup.return_value = {
            "pidx": "pidx-demo",
            "status": "Completed",
            "total_amount": 10000,
            "transaction_id": "receipt-demo",
        }
        self.client.get(self.url, {"pidx": "pidx-demo"})
        self.order.refresh_from_db()
        paid_at = self.order.paid_at
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(self.order.payment_ref, "pidx-demo")
        self.assertEqual(self.order.gateway_transaction_id, "receipt-demo")

        response = self.client.get(self.url, {"pidx": "pidx-demo"})
        self.order.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.order.paid_at, paid_at)
        self.assertEqual(lookup.call_count, 1)

    @patch("payments.gateways.khalti_lookup")
    def test_forged_callback_status_does_not_mark_pending_lookup_paid(self, lookup):
        lookup.return_value = {
            "pidx": "pidx-demo",
            "status": "Pending",
            "total_amount": 10000,
            "transaction_id": None,
        }
        self.client.get(self.url, {"pidx": "pidx-demo", "status": "Completed"})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)
        self.assertEqual(self.order.payment_ref, "pidx-demo")

    @patch("payments.gateways.khalti_lookup")
    def test_wrong_pidx_or_amount_never_marks_paid(self, lookup):
        for payload in (
            {"pidx": "another", "total_amount": 10000},
            {"pidx": "pidx-demo", "total_amount": 9999},
        ):
            with self.subTest(payload=payload):
                self.order.status = Order.Status.PENDING
                self.order.save(update_fields=["status"])
                lookup.return_value = {
                    **payload,
                    "status": "Completed",
                    "transaction_id": "receipt-demo",
                }
                self.client.get(self.url, {"pidx": "pidx-demo"})
                self.order.refresh_from_db()
                self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_foreign_reference_is_not_visible(self):
        other = get_user_model().objects.create_user(username="other-khalti", password="test-pass")
        foreign_order = Order.objects.create(
            user=other,
            full_name="Other",
            phone="9800000000",
            address="Private",
            total_amount=Decimal("10.00"),
            payment_gateway=Order.Gateway.KHALTI,
            payment_ref="other-pidx",
        )
        response = self.client.get(self.url, {"pidx": foreign_order.payment_ref})
        self.assertEqual(response.status_code, 404)


class EsewaSafetyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="esewa-buyer", password="test-pass")
        self.order = Order.objects.create(
            user=self.user,
            full_name="Buyer",
            phone="9841234567",
            address="Demo",
            total_amount=Decimal("100.00"),
            payment_gateway=Order.Gateway.ESEWA,
            payment_ref="1-demo-uuid",
        )
        self.client.force_login(self.user)

    def signed_callback(self, status="COMPLETE", total_amount=100.0, fields=None):
        names = fields or (
            "transaction_code,status,total_amount,transaction_uuid,product_code,signed_field_names"
        )
        payload = {
            "transaction_code": "tx-demo",
            "status": status,
            "total_amount": total_amount,
            "transaction_uuid": "1-demo-uuid",
            "product_code": "EPAYTEST",
            "signed_field_names": names,
        }
        message = ",".join(f"{name}={payload[name]}" for name in names.split(","))
        payload["signature"] = gw.esewa_sign(message)
        return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")

    @patch("payments.gateways.esewa_status")
    def test_signed_success_and_server_status_are_both_required(self, status):
        status.return_value = {
            "status": "COMPLETE",
            "transaction_uuid": "1-demo-uuid",
            "product_code": "EPAYTEST",
            "total_amount": 100.0,
            "ref_id": "receipt-esewa",
        }
        response = self.client.get(reverse("payments:esewa_success"), {
            "data": self.signed_callback(),
        })
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(self.order.payment_ref, "1-demo-uuid")
        self.assertEqual(self.order.gateway_transaction_id, "receipt-esewa")

    def test_bad_signed_field_list_and_bad_base64_are_rejected(self):
        for data in ("not-base64!", self.signed_callback(fields="status")):
            with self.subTest(data=data[:20]):
                with self.assertRaises(gw.GatewayError):
                    gw.esewa_decode_and_verify(data)

    def test_nonfinite_or_negative_amounts_are_rejected(self):
        for value in ("NaN", "Infinity", "-1", "invalid"):
            with self.subTest(value=value):
                self.assertIsNone(gw.parse_amount(value))

    def test_failure_redirect_keeps_order_pending(self):
        response = self.client.get(reverse("payments:esewa_failure", args=[self.order.pk]))
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)
        self.assertIsNone(self.order.stock_released_at)

    def test_status_check_is_post_only(self):
        url = reverse("payments:check_payment", args=[self.order.pk])
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_status_check_requires_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        response = csrf_client.post(reverse("payments:check_payment", args=[self.order.pk]))
        self.assertEqual(response.status_code, 403)

    @patch("payments.services.gw.esewa_status")
    def test_not_found_status_stays_pending_for_manual_reconciliation(self, status):
        status.return_value = {
            "status": "NOT_FOUND",
            "transaction_uuid": "1-demo-uuid",
            "product_code": "EPAYTEST",
            "total_amount": 100.0,
            "ref_id": None,
        }
        response = self.client.post(reverse("payments:check_payment", args=[self.order.pk]))
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)
        self.assertIsNone(self.order.stock_released_at)


class PaymentStartViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="start-buyer", password="test-pass")
        self.order = Order.objects.create(
            user=self.user,
            full_name="Buyer",
            phone="9841234567",
            address="Demo",
            total_amount=Decimal("100.00"),
        )
        self.client.force_login(self.user)

    @override_settings(KHALTI_SECRET_KEY="sandbox-key")
    @patch("payments.views.gw.khalti_initiate")
    def test_khalti_start_records_reference_and_blocks_a_second_start(self, initiate):
        initiate.return_value = {
            "pidx": "pidx-start",
            "payment_url": "https://pay.khalti.com/demo",
        }
        url = reverse("payments:khalti_start", args=[self.order.pk])
        first = self.client.post(url)
        self.order.refresh_from_db()
        self.assertEqual(first.status_code, 302)
        self.assertEqual(first["Location"], "https://pay.khalti.com/demo")
        self.assertEqual(self.order.payment_ref, "pidx-start")
        self.assertEqual(self.order.payment_gateway, Order.Gateway.KHALTI)
        self.assertFalse(self.order.payment_starting)

        second = self.client.post(url)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(initiate.call_count, 1)

    @override_settings(KHALTI_SECRET_KEY="sandbox-key")
    @patch("payments.views.gw.khalti_initiate", side_effect=gw.GatewayError("timeout"))
    def test_uncertain_start_freezes_order_for_review(self, initiate):
        response = self.client.post(reverse("payments:khalti_start", args=[self.order.pk]))
        self.order.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.order.payment_starting)
        self.assertEqual(self.order.payment_gateway, Order.Gateway.KHALTI)
        self.assertEqual(self.order.payment_ref, "")
        with self.assertRaises(LifecycleError):
            release_unpaid(self.order.pk, owner_id=self.user.pk)

    @override_settings(ESEWA_PRODUCT_CODE="EPAYTEST", ESEWA_SECRET_KEY="sandbox-key")
    def test_esewa_start_persists_uuid_before_rendering_provider_form(self):
        response = self.client.post(reverse("payments:esewa_start", args=[self.order.pk]))
        self.order.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["fields"]["transaction_uuid"], self.order.payment_ref)
        self.assertTrue(self.order.payment_ref.startswith(f"{self.order.pk}-"))
        self.assertEqual(self.order.payment_gateway, Order.Gateway.ESEWA)
        self.assertFalse(self.order.payment_starting)
