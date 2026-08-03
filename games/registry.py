active_game_of = {}

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
