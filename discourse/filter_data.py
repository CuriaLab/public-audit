import json


def exclude_user_activities_by_trust_level_0(all_activities: list):
    """Filters user activity to exclude users by trust level > 0"""
    return [
        user_activity
        for user_activity in all_activities
        if user_activity["user"]["trust_level"] > 0
    ]


def exclude_user_activities_by_trust_level_1(all_activities: list):
    """Filters user activity to exclude users by trust level > 1"""
    return [
        user_activity
        for user_activity in all_activities
        if user_activity["user"]["trust_level"] > 1
    ]


def exclude_user_activities_by_exclude_data(all_activities: list, exclude_data: dict):
    """Filters user activity data by all exclude data (users, topics, categories"""
    if not exclude_data or (
        not exclude_data["user_bool"]
        and not exclude_data["topic_bool"]
        and not exclude_data["category_bool"]
    ):
        return all_activities

    exclude_usernames = [data["username"] for data in exclude_data["users"]]
    exclude_category_ids = exclude_data["category_ids"]
    exclude_topics = exclude_data["topics"]

    # Get all topics to exclude (category ids OR prefined exclude topics)
    all_exclude_topics = [
        topic["topic_id"]
        for user_activity in all_activities
        for topic in user_activity["topics"]
        if topic["category_id"] in exclude_category_ids
        or topic["topic_id"] in exclude_topics
    ]

    for user_activity in list(all_activities):
        if user_activity["user"]["username"] in exclude_usernames:
            all_activities.remove(user_activity)
            continue

        user_activity["topics"] = [
            topic
            for topic in user_activity["topics"]
            if topic["topic_id"] not in all_exclude_topics
        ]

        user_activity["posts"] = [
            post
            for post in user_activity["posts"]
            if post["topic_id"] not in all_exclude_topics
        ]

        user_activity["likes"] = [
            like
            for like in user_activity["likes"]
            if like["topic_id"] not in all_exclude_topics
        ]

    return all_activities
