FROM python:3.14
LABEL maintainer="gabriellafonso.dev@gmail.com"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /server

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY server .

EXPOSE 8000
