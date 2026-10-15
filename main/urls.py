from django.urls import path
from main import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('basketball/', views.basketball, name='basketball'),
    path('gallery/', views.gallery, name='gallery'),
    path('projects/', views.projects, name='projects'),
]
