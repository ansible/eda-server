# Development with podman on Mac

If you are developing on Mac with podman this document will guide you thru the steps you need to 
1. Successfully run the product using podman
2. Make development changes and run product using your local changes

# Pre Requisites
1. podman: [Podman for Mac](https://podman.io/getting-started/installation#macos)
2. docker-compose: [Docker for Mac](https://www.docker.com/docker-mac)




### One time setup
1. brew install podman
2. podman machine init --cpus 2 --memory 2048 --disk-size 100 --now
3. alias docker=podman
4. This is an optional step

The podman machine typically has a user id of 501 when it runs the  
podman, if the uid is other than 501 you might have to set this env var  
Run this command to get the userid being used by podman  

```
podman info | grep podman.sock | awk '{print $2}'
```

/run/user/501/podman/podman.sock

If the value of userid is not 501

export EDA_HOST_PODMAN_SOCKET_URL=/run/user/{your_uid}/podman/podman.sock

### No docker installed
No addtional steps needed

### With docker installed
We need to create a SSH tunnel between the Mac and the podman vm created above, we need the following steps
1. podman system connection ls
```
Name URI Identity  Default

podman-machine-default ssh://core@localhost:49473/run/user/501/podman/podman.sock
```
example use the uid 501 above and port 49473 from your enviornment in the next step

2. Create a secure tunnel, and forward the local socket to the remote socket 
```
ssh -fnNT -L/tmp/podman.sock:/run/user/{uid}/podman/podman.sock -i ~/.ssh/podman-machine-default ssh://core@localhost:{port} -o StreamLocalBindUnlink=yes

ps aux | grep "ssh -fnNT" |grep -v color
```
3. export DOCKER_HOST=unix:///tmp/podman.sock


## Start the app with available images in quay.io

1. podman login quay.io
2. export EDA_CONTROLLER_URL="your_controller_url"
3. export EDA_CONTROLLER_SSL_VERIFY=no
4. docker-compose -f ./tools/docker/docker-compose-mac.yml up

## Start the app with your local changes

You can build an image with your changes and use that image in docker-compose

1. podman build -t localhost/myserver -f tools/docker/Dockerfile .
2. export EDA_IMAGE=localhost/myserver:latest
3. docker-compose -f ./tools/docker/docker-compose-mac.yml up

You can now access the api at <https://localhost:8443/api/eda/va/docs/> with default login username and password(admin/testpass).

## Layout
![Alt_PodmanDeployment](./podman_deployment.png?raw=true)
