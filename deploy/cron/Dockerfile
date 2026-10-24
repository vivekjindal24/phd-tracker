# Scheduled jobs for the self-hosted stack: same pg_dump major as the db service.
FROM postgres:16-alpine
RUN apk add --no-cache curl rclone tzdata
COPY --chmod=755 run.sh /usr/local/bin/run.sh
# Times are in the container's TZ (Asia/Kolkata by default). Output goes to `docker compose logs cron`.
RUN printf '%s\n' \
      '0 2 * * * run.sh backup >/proc/1/fd/1 2>/proc/1/fd/2' \
      '0 6 * * * run.sh daily >/proc/1/fd/1 2>/proc/1/fd/2' \
      > /etc/crontabs/root
# crond jobs don't inherit the container environment: snapshot it for run.sh.
CMD ["sh", "-c", "umask 077 && export -p > /etc/anveshan.env && exec crond -f -l 8"]
