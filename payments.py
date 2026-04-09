"""
Payments Blueprint for AutoTube AI platform.
Razorpay integration for plan subscriptions and token top-ups.
"""

import os
import hmac
import hashlib
import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import (
    get_user_by_id, update_user, add_tokens,
    create_transaction, get_transactions
)
from token_system import PLANS, TOKEN_PACKS

logger = logging.getLogger(__name__)

payments_bp = Blueprint('payments', __name__)

# Razorpay setup (optional — works without keys in dev mode)
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')

razorpay_client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    try:
        import razorpay
        razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        logger.info("✅ Razorpay initialized")
    except ImportError:
        logger.warning("⚠️ razorpay package not installed — payments will use mock mode")
else:
    logger.info("ℹ️ No RAZORPAY_KEY_ID — payments in mock mode")


def _razorpay_available():
    return razorpay_client is not None and RAZORPAY_KEY_ID


# ─── Routes ──────────────────────────────────────────────────────────────────

@payments_bp.route('/api/pricing')
def get_pricing():
    """Return pricing plans and token packs."""
    return jsonify({
        'plans': {k: {**v, 'key': k} for k, v in PLANS.items()},
        'token_packs': TOKEN_PACKS,
        'razorpay_available': _razorpay_available(),
        'razorpay_key_id': RAZORPAY_KEY_ID if _razorpay_available() else '',
    })


