import json


def insert_into_redis_client(conversation_list, redis_client, thread_name):
    print("Inserting into Redis:", thread_name)
    conversation_list_updated = []

    # check if thread exists
    if redis_client.exists(thread_name):
        # if it exists, check every message in the conversation_list
        for msg in conversation_list:
            # check if the message is already in the thread
            msg_in_redis = [
                json.loads(m) for m in redis_client.lrange(thread_name, 0, -1)
            ]

            if not any(
                [
                    msg["content"] == msg_in_redis[i]["content"]
                    and msg["role"] == msg_in_redis[i]["role"]
                    and int(msg["sent_at"].timestamp())
                    == int(msg_in_redis[i]["timestamp"])
                    for i in range(len(msg_in_redis))
                ]
            ):
                print("Message not in Redis:", msg["content"])
                # if not, add it to the thread
                conversation_list_updated.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                        "timestamp": int(msg["sent_at"].timestamp()),
                        "added_to_database": 1,
                    }
                )
            else:
                print("Message already in Redis:", msg["content"])
                # if the message is already in the thread, skip it
                continue
        print("conversation_list_updated:", conversation_list_updated)
    else:
        # if the thread does not exist, add all messages from the conversation_list
        conversation_list_updated = [
            {
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": int(msg["sent_at"].timestamp()),
                "added_to_database": 1,
            }
            for msg in conversation_list
        ]

    sorted_conversation_list = sorted(
        conversation_list_updated, key=lambda x: x["timestamp"]
    )
    for msg in sorted_conversation_list:
        redis_client.rpush(thread_name, json.dumps(msg))
