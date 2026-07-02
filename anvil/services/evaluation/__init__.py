# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Evaluation domain service package.

Provides orchestration of fine-tuned model evaluation: per-sample
generation + loss computation, side-by-side comparison against a base
model, and SSE-streamed async evaluation runs.
"""
