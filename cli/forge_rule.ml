(* Must NOT compile (see `make check-abstract`): a rule built by hand has no proof. *)
open Valscope_core

let forged : prule = { pr_name = "unsound"; pr_dir = Up; pr_fun = (fun _ -> [PFalse]) }
let () = ignore (mut_q [forged] [] Up (QTable (0, 1)))
