from django.contrib import admin
from django.contrib.auth import models
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from access.admin import *

class AccessUserAdmin(AccessControlMixin,UserAdmin):
    list_editable = ['email']

    #def get_readonly_fields(self, request, obj=None):
    #    readonly_fields = super(AccessUserAdmin, self).get_readonly_fields(request, obj) or []
    #    if request.user.is_superuser:
    #        return readonly_fields
    #    if not obj:
    #        return readonly_fields
    #    #if obj.pk != request.user.pk:
    #    #    return self.get_all_model_fields()
    #    return list(set(readonly_fields).union(['is_superuser', 'last_login', 'date_joined']))

    def get_list_display(self, request):
        fields = super(AccessUserAdmin, self).get_list_display(request) or []
        if request.user.is_superuser:
            return fields
        return list(set(fields).difference(['password','email']))

    def _fieldsets_exclude(self,fieldsets,exclude):
        ret = []
        for nm,params in fieldsets:
            if not 'fields' in params:
                ret.append((nm,params))
                continue
            fields = []
            for f in params['fields']:
                if not f in exclude:
                    fields.append(f)
            pars = {}
            pars.update(params)
            pars['fields'] = fields
            ret.append((nm,pars))
        return ret

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super(AccessUserAdmin, self).get_fieldsets(request, obj)) or []
        if request.user.is_superuser:
            return fieldsets
        if not obj:
            return fieldsets
        if obj.pk != request.user.pk:
            return self._fieldsets_exclude(fieldsets,['password', 'email'])
        return self._fieldsets_exclude(fieldsets,['is_superuser'])

class AccessGroupAdmin(AccessControlMixin,GroupAdmin):
    pass

# Register your models here.
admin.site.unregister(models.User)
admin.site.register(models.User,AccessUserAdmin)
admin.site.unregister(models.Group)
admin.site.register(models.Group,AccessGroupAdmin)
