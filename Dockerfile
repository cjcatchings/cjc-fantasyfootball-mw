FROM python:3.11-alpine

# copy requirements file to image
COPY ./requirements.txt /app/requirements.txt

# change working dir
WORKDIR /app

# install Python dependencies
RUN pip install -r requirements.txt

# copy local files to image
COPY ./auth /app/auth
COPY ./awslambda /app/awslambda
COPY ./config /app/config
COPY ./db /app/db
COPY ./draft /app/draft
COPY ./web /app/web

ENV PYTHONPATH "${PYTHONPATH}:/app"

ENTRYPOINT ["python"]
CMD ["web/ff_webserver.py"]
