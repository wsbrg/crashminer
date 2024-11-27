import click
import os
import urllib.request
import sys
import logging
import time
from tqdm import tqdm

import util


LOG_LEVEL = logging.INFO

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(LOG_LEVEL)
formatter = logging.Formatter("%(levelname)s | %(asctime)s | %(name)s | %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)


def download_testcase(url, path, local_id):
    filepath = os.path.join(path, local_id)
    if os.path.exists(filepath):
        logger.warning(f"File {filepath} exists.")
        return False

    try:
        response = urllib.request.urlopen(url)
    except Exception as e:
        logger.warning(f"Cannot download testcase for crash {local_id}.")
        return False

    if response.status != 200:
        logger.warning(f"Cannot download testcase for crash {local_id}.")
        return False

    data = response.read()

    if b"Polymer Project" in data:
        logger.warning(
            f"Testcase for crash {local_id} not available without login.")
        return False

    with open(filepath, "wb") as f:
        f.write(data)

    return True


@click.command()
@click.argument("path")
@click.argument("issues")
def testcases(path, issues):
    """Download the testcase for each crash.

    Args:
        path    Path to the testcase directory.
        issues  Path to issues file containing projects issues and commits.
    """
    if not os.path.exists(issues) or not os.path.isfile(issues):
        logger.error(f"Not a file {issues}.")
        sys.exit(1)

    if not os.path.exists(path):
        os.makedirs(path)

    if not os.path.isdir(path) or not len(os.listdir(path)) == 0:
        logger.error(f"Directory {path} does not exist or is not empty.")
        sys.exit(1)

    projects = util.load_json(issues)

    for project_name, project in tqdm(projects.items(), total=len(projects)):
        if not "crashes" in project or len(project["crashes"]) == 0:
            logger.info(
                f"Project {project_name} does not contain any crashes.")
            continue

        for idx, crash in enumerate(project["crashes"]):
            if crash["testcase"] == "":
                logger.info(
                    f"Testcase {crash['localId']} of project {project_name} does not contain a testcase."
                )
                continue

            local_id = crash["localId"]
            url = crash["testcase"]
            success = download_testcase(url, path, str(local_id))
            time.sleep(0.25)

            if not success:
                logger.warning(
                    f"Download of testcase for crash {local_id} of projcet {project_name} failed."
                )


if __name__ == "__main__":
    testcases()
