import logging

from kubernetes import client, config, watch

logger = logging.getLogger(__name__)


class ActivationKubernetes:
    def __init__(self):
        # Setup kubernetes api client
        config.load_incluster_config()

        self.batch_api = client.BatchV1Api()
        self.client_api = client.CoreV1Api()

    @staticmethod
    def create_container(image, name, pull_policy, url, activation_id):
        container = client.V1Container(
            image=image,
            name=name,
            image_pull_policy=pull_policy,
            args=[
                "--worker",
                "--websocket-address",
                url,
                "--id",
                str(activation_id),
            ],
            command=["ansible-rulebook"],
        )

        logger.info(
            f"Created container: name: {container.name}, "
            f"image: {container.image}"
            f"args: {container.args}"
        )

        return container

    @staticmethod
    def create_pod_template(pod_name, container):
        pod_template = client.V1PodTemplateSpec(
            spec=client.V1PodSpec(
                restart_policy="Never", containers=[container]
            ),
            metadata=client.V1ObjectMeta(name=pod_name, labels={"app": "eda"}),
        )

        logger.info(f"Created Pod template: {pod_name}")

        return pod_template

    @staticmethod
    def create_job(job_name, pod_template, backoff_limit=0, ttl=0):
        metadata = client.V1ObjectMeta(
            name=job_name, labels={"job-name": job_name, "app": "eda"}
        )

        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=metadata,
            spec=client.V1JobSpec(
                backoff_limit=backoff_limit,
                template=pod_template,
                ttl_seconds_after_finished=ttl,
            ),
        )

        logger.info(f"Created Job template: {job_name},")

        return job

    async def run_activation_job(self, job_name, job_spec, namespace):
        logger.info(f"Create Job: {job_name}")
        self.batch_api.create_namespaced_job(
            namespace=namespace, body=job_spec, async_req=True
        )

        w = watch.Watch()
        for event in w.stream(
            self.batch_api.list_namespaced_job,
            namespace=namespace,
            label_selector=f"job-name={job_name}",
            timeout_seconds=0,
            _request_timeout=300,
        ):
            o = event["object"]
            obj_name = o.metadata.name

            if o.status.succeeded:
                logger.info(f"Job {obj_name}: Succeeded")
                self.log_job_result(job_name=obj_name, namespace=namespace)
                w.stop()

            if o.status.active:
                logger.info(f"Job {obj_name}: Active")

            if not o.status.active and o.status.failed:
                logger.info(f"Job {obj_name}: Failed")
                self.log_job_result(job_name=obj_name, namespace=namespace)
                w.stop()

    def log_job_result(self, job_name, namespace):
        pod_list = self.client_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=f"job-name={job_name}",
            watch=False,
        )

        job_pod_name = None
        for i in pod_list.items:
            job_pod_name = i.metadata.name
            logger.info(f"Job Pod Name: {i.metadata.name}")

        if job_pod_name is not None:
            pod_log = self.client_api.read_namespaced_pod_log(
                name=job_pod_name, namespace=namespace, pretty=True
            )

            logger.info("Job Pod Logs:")
            logger.info(f"{pod_log}")

        else:
            logger.info("No job logs found")
