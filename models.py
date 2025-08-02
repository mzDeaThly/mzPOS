# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser

# 1. ระบบ Login เพื่อแบ่งของแต่ละร้านค้า
class Shop(models.Model):
    name = models.CharField(max_length=100)
    promptpay_phone = models.CharField(max_length=10, blank=True, null=True)
    promptpay_id_card = models.CharField(max_length=13, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class CustomUser(AbstractUser):
    # เชื่อม User กับร้านค้า ทำให้รู้ว่าใครเป็นเจ้าของร้านไหน
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, null=True, blank=True)

# 2, 3, 4. รายการอาหาร, รูปภาพ, และการจัดการ (เพิ่ม/ลบ/แก้ไข ผ่าน Django Admin ได้ทันที)
class MenuCategory(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.shop.name})"

class MenuItem(models.Model):
    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # 3. เพิ่มระบบรูปภาพ
    image = models.ImageField(upload_to='menu_images/', null=True, blank=True)
    # 9. ระบบจัดการสต็อก (เบื้องต้น)
    stock_quantity = models.IntegerField(default=0)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return self.name

# 7. ระบบจัดการออเดอร์และโต๊ะ
class ShopTable(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='tables')
    name = models.CharField(max_length=50) # เช่น "โต๊ะ 1", "A5"
    is_occupied = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='orders')
    table = models.ForeignKey(ShopTable, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Order #{self.id} for {self.shop.name}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2) # ราคา ณ ตอนสั่ง

    def save(self, *args, **kwargs):
        # ดึงราคาปัจจุบันมาใส่ตอนสร้างรายการ
        if not self.id:
            self.unit_price = self.menu_item.price
        super().save(*args, **kwargs)

# 5. ระบบลงทะเบียนรายเดือน/รายปี
class Subscription(models.Model):
    PLAN_CHOICES = [
        ('MONTHLY', 'รายเดือน'),
        ('YEARLY', 'รายปี'),
    ]
    shop = models.OneToOneField(Shop, on_delete=models.CASCADE, related_name='subscription')
    plan = models.CharField(max_length=10, choices=PLAN_CHOICES)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)