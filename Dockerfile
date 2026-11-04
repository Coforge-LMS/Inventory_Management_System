FROM python:3.14.10-slim

# Show output straight away instead of holding it in a buffer.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first. This layer is only rebuilt when requirements.txt changes,
# so ordinary code edits do not reinstall everything.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The code comes after the dependencies because it changes the most often.
COPY . .

# The database lives on a volume, so it survives when the container is removed.
ENV INVENTORY_DB=/data/inventory.db
VOLUME /data

CMD ["python", "main.py"]