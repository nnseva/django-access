from django.contrib.admin import TabularInline, StackedInline, ModelAdmin
from django.contrib.admin.options import csrf_protect_m

from django.contrib.admin.utils import get_fields_from_path
from django.contrib.admin.utils import model_ngettext, NestedObjects, quote
from django.contrib.admin import helpers
from django.contrib.admin.views.main import ChangeList

from django.contrib import messages

from django.template.response import TemplateResponse

from django.contrib.admin.filters import RelatedFieldListFilter
from django.contrib.admin.utils import flatten_fieldsets


from django.utils.translation import ugettext_lazy as _

from django.utils.encoding import force_text
from django.utils.text import capfirst
from django.utils.html import format_html
from django.urls import NoReverseMatch, reverse
from django.utils.safestring import mark_safe

from django.forms.formsets import DELETION_FIELD_NAME

from django.db import transaction
from django.db.models.fields.related import ForeignObjectRel

from django.core.exceptions import (
    PermissionDenied, ValidationError,
)

from django.conf import settings
from django.utils.six import text_type, string_types

from django.apps import apps

from access.managers import AccessManager

import collections


class RelatedFieldVisibleListFilter(RelatedFieldListFilter):
    def field_choices(self, field, request, model_admin):
        if not hasattr(field, 'rel'):
            return [l for l in super(RelatedFieldVisibleListFilter, self).field_choices(field, request, model_admin)]
        else:
            q = field.rel.to.objects.all()
            return [(o.pk, text_type(o)) for o in AccessManager(field.rel.to).apply_visible(q, request).distinct()]


class RelatedFieldPresentListFilter(RelatedFieldListFilter):
    def field_choices(self, field, request, model_admin):
        if not hasattr(field, 'rel'):
            return [l for l in super(RelatedFieldPresentListFilter, self).field_choices(field, request, model_admin)]
        else:
            q = field.rel.to.objects.filter(
                pk__in=model_admin.get_queryset(request).values(self.field_path)
            ).distinct()
            return [(o.pk, text_type(o)) for o in q]


class NoListEditableChangeList(ChangeList):
    def __init__(self,
        request, model, list_display,
        list_display_links, list_filter, date_hierarchy,
        search_fields, list_select_related, list_per_page,
        list_max_show_all, list_editable, admin
    ):
        super(NoListEditableChangeList, self).__init__(
            request, model, list_display,
            list_display_links, list_filter, date_hierarchy,
            search_fields, list_select_related, list_per_page,
            list_max_show_all, None, admin
        )


