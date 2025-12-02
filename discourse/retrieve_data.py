import requests
import time
import logging
import math

logging.basicConfig(level=logging.INFO)

max_retries = 20
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
}


def get_discourse_data(dao: str, url: str, endpoints: dict) -> dict:
    """Retrives a DAO's raw data from discourse.

    Data retrieved: Topic, Post, Likes, Users, Single Users (an individual user's data)"""
    raw_users = fetch_discourse_page_data(
        dao, url + endpoints["user_endpoint"] + ".json", "users"
    )
    raw_topics = fetch_discourse_page_data(
        dao, url + endpoints["topic_endpoint"] + ".json", "topics"
    )

    return {
        "users": raw_users,
        "topics": raw_topics,
        "posts": fetch_discourse_topic_post_data(
            dao, url + endpoints["single_topic_endpoint"], topics_data=raw_topics
        ),
        "likes": fetch_discourse_user_sub_data(
            dao,
            url + endpoints["like_endpoint"],
            data_type="likes",
            users_data=raw_users,
        ),
        "single_users": fetch_discourse_user_sub_data(
            dao,
            url + endpoints["single_user_endpoint"],
            data_type="single_users",
            users_data=raw_users,
        ),
    }


def fetch_discourse_page_data(dao: str, url: str, data_type: str):
    """Actual logic for fetching raw data from discourse for data which
    uses pages (i.e. we don't know how many data there is)
    FOR DATA TYPES: topics // users"""
    fetched_data = []
    page = 0
    retries = 0
    session = requests.Session()

    logging.info("*****************************")
    logging.info("Retrieving raw %s data", data_type)
    while retries < max_retries:
        try:
            response = session.get(
                url,
                params={"period": "all", "page": page, "order": "desc"},
                headers=headers if dao == "gnosis" else None,
            )

            response.raise_for_status()
            raw_data = response.json()

            if data_type == "topics":
                add_data = raw_data["topic_list"]["topics"]

            elif data_type == "users":
                add_data = raw_data["directory_items"]

            if not add_data:
                logging.info(
                    "Done retrieving all %s data (%s)", data_type, len(fetched_data)
                )
                return fetched_data

            fetched_data.extend(add_data)
            logging.info("Fetched %s %s at page: %s", len(add_data), data_type, page)
            page += 1
            retries = 0

        # Errors regarding status codes 4XX-5XX
        except requests.exceptions.HTTPError as http_error:
            if http_error.response.status_code == 429:
                retries = rate_limit_backoff(retries, max_retries)

            else:
                logging.error(
                    "Unhandled status code (%s) received: %s",
                    http_error.response.status_code,
                    http_error,
                )

        # Other requests related error
        except requests.exceptions.RequestException as req_error:
            logging.error("Other requests-related error occurred: %s", req_error)
            logging.info("Retrying...")
            retries = rate_limit_backoff(retries, max_retries)

        except Exception as e:
            logging.error("Unexpected error occurred while retrieving page data: %s", e)
            raise

    if retries >= max_retries:
        logging.error("Max retries reached.")
        raise


def fetch_discourse_topic_post_data(dao: str, base_url: str, topics_data: list) -> dict:
    """Actual logic for fetching raw data from discourse for data which
    uses looping of the raw topic data.
    DATA TYPES: Posts"""
    session = requests.Session()
    count = 0
    post_data = {}

    logging.info("*****************************")
    logging.info("Retrieving posts data")
    for topic in topics_data:
        count += 1
        topic_id = topic["id"]
        try:
            url = base_url + str(topic_id) + ".json"

        except TypeError:
            logging.error("base_url: %s", base_url)
            logging.error("topic_id: %s", topic_id)
            raise

        post_data[topic_id] = {
            "category_id": topic["category_id"],
            "tags": topic["tags"] if "tags" in topic else None,
            "posts": [],
        }

        total_pages = math.ceil(topic["posts_count"] / 20) + 1  # 20 posts per page
        logging.info("*******CURRENTLY AT TOPIC: %s / %s", count, len(topics_data))
        logging.info(
            f"Topic {topic_id} has {topic['posts_count']} posts, total page to fetch = {total_pages - 1}"
        )

        for page in range(1, total_pages):
            retries = 0
            while retries < max_retries:
                try:
                    response = session.get(
                        url,
                        params={"page": page},
                        headers=headers if dao == "gnosis" else None,
                    )

                    response.raise_for_status()
                    raw_data = response.json()

                    post_data[topic_id]["posts"].extend(
                        raw_data["post_stream"]["posts"]
                    )
                    logging.info(
                        f"Fetched topic {topic_id} - page {page}/{total_pages - 1}"
                    )
                    break

                # Errors regarding status codes 4XX-5XX
                except requests.exceptions.HTTPError as http_error:
                    if http_error.response.status_code == 429:
                        retries = rate_limit_backoff(retries, max_retries)

                    elif http_error.response.status_code == 404:
                        logging.error("ERROR: 404 received for url %s", url)
                        break

                    else:
                        logging.error(
                            "Unhandled status code (%s) received: %s",
                            http_error.response.status_code,
                            http_error,
                        )
                        raise

                # Other requests related error
                except requests.exceptions.RequestException as req_error:
                    logging.error(
                        "Other requests-related error occurred: %s", req_error
                    )
                    logging.info("Retrying...")
                    retries = rate_limit_backoff(retries, max_retries)

                except Exception as e:
                    logging.error(
                        "Unexpected error occurred while retrieving page data: %s", e
                    )
                    raise

    logging.info("Done retrieving all posts for %s topics", len(post_data))
    return post_data


