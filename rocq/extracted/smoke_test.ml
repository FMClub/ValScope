(* Smoke test for the extracted core: SELECT * FROM t0 WHERE NOT EXISTS (SELECT * FROM t1 WHERE c0 < 5). *)
open Valscope_core

let () =
  let inner = QWhere (PCmp (CLt, ECol 0, EConst (VInt 5)), QTable (1, 1)) in
  let q = QWhere (PNot (PExists inner), QTable (0, 1)) in
  let up = mut_q Up q and down = mut_q Down q in
  Printf.printf "mutants that make the result larger : %d\n" (List.length up);
  Printf.printf "mutants that make the result smaller: %d\n" (List.length down);
  (* under NOT the direction flips: the inner WHERE must become FALSE to enlarge the result *)
  let expected =
    QWhere (PNot (PExists (QWhere (PFalse, QTable (1, 1)))), QTable (0, 1)) in
  if List.mem expected up then print_endline "OK: NOT flips the polarity"
  else (print_endline "FAIL: expected mutant missing"; exit 1)
