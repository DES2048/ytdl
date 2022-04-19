FROM python:3.8.5-alpine

ARG UID=1000
ARG GID=1000
ENV UID=${UID}
ENV GID=${GID}

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

#RUN addgroup -g $UID oleg \
#   && adduser -u $UID -G oleg -s /bin/sh -D oleg

#USER $UID

WORKDIR /app/ytdl

COPY ./requirements.common.txt .

RUN pip install --upgrade pip \
    && pip install -r requirements.common.txt

RUN pip install debugpy -t /tmp

COPY . /app/ytdl

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]