class AccessControlMixin(object):
    """
    This mixin defines some additions for the Admin classes:
        - get_filter_for_field - returns filters for One-to-Many or Many-to-Many fields and is used in get_list_filter function
        - get_list_filter returns either RelatedFieldVisibleListFilter, or RelatedFieldPresentListFilter
          depending on a new present_list_filter_fields member of the ModelAdmin
        - has_basic_change_permission - returns real change permissions instead of standard
          has_change_permission which returns has_view_permission to see object list and details view
        - delete_selected - a method actually replacing the standard delete_selected action if present
        - get_deleted_objects - a method used in the delete_selected to collect all instances deleted with the requested ones

    Replacing standard methods to take dynamic access control into account
        - get_list_filter - returns modified filters for relation fields
        - get_queryset - returns modified queryset
        - get_field_queryset (!!!UNDOCUMENTED!!! instead of formfield_for...) - returns modified querysets to select values for relation fields
        - get_changelist - returns modified list view when the user has no rights to change
        - has_*_permission - returns modified permissions
        - get_model_perms - returns modified permissions
        - get_readonly_fields - returns the full set of fiedls to be readonly when the particular object is not changeable
        - delete_view - replaces a standard delete view to delete an object
        - save_model - controls rights
        - save_related - controls rights
    """

    def get_filter_for_field(self, f, request):
        field = get_fields_from_path(self.model, f)[-1]
        if hasattr(field, 'rel') and hasattr(field.rel, 'to'):
            present_list_filter_fields = getattr(self, 'present_list_filter_fields', [])
            if f in present_list_filter_fields:
                return RelatedFieldPresentListFilter
            return RelatedFieldVisibleListFilter

    def get_list_filter(self, request):
        if self.list_filter:
            filters = []
            for f in self.list_filter:
                if not isinstance(f, string_types):  # ignore custom list filters
                    filters.append(f)
                    continue
                filter = self.get_filter_for_field(f, request)
                if filter:
                    filters.append((f, filter))
                else:
                    filters.append(f)
            return filters

    def get_queryset(self, request):
        return AccessManager(self.model).visible(request)

    def get_field_queryset(self, db, db_field, request):
        # NOTE!!! Undocumented and may be changed in future versions!
        qs = super(AccessControlMixin, self).get_field_queryset(db, db_field, request)
        manager = AccessManager(db_field.rel.to)
        if qs is None:
            qs = manager.get_queryset()
        return manager.apply_visible(qs, request)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        '''
        Not all Admin subclasses use get_field_queryset here, so we will use it explicitly
        '''
        db = kwargs.get('using')
        kwargs['queryset'] = kwargs.get('queryset', self.get_field_queryset(db, db_field, request))
        return super(AccessControlMixin, self).formfield_for_manytomany(db_field, request, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        '''
        Not all Admin subclasses use get_field_queryset here, so we will use it explicitly
        '''
        db = kwargs.get('using')
        kwargs['queryset'] = kwargs.get('queryset', self.get_field_queryset(db, db_field, request))
        return super(AccessControlMixin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def get_changelist(self, request, **kwargs):
        if not self.has_basic_change_permission(request):
            return NoListEditableChangeList
        return ChangeList

    def has_add_permission(self, request):
        r = AccessManager(self.model).appendable(request) is not False
        return r

    def has_change_permission(self, request, obj=None):
        # in order to see the list and object views;
        # look into get_readonly_fields to see the object-level restriction
        r = self.has_view_permission(request, obj)
        return r

    def has_basic_change_permission(self, request, obj=None):
        manager = AccessManager(self.model)
        if manager.check_changeable(self.model, request) is False:
            return False
        if obj:
            return bool(manager.apply_changeable(obj.__class__.objects.filter(id=obj.id), request))
        return True

    def has_delete_permission(self, request, obj=None):
        manager = AccessManager(self.model)
        if manager.check_deleteable(self.model, request) is False:
            return False
        if obj:
            return bool(manager.apply_deleteable(obj.__class__.objects.filter(id=obj.id), request))
        return True

    def has_view_permission(self, request, obj=None):
        manager = AccessManager(self.model)
        if manager.check_visible(self.model, request) is False:
            return False
        if obj:
            return bool(manager.apply_visible(obj.__class__.objects.filter(id=obj.id), request))
        return True

    def get_model_perms(self, request):
        """
        Returns a dict of all perms for this model. This dict has the keys
        ``add``, ``change``, and ``delete`` mapping to the True/False for each
        of those actions.
        """
        return {
            'add': self.has_add_permission(request),
            'change': self.has_change_permission(request),
            'delete': self.has_delete_permission(request),
        }

    def has_module_permission(self, request):
        if self.has_view_permission(request):
            return True
        for model in apps.get_app_config(self.model._meta.app_label).get_models():
            if AccessManager(model).check_visible(model, request) is not False:
                return True
        return False

    def get_readonly_fields(self, request, obj=None):
        if hasattr(request, '--avoid-get_readonly_fields-recursion--'):
            return super(AccessControlMixin, self).get_readonly_fields(request, obj)
        if not obj:
            return super(AccessControlMixin, self).get_readonly_fields(request, obj)
        if not self.has_basic_change_permission(request):
            setattr(request, '--avoid-get_readonly_fields-recursion--', True)
            own_fields = flatten_fieldsets(self.get_fieldsets(request, obj))
            delattr(request, '--avoid-get_readonly_fields-recursion--')
            return list(set(super(AccessControlMixin, self).get_readonly_fields(request, obj)).union(own_fields))
        if not self.has_basic_change_permission(request, obj):
            setattr(request, '--avoid-get_readonly_fields-recursion--', True)
            own_fields = flatten_fieldsets(self.get_fieldsets(request, obj))
            delattr(request, '--avoid-get_readonly_fields-recursion--')
            return list(set(super(AccessControlMixin, self).get_readonly_fields(request, obj)).union(own_fields))
        return super(AccessControlMixin, self).get_readonly_fields(request, obj)

    def save_model(self, request, obj, form, change):
        if change and self.has_basic_change_permission(request, obj):
            return super(AccessControlMixin, self).save_model(request, obj, form, change)
        if not change and self.has_add_permission(request):
            data = AccessManager(self.model).appendable(request)
            for k in data:
                v = data[k]
                fieldname = k
                if fieldname.endswith("_set"):
                    fieldname = fieldname[:-4]
                field = form.instance._meta.get_field(fieldname)
                if isinstance(v, collections.Iterable) and not isinstance(v, string_types) and isinstance(field, ForeignObjectRel):
                    continue
                if getattr(obj, k) is None:
                    setattr(obj, k, v)
            return super(AccessControlMixin, self).save_model(request, obj, form, change)
        raise PermissionDenied

    def save_related(self, request, form, formsets, change):
        if change and self.has_basic_change_permission(request, form.instance):
            return super(AccessControlMixin, self).save_related(request, form, formsets, change)
        if not change and self.has_add_permission(request):
            data = AccessManager(self.model).appendable(request)
            for k in data:
                v = data[k]
                fieldname = k
                if fieldname.endswith("_set"):
                    fieldname = fieldname[:-4]
                field = form.instance._meta.get_field(fieldname)
                if isinstance(v, collections.Iterable) and not isinstance(v, string_types) and isinstance(field, ForeignObjectRel):
                    fld = getattr(form.instance, k)
                    for i in v:
                        fld.add(i)
            return super(AccessControlMixin, self).save_related(request, form, formsets, change)
        raise PermissionDenied

    def save_formset(self, request, form, formset, change):
        super(AccessControlMixin, self).save_formset(request, form, formset, change)

    def get_actions(self, req):
        r = super(AccessControlMixin, self).get_actions(req)
        if 'delete_selected' in r:
            old_func, name, descr = r['delete_selected']
            r['delete_selected'] = (self.__class__.delete_selected, name, descr)
        return r

    @csrf_protect_m
    @transaction.atomic
    def delete_view(self, request, object_id, extra_context=None):
        "The 'delete' admin view for this model."
        queryset = self.model._default_manager.filter(pk=object_id)
        return self.delete_selected(request, queryset)

    def delete_selected(self, request, queryset):
        '''
        The real delete function always evaluated either from the action, or from the instance delete link
        '''
        opts = self.model._meta
        app_label = opts.app_label

        # Populate deletable_objects, a data structure of all related objects that
        # will also be deleted.
        deletable_objects, model_count, perms_needed, protected = self.get_deleted_objects(request, queryset)

        # The user has already confirmed the deletion.
        # Do the deletion and return a None to display the change list view again.
        if request.POST.get('post') and not protected:
            if perms_needed or protected:
                raise PermissionDenied
            n = queryset.count()
            if n:
                for obj in queryset:
                    obj_display = force_text(obj)
                    self.log_deletion(request, obj, obj_display)
                queryset.delete()
                self.message_user(request, _("Successfully deleted %(count)d %(items)s.") % {
                    "count": n, "items": model_ngettext(self.opts, n)
                }, messages.SUCCESS)
            # Return None to display the change list page again.
            return None

        sz = queryset.count()
        if sz == 1:
            objects_name = _('%(verbose_name)s "%(object)s"') % {
                'verbose_name': force_text(opts.verbose_name),
                'object': queryset[0]
            }
        else:
            objects_name = _('%(count)s %(verbose_name_plural)s') % {
                'verbose_name_plural': force_text(opts.verbose_name_plural),
                'count': sz
            }

        if perms_needed or protected:
            title = _("Cannot delete %(name)s") % {"name": objects_name}
        else:
            title = _("Are you sure?")

        context = dict(
            self.admin_site.each_context(request),
            title=title,
            objects_name=objects_name,
            deletable_objects=[deletable_objects],
            model_count=dict(model_count).items(),
            queryset=queryset,
            perms_lacking=perms_needed,
            protected=protected,
            opts=opts,
            action_checkbox_name=helpers.ACTION_CHECKBOX_NAME,
            media=self.media,
        )

        request.current_app = self.admin_site.name

        # Display the confirmation page
        return TemplateResponse(request, self.delete_selected_confirmation_template or [
            "admin/%s/%s/delete_selected_confirmation.html" % (app_label, opts.model_name),
            "admin/%s/delete_selected_confirmation.html" % app_label,
            "admin/delete_selected_confirmation.html"
        ], context)

    delete_selected.short_description = _("Delete selected %(verbose_name_plural)s")

    def get_deleted_objects(self, request, queryset):
        """
        Find all objects related to instances of ``queryset`` that should also be deleted.

        Returns
            - to_delete - a nested list of strings suitable for display in the template with the ``unordered_list`` filter.
            - model_count - statistics for models of all deleted instances
            - perms_needed - list of names for all instances which can not be deleted because of not enough rights
            - protected - list of names for all objects protected for deletion because of reference type
        """
        collector = NestedObjects(using=queryset.db)
        collector.collect(queryset)
        model_perms_needed = set()
        object_perms_needed = set()

        STRONG_DELETION_CONTROL = getattr(settings, 'ACCESS_STRONG_DELETION_CONTROL', False)

        def format_callback(obj):
            has_admin = obj.__class__ in self.admin_site._registry
            opts = obj._meta

            no_edit_link = '%s: %s' % (capfirst(opts.verbose_name),
                                   force_text(obj))

            # Trying to get admin change URL
            admin_url = None
            try:
                admin_url = reverse('%s:%s_%s_change'
                                % (self.admin_site.name,
                                   opts.app_label,
                                   opts.model_name),
                                None, (quote(obj._get_pk_val()),))
            except NoReverseMatch:
                # Change url doesn't exist -- don't display link to edit
                pass

            # Collecting forbidden subobjects, compatible with Django or forced by the option
            if STRONG_DELETION_CONTROL or has_admin:
                if not obj.__class__._meta.auto_created:
                    manager = AccessManager(obj.__class__)
                    # filter out forbidden items
                    if manager.check_deleteable(obj.__class__, request) is False:
                        model_perms_needed.add(opts.verbose_name)
                    if not manager.apply_deleteable(obj.__class__._default_manager.filter(pk=obj.pk), request):
                        object_perms_needed.add(obj)

            if admin_url:
                # Display a link to the admin page.
                return format_html('{}: <a href="{}">{}</a>',
                               capfirst(opts.verbose_name),
                               admin_url,
                               obj)
            else:
                # Don't display link to edit, because it either has no
                # admin or is edited inline.
                return no_edit_link

        to_delete = collector.nested(format_callback)

        protected = [format_callback(obj) for obj in collector.protected]
        protected = set([format_callback(obj) for obj in object_perms_needed]).union(protected)
        model_count = {model._meta.verbose_name_plural: len(objs) for model, objs in collector.model_objs.items()}

        return to_delete, model_count, model_perms_needed, protected

    def get_formset(self, request, obj=None, **kwargs):
        def clean_delete_field(form):
            if form.instance:
                if form.cleaned_data[DELETION_FIELD_NAME]:
                    queryset = form.instance.__class__.objects.filter(pk=form.instance.pk)
                    to_delete, model_count, perms_needed, protected = self.get_deleted_objects(request, queryset)
                    if perms_needed:
                        raise ValidationError(mark_safe(_("Deleting for the following object types is forbidden: %(perms_needed)s") % {
                                'perms_needed': ', '.join(perms_needed)
                        }))
                    if protected:
                        raise ValidationError(mark_safe(_("Deleting the following objects is protected or forbidden: %(protected)s") % {
                                'protected': ', '.join(protected)
                        }))
            method = getattr(super(CheckDeleteRightsForm, form), "clean_%s" % DELETION_FIELD_NAME, None)
            if method:
                return method()
            return form.cleaned_data[DELETION_FIELD_NAME]

        def clean(form):
            err = form.errors.get(DELETION_FIELD_NAME, None)
            if err:
                for e in err:
                    # reraising an error for the special field to see it above the record
                    raise ValidationError(e)
            return super(CheckDeleteRightsForm, form).clean()

        FormBase = kwargs.get('form', self.form)

        CheckDeleteRightsForm = type("CheckDeleteRightsForm", (FormBase,), {
            'clean_%s' % DELETION_FIELD_NAME: clean_delete_field,
            'clean': clean
        })

        kw = {}
        kw.update(kwargs)
        kw['form'] = CheckDeleteRightsForm

        return super(AccessControlMixin, self).get_formset(request, obj=obj, **kw)


class AccessModelAdmin(AccessControlMixin, ModelAdmin):
    pass


class AccessTabularInline(AccessControlMixin, TabularInline):
    pass


class AccessStackedInline(AccessControlMixin, StackedInline):
    pass
