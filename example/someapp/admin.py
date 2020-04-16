from django.contrib import admin
from access.admin import *

from someapp.models import *

class ChildInline(AccessTabularInline):
    model = SomeChild

# Register your models here.
class ObjectAdmin(AccessModelAdmin):
    inlines = [
        ChildInline,
    ]

# Register your models here.
admin.site.register(SomeObject,ObjectAdmin)

class ChildAdmin(AccessModelAdmin):
    pass

admin.site.register(SomeChild,ChildAdmin)
