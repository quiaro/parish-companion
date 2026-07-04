FROM postgres:16-alpine

RUN apk add --no-cache aws-cli dcron

COPY backup.sh /backup.sh
COPY crontab /etc/crontabs/root
RUN chmod +x /backup.sh

CMD ["crond", "-f", "-l", "2"]
