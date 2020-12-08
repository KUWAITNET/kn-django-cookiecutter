# pull official base image
FROM python:3.6

#Get initial apps
RUN apt install bash git

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements ./requirements
COPY requirements.txt .
RUN pip install  --default-timeout=100 -r requirements.txt


# copy project
COPY . .
