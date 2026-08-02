import time

from telegram.ext import ContextTypes

from security import safe_tele_func_call
from subscription import is_subscribed

import init

# How long someone can sit in the queue before we stop caring about shared
# interests and just pair them with whoever's oldest in line.
MATCH_GRACE_PERIOD = 15  # seconds


def _prefs(user_id: int) -> int:
    return init.user_details.get(user_id, {}).get("preferences", 0)


def _overlap_score(a: int, b: int) -> int:
    return bin(_prefs(a) & _prefs(b)).count("1")


def _best_match_for(user_id: int):
    best_id, best_score = None, -1
    for other in init.waiting_users:
        if other == user_id:
            continue
        score = _overlap_score(user_id, other)
        if score > best_score:
            best_score = score
            best_id = other
    return best_id, best_score


def _partner_details_line(viewer_id: int, partner_id: int) -> str:
    """Subscriber-only perk: reveal the partner's age/gender/country. Gated on the
    *viewer's* own subscription, not the partner's - each side sees extra info
    about the other only if they themselves paid for it."""
    if not is_subscribed(viewer_id):
        return ""
    partner = init.user_details.get(partner_id, {})
    gender = "Male" if partner.get("gender") == "M" else "Female" if partner.get("gender") == "F" else "Unknown"
    age = partner.get("age") or "Unknown"
    country = partner.get("country") or "Unknown"
    return f"\n<i>👤 {gender}, {age} — {country}</i>"


async def _pair_users(context: ContextTypes.DEFAULT_TYPE, user1: int, user2: int):
    init.active_pairs[user1] = user2
    init.active_pairs[user2] = user1
    init.user_details[user1]["partner_id"] = user2
    init.user_details[user2]["partner_id"] = user1

    uv1 = init.user_details[user1]["votes"]
    uv2 = init.user_details[user2]["votes"]

    shared = _overlap_score(user1, user2)
    shared_note = f"\n<i>You have {shared} shared interest{'s' if shared != 1 else ''}!</i> 🏷️" if shared else ""

    details1 = _partner_details_line(user1, user2)
    details2 = _partner_details_line(user2, user1)

    await safe_tele_func_call(
        context.bot.send_message, chat_id=user1,
        text=f"🎯 <b>Found someone.... Say hi!!</b>\n<i>Rating:</i> {uv2['up']} 👍 {uv2['down']} 👎{shared_note}{details1}\n/next <i>- Next Chat</i>\n/stop <i>- Stop Chat</i>",
        parse_mode="HTML",
    )
    await safe_tele_func_call(
        context.bot.send_message, chat_id=user2,
        text=f"🎯 <b>Found someone.... Say hi!!</b>\n<i>Rating:</i> {uv1['up']} 👍 {uv1['down']} 👎{shared_note}{details2}\n/next <i>- Next Chat</i>\n/stop <i>- Stop Chat</i>",
        parse_mode="HTML",
    )

    init.dirty_users.update([user1, user2])


async def enqueue_and_match(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Adds user_id to the queue (if not already there) and tries an immediate
    interest-based match against everyone else currently waiting."""
    if user_id not in init.waiting_users:
        init.waiting_users.append(user_id)
        init.wait_started[user_id] = time.time()

    if len(init.waiting_users) < 2:
        return

    partner, score = _best_match_for(user_id)
    if partner is not None and score > 0:
        init.waiting_users.remove(user_id)
        init.waiting_users.remove(partner)
        init.wait_started.pop(user_id, None)
        init.wait_started.pop(partner, None)
        await _pair_users(context, user_id, partner)


async def queue_sweep(context: ContextTypes.DEFAULT_TYPE):
    """Runs periodically. Pairs up anyone who's been waiting past the grace
    period with the next oldest person in line, ignoring interest overlap."""
    now = time.time()
    while len(init.waiting_users) >= 2:
        # Oldest waiter first
        oldest = min(init.waiting_users, key=lambda u: init.wait_started.get(u, now))
        if now - init.wait_started.get(oldest, now) < MATCH_GRACE_PERIOD:
            break

        candidates = [u for u in init.waiting_users if u != oldest]
        if not candidates:
            break
        # Prefer someone who shares an interest even in the fallback path, but
        # never let it block the match past the grace period
        best_id, best_score = None, -1
        for other in candidates:
            score = _overlap_score(oldest, other)
            if score > best_score:
                best_score = score
                best_id = other

        init.waiting_users.remove(oldest)
        init.waiting_users.remove(best_id)
        init.wait_started.pop(oldest, None)
        init.wait_started.pop(best_id, None)
        await _pair_users(context, oldest, best_id)
