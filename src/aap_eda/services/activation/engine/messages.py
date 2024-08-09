"""Common messages for the container engine."""

IMAGE_PULL_ERROR = (
    "Image {image_url} pull failed. The image url "
    "or the credentials may be incorrect."
)

POD_COMPLETED = "Pod {pod_id} has successfully exited."
POD_UNEXPECTED = "Pod {pod_id} is in an unexpected state: {pod_state}."
POD_RUNNING = "Pod {pod_id} is running."
POD_STOPPED = "Pod {pod_id} is stopped."
POD_GENERIC_FAIL = "Pod {pod_id} exited with code {exit_code}."
POD_NOT_RUNNING = "Pod {pod_id} is not running."
POD_WRONG_STATE = "Pod {pod_id} is in a wrong state: {pod_state}."
