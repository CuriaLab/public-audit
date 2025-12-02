import os
import json
import logging
from fastapi import FastAPI

from discourse.retrieve_data import get_discourse_data
from discourse.format_data import format_discourse_data
from discourse.filter_data import (
    exclude_user_activities_by_exclude_data,
    exclude_user_activities_by_trust_level_0,
    exclude_user_activities_by_trust_level_1,
)

from metrics.forum_score import calculate_all_forum_score

dir = os.getcwd()
logging.basicConfig(level=logging.INFO)


def get_discourse_endpoints() -> dict:
    """Retrieves the discourse api endpoints for retrieving each
    DAO's raw data"""
    config_path = os.path.join(dir, "config", "config.json")
    with open(config_path, "r") as json_file:
        config_data = json.load(json_file)

        return config_data["endpoints"]


def get_dao_exclude_data(dao: str) -> dict:
    """Retrieves a DAO's exclude data which includes a list of
    users, topics, and categories to exclude from being used in
    calculating metrics."""
    config_path = os.path.join(dir, "config", "exclude_data.json")
    with open(config_path, "r") as json_file:
        exclude_data = json.load(json_file)
        if dao not in exclude_data:
            exclude_data[dao] = {
                "user_bool": False,
                "topic_bool": False,
                "category_bool": False,
            }

    return exclude_data[dao]


app = FastAPI()
endpoints = get_discourse_endpoints()


@app.get("/{dao}/config")
async def get_dao_config(dao: str) -> dict:
    """Retrieves a DAO's config data from the config file"""
    config_path = os.path.join(dir, "config", "config.json")
    with open(config_path, "r") as json_file:
        config_data = json.load(json_file)

        if dao not in config_data["dao"]:
            raise ValueError("Invalid DAO entered.")

        if not config_data["dao"][dao]["custom_forum_score_weights"]:
            config_data["dao"][dao]["forum_score_weights"] = config_data[
                "forum_score_weights"
            ]

    return config_data["dao"][dao]


@app.get("/{dao}/data/raw")
async def retrieve_dao_raw_data(dao: str) -> dict:
    """Retrieves and returns a DAO's raw data, which is retrieved
    from their forum website through its public API endpoints."""
    dao_config = await get_dao_config(dao)
    raw_data = get_discourse_data(dao, dao_config["base_url"], endpoints)

    return raw_data


@app.get("/{dao}/data/format")
async def retrieve_dao_formatted_data(dao: str):
    """Retrieves a DAO's raw data, then formats the data into a
    standardized format to be used for calculating other discourse
    forum metrics."""
    dao_config = await get_dao_config(dao)
    raw_data = get_discourse_data(dao, dao_config["base_url"], endpoints)
    formatted_data = format_discourse_data(raw_data, dao_config["base_url"])

    return formatted_data


@app.get("/{dao}/metrics/forum_score")
async def calculate_forum_score(dao: str):
    """Calculates a DAO's forum score after retrieving, formatting, and filtering
    the discourse forum data."""
    dao_config = await get_dao_config(dao)
    exclude_data = get_dao_exclude_data(dao)
    raw_data = get_discourse_data(dao, dao_config["base_url"], endpoints)
    formatted_data = format_discourse_data(raw_data, dao_config["base_url"])

    # Here, we exclude users by trust level 1 for Arbitrum due the number of users it has
    # which negatively affects the score distribution
    users_excluded_data = (
        exclude_user_activities_by_trust_level_1(formatted_data)
        if dao == "arbitrum"
        else exclude_user_activities_by_trust_level_0(formatted_data)
    )

    filtered_data = exclude_user_activities_by_exclude_data(
        users_excluded_data, exclude_data
    )

    forum_scores = calculate_all_forum_score(filtered_data, dao_config)

    return forum_scores
