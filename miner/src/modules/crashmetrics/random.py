import random
from fsdict import fsdict


def random_metric(function_ids, database, seed):
    for function_id in function_ids:
        function = database[function_id]
        meta = function["meta"]
        if not "metrics" in meta:
            meta["metrics"] = {}

        random.seed(int(function_id, 16) + seed)
        meta["metrics"]["random"] = random.randint(0, int(1e9)) / 1e9
        function["meta"] = meta
