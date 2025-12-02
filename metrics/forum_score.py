import logging
from typing import List

logging.basicConfig(level=logging.INFO)


def calculate_all_forum_score(
    all_activities: list,
    config_data: dict,
) -> list:
    """Calculates all user's forum scores and returns it in a list ordered
    by their forum score."""
    added_all_activities = add_proposal_data(all_activities, config_data)
    activity_dict = get_total_metrics(added_all_activities)

    all_proposal_topics_likes_received = get_all_avg_proposal_topics_like_received(
        added_all_activities
    )

    all_likes_dict = get_all_likes_received(added_all_activities)
    forum_score_list = []

    for user_activity in all_activities:
        forum_score_list.append(
            calculate_single_forum_score(
                user_activity,
                activity_dict,
                all_likes_dict,
                all_proposal_topics_likes_received,
                config_data["forum_score_weights"],
            )
        )

    return sorted(forum_score_list, key=lambda x: x["forum_score"], reverse=True)


def get_total_metrics(all_activities: list) -> dict:
    """Gets the total amount of various metrics for percentile calculation"""
    activity_dict = {
        "all_days_visited": [],
        "all_time_read": [],
        "all_topic_count": [],
        "all_post_count": [],
        "all_proposal_count": [],
        "all_proposal_post_count": [],
    }

    for user in all_activities:
        activity_dict["all_days_visited"].append(user["user"]["days_visited"])
        activity_dict["all_time_read"].append(user["user"]["time_read"])
        activity_dict["all_topic_count"].append(len(user["topics"]))
        activity_dict["all_post_count"].append(len(user["posts"]))
        activity_dict["all_proposal_count"].append(len(user["proposal_topics"]))
        activity_dict["all_proposal_post_count"].append(len(user["proposal_posts"]))

    return activity_dict


def calculate_single_forum_score(
    user_activity: dict,
    activity_dict: dict,
    all_likes_dict: dict,
    all_proposal_topics_likes_received: list,
    weights: dict,
) -> dict:
    # calculate activeness score
    activeness_dict = calculate_activeness_score(user_activity, activity_dict, weights)

    # calculate overall topic score
    overall_topic_dict = calculate_overall_topic_score(
        user_activity, activity_dict, all_likes_dict, weights
    )

    # calculate proposal score
    proposal_dict = calculate_proposal_score(
        user_activity, activity_dict, all_proposal_topics_likes_received, weights
    )

    # calculate final score
    return calculate_final_score(
        user_activity, proposal_dict, overall_topic_dict, activeness_dict, weights
    )


def calculate_final_score(
    user_activity: dict,
    proposal_dict: dict,
    overall_topic_dict: dict,
    activeness_dict: dict,
    weights: dict,
):
    """Takes all the lesser score dicts and calculates the final forum score for a user"""
    sum_proposal_weights = (
        weights["prop_int_weights"]
        + weights["prop_disc_weights"]
        + weights["prop_like_rec_weights"]
    )

    sum_overall_topic_weights = (
        weights["user_topic_count_weights"]
        + weights["user_post_count_weights"]
        + weights["user_like_rec_weights"]
    )

    sum_activeness_weights = (
        weights["user_day_visit_weights"] + weights["user_time_read_weights"]
    )

    sum_all_weights = weights["max_score_weights"] * (
        (sum_proposal_weights * weights["proposal_score_weights"])
        + (sum_overall_topic_weights * weights["overall_topic_score_weights"])
        + (sum_activeness_weights * weights["activeness_score_weights"])
    )

    forum_score = (
        100
        * (
            (proposal_dict["proposal_score"] * weights["proposal_score_weights"])
            + (
                overall_topic_dict["overall_topic_score"]
                * weights["overall_topic_score_weights"]
            )
            + (
                activeness_dict["activeness_score"]
                * weights["activeness_score_weights"]
            )
        )
    ) / (sum_all_weights * 100 * weights["max_score_weights"])

    forum_score_dict = {
        "user_id": user_activity["user"]["user_id"],
        "user_name": user_activity["user"]["username"],
        "forum_score": forum_score,
    }

    forum_score_dict.update(proposal_dict)
    forum_score_dict.update(overall_topic_dict)
    forum_score_dict.update(activeness_dict)

    return forum_score_dict


