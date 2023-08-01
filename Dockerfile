FROM python:3.11.4-slim

RUN pip install "poetry==1.5.1"

WORKDIR /app
COPY . .
RUN poetry install

EXPOSE 80

CMD ["poetry", "run", "run-server"]
