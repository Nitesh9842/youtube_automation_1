"""
Payments Blueprint for AutoTube AI platform.
Stripe integration for plan subscriptions and token top-ups.
"""

import os
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

# Stripe setup (optional — works without keys in dev mode)
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

stripe = None
if STRIPE_SECRET_KEY:
    try:
        import stripe as stripe_lib
        stripe_lib.api_key = STRIPE_SECRET_KEY
        stripe = stripe_lib
        logger.info("✅ Stripe initialized")
    except ImportError:
        logger.warning("⚠️ stripe package not installed — payments will use mock mode")
else:
    logger.info("ℹ️ No STRIPE_SECRET_KEY — payments in mock mode")


def _stripe_available():
    return stripe is not None and STRIPE_SECRET_KEY


# ─── Routes ──────────────────────────────────────────────────────────────────

@payments_bp.route('/api/pricing')
def get_pricing():
    """Return pricing plans and token packs."""
    return jsonify({
        'plans': {k: {**v, 'key': k} for k, v in PLANS.items()},
        'token_packs': TOKEN_PACKS,
        'stripe_available': _stripe_available(),
        'publishable_key': STRIPE_PUBLISHABLE_KEY if _stripe_available() else '',
    })


@payments_bp.route('/api/create-checkout', methods=['POST'])
@login_required
def create_checkout():
    """Create a Stripe Checkout session for plan upgrade or token pack."""
    data = request.get_json(silent=True) or {}
    item_type = data.get('type', '')  # 'plan' or 'pack'
    item_id = data.get('id', '')

    if not _stripe_available():
        # Mock mode — instant "purchase"
        if item_type == 'plan' and item_id in PLANS:
            plan = PLANS[item_id]
            tokens = plan['tokens_monthly']
            update_user(current_user.id, plan=item_id)
            add_tokens(current_user.id, tokens)
            create_transaction(
                current_user.id, plan['price_cents'], tokens,
                plan_purchased=item_id, stripe_session_id='mock_' + item_id
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
                    current_user.id, pack['price_cents'], pack['tokens'],
                    stripe_session_id='mock_' + item_id
                )
                return jsonify({
                    'success': True, 'mock': True,
                    'message': f'{pack["tokens"]} tokens added to your account!'
                })
        return jsonify({'success': False, 'error': 'Invalid item'}), 400

    # Real Stripe checkout
    try:
        base_url = request.host_url.rstrip('/')

        if item_type == 'plan' and item_id in PLANS:
            plan = PLANS[item_id]
            session_obj = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f'YouTube Auto — {plan["name"]} Plan',
                            'description': f'{plan["tokens_monthly"]} tokens/month',
                        },
                        'unit_amount': plan['price_cents'],
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=f'{base_url}/pricing?success=1',
                cancel_url=f'{base_url}/pricing?cancelled=1',
                metadata={
                    'user_id': str(current_user.id),
                    'type': 'plan',
                    'plan_id': item_id,
                    'tokens': str(plan['tokens_monthly']),
                },
            )
            return jsonify({'success': True, 'checkout_url': session_obj.url})

        elif item_type == 'pack':
            pack = next((p for p in TOKEN_PACKS if p['id'] == item_id), None)
            if not pack:
                return jsonify({'success': False, 'error': 'Invalid pack'}), 400
            session_obj = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f'Token Pack — {pack["tokens"]} tokens',
                        },
                        'unit_amount': pack['price_cents'],
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=f'{base_url}/pricing?success=1',
                cancel_url=f'{base_url}/pricing?cancelled=1',
                metadata={
                    'user_id': str(current_user.id),
                    'type': 'pack',
                    'pack_id': item_id,
                    'tokens': str(pack['tokens']),
                },
            )
            return jsonify({'success': True, 'checkout_url': session_obj.url})

        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@payments_bp.route('/api/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events."""
    if not _stripe_available():
        return jsonify({'received': True}), 200

    payload = request.data
    sig_header = request.headers.get('Stripe-Signature', '')

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            event = stripe.Event.construct_from(
                request.get_json(silent=True), stripe.api_key
            )
    except Exception as e:
        logger.error(f"Webhook verification failed: {e}")
        return jsonify({'error': 'Invalid signature'}), 400

    if event['type'] == 'checkout.session.completed':
        session_data = event['data']['object']
        meta = session_data.get('metadata', {})
        user_id = meta.get('user_id', '')
        tokens = int(meta.get('tokens', 0))

        if user_id and tokens:
            if meta.get('type') == 'plan':
                plan_id = meta.get('plan_id', 'pro')
                update_user(user_id, plan=plan_id)
                add_tokens(user_id, tokens)
                create_transaction(
                    user_id, session_data.get('amount_total', 0), tokens,
                    plan_purchased=plan_id,
                    stripe_session_id=session_data.get('id', '')
                )
            elif meta.get('type') == 'pack':
                add_tokens(user_id, tokens)
                create_transaction(
                    user_id, session_data.get('amount_total', 0), tokens,
                    stripe_session_id=session_data.get('id', '')
                )
            logger.info(f"Payment completed: user={user_id}, tokens={tokens}")

    return jsonify({'received': True}), 200


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
