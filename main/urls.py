from django.urls import path
from main import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('basketball/', views.basketball, name='basketball'),
    path('fintech/', views.fintech, name='fintech'),
    path('gallery/', views.gallery, name='gallery'),
    path('projects/', views.projects, name='projects'),
    # Fintech project 1
    path('projects/savings-goal/', views.savings_goal, name='savings_goal'),
    # Fintech project 2
    path('projects/loan-calculator/', views.loan_calculator, name='loan_calculator'),
    # Fintech project 3
    path('projects/bill-splitter/', views.bill_splitter, name='bill_splitter'),
    # Fintech project 4
    path('projects/wallet-simulator/', views.wallet_simulator, name='wallet_simulator'),
]