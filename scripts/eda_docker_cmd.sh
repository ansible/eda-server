#!/usr/bin/env bash
USAGE_EXIT_CODE=3
FIRST_ARG=$1
FINAL_EXIT_CODE=0
CONTAINER_ID=$2
EDA_DOCKER_COMPOSE_YML_DIR=${EDA_DOCKER_COMPOSE_YML_DIR:-'../tools/docker/docker-compose-mac.yml'}

check_docker_compose_install_or_not(){
	DOCKER_COMPOSE_CODE=1
	which docker-compose &>/dev/null
	[ $? -ne 0 ] && echo "Please check docker-compose install or not." && exit $DOCKER_COMPOSE_CODE
}

check_docker_cmd_install_or_not(){
    DOCKER_CODE=2
    which docker &>/dev/null
    [ $? -ne 0 ] && echo "Please check docker install or not." && exit $DOCKER_CODE
}

quick_open_a_docker_shell(){
    docker exec -it $CONTAINER_ID /bin/bash
}

check_docker_log() {
  docker logs $CONTAINER_ID
}

check_args() {
    WARNING_VARIABLE=$1
   if [ $# != 3 ]
   then
        echo ${WARNING_VARIABLE}
        exit
   fi
}

# Script usage.
if [ $# -eq 0 ]
then
    echo "============================================================================="
    echo "To manage the docker cmd easily."
    echo "NOTE:"
    echo "Make sure the base container environment already setup."
    echo "The default docker-compose yml is ../tools/docker/docker-compose-mac.yml"
    echo 'You can export yml dir e.g.: export EDA_DOCKER_COMPOSE_YML_DIR="/path/docker-compose-mac.yml"'
    echo "Usage: `basename $0` [ARGS]"
    echo "  up                                 Run: docker-compose -f docker-compose-mac.yml up -d"
    echo "  down                               Run: docker-compose -f docker-compose-mac.yml down -v"
    echo "  lp,list-process                    List the process"
    echo "  li,list-images                     List the images"
    echo "  dl,docker-log                      To check single docker log with container id"
    echo "  dcl,docker-compose-log             To check docker-compose log"
    echo "  s,shell                            Open a docker shell quickly with container id"
    echo "  ri,remove-image                    Remove images with container id"
    echo "============================================================================="
    exit $USAGE_EXIT_CODE
fi

case "$FIRST_ARG" in
	up)
		check_docker_compose_install_or_not
		docker-compose -f ${EDA_DOCKER_COMPOSE_YML_DIR} up -d
		;;
	down)
		check_docker_compose_install_or_not
		docker-compose -f ${EDA_DOCKER_COMPOSE_YML_DIR} down -v
		;;
    lp|list-process)
        check_docker_cmd_install_or_not
        docker ps -a | egrep "docker-eda-default-worker-1|docker-postgres-1|docker-eda-ws-1|docker-redis-1|docker-eda-api-1|docker-eda-scheduler-1|docker-eda-activation-worker-1|docker-eda-activation-worker-2|docker-eda-ui-1"
        ;;
    li|list-images)
        check_docker_cmd_install_or_not
        echo "REPOSITORY                        TAG         IMAGE ID      CREATED        SIZE"
        docker images | egrep "eda-ui|eda-server|redis-6-c9s|postgresql-13-c9s"
        ;;
    s|shell)
        check_docker_cmd_install_or_not
        check_args "Usage: eda_docker_cmd.sh s <container_id>"  "$@"
        quick_open_a_docker_shell
        ;;
    dl|docker-log)
        check_docker_cmd_install_or_not
        check_args "Usage: eda_docker_cmd.sh dl <container_id>"  "$@"
        check_docker_log
        ;;
     dcl|docker-compose-log)
        check_docker_compose_install_or_not
        docker-compose -f ${EDA_DOCKER_COMPOSE_YML_DIR} logs --follow
        ;;
     ri|remove-image)
        check_docker_cmd_install_or_not
        shift 1
        [ $# -lt 1 ] && echo "Usage: eda_docker_cmd.sh rmi <image_id1> <image_id2>" && exit
        echo "$@"
        docker rmi "$@"
        ;;
       *)
		echo "No this option, please check the usage!!"
		exit $FINAL_EXIT_CODE
		;;
esac
exit
