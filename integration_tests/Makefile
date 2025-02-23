all:
	@echo "Please specify a target"
	@exit 1

.PHONY: test-recipe
test-recipe: check
	@echo "... Running integration tests for building recipes"

	pyodide build-recipes --recipe-dir=recipes --force-rebuild "*"

	@echo "... Passed"

.PHONY: test-src
test-src: check
	@echo "... Running integration tests for building src"

	./src/numpy.sh

	@echo "... Passed"

.PHONY: check
check:
	@echo "... Checking dependencies"

	@which pyodide > /dev/null || (echo "pyodide-build is not installed"; exit 1)
	@which emsdk > /dev/null || (echo "emscripten is not installed"; exit 1)

	@echo "... Passed"

.PHONY: clean
clean:
	rm -rf .pyodide-xbuildenv*
	rm -rf recipes/*/build
	rm -rf src/numpy-*
	rm -rf dist
