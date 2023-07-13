FROM python:3.10.11

EXPOSE 32167

RUN mkdir /app

COPY . /app

WORKDIR /app

RUN pip3 install poetry \
    && poetry config virtualenvs.create false

RUN poetry install

ENTRYPOINT ["poetry", "run", "start"]
