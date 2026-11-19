(** Extract.v: extraction of the verified framework to OCaml.

    [extracted/valscope_core.ml] contains the generic engine ([mut_q], [mut_p]),
    the rule records and the registry ([mutate]).  Proofs are erased: a rule
    becomes a record (name, direction, rewrite function).  Inside Rocq a rule
    cannot be built without its proof; OCaml code that builds rule records by hand
    bypasses that guarantee, so plug-ins should be written and registered in Rocq. *)

From Coq Require Import Extraction ExtrOcamlBasic ExtrOcamlNatInt ExtrOcamlZInt
  ExtrOcamlNativeString.
From ValScope Require Import Logic3 Syntax Rule Engine Value VEngine Registry.

Extraction Language OCaml.
Extraction "extracted/valscope_core.ml" mutate mut_q mut_p pred_rules query_rules flip
  vmutate vmut value_rules.
