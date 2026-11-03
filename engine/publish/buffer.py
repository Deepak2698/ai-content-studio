"""Buffer (or any other scheduler) adapter: placeholder.

Buffer's public API changed in 2025 (new GraphQL API, access by application). When you have access,
fill in post() here: upload reel.mp4 + caption.txt and return {"id": ..., "url": ...}.
Until then the engine never calls it, because ready() returns False.
"""
from .. import config


def ready():
    if not config.flag("BUFFER_ENABLED"):
        return False, "BUFFER_ENABLED is not true"
    return False, "Buffer adapter not implemented yet (see engine/publish/buffer.py)"


def post(video, caption_file, meta, log):
    raise NotImplementedError("Buffer adapter not implemented yet")


def metrics(post_id):
    return {}
