.PHONY: help test run smoke report

help:
	@echo "Targets:"
	@echo "  make test                          run the harness's own test suite"
	@echo "  make run ENV=<label>               run all 12 tasks x 3 repeats against ENV"
	@echo "  make smoke ENV=<label> TASK=<id>    run one task once, for cheap smoke-testing"
	@echo "  make report                        aggregate results/*.jsonl into a report"
	@echo "  make report RESULTS_DIR=<dir>       aggregate from a different results directory"
	@echo "  make report RESULTS_DIR=<dir> OUT=<file>   also write the dashboard elsewhere"

test:
	uv run pytest -q

run:
	@if [ -z "$(ENV)" ]; then echo "usage: make run ENV=<label>"; exit 1; fi
	uv run python -m harness.run --env $(ENV)

smoke:
	@if [ -z "$(ENV)" ] || [ -z "$(TASK)" ]; then echo "usage: make smoke ENV=<label> TASK=<task_id>"; exit 1; fi
	uv run python -m harness.run --env $(ENV) --task $(TASK) --repeats 1

report:
	uv run python -m harness.report $(if $(RESULTS_DIR),--results-dir $(RESULTS_DIR)) $(if $(OUT),--out $(OUT))
