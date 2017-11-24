from django.test import TestCase as _TestCase
from django.test import Client

import unittest
import mock

import re
import json

import os

from django.core.exceptions import ValidationError

import logging

from django.utils.six import text_type, string_types

class TestCase(_TestCase):
    if not hasattr(_TestCase,'assertRegex'):
        assertRegex = _TestCase.assertRegexpMatches
    if not hasattr(_TestCase,'assertNotRegex'):
        assertNotRegex = _TestCase.assertNotRegexpMatches

class TestBase(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User, Group, Permission
        from django.contrib import auth
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Model
        from someapp.models import SomeObject, SomeChild

        self.user = User.objects.create(username="test",is_active=True,is_staff=True)
        self.user.set_password("test")
        self.user.save()
        self.another = User.objects.create(username="another",is_active=True,is_staff=True)
        self.another.set_password("test")
        self.another.save()
        self.third = User.objects.create(username="third",is_active=True,is_staff=True)
        self.third.set_password("test")
        self.third.save()
        self.fourth = User.objects.create(username="fourth",is_active=True,is_staff=True)
        self.fourth.set_password("test")
        self.fourth.save()
        self.group = Group.objects.create(name="some")
        self.group.save()
        self.other_group = Group.objects.create(name="other")
        self.other_group.save()
        self.some = SomeObject.objects.create(name='some',editor_group=self.group)
        self.user.user_permissions.add(Permission.objects.get(codename='one'))
        self.user.user_permissions.add(Permission.objects.get(codename='two'))
        self.user.user_permissions.add(Permission.objects.get(codename='two_two'))
        self.user.user_permissions.add(Permission.objects.get(codename='three_someobject'))
        self.user.user_permissions.add(Permission.objects.get(codename='four_some_object'))

        for cn in dir(auth.models):
            c = getattr(auth.models,cn)
            if isinstance(c,type) and issubclass(c,Model) and not c._meta.abstract and c._meta.app_label == 'auth':
                for cc in ['add','change','delete']:
                    self.user.user_permissions.add(
                        Permission.objects.get(
                            content_type=ContentType.objects.get(app_label=c._meta.app_label,model=c._meta.model_name),
                            codename='%s_%s' % (cc,c._meta.model_name),
                        )
                    )
                    self.group.permissions.add(
                        Permission.objects.get(
                            content_type=ContentType.objects.get(app_label=c._meta.app_label,model=c._meta.model_name),
                            codename='%s_%s' % (cc,c._meta.model_name),
                        )
                    )

        for cc in ['add','change','delete']:
            self.other_group.permissions.add(
                Permission.objects.get(
                    content_type=ContentType.objects.get(app_label='auth',model='user'),
                    codename='%s_%s' % (cc,'user'),
                )
            )

        self.group.user_set.add(self.third)
        self.other_group.user_set.add(self.fourth)

    def tearDown(self):
        from django.contrib.auth.models import User, Group, Permission
        User.objects.all().delete()
        Group.objects.all().delete()

class FirstTest(TestBase):
    def test_1_login(self):
        c = Client()
        c.login(username='test',password='test')
        response = c.get('/admin/')
        self.assertEqual(response.status_code,200)
    def test_2_login(self):
        c = Client()
        c.login(username='another',password='test')
        response = c.get('/admin/')
        self.assertEqual(response.status_code,200)

class DjangoAccessTest(TestBase):
    def test_1_check_forbidden_django_permissions(self):
        c = Client()
        c.login(username='another',password='test')
        response = c.get('/admin/auth/')
        self.assertEqual(response.status_code,200)
        response = c.get('/admin/auth/user/')
        self.assertEqual(response.status_code,200)
        response = c.get('/admin/auth/group/')
        self.assertNotEqual(response.status_code,200)

    def test_2_check_allowed_django_user_permissions(self):
        c = Client()
        c.login(username='test',password='test')
        response = c.get('/admin/auth/')
        self.assertEqual(response.status_code,200)
        response = c.get('/admin/auth/user/')
        self.assertEqual(response.status_code,200)
        response = c.get('/admin/auth/group/')
        self.assertEqual(response.status_code,200)

    def test_3_check_allowed_django_group_permissions(self):
        c = Client()
        c.login(username='third',password='test')
        response = c.get('/admin/auth/')
        self.assertEqual(response.status_code,200)
        response = c.get('/admin/auth/user/')
        self.assertEqual(response.status_code,200)
        response = c.get('/admin/auth/group/')
        self.assertEqual(response.status_code,200)

class InstanceAccessTest(TestBase):
    def test_1_check_forbidden_instance_permissions(self):
        c = Client()
        c.login(username='test',password='test')
        response = c.get('/admin/auth/group/')
        self.assertEqual(response.status_code,200)
        response = c.get('/admin/auth/group/%s/change/' % self.group.id)
        self.assertNotEqual(response.status_code,200)

    def test_2_check_allowed_instance_permissions(self):
        c = Client()
        c.login(username='third',password='test')
        response = c.get('/admin/auth/group/')
        self.assertEqual(response.status_code,200)
        response = c.get('/admin/auth/group/%s/change/' % self.group.id)
        self.assertEqual(response.status_code,200)

    def test_3_check_changeable_instance_permissions(self):
        c = Client()
        c.login(username='test',password='test')
        response = c.get('/admin/auth/user/')
        self.assertEqual(response.status_code,200)
        response = c.get('/admin/auth/user/%s/change/' % self.user.id)
        self.assertEqual(response.status_code,200)
        response = c.post('/admin/auth/user/%s/change/' % self.user.id, data={'username':'test2','_continue':'continue'})
        self.assertEqual(response.status_code,302)
        response = c.post('/admin/auth/user/%s/change/' % self.user.id, data={'username':'test','_continue':'continue'})
        self.assertEqual(response.status_code,302)

    def test_4_check_readonly_instance_permissions(self):
        c = Client()
        c.login(username='another',password='test')
        response = c.get('/admin/auth/user/')
        self.assertEqual(response.status_code,200)
        response = c.get('/admin/auth/user/%s/change/' % self.user.id)
        self.assertEqual(response.status_code,200)
        response = c.post('/admin/auth/user/%s/change/' % self.user.id, data={'username':'test2','_continue':'continue'})
        self.assertNotEqual(response.status_code,302)

    def test_5_check_restricted_filters(self):
        c = Client()
        c.login(username='fourth',password='test')
        response = c.get('/admin/auth/user/')
        self.assertEqual(response.status_code,200)
        self.assertRegex(text_type(response.content),r'href="\?groups__id__exact=%s"[^>]*>%s' % (self.other_group.pk,self.other_group.name))
        self.assertNotRegex(text_type(response.content),r'href="\?groups__id__exact=%s"[^>]*>%s' % (self.group.pk,self.group.name))

    def test_6_check_restricted_selects(self):
        c = Client()
        c.login(username='fourth',password='test')
        response = c.get('/admin/auth/user/%s/change/' % self.fourth.pk)
        self.assertEqual(response.status_code,200)
        self.assertRegex(text_type(response.content),r'<option\ value="%s"\ selected[^>]*>%s' % (self.other_group.pk,self.other_group.name))
        self.assertNotRegex(text_type(response.content),r'<option\ value="%s"\ selected[^>]*>%s' % (self.group.pk,self.group.name))

class AuthenticationBackendTest(TestBase):
    def test_1_check_classic_permissions(self):
        self.assertEqual(self.user.has_perm("auth.add_user"),True)
        self.assertEqual(self.user.has_perm("auth.change_user"),True)
        self.assertEqual(self.user.has_perm("auth.delete_user"),True)
        self.assertEqual(self.user.has_perm("auth.add_group"),True)
        self.assertEqual(self.user.has_perm("auth.change_group"),True)
        self.assertEqual(self.user.has_perm("auth.delete_group"),True)

        self.assertEqual(self.another.has_perm("auth.add_user"),False)
        self.assertEqual(self.another.has_perm("auth.change_user"),True)
        self.assertEqual(self.another.has_perm("auth.delete_user"),True)
        self.assertEqual(self.another.has_perm("auth.add_group"),False)
        self.assertEqual(self.another.has_perm("auth.change_group"),False)
        self.assertEqual(self.another.has_perm("auth.delete_group"),False)

        self.assertEqual(self.third.has_perm("auth.add_user"),True)
        self.assertEqual(self.third.has_perm("auth.change_user"),True)
        self.assertEqual(self.third.has_perm("auth.delete_user"),True)
        self.assertEqual(self.third.has_perm("auth.add_group"),True)
        self.assertEqual(self.third.has_perm("auth.change_group"),True)
        self.assertEqual(self.third.has_perm("auth.delete_group"),True)

        self.assertEqual(self.fourth.has_perm("auth.add_user"),True)
        self.assertEqual(self.fourth.has_perm("auth.change_user"),True)
        self.assertEqual(self.fourth.has_perm("auth.delete_user"),True)
        self.assertEqual(self.fourth.has_perm("auth.add_group"),False)
        self.assertEqual(self.fourth.has_perm("auth.change_group"),False)
        self.assertEqual(self.fourth.has_perm("auth.delete_group"),False)

    def test_2_check_object_permissions(self):
        self.assertEqual(self.user.has_perm("auth.change_user",self.user),True)
        self.assertEqual(self.user.has_perm("auth.change_user",self.another),True)
        self.assertEqual(self.user.has_perm("auth.delete_user",self.another),True)

        self.assertEqual(self.user.has_perm("auth.change_group",self.group),False)
        self.assertEqual(self.user.has_perm("auth.delete_group",self.group),False)

        self.assertEqual(self.third.has_perm("auth.change_group",self.group),True)
        self.assertEqual(self.third.has_perm("auth.delete_group",self.group),True)
        self.assertEqual(self.third.has_perm("auth.change_group",self.other_group),False)
        self.assertEqual(self.third.has_perm("auth.delete_group",self.other_group),False)

    def test_3_check_custom_permissions(self):
        self.assertEqual(self.user.has_perm("someapp.one"),True)
        self.assertEqual(self.user.has_perm("someapp.two"),True)
        self.assertEqual(self.user.has_perm("someapp.two_two"),True)
        self.assertEqual(self.user.has_perm("someapp.three"),False)
        self.assertEqual(self.user.has_perm("someapp.three_someobject"),True)
        self.assertEqual(self.user.has_perm("someapp.three_someobject",self.some),True)
        self.assertEqual(self.user.has_perm("someapp.four_some_object"),True)

        self.assertEqual(self.another.has_perm("someapp.one"),False)
        self.assertEqual(self.another.has_perm("someapp.two"),False)
        self.assertEqual(self.another.has_perm("someapp.two_two"),False)
        self.assertEqual(self.another.has_perm("someapp.three"),False)
        self.assertEqual(self.another.has_perm("someapp.three_someobject"),False)
        self.assertEqual(self.another.has_perm("someapp.three_someobject",self.some),False)
        self.assertEqual(self.another.has_perm("someapp.four_some_object"),False)
