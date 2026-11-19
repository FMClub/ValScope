# Build the Rocq (Coq) development, extract the verified core to OCaml and build the CLI.
all: Makefile.coq
	mkdir -p extracted
	$(MAKE) -f Makefile.coq

Makefile.coq: _CoqProject
	coq_makefile -f _CoqProject -o Makefile.coq

# The command-line mutator: extracted core + glue (cli/main.ml).
cli: all
	cp extracted/valscope_core.ml extracted/valscope_core.mli cli/
	cd cli && ocamlfind ocamlopt -w -a valscope_core.mli valscope_core.ml main.ml -o valscope_mutate

# End-to-end test: SQL text -> mutants -> SQL text (needs python3 with sqlglot).
test: cli
	python3 bridge/test_bridge.py

clean:
	@if [ -f Makefile.coq ]; then $(MAKE) -f Makefile.coq cleanall; fi
	rm -f Makefile.coq Makefile.coq.conf extracted/*.cm* extracted/*.o
	rm -f cli/valscope_core.ml cli/valscope_core.mli cli/*.cm* cli/*.o cli/valscope_mutate

.PHONY: all cli test clean
