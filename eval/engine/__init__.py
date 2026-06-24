"""Trace-lit eval engine — scores prompt versions against labeled datasets."""
from .runner import EvalResult, run_eval

__all__ = ["run_eval", "EvalResult"]
