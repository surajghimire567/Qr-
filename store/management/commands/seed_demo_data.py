from decimal import Decimal

from django.core.management.base import BaseCommand

from store.models import Category, Product


class Command(BaseCommand):
    help = "Create synthetic sample categories and products without overwriting existing rows."

    PRODUCTS = (
        ("demo-keyboard", "Demo Mechanical Keyboard", "accessories", Decimal("3199.00"), 8),
        ("demo-mouse", "Demo Wireless Mouse", "accessories", Decimal("1299.00"), 12),
        ("demo-headphones", "Demo Headphones", "audio", Decimal("2499.00"), 6),
        ("demo-laptop", "Demo Laptop", "computers", Decimal("75000.00"), 3),
    )

    def handle(self, *args, **options):
        categories = {}
        for slug, name in (
            ("accessories", "Accessories"),
            ("audio", "Audio"),
            ("computers", "Computers"),
        ):
            categories[slug], created = Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name},
            )
            state = "created" if created else "already present"
            self.stdout.write(f"Category {name}: {state}")

        for slug, name, category_slug, price, stock in self.PRODUCTS:
            _, created = Product.objects.get_or_create(
                slug=slug,
                defaults={
                    "category": categories[category_slug],
                    "name": name,
                    "description": "Synthetic sample product for a local academic demo.",
                    "price": price,
                    "stock": stock,
                    "image": "",
                    "is_active": True,
                },
            )
            state = "created" if created else "already present"
            self.stdout.write(f"Product {name}: {state}")
