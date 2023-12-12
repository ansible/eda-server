"""Common messages for the container engine."""


IMAGE_PULL_ERROR = (
    "Image {image_url} pull failed. The image url "
    "or the credentials may be incorrect."
)

POD_COMPLETED = "Pod {pod_id} has successfully exited."
POD_ERROR = "Pod {pod_id} status is unknown."
POD_RUNNING = "Pod {pod_id} is running."
POD_STOPPED = "Pod {pod_id} is stopped."
POD_GENERIC_FAIL = "Pod {pod_id} exited with code {exit_code}."
POD_NOT_RUNNING = "Pod {pod_id} is not running."
POD_PAUSED = "Pod {pod_id} is paused."
