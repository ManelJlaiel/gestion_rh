from django.contrib import admin
from .models import Holiday, LeaveType
admin.site.register(LeaveType)
admin.site.register(Holiday)
