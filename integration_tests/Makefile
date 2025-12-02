all:
	@echo "Please specify a target"
	@exit 1

.PHONY: test-recipe
test-recipe: check
	@echo "... Running integration tests for building recipes"

	@if [ -z "$(RECIPE_BUILD_TARGET)" ]; then \
		RECIPE_TARGET='*'; \
	else \
		RECIPE_TARGET='$(RECIPE_BUILD_TARGET)'; \
	fi; \
	$(UV_RUN_PREFIX) pyodide build-recipes --recipe-dir=recipes --install --force-rebuild "$${RECIPE_TARGET}"

	@echo "... Passed"

.PHONY: test-src
test-src: check
	@echo "... Running integration tests for building src"

	./src/numpy.sh

	@echo "... Passed"

.PHONY: test-src-no-isolation
test-src-no-isolation: check
	@echo "... Running integration tests for building src with --no-isolation --skip-dependency-check"

	# Some virtualenv workarounds from https://stackoverflow.com/a/24736236
	# to make sure that we are using the right environment
	@( \
        set -e; \
		python -m venv ./test_venv; \
		. ./test_venv/bin/activate; \
		pip install meson-python meson cython; \
		pip install -e ../; \
		./src/numpy_no_isolation.sh; \
		deactivate; \
	)

	@rm -rf ./test_venv

	@echo "... Passed"

.PHONY: test-scripts
test-scripts: check
	@echo "... Running integration tests for scripts"

	./scripts/pyodide_venv_test.sh

	@echo "... Passed"

.PHONY: check
check:
	@echo "... Checking dependencies"

	@which pyodide > /dev/null || (echo "pyodide-build is not installed"; exit 1)

	@echo "... Passed"

.PHONY: clean
clean:
	rm -rf .pyodide-xbuildenv*
	rm -rf recipes/*/build
	rm -rf test_venv
	rm -rf src/numpy-*
	rm -rf src/numpy-*.tar.gz
	rm -rf numpy-*
	rm -rf numpy-*.tar.gz
	rm -rf dist
