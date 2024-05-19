.DEFAULT_GOAL = lint


# load env variables from .env
ifneq ("$(wildcard .env)","")
include .env
export
endif


PIP_DISABLE_PIP_VERSION_CHECK ?= 1
PIP_UPGRADE_STRATEGY ?= eager


_REQS_DIR ?= ./requirements
_REQS ?= $(_REQS_DIR)/main
_REQS_DEV ?= $(_REQS_DIR)/dev


.PHONY: upgrade-requirements
upgrade-requirements:
	pip install --upgrade pip wheel setuptools pip-tools
	pip-compile --verbose --upgrade "$(_REQS).in"
	pip-compile --verbose --upgrade "$(_REQS_DEV).in"


.PHONY: install-dev
install-dev: PIP_NO_DEPS ?= 1
install-dev:
	pip-sync "$(_REQS).txt" "$(_REQS_DEV).txt"
	pip install --editable .


.PHONY: mypy
mypy:
	mypy


.PHONY: lint
lint: mypy
lint:
	ruff format
	ruff check --fix
	@echo "Done!"


.PHONY: run
run:
	python -m aiohttp.web assetsrates.app:create_app


.PHONY: test
test:
	pytest


.PHONY: test-dockerignore
test-dockerignore:
	rsync --archive --verbose --dry-run . /dev/shm --exclude-from .dockerignore
