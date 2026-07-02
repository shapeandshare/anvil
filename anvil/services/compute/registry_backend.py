# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Internal registry backend name enumeration."""

from enum import StrEnum


class RegistryBackend(StrEnum):
    """Internal compute backend registry names.

    Attributes
    ----------
    LOCAL_STDLIB : str
        Local stdlib backend (``"local-stdlib"``).
    LOCAL_TORCH : str
        Local PyTorch backend (``"local-torch"``).
    LOCAL_LORA : str
        Local LoRA fine-tuning backend (``"local-lora"``).
    MODAL : str
        Modal cloud GPU backend (``"modal"``).
    SAAS_FINETUNE : str
        SaaS fine-tune compute backend (``"saas-finetune"``).
    """

    LOCAL_STDLIB = "local-stdlib"
    LOCAL_TORCH = "local-torch"
    LOCAL_LORA = "local-lora"
    MODAL = "modal"
    SAAS_FINETUNE = "saas-finetune"
