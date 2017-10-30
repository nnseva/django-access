from django.contrib import admin
from access.admin import *

from someapp.models import *

class ChildAdmin(AccessTabularInline):
    model = SomeChild

# Register your models here.
class ObjectAdmin(AccessModelAdmin):
    inlines = [
        ChildAdmin,
    ]

# Register your models here.
admin.site.register(SomeObject,ObjectAdmin)
