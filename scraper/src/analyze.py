#!/usr/bin/python3

import click
import json
import os
import re
import sys
import logging
import yaml
import subprocess
from tqdm import tqdm
from tempfile import TemporaryDirectory

import util


LOG_LEVEL = logging.INFO

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(LOG_LEVEL)
formatter = logging.Formatter("%(levelname)s | %(asctime)s | %(name)s | %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)


def load_yaml(path):
    with open(path, "r") as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as exc:
            logger.error(f"Cannot load yaml file at {path}.")
            sys.exit(1)


def git_log(repo):
    with TemporaryDirectory() as directory:
        timeout = 10 * 60
        cmd = f"git clone {repo} {directory}".split(" ")
        try:
            result = util.do_run(cmd, timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning(f"Cloning repository {repo} failed.")
            return []

        if result["returncode"] != 0:
            logger.warning(f"Cloning repository {repo} failed.")
            return []

        cmd = f'git log --format="%H,%ct"'.split(" ")
        result = util.do_run(cmd, cwd=directory)
        if result["returncode"] != 0:
            logger.warning(f"Git log failed for repository {repo}.")
            return []

        log = result["stdout"].replace('"', "").split("\n")
        log = filter(lambda commit: "," in commit, log)
        log = map(
            lambda commit: {
                "hash": commit.split(",")[0],
                "timestamp": commit.split(",")[1],
            },
            log,
        )
        log = list(log)

        return log


@click.group()
def cli():
    pass


@click.command()
@click.option(
    "--save", "-s", default="", help="Write result to file instead of stdout."
)
@click.argument("issues")
def analyze(save, issues):
    """Analyze an issue+comment file."""
    if not os.path.exists(issues) or not os.path.isfile(issues):
        logger.error(f"Not a file {issues}.")
        sys.exit(1)

    if save != "" and os.path.exists(save) and os.path.isfile(save):
        logger.error(f"File {save} already exists.")
        sys.exit(1)

    issues = util.load_json(issues)
    logger.info(f"Issues loaded from file '{issues}'")
    project_issues = {}

    for issue in tqdm(issues["issues"]):
        local_id = issue["localId"]
        if not "comments" in issue:
            issue["comments"] = []
        comments = issue["comments"]
        if len(comments) == 0:
            logger.warning(f"No comments found for issue with id {local_id}. Skipping.")
            continue

        comment = comments[0]
        content = comment["content"]
        analyzed_issue = {
            "localId": local_id,
            "timestamp": comment["timestamp"],
        }

        # Get project name
        match = re.search("Project: (.*)\n", content)
        if match:
            project = match.group(1)
            analyzed_issue["project"] = project
        else:
            logger.warning(
                f"No project name found for issue with id {local_id}. Skipping."
            )
            continue

        # Get testcase
        match = re.search("Testcase.*: (.*)\n", content)
        if match:
            analyzed_issue["testcase"] = match.group(1)
        else:
            analyzed_issue["testcase"] = ""
            logger.warning(f"No testcase found for issue with id {local_id}.")

        # Get fuzzer
        match = re.search("Fuzzer: (.*)\n", content)
        if match:
            analyzed_issue["fuzzer"] = match.group(1)
        else:
            analyzed_issue["fuzzer"] = ""

        # Get fuzzing engine
        match = re.search("Fuzzing Engine: (.*)\n", content, re.IGNORECASE)
        if match:
            analyzed_issue["fuzzingEngine"] = match.group(1)
        else:
            analyzed_issue["fuzzingEngine"] = ""

        # WARN no fuzzer / fuzzing engine found
        if analyzed_issue["fuzzer"] == "" and analyzed_issue["fuzzingEngine"] == "":
            logger.warning(
                f"Neither fuzzing nor fuzzing engine found for issue with id {local_id}."
            )

        # Get sanitizer
        match = re.search("Sanitizer: (.*)\n", content)
        if match:
            analyzed_issue["sanitizer"] = match.group(1)
        else:
            analyzed_issue["sanitizer"] = ""
            logger.warning(f"No sanitizer found for issue with id {local_id}.")

        # Get target binary
        match = re.search("target binary: (.*)\n", content)
        if match:
            analyzed_issue["targetBinary"] = match.group(1)
        else:
            analyzed_issue["targetBinary"] = ""

        # Get fuzz target
        match = re.search("Fuzz Target: (.*)\n", content, re.IGNORECASE)
        if match:
            analyzed_issue["fuzzTarget"] = match.group(1)
        else:
            analyzed_issue["fuzzTarget"] = ""

        # Get job type
        match = re.search("Job Type: (.*)\n", content, re.IGNORECASE)
        if match:
            analyzed_issue["jobType"] = match.group(1)
        else:
            analyzed_issue["jobType"] = ""

        # Infer sanitzers from job type if no sanitizer could be found
        # TODO

        # WARN no target binary / fuzz target found
        if analyzed_issue["targetBinary"] == "" and analyzed_issue["fuzzTarget"] == "":
            logger.warning(
                f"Neither target binary nor fuzz target found for issue with id {local_id}."
            )

        if project not in project_issues:
            project_issues[project] = {"crashes": [analyzed_issue]}
        else:
            project_issues[project]["crashes"].append(analyzed_issue)

    if save != "":
        util.save_json(save, project_issues)
    else:
        print(json.dumps(project_issues, indent=2))


@click.command()
@click.option(
    "--save", "-s", default="", help="Write result to file instead of stdout."
)
@click.option(
    "--ossfuzzgit",
    "-g",
    default="https://github.com/google/oss-fuzz.git",
    help="Git URL of OSS-Fuzz.",
)
@click.argument("issues")
def ossfuzz(save, issues, ossfuzzgit):
    """Extend the issues file with information from the OSS-Fuzz project dir.

    Args:
        issues  Path to the issue file clustered by projects (results from
                running "analyze").
    """
    if not os.path.exists(issues) or not os.path.isfile(issues):
        logger.error(f"Not a file {issues}.")
        sys.exit(1)

    if save != "" and os.path.exists(save) and os.path.isfile(save):
        logger.error(f"File {save} already exists.")
        sys.exit(1)

    with TemporaryDirectory() as directory:
        ossfuzzdir = "oss-fuzz"
        cmd = f"git clone {ossfuzzgit} {ossfuzzdir}"
        res = util.do_run(cmd.split(" "), cwd=directory)
        if res["returncode"] != 0:
            logger.error(f"Cannot clone OSS-Fuzz from {ossfuzzgit}.")
            sys.exit(1)

        projects = os.path.join(directory, ossfuzzdir, "projects")
        project_issues = util.load_json(issues)
        logger.info(f"Issues loaded from file '{issues}'")

        for project_name, project in tqdm(
            project_issues.items(), total=len(project_issues)
        ):
            project_path = os.path.join(projects, project_name)
            if not os.path.exists(project_path) or not os.path.isdir(project_path):
                logger.warning(
                    f"Project {project_name} not found in OSS-Fuzz project dir."
                )
                continue

            yaml_path = os.path.join(project_path, "project.yaml")
            if not os.path.exists(yaml_path) or not os.path.isfile(yaml_path):
                logger.warning(f"Valid project.yaml not found in at {yaml_path}.")
                continue

            project_information = load_yaml(yaml_path)
            project_ext = {**project, **project_information}

            project_issues[project_name] = project_ext

    if save != "":
        util.save_json(save, project_issues)
    else:
        print(json.dumps(project_issues, indent=2))


@click.command()
@click.option(
    "--save", "-s", default="", help="Write result to file instead of stdout."
)
@click.argument("issues")
def git(save, issues):
    """Extend the issues file with information from their respective github repositories.

    Args:
        issues  Path to the extended issue file clustered by projects (results from
                running "analyze" and "ossfuzz" before).
    """
    if not os.path.exists(issues) or not os.path.isfile(issues):
        logger.error(f"Not a file {issues}.")
        sys.exit(1)

    if save != "" and os.path.exists(save) and os.path.isfile(save):
        logger.error(f"File {save} already exists.")
        sys.exit(1)

    project_issues = util.load_json(issues)
    logger.info(f"Issues loaded from file '{issues}'")

    for project_name in tqdm(project_issues):
        project = project_issues[project_name]

        if not "main_repo" in project:
            logger.warning(f"No main_repo found for project {project_name}.")
            continue

        repo = project["main_repo"]

        if not "git" in repo:
            logger.warning(f"It seems project {project_name} does not use Git.")
            continue

        log = git_log(repo)
        if log == []:
            logger.warning(f"Log for repository {repo} missing.")
            continue

        project_ext = {"commits": log, **project}
        project_issues[project_name] = project_ext

    if save != "":
        util.save_json(save, project_issues)
    else:
        print(json.dumps(project_issues, indent=2))


if __name__ == "__main__":
    cli.add_command(analyze)
    cli.add_command(ossfuzz)
    cli.add_command(git)
    cli()
