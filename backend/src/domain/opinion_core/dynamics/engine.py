"""Joint-vector bounded-confidence HK with ensemble distribution-summary assimilation.

Real posts enter only the summary observation operator. Virtual particles are not
matched to individual posts. Categorical coordinates live on probability simplexes.
"""

from datetime import datetime
import numpy as np
from opinion_core.schemas.workflow import ModelSpec
from .latent import fit_codec, encode, decode, constrain, calibrate


def project(particles, blocks):
    out = np.asarray(particles, dtype=float).copy()
    for low, high in blocks:
        x = out[..., low:high]
        ordered = np.sort(x, axis=-1)[..., ::-1]
        cssv = np.cumsum(ordered, axis=-1) - 1
        indices = np.arange(1, high - low + 1)
        rho = np.maximum((ordered - cssv / indices > 0).sum(axis=-1) - 1, 0)
        theta = np.take_along_axis(cssv, np.expand_dims(rho, -1), axis=-1)[..., 0] / (
            rho + 1
        )
        out[..., low:high] = np.maximum(x - theta[..., None], 0)
    out[..., -2:] = np.clip(out[..., -2:], -1, 1)
    return out


def summary(particles):
    return np.concatenate(
        [particles.mean(axis=-2), (particles * particles).mean(axis=-2)], axis=-1
    )


def evolve(ensemble, config, blocks, rng, codec=None):
    out = []
    for particles in ensemble:
        if config.algorithm == "coordinate_hk_enkf":
            target = particles.copy()
            for d in range(particles.shape[1]):
                mask = (
                    np.abs(particles[:, None, d] - particles[None, :, d])
                    <= config.epsilon
                )
                target[:, d] = mask @ particles[:, d] / mask.sum(axis=1)
        else:
            distance = np.sqrt(
                ((particles[:, None, :] - particles[None, :, :]) ** 2).sum(axis=-1)
            )
            mask = distance <= config.epsilon
            target = mask @ particles / mask.sum(axis=1, keepdims=True)
        out.append(particles + config.relaxation * (target - particles))
    out = np.asarray(out) + rng.normal(0, config.process_noise, size=ensemble.shape)
    return constrain(out, codec, blocks) if codec else project(out, blocks)


def assimilate(
    ensemble, observation, sampling_variance, config, blocks, rng, codec=None
):
    n = len(ensemble)
    x = ensemble.reshape(n, -1)
    predicted = summary(decode(ensemble, codec, blocks) if codec else ensemble)
    xa, ya = x - x.mean(axis=0), predicted - predicted.mean(axis=0)
    r = np.diag(np.asarray(sampling_variance) + config.observation_noise**2)
    cross = xa.T @ ya / (n - 1)
    innovation_cov = ya.T @ ya / (n - 1) + r
    gain = np.linalg.solve(innovation_cov, cross.T).T
    perturb = rng.multivariate_normal(np.zeros(len(observation)), r, size=n)
    updated = x + (np.asarray(observation) + perturb - predicted) @ gain.T
    updated = updated.reshape(ensemble.shape)
    return constrain(updated, codec, blocks) if codec else project(updated, blocks)