def calculate_activeness_score(
    user_activity: dict, activity_dict: dict, weights: dict
) -> dict:
    user_data = user_activity["user"]

    all_days_visited = activity_dict["all_days_visited"]
    days_visited_percentile = calculate_percentile(
        user_data["days_visited"], all_days_visited
    )

    all_time_read = activity_dict["all_time_read"]
    time_read_percentile = calculate_percentile(user_data["time_read"], all_time_read)

    activeness_score = (days_visited_percentile * weights["user_day_visit_weights"]) + (
        time_read_percentile * weights["user_time_read_weights"]
    )

    return {
        "activeness_score": activeness_score,
        "days_visited_percentile": days_visited_percentile,
        "user_days_visited": user_data["days_visited"],
        "time_read_percentile": time_read_percentile,
        "user_time_read": user_data["time_read"],
    }


def calculate_overall_topic_score(
    user_activity: dict, activity_dict: dict, likes_dict: dict, weights: dict
) -> dict:
    user_topic_count = len(user_activity["topics"])
    topic_count_percentile = calculate_percentile(
        user_topic_count, activity_dict["all_topic_count"]
    )

    user_post_count = len(user_activity["posts"])
    post_count_percentile = calculate_percentile(
        user_post_count, activity_dict["all_post_count"]
    )

    user_like_count = likes_dict["users"][user_activity["user"]["username"]]
    all_like_count = likes_dict["total"]

    like_rec_percentile = calculate_percentile(user_like_count, all_like_count)

    overall_topic_score = (
        (topic_count_percentile * weights["user_topic_count_weights"])
        + (post_count_percentile * weights["user_post_count_weights"])
        + (like_rec_percentile * weights["user_like_rec_weights"])
    )

    return {
        "overall_topic_score": overall_topic_score,
        "topic_count_percentile": topic_count_percentile,
        "total_topic_count": user_topic_count,
        "post_count_percentile": post_count_percentile,
        "total_post_count": user_post_count,
        "like_rec_percentile": like_rec_percentile,
        "total_likes_received": user_like_count,
    }


def calculate_proposal_score(
    user_activity: dict,
    activity_dict: dict,
    all_proposal_topic_likes_received: list,
    weights: dict,
) -> dict:
    user_proposal_int_count = len(user_activity["proposal_topics"])
    proposal_initiated_percentile = calculate_percentile(
        user_proposal_int_count, activity_dict["all_proposal_count"]
    )

    user_proposal_disc_count = len(user_activity["proposal_posts"])
    proposal_discussed_percentile = calculate_percentile(
        user_proposal_disc_count, activity_dict["all_proposal_post_count"]
    )

    # Get avg proposal topics like received
    user_avg_prop_like_rec = all_proposal_topic_likes_received["users"][
        user_activity["user"]["username"]
    ]

    all_avg_prop_like_rec = all_proposal_topic_likes_received["total"]
    average_proposal_like_rec_percentile = calculate_percentile(
        user_avg_prop_like_rec, all_avg_prop_like_rec
    )

    proposal_score = (
        (proposal_initiated_percentile * weights["prop_int_weights"])
        + (proposal_discussed_percentile * weights["prop_disc_weights"])
        + (average_proposal_like_rec_percentile * weights["prop_like_rec_weights"])
    )

    return {
        "proposal_score": proposal_score,
        "proposal_initiated_percentile": proposal_initiated_percentile,
        "total_proposals_initiated": user_proposal_int_count,
        "proposal_discussed_percentile": proposal_discussed_percentile,
        "total_proposals_discussed": user_proposal_disc_count,
        "average_proposal_likes_received_percentile": average_proposal_like_rec_percentile,
        "average_proposal_likes_received": user_avg_prop_like_rec,
    }


