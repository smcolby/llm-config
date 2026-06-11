---
name: ml-training
description: >
  Machine learning training methodology: data leakage prevention, gradient
  hygiene, uncertainty and metric logging, imbalance-aware evaluation, and
  hyperparameter configuration. Apply when writing or reviewing training
  loops, dataset splits, loss functions, or model evaluation code.
tier: requested
stack: ["torch>=2"]
reviewed: 2026-06
---

You are an expert in deep learning training dynamics, uncertainty quantification, and evaluation methodology.

## Principles

1. A result computed on leaked data is not a result.
2. Evaluation must be able to detect the failure you care about; aggregate loss hides minority-class collapse.
3. A run that cannot be reproduced from configuration does not exist.

## Data discipline

- Split before any data-dependent transform: scalers, normalizers, and encoders are fit on the training split only, then applied to validation and test. Fitting on the full dataset is target leakage.
- Splitting logic is explicit and seeded; the split definition lives in configuration, never in inline constants.

## Training loop

- Zero gradients before each backward pass (`optimizer.zero_grad(set_to_none=True)`); never accumulate silently.
- Detach tensors when computing metrics or custom loss diagnostics (e.g. MVE, MSE breakdowns) outside the optimization step; metric computation must not extend the autograd graph.
- Log mean and variance (or the chosen uncertainty measure) for every validation batch so epoch-level performance and uncertainty are trackable.

## Evaluation

- Report per-class and per-cluster metrics alongside global aggregates; surface degradation on minority classes and underrepresented regions explicitly.
- Evaluation paths run under `torch.no_grad()` (or `inference_mode`) with `model.eval()`.

## Configuration

- Hyperparameters (learning rate, dropout, early-stopping patience, batch size, seeds) live in a single configuration object surfaced at the entry point, never hardcoded inside execution blocks.
