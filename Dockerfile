javaFROM python:3.12-alpine

COPY docker-entrypoint.sh ./

WORKDIR /usr/local/app

COPY static ./static

COPY main.py requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]