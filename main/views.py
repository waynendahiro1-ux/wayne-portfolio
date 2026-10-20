import json
import logging
import secrets
import urllib.error
import urllib.request
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import segno
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone

from .forms import ContactForm
from .models import Game, Wallet, Transfer, PaymentRequest

logger = logging.getLogger(__name__)


def send_contact_email(data):
    """Send the message to my inbox using the Resend web API. Returns True if it worked."""
    if not settings.RESEND_API_KEY:
        logger.error("RESEND_API_KEY is not set")
        return False

    payload = {
        'from': 'Wayne Portfolio <onboarding@resend.dev>',
        'to': [settings.CONTACT_RECIPIENT],
        'reply_to': data['email'],
        'subject': f"Portfolio message: {data['subject'] or 'No subject'}",
        'text': (
            f"Name: {data['name']}\n"
            f"Email: {data['email']}\n"
            f"Subject: {data['subject'] or 'No subject'}\n\n"
            f"{data['message']}"
        ),
    }
    request = urllib.request.Request(
        'https://api.resend.com/emails',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {settings.RESEND_API_KEY}',
            'Content-Type': 'application/json',
            'User-Agent': 'wayne-portfolio/1.0',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as error:
        logger.error("Resend rejected the email: %s %s", error.code, error.read().decode('utf-8', 'ignore'))
    except Exception:
        logger.exception("Could not send contact email")
    return False


def home(request):
    return render(request, 'main/home.html')

def about(request):
    return render(request, 'main/about.html')

def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            if send_contact_email(form.cleaned_data):
                messages.success(request, "Thanks! Your message has been sent. I'll get back to you soon.")
                return redirect(reverse('contact') + '#send-message')
            messages.error(request, "Sorry, your message could not be sent right now. Please email me directly instead.")
    else:
        form = ContactForm()
    return render(request, 'main/contact.html', {'form': form})

def basketball(request):
    # NEW: the stats tracker
    games = Game.objects.all()          # newest game first
    total_games = games.count()

    stats = None
    if total_games > 0:
        total_points = sum(g.points for g in games)
        total_rebounds = sum(g.rebounds for g in games)
        total_assists = sum(g.assists for g in games)
        stats = {
            'games': total_games,
            'ppg': round(total_points / total_games, 1),
            'rpg': round(total_rebounds / total_games, 1),
            'apg': round(total_assists / total_games, 1),
            'best': max(g.points for g in games),
        }

    return render(request, 'main/basketball.html', {'games': games, 'stats': stats})

def fintech(request):
    return render(request, 'main/fintech.html')

def gallery(request):
    folder = Path(__file__).resolve().parent / 'static' / 'main' / 'gallery'
    exts = {'.jpg', '.jpeg', '.png', '.webp'}
    photos = []
    if folder.exists():
        for p in sorted(folder.iterdir()):
            if p.suffix.lower() in exts:
                caption = p.stem.replace('-', ' ').replace('_', ' ').title()
                photos.append({'file': p.name, 'caption': caption})
    return render(request, 'main/gallery.html', {'photos': photos})


# ---------- Fintech project 1: Savings Goal Calculator ----------

def read_whole_number(text, label, errors, required=False):
    """Turn what the visitor typed into a whole number.
    If something is wrong, add a friendly message to the errors list and return None."""
    text = text.replace(',', '').replace(' ', '')   # allow "500,000" or "500 000"

    if text == '':
        if required:
            errors.append(f"Please enter {label}.")
        return None

    # isdecimal() is True only for digits 0-9, so letters, minus signs and dots are rejected
    if not text.isdecimal():
        errors.append(f"{label} must be a whole number like 500000 (no letters, minus signs or decimals).")
        return None

    number = int(text)
    if number > 1_000_000_000_000:
        errors.append(f"{label} is too big for this demo.")
        return None
    return number


def savings_goal(request):
    # What the visitor typed, so the boxes keep their values after pressing Calculate
    values = {'target': '', 'saved': '', 'monthly': '', 'months': ''}
    errors = []
    result = None

    if request.method == 'POST':
        values['target'] = request.POST.get('target', '').strip()
        values['saved'] = request.POST.get('saved', '').strip()
        values['monthly'] = request.POST.get('monthly', '').strip()
        values['months'] = request.POST.get('months', '').strip()

        # 1. Read and check each box
        target = read_whole_number(values['target'], 'Your target amount', errors, required=True)
        saved = read_whole_number(values['saved'], 'Amount already saved', errors)
        monthly = read_whole_number(values['monthly'], 'Monthly saving', errors)
        months = read_whole_number(values['months'], 'Number of months', errors)

        if saved is None:
            saved = 0   # blank "already saved" means 0

        # 2. Check the rules between the boxes
        if target == 0:
            errors.append("Your target amount must be more than 0.")
        if monthly == 0:
            errors.append("Monthly saving must be more than 0.")
        if months == 0:
            errors.append("Number of months must be more than 0.")
        if months is not None and months > 1200:
            errors.append("Please use 1,200 months (100 years) or less.")
        if monthly is not None and months is not None:
            errors.append("Fill in only ONE of 'Monthly saving' or 'Number of months', not both.")
        if monthly is None and months is None and not errors:
            errors.append("Fill in either 'Monthly saving' or 'Number of months'.")

        # 3. If everything is fine, do the maths
        if not errors:
            remaining = max(target - saved, 0)      # how much is still left to save
            percent = min(saved * 100 // target, 100)   # progress bar, 0 to 100

            if remaining == 0:
                result = {'done': True, 'percent': 100}
            elif monthly is not None:
                # Months needed = remaining / monthly, rounded UP to the next whole month.
                # (a + b - 1) // b is a way to round up using only whole numbers.
                months_needed = (remaining + monthly - 1) // monthly
                years, extra_months = divmod(months_needed, 12)
                result = {
                    'done': False,
                    'mode': 'months',
                    'remaining': remaining,
                    'months': months_needed,
                    'years': years,
                    'extra_months': extra_months,
                    'percent': percent,
                }
            else:
                # Monthly saving needed = remaining / months, rounded UP to a whole RWF
                monthly_needed = (remaining + months - 1) // months
                result = {
                    'done': False,
                    'mode': 'monthly',
                    'remaining': remaining,
                    'monthly': monthly_needed,
                    'months': months,
                    'percent': percent,
                }

    return render(request, 'main/project_savings_goal.html', {
        'values': values,
        'errors': errors,
        'result': result,
    })


# ---------- Fintech project 2: Loan and Interest Calculator ----------

def read_rate(text, label, errors):
    """Read an interest rate like 18 or 18.5. Adds a friendly error and returns None if wrong."""
    text = text.replace(' ', '').replace(',', '.')   # allow "18,5" as well as "18.5"

    if text == '':
        errors.append(f"Please enter {label}.")
        return None

    # Allow digits with at most ONE dot. This rejects letters and minus signs.
    if len(text) > 8 or not text.replace('.', '', 1).isdecimal():
        errors.append(f"{label} must be a number like 18 or 18.5 (no letters or minus signs).")
        return None

    return Decimal(text)


def to_rwf(amount):
    """Round a Decimal amount to the nearest whole franc and return a normal whole number."""
    return int(amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def loan_calculator(request):
    # What the visitor typed, so the boxes keep their values after pressing Calculate
    values = {'amount': '', 'rate': '', 'months': ''}
    errors = []
    result = None

    if request.method == 'POST':
        values['amount'] = request.POST.get('amount', '').strip()
        values['rate'] = request.POST.get('rate', '').strip()
        values['months'] = request.POST.get('months', '').strip()

        # 1. Read and check each box
        amount = read_whole_number(values['amount'], 'Loan amount', errors, required=True)
        rate = read_rate(values['rate'], 'Yearly interest rate', errors)
        months = read_whole_number(values['months'], 'Loan length in months', errors, required=True)

        # 2. Check the limits
        if amount == 0:
            errors.append("Loan amount must be more than 0.")
        if months == 0:
            errors.append("Loan length must be at least 1 month.")
        if months is not None and months > 360:
            errors.append("Please use 360 months (30 years) or less.")
        if rate is not None and rate > 100:
            errors.append("Yearly interest rate must be 100% or less.")

        # 3. If everything is fine, do the maths
        if not errors:
            # Decimal is safer than normal decimals for money maths (no tiny rounding surprises)
            r = rate / Decimal(1200)        # monthly rate: yearly % / 12 months / 100

            if r == 0:
                payment = Decimal(amount) / months      # 0% interest: just split the loan equally
            else:
                # Standard loan formula:  payment = P * r / (1 - (1 + r) ** -n)
                payment = Decimal(amount) * r / (1 - (1 + r) ** -months)

            # Build the repayment table, one row per month
            balance = Decimal(amount)       # how much is still owed
            rows = []
            for month in range(1, months + 1):
                interest = balance * r              # interest is charged on what is still owed
                principal = payment - interest      # the rest of the payment pays off the loan
                balance = balance - principal
                if month == months:
                    balance = Decimal(0)            # remove tiny leftover from rounding
                rows.append({
                    'month': month,
                    'payment': to_rwf(payment),
                    'interest': to_rwf(interest),
                    'principal': to_rwf(principal),
                    'balance': to_rwf(balance),
                })

            total_paid = payment * months
            total_interest = total_paid - amount

            result = {
                'amount': amount,
                'months': months,
                'monthly_payment': to_rwf(payment),
                'total_paid': to_rwf(total_paid),
                'total_interest': to_rwf(total_interest),
                'interest_share': to_rwf(total_interest * 100 / total_paid),   # % of what you pay that is interest
                'rows': rows,
            }

    return render(request, 'main/project_loan_calculator.html', {
        'values': values,
        'errors': errors,
        'result': result,
    })


# ---------- Fintech project 3: Bill Splitter ----------

def read_tip(text, errors):
    """Read an optional tip percentage. A blank box means 0%."""
    if text.strip() == '':
        return Decimal(0)
    tip = read_rate(text, 'Tip percentage', errors)     # reuse the rate reader from project 2
    if tip is not None and tip > 100:
        errors.append("Tip percentage must be 100% or less.")
        return None
    return tip


def share_out(amount, weights):
    """Share a whole number of francs between people in proportion to their weights,
    so that the shares add up to EXACTLY the amount (no franc lost to rounding).
    This is called the 'largest remainder' method."""
    total_weight = sum(weights)

    # Step 1: give everyone their share rounded DOWN to a whole franc
    shares = [amount * w // total_weight for w in weights]

    # Step 2: some francs are left over. Give one extra franc each to the people
    # whose exact share had the biggest fraction cut off (ties go to the first person).
    left_over = amount - sum(shares)
    order = sorted(range(len(weights)), key=lambda i: (-(amount * weights[i] % total_weight), i))
    for i in order[:left_over]:
        shares[i] += 1
    return shares


def bill_splitter(request):
    # What the visitor typed, so the boxes keep their values after pressing a button
    equal_values = {'total': '', 'people': '', 'tip': ''}
    split_rows = [{'n': i, 'name': '', 'amount': ''} for i in range(1, 7)]   # 6 rows
    split_values = {'tip': '', 'shared': ''}
    equal_errors = []
    split_errors = []
    equal_result = None
    split_result = None

    if request.method == 'POST':
        mode = request.POST.get('mode', '')     # which form was sent: 'equal' or 'unequal'

        # ----- Form 1: equal split -----
        if mode == 'equal':
            equal_values['total'] = request.POST.get('total', '').strip()
            equal_values['people'] = request.POST.get('people', '').strip()
            equal_values['tip'] = request.POST.get('tip', '').strip()

            total = read_whole_number(equal_values['total'], 'Bill total', equal_errors, required=True)
            people = read_whole_number(equal_values['people'], 'Number of people', equal_errors, required=True)
            tip = read_tip(equal_values['tip'], equal_errors)

            if total == 0:
                equal_errors.append("Bill total must be more than 0.")
            if people is not None and not 2 <= people <= 50:
                equal_errors.append("Number of people must be between 2 and 50.")

            if not equal_errors:
                tip_amount = to_rwf(Decimal(total) * tip / Decimal(100))
                grand_total = total + tip_amount

                # Whole-number division: everyone pays 'base'. The 'remainder' francs
                # that do not divide evenly are paid one each by the first few people.
                base, remainder = divmod(grand_total, people)
                rows = []
                for i in range(1, people + 1):
                    rows.append({
                        'person': f"Person {i}",
                        'pays': base + 1 if i <= remainder else base,
                    })

                equal_result = {
                    'total': total,
                    'tip_amount': tip_amount,
                    'grand_total': grand_total,
                    'people': people,
                    'base': base,                   # what most people pay
                    'base_plus': base + 1,          # what the first few pay when it does not divide evenly
                    'remainder': remainder,
                    'rows': rows,
                    'check': sum(row['pays'] for row in rows),   # must equal grand_total
                }

        # ----- Form 2: unequal split -----
        elif mode == 'unequal':
            split_values['tip'] = request.POST.get('utip', '').strip()
            split_values['shared'] = request.POST.get('shared', '').strip()

            people_list = []    # (name, amount) for every row that was filled in
            for row in split_rows:
                i = row['n']
                row['name'] = request.POST.get(f'name{i}', '').strip()[:20]     # keep names short
                row['amount'] = request.POST.get(f'amount{i}', '').strip()

                if row['name'] == '' and row['amount'] == '':
                    continue    # empty row, skip it

                amount = read_whole_number(row['amount'], f"Amount for row {i}", split_errors, required=True)
                if amount == 0:
                    split_errors.append(f"Amount for row {i} must be more than 0.")
                elif amount is not None:
                    people_list.append((row['name'] or f"Person {i}", amount))

            tip = read_tip(split_values['tip'], split_errors)
            shared = read_whole_number(split_values['shared'], 'Shared cost', split_errors)
            if shared is None:
                shared = 0

            if len(people_list) < 2 and not split_errors:
                split_errors.append("Please fill in at least 2 rows (a name is optional, an amount is needed).")

            if not split_errors:
                amounts = [amount for name, amount in people_list]
                items_total = sum(amounts)

                tip_amount = to_rwf(Decimal(items_total) * tip / Decimal(100))
                extras = tip_amount + shared                # tip and shared cost, split by share
                extra_shares = share_out(extras, amounts)   # exact, no franc lost

                rows = []
                for (name, amount), extra in zip(people_list, extra_shares):
                    rows.append({'name': name, 'ordered': amount, 'extra': extra, 'pays': amount + extra})

                split_result = {
                    'items_total': items_total,
                    'tip_amount': tip_amount,
                    'shared': shared,
                    'extras_total': extras,              # tip + shared cost (used in the table footer)
                    'grand_total': items_total + extras,
                    'rows': rows,
                    'check': sum(row['pays'] for row in rows),   # must equal grand_total
                }

    return render(request, 'main/project_bill_splitter.html', {
        'equal_values': equal_values,
        'split_rows': split_rows,
        'split_values': split_values,
        'equal_errors': equal_errors,
        'split_errors': split_errors,
        'equal_result': equal_result,
        'split_result': split_result,
    })


# ---------- Fintech project 4: Mobile Money Wallet Simulator ----------
# Stage 1: wallet. Stage 2: send money. Stage 3: fees and history. Stage 4: QR payment request.

STARTING_BALANCE = 50000    # fake RWF every new demo wallet starts with
MAX_WALLETS = 300           # safety limit so the free database does not fill up
WALLET_LIFETIME_DAYS = 7    # demo wallets older than this are deleted automatically
FRIEND_NUMBER = 'DW-000000'     # the permanent "Demo Friend" wallet (random numbers never start with 000)
OPERATOR_NUMBER = 'DW-000001'   # the permanent "Demo Operator" wallet that receives all the fees
SPECIAL_NUMBERS = [FRIEND_NUMBER, OPERATOR_NUMBER]   # these two are never deleted and do not count toward the cap

REQUEST_LIFETIME_HOURS = 24     # an unpaid payment request expires after this many hours
MAX_OPEN_REQUESTS = 5           # one wallet can have at most this many open requests
CODE_LETTERS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'   # letters and digits that are hard to mix up (no O, 0, I, 1)

# The DEMO fee table. These are MADE-UP fees for learning, NOT real MTN or Airtel fees.
# Each line is (biggest amount in this band, fee in RWF). Change the numbers to try your own table.
# The last line must have a very big number so it catches every amount.
FEE_TABLE = [
    (1000, 0),
    (5000, 50),
    (20000, 150),
    (50000, 300),
    (1_000_000_000_000, 500),
]


def calculate_fee(amount):
    """Find the demo fee for a transfer amount using FEE_TABLE."""
    for biggest, fee in FEE_TABLE:
        if amount <= biggest:
            return fee
    return FEE_TABLE[-1][1]


def fee_table_rows():
    """Turn FEE_TABLE into rows the page can show, like '1,001 to 5,000'."""
    rows = []
    start = 1
    for biggest, fee in FEE_TABLE:
        if biggest == FEE_TABLE[-1][0]:
            label = f"{start:,} and above"
        else:
            label = f"{start:,} to {biggest:,}"
        rows.append({'range': label, 'fee': fee})
        start = biggest + 1
    return rows


def get_demo_friend():
    """Make sure the permanent Demo Friend wallet exists, so a visitor always has someone to send to."""
    friend, created = Wallet.objects.get_or_create(
        wallet_number=FRIEND_NUMBER,
        defaults={'nickname': 'Demo Friend', 'balance': STARTING_BALANCE},
    )
    return friend


def get_demo_operator():
    """Make sure the permanent Demo Operator wallet exists. It collects the fees, so no franc disappears."""
    operator, created = Wallet.objects.get_or_create(
        wallet_number=OPERATOR_NUMBER,
        defaults={'nickname': 'Demo Operator', 'balance': 0},
    )
    return operator


def read_nickname(text, errors):
    """Read a made-up nickname: 2 to 20 characters, letters, spaces and hyphens only.
    Digits are not allowed, so nobody can type a phone number by mistake."""
    text = ' '.join(text.split())      # remove extra spaces

    if text == '':
        errors.append("Please type a nickname for your demo wallet.")
        return None
    if not 2 <= len(text) <= 20:
        errors.append("The nickname must be between 2 and 20 characters.")
        return None
    if not all(ch.isalpha() or ch in ' -' for ch in text):
        errors.append("Use only letters, spaces and hyphens in the nickname (no numbers or symbols).")
        return None
    return text


def make_wallet_number():
    """Make a random, made-up wallet number like DW-482915 that no other wallet has."""
    while True:
        number = 'DW-' + str(secrets.randbelow(900000) + 100000)   # always 6 digits
        if not Wallet.objects.filter(wallet_number=number).exists():
            return number


def read_wallet_number(text, errors):
    """Read the wallet number to send to. Accepts DW-482915, dw-482915 or just 482915."""
    text = text.strip().upper().replace(' ', '')

    if text == '':
        errors.append("Please type the wallet number you want to send to.")
        return None

    if text.isdecimal() and len(text) == 6:
        text = 'DW-' + text                 # allow the number without the DW- part

    good_shape = len(text) == 9 and text.startswith('DW-') and text[3:].isdecimal() and text.isascii()
    if not good_shape:
        errors.append("A wallet number looks like DW-482915.")
        return None
    return text


def do_transfer(sender_id, receiver_id, amount):
    """Move fake money from one wallet to another and charge the demo fee.
    Returns (error message or None, fee).

    The sender pays amount + fee. The receiver gets the full amount. The Demo Operator gets the fee.
    So: sender loses (amount + fee) = receiver gains amount + operator gains fee. Every franc is accounted for.

    transaction.atomic() means ALL the balances change together, or none of them change.
    select_for_update() locks the wallets while we work, so two payments at the
    same moment cannot spend the same money."""
    fee = calculate_fee(amount)
    operator_id = get_demo_operator().id

    with transaction.atomic():
        locked = Wallet.objects.select_for_update().filter(id__in=[sender_id, receiver_id, operator_id]).order_by('id')
        wallets = {w.id: w for w in locked}
        sender = wallets.get(sender_id)
        receiver = wallets.get(receiver_id)
        operator = wallets.get(operator_id)

        if sender is None or receiver is None or operator is None:
            return "One of the wallets no longer exists. Please try again.", fee
        if amount + fee > sender.balance:
            return (
                f"Not enough balance. This transfer needs {amount:,} + {fee:,} fee = {amount + fee:,} RWF, "
                f"and the balance is {sender.balance:,} RWF."
            ), fee

        sender.balance -= amount + fee
        receiver.balance += amount
        operator.balance += fee
        for wallet in wallets.values():     # if the receiver IS the operator, it is the same object and saved once
            wallet.save(update_fields=['balance'])
        Transfer.objects.create(sender=sender, receiver=receiver, amount=amount, fee=fee)
    return None, fee


def build_history(wallet):
    """Make the list of this wallet's latest 20 transfers (sent and received) for the history table."""
    transfers = (
        Transfer.objects
        .filter(Q(sender=wallet) | Q(receiver=wallet))
        .select_related('sender', 'receiver')
        .order_by('-created_at', '-id')[:20]
    )
    rows = []
    for t in transfers:
        if t.sender_id == wallet.id:
            rows.append({
                'when': t.created_at,
                'sent': True,
                'other': f"{t.receiver.nickname} ({t.receiver.wallet_number})",
                'amount': t.amount,
                'fee': t.fee,
                'total': t.amount + t.fee,      # what left this wallet
            })
        else:
            rows.append({
                'when': t.created_at,
                'sent': False,
                'other': f"{t.sender.nickname} ({t.sender.wallet_number})",
                'amount': t.amount,
                'fee': 0,                       # the receiver pays no fee
                'total': t.amount,              # what arrived in this wallet
            })
    return rows


# ----- Stage 4: QR payment requests -----

def get_session_wallet(request):
    """Find this visitor's demo wallet from the session. Returns None if they have none."""
    wallet_id = request.session.get('wallet_id')
    if not wallet_id:
        return None
    wallet = Wallet.objects.filter(id=wallet_id).first()
    if wallet is None:
        request.session.pop('wallet_id', None)      # the wallet was deleted, forget it
    return wallet


def make_request_code():
    """Make a random 8-character code like K7M2XQ4P that no other payment request has."""
    while True:
        code = ''.join(secrets.choice(CODE_LETTERS) for _ in range(8))
        if not PaymentRequest.objects.filter(code=code).exists():
            return code


def request_status(pr):
    """The real state of a request: open, paid, cancelled or expired."""
    if pr.status == 'open' and pr.created_at <= timezone.now() - timedelta(hours=REQUEST_LIFETIME_HOURS):
        return 'expired'
    return pr.status


def count_open_requests(wallet):
    """How many requests from this wallet are still open (not paid, cancelled or expired)."""
    cutoff = timezone.now() - timedelta(hours=REQUEST_LIFETIME_HOURS)
    return PaymentRequest.objects.filter(wallet=wallet, status='open', created_at__gt=cutoff).count()


def pay_url(request, code):
    """The full link that goes inside the QR code, like https://.../pay/K7M2XQ4P/"""
    url = request.build_absolute_uri(reverse('wallet_pay', args=[code]))
    host = request.get_host().split(':')[0]
    if host not in ('127.0.0.1', 'localhost') and url.startswith('http://'):
        url = 'https://' + url[len('http://'):]     # Render serves the site over https
    return url


def make_qr(url):
    """Turn a link into a QR code picture. Returns a data URI that can go straight into <img src>."""
    return segno.make(url, error='m').png_data_uri(scale=6, border=3)


def pay_request(code, payer):
    """Pay a payment request from the payer's wallet. Returns (error message or None, fee).
    The request row is locked, so the same request can never be paid twice."""
    with transaction.atomic():
        pr = PaymentRequest.objects.select_for_update().filter(code=code).first()
        if pr is None:
            return "This payment request does not exist.", 0

        fee = calculate_fee(pr.amount)
        state = request_status(pr)
        if state == 'paid':
            return "This request has already been paid.", fee
        if state == 'cancelled':
            return "This request was cancelled.", fee
        if state == 'expired':
            return "This request has expired.", fee
        if pr.wallet_id == payer.id:
            return "You cannot pay your own request.", fee

        # Same transfer as stage 3: the payer pays amount + fee, the requester gets the full amount
        problem, fee = do_transfer(payer.id, pr.wallet_id, pr.amount)
        if problem:
            return problem, fee

        pr.status = 'paid'
        pr.paid_by_id = payer.id
        pr.paid_at = timezone.now()
        pr.save(update_fields=['status', 'paid_by', 'paid_at'])
    return None, fee


def build_request_list(request, wallet):
    """This wallet's latest 10 payment requests, with a QR code for each open one."""
    rows = []
    requests_found = PaymentRequest.objects.filter(wallet=wallet).select_related('paid_by').order_by('-created_at', '-id')[:10]
    for r in requests_found:
        state = request_status(r)
        row = {
            'id': r.id,
            'amount': r.amount,
            'fee': calculate_fee(r.amount),
            'state': state,
            'paid_by': r.paid_by.nickname if r.paid_by else '',
            'created': r.created_at,
            'url': '',
            'qr': '',
        }
        if state == 'open':
            row['url'] = pay_url(request, r.code)
            row['qr'] = make_qr(row['url'])
        rows.append(row)
    return rows


def wallet_simulator(request):
    errors = []             # errors for the "create wallet" form
    send_errors = []        # errors for the "send money" form
    request_errors = []     # errors for the "payment request" box
    nickname = ''
    send_values = {'to': '', 'amount': ''}
    request_values = {'amount': ''}

    # The permanent Demo Friend and Demo Operator wallets always exist
    get_demo_friend()
    get_demo_operator()

    # 1. Does this visitor already have a demo wallet? (we remember it with the session)
    wallet = get_session_wallet(request)

    # If the visitor came from a payment request link, remember which one (only if it really exists)
    pay_code = (request.POST.get('pay') or request.GET.get('pay') or '').strip().upper()[:8]
    if pay_code and not PaymentRequest.objects.filter(code=pay_code).exists():
        pay_code = ''

    # One-time messages saved before a redirect
    flash = request.session.pop('wallet_flash', None)
    request_flash = request.session.pop('request_flash', None)

    if request.method == 'POST':
        mode = request.POST.get('mode', '')     # which button was pressed

        # ----- Start over: delete this visitor's demo wallet -----
        if mode == 'reset':
            if wallet is not None and wallet.wallet_number not in SPECIAL_NUMBERS:
                wallet.delete()
            request.session.pop('wallet_id', None)
            return redirect(reverse('wallet_simulator') + '#demo')

        # ----- Create a demo wallet -----
        if mode == 'create' and wallet is None:
            nickname = request.POST.get('nickname', '').strip()
            clean_nickname = read_nickname(nickname, errors)

            # Tidy up: delete demo wallets older than 7 days (never the Demo Friend or Demo Operator)
            old = timezone.now() - timedelta(days=WALLET_LIFETIME_DAYS)
            Wallet.objects.filter(created_at__lt=old).exclude(wallet_number__in=SPECIAL_NUMBERS).delete()

            if not errors and Wallet.objects.exclude(wallet_number__in=SPECIAL_NUMBERS).count() >= MAX_WALLETS:
                errors.append("The demo is full right now. Please try again later.")

            if not errors:
                wallet = Wallet.objects.create(
                    nickname=clean_nickname,
                    wallet_number=make_wallet_number(),
                    balance=STARTING_BALANCE,
                )
                request.session['wallet_id'] = wallet.id
                if pay_code:
                    return redirect(reverse('wallet_pay', args=[pay_code]))   # back to the payment request they scanned
                return redirect(reverse('wallet_simulator') + '#demo')     # avoids re-sending the form on refresh

        # ----- Send money to another demo wallet -----
        elif mode == 'send' and wallet is not None:
            send_values['to'] = request.POST.get('to', '').strip()
            send_values['amount'] = request.POST.get('amount', '').strip()

            to_number = read_wallet_number(send_values['to'], send_errors)
            amount = read_whole_number(send_values['amount'], 'The amount', send_errors, required=True)

            if amount == 0:
                send_errors.append("The amount must be more than 0.")

            receiver = None
            if not send_errors:
                if to_number == wallet.wallet_number:
                    send_errors.append("You cannot send money to your own wallet.")
                else:
                    receiver = Wallet.objects.filter(wallet_number=to_number).first()
                    if receiver is None:
                        send_errors.append(f"No demo wallet has the number {to_number}.")

            if not send_errors:
                problem, fee = do_transfer(wallet.id, receiver.id, amount)
                if problem:
                    send_errors.append(problem)
                else:
                    wallet.refresh_from_db()    # get the new balance
                    request.session['wallet_flash'] = (
                        f"Sent {amount:,} RWF to {receiver.nickname} ({receiver.wallet_number}). "
                        f"Fee: {fee:,} RWF. Total taken from your wallet: {amount + fee:,} RWF. "
                        f"Your new balance is {wallet.balance:,} RWF."
                    )
                    return redirect(reverse('wallet_simulator') + '#send')

        # ----- Create a payment request (shown as a QR code) -----
        elif mode == 'create_request' and wallet is not None:
            request_values['amount'] = request.POST.get('request_amount', '').strip()
            amount = read_whole_number(request_values['amount'], 'The amount', request_errors, required=True)

            if amount == 0:
                request_errors.append("The amount must be more than 0.")
            if not request_errors and count_open_requests(wallet) >= MAX_OPEN_REQUESTS:
                request_errors.append(
                    f"You already have {MAX_OPEN_REQUESTS} open requests. Cancel one or wait for it to be paid."
                )

            if not request_errors:
                PaymentRequest.objects.create(code=make_request_code(), wallet=wallet, amount=amount)
                request.session['request_flash'] = (
                    f"Payment request for {amount:,} RWF created. Show the QR code to another demo wallet."
                )
                return redirect(reverse('wallet_simulator') + '#requests')

        # ----- Cancel one of my open payment requests -----
        elif mode == 'cancel_request' and wallet is not None:
            request_id = request.POST.get('request_id', '')
            if request_id.isdecimal():
                PaymentRequest.objects.filter(id=int(request_id), wallet=wallet, status='open').update(status='cancelled')
                request.session['request_flash'] = "Payment request cancelled."
            return redirect(reverse('wallet_simulator') + '#requests')

        # ----- Let the Demo Friend pay my request (so I can try it alone) -----
        elif mode == 'friend_pays' and wallet is not None:
            request_id = request.POST.get('request_id', '')
            pr = None
            if request_id.isdecimal():
                pr = PaymentRequest.objects.filter(id=int(request_id), wallet=wallet).first()

            if pr is None:
                request_errors.append("That payment request was not found.")
            else:
                problem, fee = pay_request(pr.code, get_demo_friend())
                if problem:
                    request_errors.append("Demo Friend could not pay this request. " + problem)
                else:
                    wallet.refresh_from_db()
                    request.session['request_flash'] = (
                        f"Demo Friend paid your request of {pr.amount:,} RWF. "
                        f"Your new balance is {wallet.balance:,} RWF."
                    )
                    return redirect(reverse('wallet_simulator') + '#requests')

    history = build_history(wallet) if wallet is not None else []
    requests_list = build_request_list(request, wallet) if wallet is not None else []

    return render(request, 'main/project_wallet_simulator.html', {
        'wallet': wallet,
        'errors': errors,
        'nickname': nickname,
        'starting_balance': STARTING_BALANCE,
        'send_errors': send_errors,
        'send_values': send_values,
        'flash': flash,
        'friend_number': FRIEND_NUMBER,
        'operator_number': OPERATOR_NUMBER,
        'fee_rows': fee_table_rows(),
        'history': history,
        'request_errors': request_errors,
        'request_values': request_values,
        'request_flash': request_flash,
        'requests_list': requests_list,
        'max_open_requests': MAX_OPEN_REQUESTS,
        'lifetime_hours': REQUEST_LIFETIME_HOURS,
        'pay_code': pay_code,
    })


def wallet_pay(request, code):
    """The page that opens when someone scans a payment request QR code."""
    code = code.strip().upper()[:20]
    wallet = get_session_wallet(request)
    errors = []
    flash = request.session.pop('wallet_flash', None)

    # ----- Pay the request -----
    if request.method == 'POST' and request.POST.get('mode') == 'pay' and wallet is not None:
        problem, fee = pay_request(code, wallet)
        if problem:
            errors.append(problem)
        else:
            paid = PaymentRequest.objects.select_related('wallet').filter(code=code).first()
            wallet.refresh_from_db()
            request.session['wallet_flash'] = (
                f"You paid {paid.amount:,} RWF to {paid.wallet.nickname} ({paid.wallet.wallet_number}). "
                f"Fee: {fee:,} RWF. Total taken from your wallet: {paid.amount + fee:,} RWF. "
                f"Your new balance is {wallet.balance:,} RWF."
            )
            return redirect(reverse('wallet_pay', args=[code]))

    pr = PaymentRequest.objects.select_related('wallet', 'paid_by').filter(code=code).first()
    if pr is None:
        return render(request, 'main/project_wallet_pay.html', {'pr': None}, status=404)

    fee = calculate_fee(pr.amount)
    return render(request, 'main/project_wallet_pay.html', {
        'pr': pr,
        'state': request_status(pr),
        'fee': fee,
        'total': pr.amount + fee,
        'wallet': wallet,
        'is_owner': wallet is not None and wallet.id == pr.wallet_id,
        'errors': errors,
        'flash': flash,
    })


def projects(request):
    projects = [
        {
            'icon': '🌐',
            'title': 'Personal Portfolio Website',
            'description': 'This site: a multi-page portfolio built with Django and deployed on Render with automatic updates from GitHub.',
            'tech': ['Python', 'Django', 'HTML/CSS', 'Render'],
            'live': 'https://wayne-portfolio-bo8z.onrender.com',
            'code': 'https://github.com/waynendahiro1-ux/wayne-portfolio',
        },
        {
            'icon': '💰',
            'title': 'Savings Goal Calculator',
            'description': 'Enter a target in RWF and either what you save each month or how many months you have. It works out the rest. For learning, not financial advice.',
            'tech': ['Python', 'Django', 'Fintech'],
            'page': 'savings_goal',     # opens the demo page on this site
            'code': 'https://github.com/waynendahiro1-ux/wayne-portfolio',
        },
        {
            'icon': '🏦',
            'title': 'Loan and Interest Calculator',
            'description': 'Enter a loan amount, a yearly interest rate and a length in months. See the monthly payment, the total interest and a month-by-month repayment table. For learning, not financial advice.',
            'tech': ['Python', 'Django', 'Fintech'],
            'page': 'loan_calculator',   # opens the demo page on this site
            'code': 'https://github.com/waynendahiro1-ux/wayne-portfolio',
        },
        {
            'icon': '🧾',
            'title': 'Bill Splitter',
            'description': 'Split a bill equally, or by what each person ordered, with an optional tip and shared cost. The shares always add up exactly. For learning, not financial advice.',
            'tech': ['Python', 'Django', 'Fintech'],
            'page': 'bill_splitter',     # opens the demo page on this site
            'code': 'https://github.com/waynendahiro1-ux/wayne-portfolio',
        },
        {
            'icon': '📱',
            'title': 'Mobile Money Wallet Simulator',
            'description': 'Create a demo wallet with fake money, send it to other demo wallets, see fees and your transaction history, and ask for money with a QR payment request. Fake money only, for learning, not financial advice.',
            'tech': ['Python', 'Django', 'Fintech'],
            'page': 'wallet_simulator',  # opens the demo page on this site
            'code': 'https://github.com/waynendahiro1-ux/wayne-portfolio',
        },
    ]
    return render(request, 'main/projects.html', {'projects': projects})