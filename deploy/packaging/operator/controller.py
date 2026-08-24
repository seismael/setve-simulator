"""Kubernetes Kopf Operator for STEVECluster CRD Lifecycle Management."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("steve.operator")

try:
    import kopf
except ImportError:
    kopf = None


def reconcile_steve_cluster(spec: dict[str, Any], name: str, namespace: str) -> dict[str, Any]:
    """Pure reconciliation logic translating STEVECluster spec into workload manifests."""
    target_endpoint = spec.get("targetEndpoint", "posix://local")
    target_throughput_gbps = spec.get("targetThroughputGbps", 100)
    block_size_bytes = spec.get("blockSizeBytes", 1048576)
    entropy_ratio = spec.get("entropyRatio", 0.8)
    duration_seconds = spec.get("workloadDurationSeconds", 30)
    scaling_policy = spec.get("scalingPolicy", {})

    min_replicas = scaling_policy.get("minReplicas", 1)
    max_replicas = scaling_policy.get("maxReplicas", 32)

    logger.info(
        f"Reconciling STEVECluster '{name}' in '{namespace}' "
        f"[Target: {target_endpoint}, Throughput: {target_throughput_gbps} Gbps, "
        f"Scale: {min_replicas}..{max_replicas}]"
    )

    # Master Deployment Spec
    master_deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": f"{name}-master",
            "namespace": namespace,
            "labels": {"app.kubernetes.io/name": "steve-master", "steve.io/cluster": name},
        },
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"steve.io/cluster": name, "role": "master"}},
            "template": {
                "metadata": {"labels": {"steve.io/cluster": name, "role": "master"}},
                "spec": {
                    "containers": [
                        {
                            "name": "master",
                            "image": "steve-master:latest",
                            "env": [
                                {"name": "STEVE_RUN_ID", "value": name},
                                {"name": "STEVE_TARGET_URI", "value": target_endpoint},
                                {
                                    "name": "STEVE_THROUGHPUT_GBPS",
                                    "value": str(target_throughput_gbps),
                                },
                                {"name": "STEVE_BLOCK_SIZE", "value": str(block_size_bytes)},
                                {"name": "STEVE_ENTROPY_RATIO", "value": str(entropy_ratio)},
                                {"name": "STEVE_DURATION_SEC", "value": str(duration_seconds)},
                            ],
                            "ports": [{"containerPort": 50051, "name": "grpc-sync"}],
                        }
                    ]
                },
            },
        },
    }

    # KEDA ScaledObject Spec
    scaled_object = {
        "apiVersion": "keda.sh/v1alpha1",
        "kind": "ScaledObject",
        "metadata": {
            "name": f"{name}-autoscaler",
            "namespace": namespace,
            "labels": {"steve.io/cluster": name},
        },
        "spec": {
            "scaleTargetRef": {"name": f"{name}-worker"},
            "minReplicaCount": min_replicas,
            "maxReplicaCount": max_replicas,
            "triggers": [
                {
                    "type": "metrics-api",
                    "metadata": {
                        "targetValue": str(scaling_policy.get("targetQueueLag", 50)),
                        "url": f"http://{name}-master.{namespace}.svc:8123/metrics/queue_lag",
                    },
                }
            ],
        },
    }

    return {
        "master_deployment": master_deployment,
        "scaled_object": scaled_object,
        "status": "Configured",
    }


if kopf is not None:

    @kopf.on.create("steve.io", "v1alpha1", "steveclusters")
    def create_fn(
        spec: dict[str, Any], name: str, namespace: str, logger: Any, **kwargs: Any
    ) -> dict[str, Any]:
        """Kopf create handler for STEVECluster Custom Resources."""
        return reconcile_steve_cluster(spec, name, namespace)

    @kopf.on.update("steve.io", "v1alpha1", "steveclusters")
    def update_fn(
        spec: dict[str, Any], name: str, namespace: str, logger: Any, **kwargs: Any
    ) -> dict[str, Any]:
        """Kopf update handler for STEVECluster Custom Resources."""
        return reconcile_steve_cluster(spec, name, namespace)
