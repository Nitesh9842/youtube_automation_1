"""
Token system for AutoTube AI platform.
Defines plans, costs, and token management logic.
"""

from models import deduct_tokens, add_tokens, get_user_by_id, update_user
from datetime import datetime, timedelta

# ─── Plan Definitions ────────────────────────────────────────────────────────

PLANS = {
    'free': {
        'name': 'Free',
        'price_paise': 0,
        'price_display': '₹0',
        'tokens_monthly': 40,
        'daily_refill': 0,
        'max_tokens': 40,
        'features': [
            '40 tokens free on signup',
            'No daily refill',
            'AI video analysis',
            'Basic video editing',
            'YouTube auto-upload',
            'Community support',
        ],
        'badge_color': '#6b7280',
    },
    'pro': {
        'name': 'Pro',
        'price_paise': 39900,
        'price_display': '₹399/mo',
        'tokens_monthly': 250,
        'daily_refill': 10,
        'max_tokens': 500,
        'features': [
            '250 tokens monthly',
            '10 tokens daily refill',
            'Priority AI processing',
            'Advanced video editing',
            'Bulk upload support',
            'Priority support',
            'Analytics dashboard',
        ],
        'badge_color': '#8b5cf6',
        'popular': True,
    },
    'pro_yearly': {
        'name': 'Pro Yearly',
        'price_paise': 399900,
        'price_display': '₹3,999/yr',
        'tokens_monthly': 250,
        'daily_refill': 10,
        'max_tokens': 500,
        'yearly': True,
        'features': [
            '250 tokens every month',
            '3,000 tokens/year total',
            '10 tokens daily refill',
            'Priority AI processing',
            'Advanced video editing',
            'Bulk upload support',
            'Priority support',
            'Analytics dashboard',
        ],
        'badge_color': '#10b981',
        'savings': 'Save ₹789',
    },
}

# ─── Token Costs Per Action ──────────────────────────────────────────────────

TOKEN_COSTS = {
    'upload': 5,
    'ai_analyze': 3,
    'video_edit': 4,
    'download': 2,
}

# ─── Token Top-Up Packs ─────────────────────────────────────────────────────

TOKEN_PACKS = [
    {'id': 'pack_50', 'tokens': 50, 'price_paise': 9900, 'price_display': '₹99', 'savings': ''},
    {'id': 'pack_150', 'tokens': 150, 'price_paise': 24900, 'price_display': '₹249', 'savings': 'Save 17%'},
    {'id': 'pack_350', 'tokens': 350, 'price_paise': 49900, 'price_display': '₹499', 'savings': 'Save 29%'},
]


# ─── Functions ───────────────────────────────────────────────────────────────

def get_token_cost(action):
    """Get the token cost for an action."""
    return TOKEN_COSTS.get(action, 1)


def check_balance(user_id, action):
    """Check if user has enough tokens for an action. Returns (ok, cost, balance)."""
    cost = get_token_cost(action)
    user = get_user_by_id(user_id)
    if not user:
        return False, cost, 0
    return user['tokens_balance'] >= cost, cost, user['tokens_balance']


def use_tokens(user_id, action, task_id='', details=''):
    """Deduct tokens for an action. Returns (success, cost)."""
    cost = get_token_cost(action)
    ok = deduct_tokens(user_id, cost, action, task_id, details)
    return ok, cost


def refill_daily_tokens(user_id):
    """Refill daily tokens if enough time has passed (24h cooldown)."""
    user = get_user_by_id(user_id)
    if not user:
        return False

    plan = PLANS.get(user['plan'], PLANS['free'])

    # Free plan gets no daily refill — only one-time signup tokens
    if plan['daily_refill'] <= 0:
        return False

    last_refill = user.get('last_refill', '')

    if last_refill:
        try:
            last_dt = datetime.fromisoformat(last_refill)
            if datetime.utcnow() - last_dt < timedelta(hours=24):
                return False  # Too soon
        except ValueError:
            pass

    # Check max cap
    new_balance = min(
        user['tokens_balance'] + plan['daily_refill'],
        plan['max_tokens']
    )
    refill_amount = new_balance - user['tokens_balance']

    if refill_amount > 0:
        add_tokens(user_id, refill_amount)

    update_user(user_id, last_refill=datetime.utcnow().isoformat())
    return refill_amount > 0


def get_plan_info(plan_name):
    """Get plan details."""
    return PLANS.get(plan_name, PLANS['free'])


def get_all_plans():
    """Get all plans for pricing page."""
    return PLANS


def get_token_packs():
    """Get available token top-up packs."""
    return TOKEN_PACKS


def calculate_upload_cost(has_editing=False, has_music=False):
    """Calculate total token cost for an upload operation."""
    cost = TOKEN_COSTS['upload'] + TOKEN_COSTS['ai_analyze']
    if has_editing:
        cost += TOKEN_COSTS['video_edit']
    if has_music:
        cost += TOKEN_COSTS['download']
    return cost
