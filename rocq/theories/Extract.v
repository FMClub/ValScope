(** Extract.v: extraction of the verified mutators to OCaml.

    The generated module [extracted/valscope_core.ml] contains [mut_q] and [mut_p].
    Because [Mutate.mutate_sound] is proved for exactly these functions, every query
    they return is a super-bag (direction [Up]) or a sub-bag (direction [Down]) of the
    input on every database.  The OCaml/Python glue only has to parse SQL into
    [Syntax.query], call these functions and print the result.

    Integers are extracted to native OCaml [int]: the mutators never do arithmetic on
    SQL integers (they only copy constants), so this does not affect soundness. *)

From Coq Require Import Extraction ExtrOcamlBasic ExtrOcamlNatInt ExtrOcamlZInt.
From ValScope Require Import Logic3 Syntax Mutate.

Extraction Language OCaml.
Extraction "extracted/valscope_core.ml" mut_p mut_q flip.