def fit_assimilate(observations, config, check_cancel=lambda: None):
    config = ModelSpec.model_validate(config)
    calibration = {"status": "disabled", "selected_by": "configured_parameters"}
    if config.calibrate:
        config, calibration = calibrate(observations, config, check_cancel)
    train = [
        w
        for w in observations["windows"]
        if datetime.fromisoformat(w["end"]) <= config.training_cutoff
    ]
    first = next((i for i, w in enumerate(train) if w["joint_n"]), None)
    if first is None:
        raise ValueError("no joint valid observations before cutoff")
    rng = np.random.default_rng(config.seed)
    rows = np.asarray(train[first]["joint_vectors"])
    ensemble = rows[
        rng.integers(len(rows), size=(config.ensemble_size, config.particles))
    ]
    codec = None
    if config.algorithm == "latent_hk_enkf":
        codec = fit_codec(
            [v for w in train for v in w["joint_vectors"]], config.latent_dimensions
        )
        codec["training_cutoff"] = config.training_cutoff.isoformat()
        ensemble = encode(ensemble, codec)
    trace = [{"end": train[first]["end"], "joint_n": len(rows), "action": "initialize"}]
    for window in train[first + 1 :]:
        check_cancel()
        ensemble = evolve(ensemble, config, observations["simplex_blocks"], rng, codec)
        action = "predict_missing"
        if window["joint_n"] and config.algorithm != "hk_without_assimilation":
            ensemble = assimilate(
                ensemble,
                window["summary"],
                window["summary_sampling_variance"],
                config,
                observations["simplex_blocks"],
                rng,
                codec,
            )
            action = "assimilate_summary"
        trace.append(
            {"end": window["end"], "joint_n": window["joint_n"], "action": action}
        )
    return {
        "model_version": "latent-pca-joint-hk-summary-enkf-v1"
        if codec
        else "joint-hk-summary-enkf-v1",
        "config": config.model_dump(mode="json"),
        "codec": codec,
        "calibration": calibration,
        "features": observations["features"],
        "simplex_blocks": observations["simplex_blocks"],
        "bins": observations["bins"],
        "schema_version": observations["schema_version"],
        "target_id": observations["target_id"],
        "state_time": train[-1]["end"],
        "window_seconds": observations["spec"]["window_seconds"],
        "ensemble": ensemble.tolist(),
        "trace": trace,
        "validation_status": "experimental_unvalidated",
        "historical_availability_verified": observations[
            "historical_availability_verified"
        ],
    }


def forecast(state, scenario=None, check_cancel=lambda: None):
    config = ModelSpec.model_validate(state["config"])
    codec = state.get("codec")
    ensemble = np.asarray(state["ensemble"], dtype=float)
    rng = np.random.default_rng(config.seed + 1)
    steps = []
    for step in range(1, config.horizon + 1):
        check_cancel()
        active = (
            scenario
            and scenario.start_step <= step < scenario.start_step + scenario.duration
        )
        local = config
        if active and scenario.mechanism == "confidence_change":
            local = config.model_copy(update={"epsilon": scenario.parameter_value})
        elif active and scenario.mechanism == "relaxation_change":
            local = config.model_copy(update={"relaxation": scenario.parameter_value})
        ensemble = evolve(ensemble, local, state["simplex_blocks"], rng, codec)
        decoded = (
            decode(ensemble, codec, state["simplex_blocks"])
            if codec
            else ensemble.copy()
        )
        if active and scenario.mechanism == "state_shift":
            dimension = -2 if scenario.dimension == "stance" else -1
            decoded[..., dimension] += scenario.shift
            decoded = project(decoded, state["simplex_blocks"])
            ensemble = encode(decoded, codec) if codec else decoded
            if codec:
                decoded = decode(ensemble, codec, state["simplex_blocks"])
        fields = {}
        for name, d in [("stance", -2), ("sentiment", -1)]:
            masses = np.array(
                [np.histogram(x[:, d], bins=state["bins"])[0] / len(x) for x in decoded]
            )
            means = decoded[..., d].mean(axis=1)
            fields[name] = {
                "mass": masses.mean(axis=0).tolist(),
                "mean": float(means.mean()),
                "variance": float(decoded[..., d].var(axis=1).mean()),
                "negative_mass": float((decoded[..., d] < 0).mean()),
                "mean_interval": np.quantile(means, [0.05, 0.95]).tolist(),
                "mass_interval": np.quantile(masses, [0.05, 0.95], axis=0).tolist(),
            }
        categories = {}
        for low, high in state["simplex_blocks"]:
            means = decoded[..., low:high].mean(axis=1)
            categories[state["features"][low].split(":")[0]] = {
                "labels": state["features"][low:high],
                "mass": means.mean(axis=0).tolist(),
                "mass_interval": np.quantile(means, [0.05, 0.95], axis=0).tolist(),
            }
        steps.append({"step": step, "fields": fields, "categories": categories})
    return {
        "kind": "simulated" if scenario else "forecast",
        "state_time": state["state_time"],
        "model_version": state["model_version"],
        "schema_version": state["schema_version"],
        "target_id": state["target_id"],
        "config": state["config"],
        "window_seconds": state["window_seconds"],
        "bins": state["bins"],
        "steps": steps,
        "interval_meaning": "90% ensemble spread; coverage has not been calibrated",
        "validation_status": "experimental_unvalidated",
        "historical_availability_verified": state["historical_availability_verified"],
    }
