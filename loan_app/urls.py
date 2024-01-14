from django.urls import path
from .views import register_user,apply_loan,make_repayment,get_statement
# from django.utils.regex_validation import uuid_pattern

urlpatterns = [
    path('api/make-payment/',make_repayment,name='make_repayment'),
    path('api/get-statement/',get_statement,name = 'get_statement'),
    path('apply-loan/', apply_loan, name='apply_loan'),
    path('api/register-user/', register_user, name='register_user'),
]
