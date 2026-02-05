# Building an eda-server image

If you need to build an eda-server for testing you can follow the following steps

### When fetching packages from public git repositories

```
podman build  -t localhost/myserver:latest  -f tools/docker/Dockerfile .
```

### When fetching packages from private git repositories

#### If your ssh key is pass phrase protected follow these steps
```
cp ~/.ssh/id_ed25519 /tmp/build_key  
ssh-keygen -p -f /tmp/build_key # Remove pass phrase interactively
   
podman build --secret id=git_ssh_key,src=/tmp/build_key \ 
 -t localhost/myserver:latest  \
 -f tools/docker/Dockerfile .

shred -u /tmp/build_key
```

#### If your ssh key is not pass phrase protected

```
podman build  --secret id=git_ssh_key,src=$HOME/.ssh/id_ed25519  \
-t localhost/myserver:latest  \
-f tools/docker/Dockerfile .
```

