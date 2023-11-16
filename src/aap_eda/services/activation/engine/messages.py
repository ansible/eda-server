"""Common messages for the container engine."""


IMAGE_PULL_ERROR = (
    "Image {image_url} pull failed. The image url "
    "or the credentials may be incorrect."
)

POD_COMPLETED = "Pod {pod_id} has successfully exited."
POD_ERROR = "Pod {pod_id} status is unknown."
POD_RUNNING = "Pod {pod_id} is running."
POD_STOPPED = "Pod {pod_id} is stopped."
