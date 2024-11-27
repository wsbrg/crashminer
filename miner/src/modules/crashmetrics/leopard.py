from pathlib import Path
from mcpp.config import TreeSitterConfig, Config
from mcpp.__main__ import run
from fsdict import fsdict
from config import PARSER_LIB


def complexity_metric(function_ids, database):
    treesitter = TreeSitterConfig(Path(PARSER_LIB), None)
    complexity_metrics = ["C1", "C2", "C3", "C4"]

    for function_id in function_ids:
        function = database[function_id]
        meta = function["meta"]
        source_path = function.abspath / "source"
        config = Config(source_path, None, complexity_metrics, None, treesitter)
        scores = run(config)
        score = sum(scores[str(source_path)][cm] for cm in complexity_metrics)

        if not "metrics" in meta:
            meta["metrics"] = {}
        metrics = meta["metrics"]

        if not "complexity" in metrics:
            metrics["complexity"] = score
            meta["metrics"] = metrics
            function["meta"] = meta


def vulnerability_metric(function_ids, database):
    treesitter = TreeSitterConfig(Path(PARSER_LIB), None)
    vulnerability_metrics = [
        "V1",
        "V2",
        "V3",
        "V4",
        "V5",
        "V6",
        "V7",
        "V8",
        "V9",
        "V10",
        "V11",
    ]
    for function_id in function_ids:
        function = database[function_id]
        meta = function["meta"]
        source_path = function.abspath / "source"
        config = Config(source_path, None, vulnerability_metrics, None, treesitter)
        scores = run(config)
        score = sum(scores[str(source_path)][cm] for cm in vulnerability_metrics)

        if not "metrics" in meta:
            meta["metrics"] = {}
        metrics = meta["metrics"]

        if not "vulnerability" in metrics:
            metrics["vulnerability"] = score
            meta["metrics"] = metrics
            function["meta"] = meta
