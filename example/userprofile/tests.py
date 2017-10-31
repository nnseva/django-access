from django.test import TestCase
from django.test import Client

import unittest
import mock

import re
import json

import os

from django.core.exceptions import ValidationError

import logging


class TestBase(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User, Group, Permission
        from django.contrib import auth
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Model

        self.user = User.objects.create(username="test",is_active=True,is_staff=True)
        self.user.set_password("test")
        self.user.save()
        self.another = User.objects.create(username="another",is_active=True,is_staff=True)
        self.another.set_password("test")
        self.another.save()
        self.third = User.objects.create(username="third",is_active=True,is_staff=True)
        self.third.set_password("test")
        self.third.save()
        self.group = Group.objects.create(name="some")
        self.group.save()

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

        self.group.user_set.add(self.third)

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
        self.assertNotEqual(response.status_code,200)
        response = c.get('/admin/auth/user/')
        self.assertNotEqual(response.status_code,200)
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
        response = c.post('/admin/auth/user/%s/change/' % self.user.id, data={'username':'test2'})
        self.assertEqual(response.status_code,200)
        response = c.post('/admin/auth/user/%s/change/' % self.user.id, data={'username':'test'})
        self.assertEqual(response.status_code,200)

    def test_4_check_readonly_instance_permissions(self):
        c = Client()
        c.login(username='test',password='test')
        response = c.get('/admin/auth/user/')
        self.assertEqual(response.status_code,200)
        response = c.get('/admin/auth/user/%s/change/' % self.another.id)
        self.assertEqual(response.status_code,200)
        response = c.post('/admin/auth/user/%s/change/' % self.another.id, data={'username':'test2'})
        self.assertNotEqual(response.status_code,200)
