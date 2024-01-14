from django.db import models
from uuid import uuid4

class User(models.Model):
    unique_user_id = models.UUIDField(primary_key=True, default=uuid4)
    aadhar_number = models.CharField(max_length=20,unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    annual_income = models.DecimalField(max_digits=10,decimal_places=2)
    credit_score = models.IntegerField(blank=True,null=True)

class LoanApplication(models.Model):
    unique_user_id = models.UUIDField(primary_key=True, default=uuid4)
    loan_type = models.CharField(max_length=100,default="CREDIT CARD")
    loan_amount = models.IntegerField()
    interest_rate = models.IntegerField(default=15)
    term_period = models.IntegerField(null=True)
    disbursement_date = models.DateField()
    emi_amount = models.DecimalField(null=True,max_digits=10,decimal_places=2)
    due_dates = models.JSONField(null=True)

class Repayment(models.Model):
    loan_application = models.ForeignKey(LoanApplication, on_delete=models.CASCADE)
    payment_date = models.DateField(null=True)
    payment_amount = models.DecimalField(null=True,max_digits=10,decimal_places=2)
    emi_amount = models.DecimalField(null = True,max_digits=10,decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=[('PENDING', 'Pending'), ('SUCCESS', 'Success'), ('FAILED', 'Failed')], default='PENDING')
