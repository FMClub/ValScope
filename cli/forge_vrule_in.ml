(* Must NOT compile (see `make check-abstract`): a value rule of a class of worlds built
   by hand has no proof either. *)
open Valscope_core

let forged : vrule_in = { vri_name = "unsound"; vri_rel = VLe; vri_fun = (fun _ -> [AConst 0]) }
let () = ignore forged
