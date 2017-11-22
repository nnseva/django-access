from django.contrib.auth.backends import ModelBackend as ModelBackendBase
from django.apps import apps

from access.managers import AccessManager


class FakeRequest(object):
    def __init__(self, backend, user):
        self.user = user


class ModelBackend(ModelBackendBase):
    PERM_ABILITY = {
        "add": "appendable",
        "change": "changeable",
        "delete": "deleteable",
        "view": "visible",
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
            return super(ModelBackend, self).has_perm(user, perm, obj=obj)
        app_label, p = p
        p = p.split('_', 1)
        if not len(p) == 2:
            return super(ModelBackend, self).has_perm(user, perm, obj=obj)
        right, model_name = p
        model = self.get_model(app_label, model_name)
        if not model:
            return super(ModelBackend, self).has_perm(user, perm, obj=obj)
        ability = self.PERM_ABILITY.get(right, right)
        manager = AccessManager(model)
        if obj:
            if not isinstance(obj, model):
                return super(ModelBackend, self).has_perm(user, perm, obj=obj)
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
        # is not used anyway
        return set()

    def get_group_permissions(self, user, obj=None):
        # is not used anyway
        return set()
