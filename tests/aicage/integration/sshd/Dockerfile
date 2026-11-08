FROM alpine:3.24.4

RUN apk add --no-cache openssh-server \
    && mkdir -p /run/sshd \
    && ssh-keygen -A

CMD ["/usr/sbin/sshd", "-D", "-e", "-p", "2222", \
     "-o", "AuthorizedKeysFile=/authorized_keys", \
     "-o", "PasswordAuthentication=no", \
     "-o", "KbdInteractiveAuthentication=no", \
     "-o", "PermitRootLogin=yes", \
     "-o", "StrictModes=no"]
