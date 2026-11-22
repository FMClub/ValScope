(* Must NOT compile (see `make check-abstract`): a rule of a class of worlds built by
   hand has no proof either. *)
open Valscope_core

let forged : prule_in = { pri_name = "unsound"; pri_dir = Up; pri_fun = (fun _ -> [PFalse]) }
let () = ignore forged
