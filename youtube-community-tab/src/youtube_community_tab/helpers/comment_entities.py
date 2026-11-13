"""Adapters for YouTube's entity-based comment format.

YouTube no longer sends ``commentRenderer`` objects for comments/replies. Threads and
replies now contain a ``commentViewModel`` that only holds keys, while the actual data
lives in ``frameworkUpdates.entityBatchUpdate.mutations`` as ``commentEntityPayload``
entities. These helpers resolve those entities and convert them into the legacy
``commentRenderer`` shape so the rest of the library (and its JSON output) keeps working.
"""

from .utils import safely_get_value_from_key


def get_comment_entities(data):
    """Map entityKey -> commentEntityPayload for every comment entity in a response."""
    mutations = safely_get_value_from_key(data, "frameworkUpdates", "entityBatchUpdate", "mutations", default=[]) or []
    entities = {}
    for mutation in mutations:
        payload = safely_get_value_from_key(mutation, "payload", "commentEntityPayload")
        if payload is not None:
            entities[mutation.get("entityKey", payload.get("key"))] = payload
    return entities


def _content_to_runs(content):
    text = safely_get_value_from_key(content, "content", default="") or ""
    command_runs = sorted(safely_get_value_from_key(content, "commandRuns", default=[]) or [], key=lambda run: run.get("startIndex", 0))

    # startIndex/length are expressed in UTF-16 code units
    encoded = text.encode("utf-16-le")

    def piece(start, end):
        return encoded[start * 2:end * 2].decode("utf-16-le", errors="replace")

    runs = []
    position = 0
    total = len(encoded) // 2
    for command_run in command_runs:
        start = command_run.get("startIndex", 0)
        end = min(start + command_run.get("length", 0), total)
        if start < position:
            continue
        if start > position:
            runs.append({"text": piece(position, start)})
        run = {"text": piece(start, end)}
        endpoint = safely_get_value_from_key(command_run, "onTap", "innertubeCommand")
        if endpoint is not None:
            run["navigationEndpoint"] = endpoint
        runs.append(run)
        position = end
    if position < total or not runs:
        runs.append({"text": piece(position, total)})
    return {"runs": runs}


def comment_entity_to_renderer(entity):
    """Convert a commentEntityPayload into a dict shaped like the legacy commentRenderer."""
    properties = entity.get("properties", {})
    author = entity.get("author", {})
    toolbar = entity.get("toolbar", {})

    renderer = {
        "commentId": properties.get("commentId"),
        "contentText": _content_to_runs(properties.get("content", {})),
        "publishedTimeText": {"runs": [{"text": properties.get("publishedTime", "")}]},
        "authorText": {"simpleText": author.get("displayName")},
        "authorThumbnail": {"thumbnails": [{"url": author["avatarThumbnailUrl"]}]} if author.get("avatarThumbnailUrl") else None,
        "authorEndpoint": {
            "browseEndpoint": safely_get_value_from_key(
                author, "channelCommand", "innertubeCommand", "browseEndpoint", default={"browseId": author.get("channelId")}
            )
        },
        "authorIsChannelOwner": bool(author.get("isCreator", False)),
        "voteCount": {"simpleText": toolbar.get("likeCountNotliked", "")},
        "replyCount": toolbar.get("replyCount"),
    }

    if author.get("sponsorBadgeUrl"):
        renderer["sponsorCommentBadge"] = {
            "sponsorCommentBadgeRenderer": {
                "customBadge": {"thumbnails": [{"url": author["sponsorBadgeUrl"]}]},
                "tooltip": author.get("sponsorBadgeA11y", ""),
            }
        }

    return renderer


def resolve_comment(item, entities):
    """Return a legacy commentRenderer dict from either a commentRenderer or a commentViewModel item.

    ``item`` is the value of a ``commentRenderer``/``commentViewModel`` key, or a thread's
    ``commentViewModel`` wrapper (which nests another ``commentViewModel``).
    """
    if item is None:
        return None
    if "commentViewModel" in item:
        item = item["commentViewModel"]
    if "commentId" in item and "commentKey" not in item:
        return item  # already a legacy commentRenderer
    entity = entities.get(item.get("commentKey"))
    if entity is None:
        return None
    return comment_entity_to_renderer(entity)


def resolve_thread_comment(thread, entities):
    """Return the top-level comment (legacy shape) of a commentThreadRenderer."""
    legacy = safely_get_value_from_key(thread, "comment", "commentRenderer")
    if legacy is not None:
        return legacy
    return resolve_comment(thread.get("commentViewModel"), entities)


def get_replies_continuation(thread):
    """Return (token, clickTrackingParams) for a thread's replies, or (None, None)."""
    endpoint = safely_get_value_from_key(
        thread, "replies", "commentRepliesRenderer", "contents", 0, "continuationItemRenderer", "continuationEndpoint"
    )
    return (
        safely_get_value_from_key(endpoint, "continuationCommand", "token"),
        safely_get_value_from_key(endpoint, "clickTrackingParams"),
    )


def get_continuation_items(data, action):
    """Collect continuationItems from every onResponseReceivedEndpoints entry of the given action type."""
    items = []
    found = False
    for endpoint in safely_get_value_from_key(data, "onResponseReceivedEndpoints", default=[]) or []:
        if action in endpoint:
            found = True
            items += endpoint[action].get("continuationItems", [])
    return items if found else None