def calculate_percentile(user_data: int, all_data: List[int]) -> int | float:
    """Calculates the percentile of the user's data compared to all data"""
    if user_data == 0 or not all_data:
        return 0

    # Calculates the amount of data that is less than user data
    less_count = sum(1 for data in all_data if data <= user_data)

    return (less_count / len(all_data)) * 100


def add_proposal_data(all_activities: list, config_data: dict) -> list:
    """Finds out and inserts all proposal topics and posts into user activity
    Here, 2 extra columns, "proposal_topics" and "proposal_posts" will be added
    to each user activity, each a list of proposal topic / posts data
    """
    for user_activity in all_activities:
        user_activity["proposal_topics"] = find_proposal_data(
            user_activity, "topics", config_data
        )
        user_activity["proposal_posts"] = find_proposal_data(
            user_activity, "posts", config_data
        )

    return all_activities


def find_proposal_data(user_activity: dict, data_type: str, config_data: dict):
    """Supports data types "topics" or "posts"...."""
    proposal_category_ids = config_data["proposal_category_ids"]
    tag_usage = config_data["tags"]
    proposal_tags = config_data["proposal_tags"]

    proposal_data = []
    for data in user_activity[data_type]:
        if data["category_id"] in proposal_category_ids:
            if tag_usage:
                for tag in proposal_tags:
                    if tag in data["tags"]:
                        proposal_data.append(data)

            else:
                proposal_data.append(data)

    return proposal_data


def get_all_likes_received(all_activities: list) -> dict:
    """Returns a dict of all users' likes received from all activities"""
    all_usernames = [user["user"]["username"] for user in all_activities]

    all_likes_received = {}
    for user in all_activities:
        username = user["user"]["username"]
        if username not in all_likes_received:
            all_likes_received[username] = 0

        for like in user["likes"]:
            # If self like or invalid user, don't count
            if (
                like["like_given_to"] == username
                or like["like_given_to"] not in all_usernames
            ):
                continue

            if like["like_given_to"] not in all_likes_received:
                all_likes_received[like["like_given_to"]] = 0

            all_likes_received[like["like_given_to"]] += 1

    return {"users": all_likes_received, "total": list(all_likes_received.values())}


def get_all_avg_proposal_topics_like_received(all_activities: dict):
    """Gets a list of all user's avg proposal topic's like received"""
    # Gets a list of all proposal topic ids
    proposal_topics = [
        topic["topic_id"]
        for user_activity in all_activities
        for topic in user_activity["proposal_topics"]
    ]

    # Gets a dict of each user's proposal topics like received
    proposal_like_dict = {}
    for user_activity in all_activities:
        activity_username = user_activity["user"]["username"]
        if activity_username not in proposal_like_dict:
            proposal_like_dict[activity_username] = {}

        for like in user_activity["likes"]:
            topic_id = like["topic_id"]
            if topic_id in proposal_topics and like["post_number"] == 1:
                username = like["like_given_to"]
                # NOTE: If self like, don't count
                if username == activity_username:
                    continue

                if username not in proposal_like_dict:
                    proposal_like_dict[username] = {}

                if topic_id not in proposal_like_dict[username]:
                    proposal_like_dict[username][topic_id] = 0

                proposal_like_dict[username][topic_id] += 1

    avg_prop_topic_likes_dict = {"users": {}, "total": []}
    for user in proposal_like_dict:
        if not proposal_like_dict[user]:
            avg_like_rec = 0

        else:
            sum_likes = sum(proposal_like_dict[user].values())
            avg_like_rec = sum_likes / len(proposal_like_dict[user])

        avg_prop_topic_likes_dict["users"][user] = avg_like_rec
        avg_prop_topic_likes_dict["total"].append(avg_like_rec)

    return avg_prop_topic_likes_dict
