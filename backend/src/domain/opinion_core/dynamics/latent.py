"""Train-only PCA map. Joint HK operates in this latent coordinate system.

Decoder projection enforces categorical simplexes and scalar [-1,1] bounds.
This is an experimental model, not a reproduction of a validated latent HK paper.
"""

import numpy as np


def fit_codec(rows, dimensions):
    x = np.asarray(rows, dtype=float)
    mean = x.mean(axis=0)
    _, singular, components = np.linalg.svd(x - mean, full_matrices=False)
    rank = int(
        np.sum(singular > max(float(singular[0]) if len(singular) else 0, 1) * 1e-10)
    )
    count = min(dimensions, len(components), max(1, rank))
    total = float(np.sum(singular**2))
    return {
        "kind": "pca",
        "version": "train-only-pca-v1",
        "mean": mean.tolist(),
        "components": components[:count].tolist(),
        "dimensions": count,
        "training_rows": len(x),
        "explained_variance_ratio": (singular[:count] ** 2 / total).tolist()
        if total
        else [0.0] * count,
        "rank": rank,
        "whiten": False,
    }


def encode(x, codec):
    return (np.asarray(x) - np.asarray(codec["mean"])) @ np.asarray(
        codec["components"]
    ).T


def decode(z, codec, blocks):
    from .engine import project

    return project(
        np.asarray(z) @ np.asarray(codec["components"]) + np.asarray(codec["mean"]),
        blocks,
    )


def constrain(z, codec, blocks):
    return encode(decode(z, codec, blocks), codec)


def calibrate(observations, config, check_cancel):
    """Rolling one-window validation, fitting a fresh encoder only on each prefix."""
    from datetime import datetime
    from .engine import fit_assimilate, forecast

    windows = [
        w
        for w in observations["windows"]
        if datetime.fromisoformat(w["end"]) <= config.training_cutoff
    ]
    origins = [
        i
        for i in range(2, len(windows))
        if windows[i]["joint_n"] and any(w["joint_n"] for w in windows[:i])
    ][-3:]
    if not origins:
        return config, {
            "status": "insufficient_training_windows",
            "selected_by": "configured_defaults",
            "candidates": [],
        }
    scores = []
    for epsilon in config.epsilon_candidates:
        for relaxation in config.relaxation_candidates:
            errors = []
            for i in origins:
                check_cancel()
                local = config.model_copy(
                    update={
                        "epsilon": epsilon,
                        "relaxation": relaxation,
                        "calibrate": False,
                        "horizon": 1,
                        "training_cutoff": datetime.fromisoformat(
                            windows[i - 1]["end"]
                        ),
                    }
                )
                state = fit_assimilate(observations, local, check_cancel)
                predicted = forecast(state, check_cancel=check_cancel)["steps"][0][
                    "fields"
                ]
                real = np.asarray(windows[i]["joint_vectors"])
                loss = 0.0
                for name, d in [("stance", -2), ("sentiment", -1)]:
                    mass = np.histogram(real[:, d], bins=observations["bins"])[0] / len(
                        real
                    )
                    # Integrated absolute CDF error on the fixed support.
                    loss += float(
                        np.sum(
                            np.abs(np.cumsum(mass) - np.cumsum(predicted[name]["mass"]))
                        )
                        * np.diff(observations["bins"])[0]
                    )
                errors.append(loss / 2)
            scores.append(
                {
                    "epsilon": epsilon,
                    "relaxation": relaxation,
                    "mean_binned_w1": float(np.mean(errors)),
                    "fold_losses": errors,
                }
            )
    best = min(scores, key=lambda v: v["mean_binned_w1"])
    return config.model_copy(
        update={"epsilon": best["epsilon"], "relaxation": best["relaxation"]}
    ), {
        "status": "fitted",
        "selected_by": "rolling_training_prefix_validation",
        "metric": "mean stance/sentiment binned Wasserstein-1",
        "folds": [
            {"training_end": windows[i - 1]["end"], "validation_end": windows[i]["end"]}
            for i in origins
        ],
        "selected": best,
        "candidates": scores,
        "external_test_used": False,
    }
