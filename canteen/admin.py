from django.contrib import admin
from adminpanel.models import MenuItem, OrderItem,Order

admin.site.register(MenuItem)
admin.site.register(Order)
admin.site.register(OrderItem)
