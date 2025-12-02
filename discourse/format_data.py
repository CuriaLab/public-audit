from bs4 import BeautifulSoup
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)


def format_discourse_data(
    raw_data: dict,
    dao_base_url: str,
) -> list:
    """Transforms raw discourse data into a standardized format
    for calculating other metrics.


    Returns a list of users and their topics, posts, and likes
    """
    all_activity_data = []
    single_user_dict = {
        user["user"]["username"]: user["user"] for user in raw_data["single_users"]
    }

    likes_dict = {user["username"]: user["user_actions"] for user in raw_data["likes"]}

    topics_dict = {topic["id"]: topic for topic in raw_data["topics"]}

    activities = get_topics_and_posts_activity(
        topics_dict, raw_data["posts"], dao_base_url
    )

    for user in raw_data["users"]:
        username = user["user"]["username"]
        user_likes_data = get_user_likes(username, likes_dict)

        if username in activities:
            user_topics_data = activities[username]["topics"]
            user_posts_data = activities[username]["posts"]

        else:
            user_topics_data = []
            user_posts_data = []

        all_activity_data.append(
            {
                "user": get_user_data(user, single_user_dict),
                "topics": get_topic_participants(
                    user_topics_data, raw_data["posts"], raw_data["likes"]
                ),
                "posts": user_posts_data,
                "likes": user_likes_data,
            }
        )

    return all_activity_data


def get_user_likes(username: str, likes_dict: dict) -> list:
    """Get a user's list of likes data"""
    likes = []
    if username in likes_dict:
        for like in likes_dict[username]:
            likes.append(
                {
                    "like_given_to": like["username"],
                    "like_given_to_id": like["user_id"],
                    "date": like["created_at"],
                    "topic_id": like["topic_id"],
                    "post_number": like["post_number"],
                }
            )

    return likes


def get_user_data(user_data: dict, raw_single_users_data: dict) -> dict:
    """Formats a user's data and combines them with the raw single users data"""
    username = user_data["user"]["username"]
    join_date = None

    if username in raw_single_users_data:
        if "created_at" in raw_single_users_data[username]:
            join_date = str(
                datetime.fromisoformat(
                    raw_single_users_data[username]["created_at"][:-1]
                ).strftime("%Y-%m-%d")
            )

    else:
        join_date = None

    return {
        "username": username,
        "user_id": user_data["id"],
        "name": user_data["user"]["name"] if "name" in user_data["user"] else None,
        "trust_level": user_data["user"]["trust_level"],
        "topics_entered": user_data["topics_entered"],
        "posts_read": user_data["posts_read"],
        "days_visited": user_data["days_visited"],
        "time_read": user_data["time_read"],
        "join_date": join_date,
    }


def get_topics_and_posts_activity(
    raw_topics_data: dict, raw_posts_data: dict, dao_base_url: str
) -> dict:
    """Uses the raw topic and post data to format every topics and posts."""
    activities = {}
    for count, post_thread in enumerate(raw_posts_data):
        topic_data = raw_topics_data[int(post_thread)]
        reply_list = {}
        category_id = raw_posts_data[post_thread]["category_id"]
        tags = raw_posts_data[post_thread]["tags"]
        for post_count, post in enumerate(raw_posts_data[post_thread]["posts"]):
            # Action codes are for admin actions like listing, unlisting, closing, or opening topic threads
            if "action_code" in post:
                continue

            if post["reply_count"] != 0:
                reply_list[post["post_number"]] = {
                    "created_at": post["created_at"],
                    "user": post["username"],
                }

            if post["username"] not in activities:
                activities[post["username"]] = {
                    "topics": [],
                    "posts": [],
                }

                post_likes = (
                    0
                    if post["actions_summary"] == []
                    else post["actions_summary"][0]["count"]
                )

            # Raw Data Meaning:
            # Quote Count = How many posts you quoted in your post
            # Reply Count = How many posts are replying to you or quoting your post / topic

            # Our Data Meaning:
            # Quote Count = How many posts in your thread contains quotes that reference the topic you created.
            # Reply Count = Same as above.
            if post["post_number"] == 1:
                activities[post["username"]]["topics"].append(
                    {
                        "topic_id": int(post_thread),
                        "topic_title": topic_data["title"],
                        "date": post["created_at"],
                        "view_count": topic_data["views"],
                        "read_count": post["reads"],
                        "post_count": topic_data["posts_count"],
                        "like_count": post_likes,
                        "category_id": category_id,
                        "tags": tags,
                        "quote_count": None,
                        "reply_count": post["reply_count"],
                        "last_posted_at": topic_data["last_posted_at"],
                        "participant_count": None,
                        "participant_list": None,
                        "body": post["cooked"],
                        "url": dao_base_url + f"/t/{post_thread}",
                    }
                )

            else:
                activities[post["username"]]["posts"].append(
                    {
                        "topic_id": int(post_thread),
                        "topic_title": topic_data["title"],
                        "topic_created_date": raw_posts_data[post_thread]["posts"][0][
                            "created_at"
                        ],
                        "topic_creator": raw_posts_data[post_thread]["posts"][0][
                            "username"
                        ],
                        "date": post["created_at"],
                        "post_number": post["post_number"],
                        "like_count": post_likes,
                        "body": post["cooked"],
                        "category_id": category_id,
                        "tags": tags,
                        "post_creator": post["username"],
                        "reply_count": post["reply_count"],
                        "reply_to_post_number": post["reply_to_post_number"],
                        "reply_to_post_number_created_date": (
                            reply_list[post["reply_to_post_number"]]["created_at"]
                            if post["reply_to_post_number"]
                            and post["reply_to_post_number"] in reply_list
                            else None
                        ),
                        "reply_to_post_username": (
                            reply_list[post["reply_to_post_number"]]["user"]
                            if post["reply_to_post_number"]
                            and post["reply_to_post_number"] in reply_list
                            else None
                        ),
                        "url": dao_base_url + f"/t/{post_thread}/{post['post_number']}",
                    }
                )

    return activities


def get_topic_participants(
    topic_activity: dict,
    all_posts_data: dict,
    all_likes_data: dict,
) -> dict:
    """Calculates each topic's participant and quote data,
    then return it."""
    for count, topic in enumerate(topic_activity):
        unique_users = []
        quote_count = 0
        for post in all_posts_data[topic["topic_id"]]["posts"]:
            soup = BeautifulSoup(post["cooked"], "html.parser")
            mentions = soup.find_all("aside", class_="quote no-group")
            for mention in mentions:
                # In case the quote has no post number
                if mention.has_attr("data-post"):
                    if mention["data-post"] == "1":
                        quote_count += 1
                        # In case the post quotes the post multiple times, we count as 1
                        continue
            if post["username"] not in unique_users:
                unique_users.append(post["username"])

        for like_count, like in enumerate(all_likes_data):
            for action in like["user_actions"]:
                if action["topic_id"] == topic["topic_id"]:
                    if action["acting_username"] not in unique_users:
                        unique_users.append(action["acting_username"])

        topic_activity[count]["participant_count"] = len(unique_users)
        topic_activity[count]["participant_list"] = unique_users
        topic_activity[count]["quote_count"] = quote_count

    return topic_activity
