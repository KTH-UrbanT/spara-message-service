import json


def insert_into_redis_client(conversation_list, redis_client, thread_id):
    print("Inserting into Redis:", thread_id)
    thread_name = f"thread:{thread_id}:messages"
    conversation_list_updated = []

    # check if thread exists
    if redis_client.exists(thread_name):
        # if it exists, check every message in the conversation_list
        for msg in conversation_list:
            # check if the message is already in the thread
            msg_in_redis = [
                json.loads(m) for m in redis_client.lrange(thread_name, 0, -1)
            ]
            matching_index = next(
                (
                    i
                    for i in range(len(msg_in_redis))
                    if msg["content"] == msg_in_redis[i]["content"]
                    and msg["role"] == msg_in_redis[i]["role"]
                    and int(msg["sent_at"].timestamp())
                    == int(msg_in_redis[i]["timestamp"])
                ),
                None,
            )

            payload = {
                "message_id": msg.get("message_id"),
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": int(msg["sent_at"].timestamp()),
                "rating_id": msg.get("rating_id"),
                "rating": msg.get("rating"),
                "version": msg.get("version"),
                "added_to_database": 1,
            }

            if matching_index is None:
                print("Message not in Redis:", msg["content"])
                # if not, add it to the thread
                conversation_list_updated.append(payload)
            else:
                existing_message = msg_in_redis[matching_index]
                merged_message = {
                    **existing_message,
                    "message_id": payload["message_id"] or existing_message.get("message_id"),
                    "rating_id": payload["rating_id"],
                    "rating": payload["rating"],
                    "version": payload["version"],
                }
                if merged_message != existing_message:
                    print("Updating message in Redis:", msg["content"])
                    redis_client.lset(
                        thread_name, matching_index, json.dumps(merged_message)
                    )
                else:
                    print("Message already in Redis:", msg["content"])
        print("conversation_list_updated:", conversation_list_updated)
    else:
        # if the thread does not exist, add all messages from the conversation_list
        conversation_list_updated = [
            {
                "message_id": msg.get("message_id"),
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": int(msg["sent_at"].timestamp()),
                "rating_id": msg.get("rating_id"),
                "rating": msg.get("rating"),
                "version": msg.get("version"),
                "added_to_database": 1,
            }
            for msg in conversation_list
        ]

    sorted_conversation_list = sorted(
        conversation_list_updated, key=lambda x: x["timestamp"]
    )
    for msg in sorted_conversation_list:
        redis_client.rpush(thread_name, json.dumps(msg))
        redis_client.publish("thread_events", json.dumps(msg))
