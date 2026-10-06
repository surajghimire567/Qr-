from django.db import models
class Category(models.Model):
 name = models.CharField(max_length=100, unique=True)
 slug=models.SlugField(max_length=100,unique=True)

 class Meta: # model-level options (ordering, names, indexes)
  ordering = ["name"]

 def __str__(self): # how the object prints in admin / shell
  return self.name
 
class Product(models.Model):
 category = models.ForeignKey(
 Category,
 on_delete=models.PROTECT, # can't delete a category that still has products
 related_name="products", # category.products.all()
 )
 name = models.CharField(max_length=200)
 slug = models.SlugField(max_length=220, unique=True)
 description = models.TextField(blank=True)
 price = models.DecimalField(max_digits=10, decimal_places=2)
 stock = models.PositiveIntegerField(default=0)
 image = models.ImageField(upload_to="products/", blank=True)
 is_active = models.BooleanField(default=True)
 created_at = models.DateTimeField(auto_now_add=True)
 updated_at = models.DateTimeField(auto_now=True)
 class Meta:
  ordering = ["-created_at"] # '-' = descending (newest first)
 def __str__(self):
  return self.name
 @property
 def in_stock(self):
  return self.stock > 0
