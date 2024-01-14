import csv
from celery import shared_task
from .models import User

@shared_task
def calculate_credit_score(aadhar_number):
    try:
        total_account_balance = 0
        #    with open('transactions.csv', 'r') as csvfile:
        # reader = csv.DictReader(csvfile)
        # for row in reader:
        #     if aadhar_number== row['aadhar_id']:
        #         credit = row['credit']
        #         debit = row['debit']
        #         total_account_balance += credit - debit
        credit_score = calculate_credit_score_from_balance(total_account_balance)
        user = User.objects.get(aadhar_number=aadhar_number)
        user.credit_score = credit_score
        user.save()

    except User.DoesNotExist:
        user = User.objects.get(aadhar_number=aadhar_number)
        user.credit_score = 0
        user.save()
          
    

def calculate_credit_score_from_balance(total_account_balance):
    if total_account_balance >= 1000000:
        credit_score = 900
    elif total_account_balance <= 10000:
        credit_score = 300
    else:
        credit_score = 300 + (total_account_balance - 10000) // 15000

    return credit_score
