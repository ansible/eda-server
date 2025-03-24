# Task Dispatcher

At demo phase currently, this removes use of Redis pub/sub queues in favor of pg_notify.
RQ worker is removed and replaced with in-house dispatcherd library,
coming from the AWX dispatcher.

## Demo Deployment

Currently only tested with Docker Compose development environment `tools/docker/docker-compose-dev.yaml`.
No aditional steps required, just follow the normal deployment steps. We expect the system works as before.

You may want to deploy the development environment to test the dispatcherd in parallel with the regular deployment,
in this case you need to define EDA_IMAGE environment variable with a different value, for example `localhost/aap-eda-dispatcherd`
and run manually the docker compose command with a different project name, for example `docker-compose -p eda-dispatcherd -f ./tools/docker/docker-compose-dev.yaml up`.

## Development of the dispatcherd alongside the EDA

Clone the project in `./dispatcherd` directory and run `pip install -e ./dispatcherd` to install the dispatcherd library in development mode in the current virtual environment.
You may need to configure the environment variable PYTHONPATH in your session and IDE to include the dispatcherd directory.
`export PYTHONPATH=./dispatcherd:${PYTHONPATH}`
The docker compose already sets the PYTHONPATH in the environment

## Main Changes

#### Plugging in Schedules

The setting `RQ_PERIODIC_JOBS` is replaced with `CELERYBEAT_SCHEDULE`,
naming subject to revision.
This is the dispatcherd naming for this.

#### Substutiting RQ Workers with Dispatchers

Commands that run `rqworker` are replaced with dispatcherd commands in `tools/docker/docker-compose-dev.yaml`, for example.

#### Task Modifications

Behaviorly, pg_notify will work differently than RQ.
Some changes to the tasks are needed so that it doesn't error.
This is seen with the use of `advisory_lock`, for example.
