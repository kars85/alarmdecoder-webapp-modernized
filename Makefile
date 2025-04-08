.PHONY: test lint format run

test:
	pytest

lint:
	black --check .

format:
	black .

run:
	flask run
