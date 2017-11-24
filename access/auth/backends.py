from django.contrib.auth.backends import ModelBackend as ModelBackendBase
from django.contrib.auth.models import Permission

from django.apps import apps

from access.managers import AccessManager

import logging
logger = logging.getLogger(__name__)


class FakeRequest(object):
    def __init__(self, backend, user):
        self.user = user


class ModelBackend(ModelBackendBase):
    PERM_ABILITY = {
        "add": "appendable",
        "change": "changeable",
        "delete": "deleteable",
    }

    FakeRequest = FakeRequest

    def get_model(self, app_label, model_name):
        return apps.get_model(app_label, model_name)

    def get_models(self, app_label):
        return list(apps.get_app_config(app_label).get_models())

    def has_perm(self, user, perm, obj=None):
        if not user.is_active:
            return False
        p = perm.split('.')
        if not len(p) == 2:
            return False
        app_label, codename = p
        try:
            permission = Permission.objects.get(content_type__app_label=app_label, codename=codename)
        except Permission.DoesNotExist:
            return False
        model = permission.content_type.model_class()
        p = codename.split('_', 1)
        if not len(p) == 2:
            return self.has_ability(user, model, codename, obj)
        right, model_name = p
        if right not in self.PERM_ABILITY:
            return self.has_ability(user, model, codename, obj)
        if model_name != model._meta.model_name:
            return self.has_ability(user, model, codename, obj)
        ability = self.PERM_ABILITY[right]
        return self.has_ability(user, model, ability, obj)

    def has_ability(self, user, model, ability, obj=None):
        manager = AccessManager(model)
        if obj and isinstance(obj, model):
            apply = getattr(manager, "apply_%s" % ability)
            return bool(apply(model.objects.filter(pk=obj.pk), self.FakeRequest(self, user)))
        check = getattr(manager, "check_%s" % ability)
        return check(model, self.FakeRequest(self, user)) is not False

    def has_module_perms(self, user, app_label):
        models = self.get_models(app_label)
        for model in models:
            manager = AccessManager(model)
            if manager.check_visible(model, self.FakeRequest(self, user)):
                return True
        return False

    def get_all_permissions(self, user, obj=None):
        logger.warning("The get_all_permissions is DEPRECATED here and always returns empty set!!!")
        return set()

    def get_group_permissions(self, user, obj=None):
        logger.warning("The get_group_permissions is DEPRECATED here and always returns empty set!!!")
        return set()
