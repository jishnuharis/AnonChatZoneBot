# Tracks which mini-game (if any) a user is currently playing, so /next and /stop
# can cleanly end whatever game is running without every command needing to know
# about every game module individually.

active_game_of = {}  # user_id -> game_type (string key, see GAMES in commands/games.py)

# game_type -> async def force_end_game(context, user_id) function, filled in by main.py
# once all game modules are imported (avoids circular imports).
_force_end_handlers = {}


def register(user_id: int, game_type: str):
    active_game_of[user_id] = game_type


def unregister(user_id: int):
    active_game_of.pop(user_id, None)


def get_active(user_id: int):
    return active_game_of.get(user_id)


def set_force_end_handler(game_type: str, handler):
    _force_end_handlers[game_type] = handler


def other_player(game: dict, user_id: int):
    """Returns the other player in a 2-player game dict, or None if user_id isn't
    a recognized player. Deliberately uses next(..., None) instead of a bare
    next(generator) - a bare next() with no match raises StopIteration, which
    (per PEP 479) surfaces from inside an async function as
    'RuntimeError: coroutine raised StopIteration' and crashes the handler.
    Every game module should go through this helper instead of calling next()
    on game["players"] directly."""
    return next((u for u in game["players"] if u != user_id), None)


async def end_any_active_game(context, user_id: int):
    game_type = active_game_of.get(user_id)
    if not game_type:
        return
    handler = _force_end_handlers.get(game_type)
    if handler:
        await handler(context, user_id)
    else:
        unregister(user_id)
