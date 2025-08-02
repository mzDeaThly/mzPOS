from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import datetime

class Shop(models.Model):
    name = models.CharField(max_length=100, unique=True)
    promptpay_phone = models.CharField(max_length=10, blank=True, null=True)
    promptpay_id_card = models.CharField(max_length=13, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name

class CustomUser(AbstractUser):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True)

class MenuCategory(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    def __str__(self): return f"{self.name} ({self.shop.name})"

class MenuItem(models.Model):
    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='menu_images/', null=True, blank=True)
    stock_quantity = models.IntegerField(default=100)
    is_available = models.BooleanField(default=True)
    def __str__(self): return self.name

class ShopTable(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='tables')
    name = models.CharField(max_length=50)
    is_occupied = models.BooleanField(default=False)
    def __str__(self): return self.name

class Order(models.Model):
    STATUS_CHOICES = [('PENDING', 'Pending'), ('COMPLETED', 'Completed'), ('CANCELLED', 'Cancelled')]
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='orders')
    table = models.ForeignKey(ShopTable, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"Order #{self.id} for {self.shop.name}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

class Subscription(models.Model):
    PLAN_CHOICES = [('MONTHLY', 'รายเดือน'), ('YEARLY', 'รายปี')]
    shop = models.OneToOneField(Shop, on_delete=models.CASCADE, related_name='subscription')
    plan = models.CharField(max_length=10, choices=PLAN_CHOICES)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.id: # Set end_date only on creation
            if self.plan == 'MONTHLY':
                self.end_date = timezone.now() + datetime.timedelta(days=30)
            elif self.plan == 'YEARLY':
                self.end_date = timezone.now() + datetime.timedelta(days=365)
        super().save(*args, **kwargs)

class ShopCustomer(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='customers')
    phone_number = models.CharField(max_length=10, blank=True, null=True, unique=True)
    points = models.PositiveIntegerField(default=0)
    def __str__(self): return f"{self.phone_number or 'N/A'} ({self.shop.name})"