FROM localhost/aap-eda:latest

ARG CA_FILE

COPY $CA_FILE  /etc/pki/ca-trust/source/anchors/

RUN update-ca-trust extract

CMD ["aap-eda-manage", "runserver", "0.0.0.0:8000"]
