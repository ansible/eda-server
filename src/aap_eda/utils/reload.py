# Copyright (c) 2017 Ansible by Red Hat
# All Rights Reserved.

import logging
import os

# Python
import subprocess

logger = logging.getLogger("eda.main.utils.reload")

def supervisor_service_command(command, service="*", communicate=True):
    # noqa
    """
    Do read this example use pattern of supervisorctl.

    # supervisorctl restart
    #   eda-processes:receiver
    #   eda-processes:factcacher
    """
    args = ["supervisorctl"]

    supervisor_config_path = os.getenv("SUPERVISOR_CONFIG_PATH", None)
    if supervisor_config_path:
        args.extend(["-c", supervisor_config_path])

    args.extend([command, ":".join(["eda-processes", service])])
    logger.debug(
        "Issuing command to {} services, args={}".format(  # noqa: P101
            command, args
        )  # noqa: P101, E501
    )
    supervisor_process = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if communicate:
        restart_stdout, restart_err = supervisor_process.communicate()
        restart_code = supervisor_process.returncode
        if restart_code or restart_err:
            logger.error(
                "supervisorctl {} {} errored with exit code `{}`, stdout:\n{}stderr:\n{}".format(  # noqa
                    command,
                    service,
                    restart_code,
                    restart_stdout.strip(),
                    restart_err.strip(),
                )
            )
        else:
            logger.debug(
                "supervisorctl {} {} succeeded".format(  # noqa: P101
                    command, service
                )  # noqa: P101, E501
            )
    else:
        logger.info(
            "Submitted supervisorctl {} command, not waiting for result".format(  # noqa
                command
            )
        )


def stop_local_services(communicate=True):
    logger.warning("Stopping services on this node in response to user action")
    supervisor_service_command(command="stop", communicate=communicate)