def fetch_discourse_user_sub_data(
    dao: str, base_url: str, data_type: str, users_data: list
) -> list[dict]:
    """Actual logic for fetching raw data from discourse for data which
    uses looping of the raw user data.
    DATA TYPES: Single Users, Likes"""
    session = requests.Session()
    logging.info("*****************************")
    logging.info("Retrieving %s data", data_type)
    fetched_data = []
    count = 1
    added_users = 0
    for user in users_data:
        username = user["user"]["username"]
        retries = 0
        if data_type == "single_users":
            url = base_url + username + ".json"

        if data_type == "likes":
            url = base_url + ".json"
            user_likes = []
            offset = 0

        while retries < max_retries:
            try:
                response = session.get(
                    url,
                    params={
                        "offset": offset,
                        "username": username,
                        "filter": 1,
                    }
                    if data_type == "likes"
                    else None,
                    headers=headers if dao == "gnosis" else None,
                )

                response.raise_for_status()
                raw_data = response.json()

                if data_type == "single_users":
                    if "user_badges" in raw_data:
                        added_users += 1
                        fetched_data.append(raw_data)
                        logging.info(
                            f"Fetched {data_type} data for user {count}/{len(users_data)}: {username} ({added_users})"
                        )

                    else:
                        logging.debug(
                            "User %s/%s has their profile hidden (%s)",
                            count,
                            len(users_data),
                            username,
                        )

                    count += 1
                    break

                elif data_type == "likes":
                    page_actions = raw_data["user_actions"]

                    if not page_actions:
                        if user_likes:
                            added_users += 1
                            logging.info(
                                f"Fetched {data_type} data for user {count}/{len(users_data)}: {username} ({added_users})"
                            )
                            fetched_data.append(
                                {"username": username, "user_actions": user_likes}
                            )
                        count += 1
                        break

                    user_likes.extend(page_actions)
                    retries = 0
                    offset += 30
                    continue

            # Errors regarding status codes 4XX-5XX
            except requests.exceptions.HTTPError as http_error:
                if http_error.response.status_code == 429:
                    retries = rate_limit_backoff(retries, max_retries)

                elif http_error.response.status_code == 404:
                    if data_type == "likes":
                        pass

                    else:
                        logging.error("ERROR: 404 received for url %s", url)

                    break

                else:
                    logging.error(
                        "Unhandled status code (%s) received: %s",
                        http_error.response.status_code,
                        http_error,
                    )
                    raise

            # Other requests related error
            except requests.exceptions.RequestException as req_error:
                logging.error("Other requests-related error occurred: %s", req_error)
                logging.info("Retrying...")
                retries = rate_limit_backoff(retries, max_retries)

            except Exception as e:
                logging.error(
                    "Unexpected error occurred while retrieving page data: %s", e
                )
                raise

        if retries >= max_retries:
            logging.error("Max retries reached.")
            raise

    logging.info("Done retrieving all %s data for %s users", data_type, added_users)
    return fetched_data


def rate_limit_backoff(retries, max_retries) -> int:
    retries += 1
    wait_time = min(2**retries, 600)
    logging.warning(f"Rate limited. Waiting {wait_time} seconds")
    logging.warning(f"Attempt {retries}/{max_retries}")
    if retries < max_retries:
        time.sleep(wait_time)

    return retries
