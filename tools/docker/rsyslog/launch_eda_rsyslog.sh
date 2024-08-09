#!/usr/bin/env bash
if [ `id -u` -ge 500 ]; then
    echo "awx:x:`id -u`:`id -g`:,,,:/var/lib/eda:/bin/bash" >> /tmp/passwd
    cat /tmp/passwd > /etc/passwd
    rm /tmp/passwd
fi

set -e

wait-for-migrations

# This file will be re-written when the dispatcher calls reconfigure_rsyslog(),
# but it needs to exist when supervisor initially starts rsyslog to prevent the
# container from crashing. This was the most minimal config I could get working.
cat << EOF > /var/lib/eda/rsyslog/rsyslog.conf
action(type="omfile" file="/dev/null")
EOF

exec supervisord -c /etc/supervisord_rsyslog.conf