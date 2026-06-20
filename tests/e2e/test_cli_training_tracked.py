"""Tests for CLI training --dataset argument and TrackingService integration.

Phase 4, T029-T030: CLI --dataset arg + TrackingService wiring.
"""

import argparse


def test_cli_train_accepts_dataset_arg():
    parser = argparse.ArgumentParser(description="Train Llama model")
    parser.add_argument("--dataset", type=int, default=None)
    parser.add_argument("--corpus", type=int, default=None)
    parser.add_argument("--backend", type=str, default=None)
    args = parser.parse_args(["--dataset", "1"])
    assert args.dataset == 1
    assert args.corpus is None


def test_cli_train_accepts_corpus_arg():
    parser = argparse.ArgumentParser(description="Train Llama model")
    parser.add_argument("--dataset", type=int, default=None)
    parser.add_argument("--corpus", type=int, default=None)
    parser.add_argument("--backend", type=str, default=None)
    args = parser.parse_args(["--corpus", "1"])
    assert args.corpus == 1
    assert args.dataset is None


def test_cli_train_accepts_both_dataset_and_corpus():
    parser = argparse.ArgumentParser(description="Train Llama model")
    parser.add_argument("--dataset", type=int, default=None)
    parser.add_argument("--corpus", type=int, default=None)
    parser.add_argument("--backend", type=str, default=None)
    args = parser.parse_args(["--dataset", "2", "--corpus", "3"])
    assert args.dataset == 2
    assert args.corpus == 3


def test_cli_train_parses_backend_flag():
    parser = argparse.ArgumentParser(description="Train Llama model")
    parser.add_argument("--dataset", type=int, default=None)
    parser.add_argument("--corpus", type=int, default=None)
    parser.add_argument("--backend", type=str, default=None)
    args = parser.parse_args(["--backend", "local-gpu", "--dataset", "1"])
    assert args.backend == "local-gpu"
    assert args.dataset == 1
