from django.contrib import admin
from .models import (
    Shop, CustomUser, MenuCategory, MenuItem, ShopTable, 
    Order, OrderItem, Subscription, ShopCustomer
)

admin.site.register(Shop)
admin.site.register(CustomUser)
admin.site.register(MenuCategory)
admin.site.register(MenuItem)
admin.site.register(ShopTable)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(Subscription)
admin.site.register(ShopCustomer)