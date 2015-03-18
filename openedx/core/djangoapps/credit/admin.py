"""
Django admin page for credit eligibility
"""
from .models import CreditCourse, CreditProvider
from django.contrib import admin

admin.site.register(CreditCourse)
admin.site.register(CreditProvider)
