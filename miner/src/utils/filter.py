import re
import os.path as osp
#from toolz.curried import *
from datetime import datetime as dt, timedelta

from utils.utils import *


def load_filter(data):
    def parse(element):
        if "-" in element:
            # ISO format timestamp
            return dt.fromisoformat(element)
        else:
            # Crash ID
            return element

    lines = data.split("\n")
    lines = map(lambda line: line.replace(" ", ""), lines)
    lines = map(lambda line: line.split("#")[0], lines)
    lines = map(lambda line: line.split(","), lines)
    lines = map(lambda cols: (cols[0], [parse(el.strip()) for el in cols[1:]]), lines)
    project_filter = {}
    for project, filter_elements in lines:
        if not project in project_filter:
            project_filter[project] = {}
        project_filter[project]["ids"] = [
            el for el in filter_elements if isinstance(el, str)
        ]
        project_filter[project]["minTime"] = [
            el for el in filter_elements if isinstance(el, dt)
        ]
    return project_filter


def filter_it(database, filter_file):
    if filter_file == None:
        project_filter = None
    else:
        project_filter = load_filter(fread(filter_file))

    for project_name, project in database.items():
        if project_filter != None and project_name not in project_filter:
            continue

        for local_id, crash in project["crashes"].items():
            if project_filter == None:
                yield crash
                continue

            if (
                project_filter[project_name]["ids"] == []
                and project_filter[project_name]["minTime"] == []
            ):
                yield crash
                continue

            if local_id in project_filter[project_name]["ids"]:
                yield crash
                continue

            ts = dt.fromtimestamp(crash["meta"]["timestamp"])
            if any(min_ts < ts for min_ts in project_filter[project_name]["minTime"]):
                yield crash
                continue
