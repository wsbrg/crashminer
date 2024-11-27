#!/usr/bin/python3

from selenium import webdriver
from tqdm import tqdm
import requests
import json
import logging
import re
import sys
import click
import os
import sys

import util


LOG_LEVEL = logging.INFO

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(LOG_LEVEL)
formatter = logging.Formatter("%(levelname)s | %(asctime)s | %(name)s | %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)


def get_xsrf_token():
    logger.debug("Acquire XSRF token.")

    url = "https://bugs.chromium.org/p/oss-fuzz/issues/list"
    resp = requests.get(url)

    if not resp.status_code == 200:
        logger.error("Cannot get XSRF token. Invalid status code.")
        sys.exit(1)

    xsrf_token_match = re.search("'token': '(.*)',", resp.content.decode("ascii"))

    if xsrf_token_match:
        xsrf_token = xsrf_token_match.group(1)
        logger.debug(f"XSRF token: { xsrf_token }.")
        return xsrf_token

    logger.error("Cannot get XSRF token. XSRF token not found.")
    sys.exit(1)


def get_issues(xsrf_token, query, start, max_items):
    logger.debug(f"Get {max_items} issues starting at {start}.")

    headers = {
        "Accept": "application/json",
        "content-type": "application/json",
        "X-Xsrf-Token": xsrf_token,
    }
    data = {
        "projectNames": ["oss-fuzz"],
        "query": query,
        "cannedQuery": 1,
        "pagination": {
            "start": start,
            "maxItems": max_items,
        },
    }
    url = "https://bugs.chromium.org/prpc/monorail.Issues/ListIssues"

    resp = requests.post(url, data=json.dumps(data), headers=headers)

    if resp.status_code != 200:
        logger.error("Cannot get issues. Invalid status code.")
        sys.exit(1)

    issues = resp.content.decode("ascii")
    issues = json.loads(issues[5:])

    return issues


def get_all_issues(query):
    xsrf_token = get_xsrf_token()

    step_width = 1000
    issues = get_issues(xsrf_token, query, 0, step_width)
    total_results = issues["totalResults"]

    for issue_idx in tqdm(range(step_width, total_results, step_width)):
        new_issues = get_issues(xsrf_token, query, issue_idx, step_width)
        logger.debug(f"Got {len(new_issues['issues'])} new issues.")
        issues["issues"] += new_issues["issues"]

    return issues


def get_comments(xsrf_token, local_id):
    logger.debug(f"Get comment for id {local_id}.")

    url = "https://bugs.chromium.org/prpc/monorail.Issues/ListComments"
    headers = {
        "Accept": "application/json",
        "content-type": "application/json",
        "X-Xsrf-Token": xsrf_token,
    }
    data = {"issueRef": {"localId": local_id, "projectName": "oss-fuzz"}}

    resp = requests.post(url, data=json.dumps(data), headers=headers)

    if resp.status_code != 200:
        logger.warning(f"Cannot get comment for id {local_id}.")
        return {}

    return json.loads(resp.content.decode("ascii")[5:])


def save_issues(path, issues):
    with open(path, "w") as f:
        f.write(json.dumps(issues, indent=2))
    logger.info(f"Saved issues at {path}.")


def load_issues(path):
    with open(path, "r") as f:
        issues = json.loads(f.read())
    logger.info(f"Loaded issues from {path}.")
    return issues


@click.group()
def cli():
    pass


@click.command()
@click.option(
    "--save", "-s", default="", help="Write result to file instead of stdout."
)
@click.option(
    "--query",
    "-q",
    default="label:Reproducible label:ClusterFuzz",
    help="Query string for quering issues from OSS-Fuzz.",
)
def issues(save, query):
    """Download issues from OSS-Fuzz project."""
    if save != "" and os.path.exists(save) and os.path.isfile(save):
        logger.error(f"File {save} already exists.")
        sys.exit(1)

    issues = get_all_issues(query)

    if save != "":
        save_issues(save, issues)
    else:
        print(json.dumps(issues, indent=2))


@click.command()
@click.option(
    "--save", "-s", default="", help="Write result to file instead of stdout."
)
@click.argument("issues")
def comments(save, issues):
    """Download comments from OSS-Fuzz and add them to the issues."""
    if save != "" and os.path.exists(save) and os.path.isfile(save):
        logger.error(f"File {save} already exists.")
        sys.exit(1)

    if not os.path.exists(issues) or not os.path.isfile(issues):
        logger.error(f"Not a file {issues}.")
        sys.exit(1)

    issues = load_issues(issues)
    xsrf_token = get_xsrf_token()

    total_issues = len(issues["issues"])
    update_interval = total_issues // 1000

    for idx, issue in tqdm(enumerate(issues["issues"]), total=total_issues):
        if "comments" in issue:
            # Issue already contains comments
            continue
        local_id = issue["localId"]
        comments = get_comments(xsrf_token, local_id)
        issues["issues"][idx] = dict(**issue, **comments)

    if save != "":
        save_issues(save, issues)
    else:
        print(json.dumps(issues, indent=2))


if __name__ == "__main__":
    cli.add_command(issues)
    cli.add_command(comments)
    cli()
