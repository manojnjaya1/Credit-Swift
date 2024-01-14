from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status,serializers
from .serializers import UserSerializer
from .tasks import calculate_credit_score
from .models import User,LoanApplication,Repayment
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime,timedelta
from datetime import date
import json
import simplejson
# Create your views here.


# @api_view(['POST'])
# def register_user(request):
#     data = request.data
#     serializer =  UserSerializer(data=data)
#     if serializer.is_valid():
#         user = serializer.save()
#         calculate_credit_score.delay(user.aadhar_number) 
#         return Response({'unique_user_id': str(user.id), 'Error': None}, status=status.HTTP_200_OK)
#     else:
#        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#     # return Response({'Error': 'Invalid data'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def register_user(request):
    data = request.data
    serializer = UserSerializer(data=data)
    if serializer.is_valid():
        user = serializer.save()
        calculate_credit_score.delay(user.aadhar_number)  # Delay the task to a Celery worker
        return Response({'unique_user_id': str(user.unique_user_id ), 'Error': None}, status=status.HTTP_200_OK)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

@api_view(['POST'])
def apply_loan(request):
    if request.method == 'POST':
        data = request.data
        try:
            user = User.objects.get(unique_user_id=data["uuid"])
        except User.DoesNotExist:
            return JsonResponse({'Error': 'User registration required before applying for a loan'}, status=status.HTTP_400_BAD_REQUEST)

        if data['loan_type'] != 'CREDIT CARD':
            return JsonResponse({'Error': 'Invalid loan type. Currently, only Credit Card loans are supported'}, status=status.HTTP_400_BAD_REQUEST)

        if data['loan_amount'] > 5000:
            return JsonResponse({'Error': 'Loan amount cannot exceed Rs. 5000'}, status=status.HTTP_400_BAD_REQUEST)

        if user.credit_score < 450 or not user.credit_score:
            return JsonResponse({'Error': 'Loan application cannot be processed. Insufficient credit score'}, status=status.HTTP_400_BAD_REQUEST)

        if user.annual_income < 150000:
            return JsonResponse({'Error': 'Loan application cannot be processed. Annual income must be Rs. 1,50,000 or more'}, status=status.HTTP_400_BAD_REQUEST)

        def calculate_due_dates():
                due_dates = []
                disbursement_date_str = data['disbursement_date']
                disbursement_date = datetime.strptime(disbursement_date_str, '%Y-%m-%d')
                term_period = data['term_period']

                for month_number in range(1, term_period + 1):
                    # Calculate the current month based on the disbursement date and month number
                    current_month = disbursement_date.month + month_number - 1

                    # Handle cases where the calculated month exceeds 12
                    if current_month > 12:
                        current_month -= 12  # Adjust month index to stay within the valid range
                        due_date = date(disbursement_date.year + 1, current_month, 15)
                    else:
                        due_date = date(disbursement_date.year, current_month, 15)

                    # Adjust the due date if it falls on a weekend or holiday
                    while due_date.weekday() in [5, 6]:  # Check for weekends (Saturday, Sunday)
                        due_date = due_date + datetime.timedelta(days=1)

                    # Add the calculated due date to the list
                    due_dates.append(due_date)

                return due_dates
        emi_amount = (data['loan_amount'] * (data['interest_rate']/12) * (int(1+(data['interest_rate']/12))^data['term_period'])) / ((int(1+(data['interest_rate']/12))^data['term_period']-1))
        due_dates = calculate_due_dates()
        json_data = []
        for datetime_object in due_dates:
            json_data.append(datetime_object.strftime('%Y-%m-%d')) 
        loan_application = LoanApplication.objects.create(
            loan_type=data['loan_type'],
            loan_amount=data['loan_amount'],
            interest_rate=data['interest_rate'],
            term_period=data['term_period'],
            disbursement_date=data['disbursement_date'],
            emi_amount = emi_amount,
            due_dates =json.dumps(json_data)
        )
        monthly_data = []
        for due_date in due_dates:
            monthly_data.append(
                {
                    'Due Date' : due_date,
                    'Emi amount':emi_amount
                }
            )
        response_data = {
            'Loan_id': loan_application.unique_user_id,
            'Monthly_Data' : monthly_data
        }

        return JsonResponse(response_data, status=status.HTTP_200_OK)
    else:
        return JsonResponse({'Error': 'Invalid request method'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def make_repayment(request):
    if request.method == 'POST':
        data = request.data
        try:
            loan_application = LoanApplication.objects.get(unique_user_id=data['unique_user_id'])
        except LoanApplication.DoesNotExist:
            return JsonResponse({'Error': 'Invalid user payment'}, status=status.HTTP_400_BAD_REQUEST)
        payment_date = datetime.strptime(data['payment_date'], '%Y-%m-%d')
        
        if Repayment.objects.filter(loan_application=loan_application, payment_date=payment_date).exists():
            return JsonResponse({'Error': 'Payment has already been recorded for this date'}, status=status.HTTP_400_BAD_REQUEST)
        

        last_date_data = simplejson.loads(loan_application.due_dates)
        last_due_date = last_date_data[-1]
        last_date = datetime.strptime(last_due_date, '%Y-%m-%d')
        if payment_date.date() <= last_date.date():
            latest_paid_emi = Repayment.objects.filter(loan_application=loan_application).order_by('payment_date').last()
            if latest_paid_emi is not None and latest_paid_emi.payment_date < payment_date.date():
                unpaid_emis = Repayment.objects.filter(loan_application=loan_application, payment_date__lt=payment_date, payment_status='PENDING')

                if unpaid_emis.exists():
                    return JsonResponse({'Error': 'Previous EMIs remain unpaid'}, status=status.HTTP_400_BAD_REQUEST)
            
            payment_amount = data['amount']
            due_amount = loan_application.emi_amount
            if payment_amount >  due_amount:
                loan_application.emi_amount=int(loan_application.emi_amount) - (int(payment_amount) - int(due_amount))
                loan_application.save()
            else:
                loan_application.emi_amount=int(loan_application.emi_amount) + (int(due_amount) - int(payment_amount))
                loan_application.save()
            payment = Repayment.objects.create(
            loan_application=loan_application,
            payment_date=payment_date,
            payment_amount=payment_amount,
            emi_amount=due_amount,
            payment_status='PENDING'
            )

            response_data = {
                'Message': 'Payment recorded successfully',
                'Emi_amount': payment_amount
            }
            return JsonResponse(response_data, status=status.HTTP_200_OK)
        else:
           return JsonResponse({'Error': 'All emis are cleared for this transaction'}, status=status.HTTP_400_BAD_REQUEST)


    else:
        return JsonResponse({'Error': 'Invalid request method'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_statement(request):
    if request.method == "GET":
        data = request.data
        try:
            loan_application = LoanApplication.objects.get(unique_user_id=data['unique_user_id'])
            last_date_data = simplejson.loads(loan_application.due_dates)
            print("last_date_data",type(last_date_data[1]))
            repayments = Repayment.objects.filter(loan_application = loan_application)
            last_date= repayments.last().payment_date
            response_data = {
                'Message' : "Got Statement",
                'transactions': [],
                'upcoming transactions' : []
            }
            for repayment in repayments:
                transaction_data = {
                    'due_date': repayment.payment_date,
                    'payment_date': repayment.payment_date,
                    'payment_amount': repayment.payment_amount
                }
                response_data['transactions'].append(transaction_data)
            for date in last_date_data:
                date_needed = datetime.strptime(date, '%Y-%m-%d').date()
                print("date to see",date_needed)
                if date_needed > last_date:
                    upcoming_transaction = {
                        'due_date' : date
                    }
                    response_data['upcoming transactions'].append(upcoming_transaction)
        except LoanApplication.DoesNotExist:
            return JsonResponse({'Error': 'Invalid user'}, status=status.HTTP_400_BAD_REQUEST)
        return JsonResponse(response_data)
    else:
        return JsonResponse({'Error:Invalid request'})
