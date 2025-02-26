from django.conf import settings

from .post_load import get_boolean


def _rq_common_parameters():
    params = {
        "DB": settings.REDIS_DB,
        "USERNAME": settings.REDIS_USER,
        "PASSWORD": settings.REDIS_USER_PASSWORD,
    }
    if settings.REDIS_UNIX_SOCKET_PATH:
        params["UNIX_SOCKET_PATH"] = settings.REDIS_UNIX_SOCKET_PATH
    else:
        params |= {
            "HOST": settings.REDIS_HOST,
            "PORT": settings.REDIS_PORT,
        }
        if settings.REDIS_TLS:
            params["SSL"] = True
        else:
            # TODO: Deprecate implicit setting based on cert path in favor of
            #       MQ_TLS as the determinant.
            if settings.REDIS_CLIENT_CERT_PATH and settings.REDIS_TLS is None:
                params["SSL"] = True
            else:
                params["SSL"] = False
    return params


def _rq_redis_client_additional_parameters():
    params = {}
    if (
        not settings.REDIS_UNIX_SOCKET_PATH
    ) and settings.REDIS_CLIENT_CERT_PATH:
        params |= {
            "ssl_certfile": settings.REDIS_CLIENT_CERT_PATH,
            "ssl_keyfile": settings.REDIS_CLIENT_KEY_PATH,
            "ssl_ca_certs": settings.REDIS_CLIENT_CACERT_PATH,
        }
    return params


def rq_standalone_redis_client_instantiation_parameters():
    params = _rq_common_parameters() | _rq_redis_client_additional_parameters()

    # Convert to lowercase for use in instantiating a redis client.
    params = {k.lower(): v for (k, v) in params.items()}
    return params


def rq_redis_client_instantiation_parameters():
    params = rq_standalone_redis_client_instantiation_parameters()

    # Include the HA cluster parameters.
    if settings.REDIS_HA_CLUSTER_HOSTS:
        params["mode"] = "cluster"
        params["redis_hosts"] = settings.REDIS_HA_CLUSTER_HOSTS
        params["socket_keepalive"] = get_boolean(
            settings, "MQ_SOCKET_KEEP_ALIVE", True
        )
        params["socket_connect_timeout"] = settings.get(
            "MQ_SOCKET_CONNECT_TIMEOUT", 10
        )
        params["socket_timeout"] = settings.get("MQ_SOCKET_TIMEOUT", 150)
        params["cluster_error_retry_attempts"] = settings.get(
            "MQ_CLUSTER_ERROR_RETRY_ATTEMPTS", 3
        )
        from redis.backoff import ConstantBackoff
        from redis.retry import Retry

        params["retry"] = Retry(backoff=ConstantBackoff(3), retries=20)
    return params