@payments_bp.route('/api/create-checkout', methods=['POST'])
@login_required
def create_checkout():
    """Create a Razorpay Order for plan upgrade or token pack."""
    data = request.get_json(silent=True) or {}
    item_type = data.get('type', '')  # 'plan' or 'pack'
    item_id = data.get('id', '')

    if not _razorpay_available():
        # Mock mode — instant "purchase"
        if item_type == 'plan' and item_id in PLANS:
            plan = PLANS[item_id]
            tokens = plan['tokens_monthly']
            # For yearly plans, store as 'pro' plan but add extra info
            plan_key = 'pro' if item_id in ('pro', 'pro_yearly') else item_id
            update_user(current_user.id, plan=plan_key)
            add_tokens(current_user.id, tokens)
            create_transaction(
                current_user.id, plan['price_paise'], tokens,
                plan_purchased=item_id, razorpay_payment_id='mock_' + item_id
            )
            return jsonify({
                'success': True, 'mock': True,
                'message': f'Plan upgraded to {plan["name"]}! {tokens} tokens added.'
            })
        elif item_type == 'pack':
            pack = next((p for p in TOKEN_PACKS if p['id'] == item_id), None)
            if pack:
                add_tokens(current_user.id, pack['tokens'])
                create_transaction(
                    current_user.id, pack['price_paise'], pack['tokens'],
                    razorpay_payment_id='mock_' + item_id
                )
                return jsonify({
                    'success': True, 'mock': True,
                    'message': f'{pack["tokens"]} tokens added to your account!'
                })
        return jsonify({'success': False, 'error': 'Invalid item'}), 400

    # Real Razorpay order
    try:
        if item_type == 'plan' and item_id in PLANS:
            plan = PLANS[item_id]
            order_data = {
                'amount': plan['price_paise'],
                'currency': 'INR',
                'receipt': f'plan_{item_id}_{current_user.id}',
                'notes': {
                    'user_id': str(current_user.id),
                    'type': 'plan',
                    'plan_id': item_id,
                    'tokens': str(plan['tokens_monthly']),
                }
            }
            order = razorpay_client.order.create(data=order_data)
            user = get_user_by_id(current_user.id)
            return jsonify({
                'success': True,
                'order_id': order['id'],
                'amount': plan['price_paise'],
                'currency': 'INR',
                'razorpay_key_id': RAZORPAY_KEY_ID,
                'plan_name': plan['name'],
                'user_email': user.get('email', '') if user else '',
                'user_name': user.get('username', '') if user else '',
            })

        elif item_type == 'pack':
            pack = next((p for p in TOKEN_PACKS if p['id'] == item_id), None)
            if not pack:
                return jsonify({'success': False, 'error': 'Invalid pack'}), 400
            order_data = {
                'amount': pack['price_paise'],
                'currency': 'INR',
                'receipt': f'pack_{item_id}_{current_user.id}',
                'notes': {
                    'user_id': str(current_user.id),
                    'type': 'pack',
                    'pack_id': item_id,
                    'tokens': str(pack['tokens']),
                }
            }
            order = razorpay_client.order.create(data=order_data)
            user = get_user_by_id(current_user.id)
            return jsonify({
                'success': True,
                'order_id': order['id'],
                'amount': pack['price_paise'],
                'currency': 'INR',
                'razorpay_key_id': RAZORPAY_KEY_ID,
                'plan_name': f'{pack["tokens"]} Token Pack',
                'user_email': user.get('email', '') if user else '',
                'user_name': user.get('username', '') if user else '',
            })

        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    except Exception as e:
        logger.error(f"Razorpay order creation error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@payments_bp.route('/api/razorpay-verify', methods=['POST'])
@login_required
def razorpay_verify():
    """Verify Razorpay payment signature and fulfill the order."""
    data = request.get_json(silent=True) or {}
    razorpay_order_id = data.get('razorpay_order_id', '')
    razorpay_payment_id = data.get('razorpay_payment_id', '')
    razorpay_signature = data.get('razorpay_signature', '')
    item_type = data.get('type', '')
    item_id = data.get('id', '')

    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        return jsonify({'success': False, 'error': 'Missing payment details'}), 400

    # Verify signature using HMAC SHA256
    try:
        message = f'{razorpay_order_id}|{razorpay_payment_id}'
        generated_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        if generated_signature != razorpay_signature:
            logger.warning(f"Razorpay signature mismatch for order {razorpay_order_id}")
            return jsonify({'success': False, 'error': 'Payment verification failed'}), 400

    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return jsonify({'success': False, 'error': 'Verification error'}), 500

    # Signature is valid — fulfill the order
    try:
        if item_type == 'plan' and item_id in PLANS:
            plan = PLANS[item_id]
            tokens = plan['tokens_monthly']
            plan_key = 'pro' if item_id in ('pro', 'pro_yearly') else item_id
            update_user(current_user.id, plan=plan_key)
            add_tokens(current_user.id, tokens)
            create_transaction(
                current_user.id, plan['price_paise'], tokens,
                plan_purchased=item_id,
                razorpay_payment_id=razorpay_payment_id
            )
            logger.info(f"Plan upgraded: user={current_user.id}, plan={item_id}, tokens={tokens}")
            return jsonify({
                'success': True,
                'message': f'Plan upgraded to {plan["name"]}! {tokens} tokens added.'
            })

        elif item_type == 'pack':
            pack = next((p for p in TOKEN_PACKS if p['id'] == item_id), None)
            if not pack:
                return jsonify({'success': False, 'error': 'Invalid pack'}), 400
            add_tokens(current_user.id, pack['tokens'])
            create_transaction(
                current_user.id, pack['price_paise'], pack['tokens'],
                razorpay_payment_id=razorpay_payment_id
            )
            logger.info(f"Token pack purchased: user={current_user.id}, pack={item_id}, tokens={pack['tokens']}")
            return jsonify({
                'success': True,
                'message': f'{pack["tokens"]} tokens added to your account!'
            })

        return jsonify({'success': False, 'error': 'Invalid item type'}), 400

    except Exception as e:
        logger.error(f"Order fulfillment error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@payments_bp.route('/api/billing')
@login_required
def get_billing():
    """Get billing history for current user."""
    transactions = get_transactions(current_user.id)
    user = get_user_by_id(current_user.id)
    return jsonify({
        'transactions': transactions,
        'plan': user['plan'] if user else 'free',
        'tokens_balance': user['tokens_balance'] if user else 0,
    })
