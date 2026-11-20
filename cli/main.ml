(* Command-line front end of the extracted, verified mutator.

   Protocol (one query per line on stdin, S-expressions):
     query ::= (T id arity) | (Proj (e ...) q) | (Where p q) | (Distinct q)
             | (UnionAll q q) | (Union q q) | (Intersect q q) | (Except q q)
             | (Inner p q q) | (Left pad p q q)
             | (IntersectAll q q) | (ExceptAll q q)
             | (Named id q)          a derived table or CTE reference, kept as written
             | (QAtom id arity)      an opaque subquery (aggregates, LIMIT, windows, ...)
     pred  ::= True | False | (Cmp op e e) | (IsNull e) | (Not p) | (And p p)
             | (Or p p) | (Exists q) | (In e q) | (InT (e ...) q) | (Atom id)
             | (Like e hex)          hex: the LIKE pattern, hex-encoded; % and _ are wildcards
             | (Regex e hex)         hex: a regular expression of the fragment
                                     ^? (c | .)(?|*|+)? ... $?   (c a literal character)
     expr  ::= (Col id) | (Null) | (Int n) | (Num p q) | (Str hex) | (Add e e) | (Mul e e)
             | (EAtom id)            an opaque expression (function call, CASE, ...)
     op    ::= eq | ne | lt | le | gt | ge
   For every input line the program prints one line per mutant,
     <Up|Down> TAB <rule name> TAB <query>
   followed by a line "END".  `--rules` lists the registered plug-ins.

   Value queries (one select item is mutated, the rows stay the same):
     vquery ::= (VProj (item ...) q) | (VGroup (e ...) (item ...) having q)
              | (VGlobal (item ...) having q)        having is a pred, True when absent
     item   ::= (ACol e) | (AConst n) | (ACount e) | (ACountD e) | (ASum e) | (AMin e)
              | (AMax e) | (AAvg e) | (AVar e) | (AStd e) | (AAdd item item)
              | (AMul item item) | (AMono id item)
              | (AOpaque id)       an item that is not analysed (copied, never mutated)
     vtop   ::= vquery | (VUnionAll vtop vtop)          UNION ALL of value queries
   Each mutant is printed as
     <Le|Ge|AwayZero|TowardOne|AwayOne> TAB <rule name> TAB <column> TAB <vquery>
   where the relation says how the mutated column of the mutant relates to the original.
   Mutants of the HAVING predicate are printed as
     <Up|Down> TAB <rule name> TAB <vquery>
   (Up: the mutant outputs the same rows and possibly more; Down: a subset).

   This file is glue: it only parses, calls Valscope_core.mutate and prints. *)

open Valscope_core

type sexp = A of string | L of sexp list

let tokenize (s : string) : string list =
  let buf = Buffer.create 16 and out = ref [] in
  let flush () =
    if Buffer.length buf > 0 then (out := Buffer.contents buf :: !out; Buffer.clear buf) in
  String.iter (fun c ->
    match c with
    | '(' | ')' -> flush (); out := String.make 1 c :: !out
    | ' ' | '\t' | '\n' | '\r' -> flush ()
    | c -> Buffer.add_char buf c) s;
  flush (); List.rev !out

let parse_sexp (s : string) : sexp =
  let rec one = function
    | "(" :: rest -> let items, rest = many rest in (L items, rest)
    | ")" :: _ -> failwith "unexpected )"
    | tok :: rest -> (A tok, rest)
    | [] -> failwith "unexpected end of input"
  and many = function
    | ")" :: rest -> ([], rest)
    | [] -> failwith "missing )"
    | toks -> let x, rest = one toks in let xs, rest = many rest in (x :: xs, rest) in
  match one (tokenize s) with
  | x, [] -> x
  | _ -> failwith "trailing input"

let cmp_of = function
  | "eq" -> CEq | "ne" -> CNe | "lt" -> CLt | "le" -> CLe | "gt" -> CGt | "ge" -> CGe
  | s -> failwith ("unknown comparison " ^ s)

let cmp_to = function
  | CEq -> "eq" | CNe -> "ne" | CLt -> "lt" | CLe -> "le" | CGt -> "gt" | CGe -> "ge"

(* ---- hex strings, LIKE patterns, regular expressions ---- *)

let unhex (h : string) : string =
  if String.length h mod 2 <> 0 then failwith "bad hex string";
  String.init (String.length h / 2) (fun i -> Char.chr (int_of_string ("0x" ^ String.sub h (2 * i) 2)))

let hex (s : string) : string =
  String.concat "" (List.init (String.length s) (fun i -> Printf.sprintf "%02x" (Char.code s.[i])))

let chars (s : string) : char list = List.init (String.length s) (String.get s)

let string_of_chars (l : char list) : string = String.concat "" (List.map (String.make 1) l)

let lpat_of (s : string) : lpat =
  List.map (function '%' -> LAny | '_' -> LOne | c -> LChar c) (chars s)

let lpat_to (p : lpat) : string =
  string_of_chars (List.map (function LAny -> '%' | LOne -> '_' | LChar c -> c) p)

let special c = String.contains "^$.?*+()[]{}|\\" c

let rx_of (s : string) : rx =
  let l = chars s in
  let start, l = (match l with '^' :: t -> true, t | _ -> false, l) in
  let fin, l = (match List.rev l with '$' :: t -> true, List.rev t | _ -> false, l) in
  let rec items = function
    | [] -> []
    | a :: rest ->
        let atom = if a = '.' then RDot else if special a then failwith "regex outside the fragment"
                   else RChar a in
        (match rest with
         | '?' :: r -> (atom, QOpt) :: items r
         | '*' :: r -> (atom, QStar) :: items r
         | '+' :: r -> (atom, QPlus) :: items r
         | r -> (atom, QOne) :: items r) in
  { rx_start = start; rx_end = fin; rx_items = items l }

let rx_to (r : rx) : string =
  let item (a, q) =
    (match a with RDot -> "." | RChar c -> String.make 1 c) ^
    (match q with QOne -> "" | QOpt -> "?" | QStar -> "*" | QPlus -> "+") in
  (if r.rx_start then "^" else "") ^ String.concat "" (List.map item r.rx_items) ^
  (if r.rx_end then "$" else "")

let rec expr_of = function
  | L [A "Col"; A i] -> ECol (int_of_string i)
  | L [A "Null"] -> EConst VNull
  | L [A "Int"; A n] -> EConst (VInt (int_of_string n))
  | L [A "Num"; A p; A q] -> EConst (VNum { qnum = int_of_string p; qden = int_of_string q })
  | L [A "Str"; A h] -> EConst (VStr (unhex h))
  | L [A "Str"] -> EConst (VStr "")
  | L [A "EAtom"; A i] -> EAtom (int_of_string i)
  | L [A "Add"; a; b] -> EAdd (expr_of a, expr_of b)
  | L [A "Mul"; a; b] -> EMul (expr_of a, expr_of b)
  | _ -> failwith "bad expression"

let rec pred_of = function
  | A "True" -> PTrue
  | A "False" -> PFalse
  | L [A "Cmp"; A op; a; b] -> PCmp (cmp_of op, expr_of a, expr_of b)
  | L [A "IsNull"; e] -> PIsNull (expr_of e)
  | L [A "Not"; p] -> PNot (pred_of p)
  | L [A "And"; a; b] -> PAnd (pred_of a, pred_of b)
  | L [A "Or"; a; b] -> POr (pred_of a, pred_of b)
  | L [A "Exists"; q] -> PExists (query_of q)
  | L [A "In"; e; q] -> PIn (expr_of e, query_of q)
  | L [A "InT"; L es; q] -> PInT (List.map expr_of es, query_of q)
  | L [A "Atom"; A i] -> PAtom (int_of_string i)
  | L [A "Like"; e; A h] -> PLike (expr_of e, lpat_of (unhex h))
  | L [A "Like"; e] -> PLike (expr_of e, [])
  | L [A "Regex"; e; A h] -> PRegex (expr_of e, rx_of (unhex h))
  | L [A "Regex"; e] -> PRegex (expr_of e, rx_of "")
  | _ -> failwith "bad predicate"

and query_of = function
  | L [A "T"; A i; A n] -> QTable (int_of_string i, int_of_string n)
  | L [A "Proj"; L es; q] -> QProject (List.map expr_of es, query_of q)
  | L [A "Where"; p; q] -> QWhere (pred_of p, query_of q)
  | L [A "Distinct"; q] -> QDistinct (query_of q)
  | L [A "UnionAll"; a; b] -> QUnionAll (query_of a, query_of b)
  | L [A "Union"; a; b] -> QUnion (query_of a, query_of b)
  | L [A "Intersect"; a; b] -> QIntersect (query_of a, query_of b)
  | L [A "Except"; a; b] -> QExcept (query_of a, query_of b)
  | L [A "IntersectAll"; a; b] -> QIntersectAll (query_of a, query_of b)
  | L [A "ExceptAll"; a; b] -> QExceptAll (query_of a, query_of b)
  | L [A "Inner"; p; a; b] -> QInnerJoin (pred_of p, query_of a, query_of b)
  | L [A "Left"; A n; p; a; b] -> QLeftJoin (int_of_string n, pred_of p, query_of a, query_of b)
  | L [A "Named"; A i; q] -> QNamed (int_of_string i, query_of q)
  | L [A "QAtom"; A i; A n] -> QAtom (int_of_string i, int_of_string n)
  | _ -> failwith "bad query"

let rec expr_to = function
  | ECol i -> Printf.sprintf "(Col %d)" i
  | EConst VNull -> "(Null)"
  | EConst (VInt n) -> Printf.sprintf "(Int %d)" n
  | EConst (VNum q) -> Printf.sprintf "(Num %d %d)" q.qnum q.qden
  | EConst (VStr s) -> if s = "" then "(Str)" else Printf.sprintf "(Str %s)" (hex s)
  | EAtom i -> Printf.sprintf "(EAtom %d)" i
  | EAdd (a, b) -> Printf.sprintf "(Add %s %s)" (expr_to a) (expr_to b)
  | EMul (a, b) -> Printf.sprintf "(Mul %s %s)" (expr_to a) (expr_to b)

let rec pred_to = function
  | PTrue -> "True"
  | PFalse -> "False"
  | PCmp (c, a, b) -> Printf.sprintf "(Cmp %s %s %s)" (cmp_to c) (expr_to a) (expr_to b)
  | PIsNull e -> Printf.sprintf "(IsNull %s)" (expr_to e)
  | PNot p -> Printf.sprintf "(Not %s)" (pred_to p)
  | PAnd (a, b) -> Printf.sprintf "(And %s %s)" (pred_to a) (pred_to b)
  | POr (a, b) -> Printf.sprintf "(Or %s %s)" (pred_to a) (pred_to b)
  | PExists q -> Printf.sprintf "(Exists %s)" (query_to q)
  | PIn (e, q) -> Printf.sprintf "(In %s %s)" (expr_to e) (query_to q)
  | PInT (es, q) ->
      Printf.sprintf "(InT (%s) %s)" (String.concat " " (List.map expr_to es)) (query_to q)
  | PAtom i -> Printf.sprintf "(Atom %d)" i
  | PLike (e, p) ->
      let h = hex (lpat_to p) in
      if h = "" then Printf.sprintf "(Like %s)" (expr_to e) else Printf.sprintf "(Like %s %s)" (expr_to e) h
  | PRegex (e, r) ->
      let h = hex (rx_to r) in
      if h = "" then Printf.sprintf "(Regex %s)" (expr_to e) else Printf.sprintf "(Regex %s %s)" (expr_to e) h

and query_to = function
  | QTable (i, n) -> Printf.sprintf "(T %d %d)" i n
  | QProject (es, q) ->
      Printf.sprintf "(Proj (%s) %s)" (String.concat " " (List.map expr_to es)) (query_to q)
  | QWhere (p, q) -> Printf.sprintf "(Where %s %s)" (pred_to p) (query_to q)
  | QDistinct q -> Printf.sprintf "(Distinct %s)" (query_to q)
  | QUnionAll (a, b) -> Printf.sprintf "(UnionAll %s %s)" (query_to a) (query_to b)
  | QUnion (a, b) -> Printf.sprintf "(Union %s %s)" (query_to a) (query_to b)
  | QIntersect (a, b) -> Printf.sprintf "(Intersect %s %s)" (query_to a) (query_to b)
  | QExcept (a, b) -> Printf.sprintf "(Except %s %s)" (query_to a) (query_to b)
  | QIntersectAll (a, b) -> Printf.sprintf "(IntersectAll %s %s)" (query_to a) (query_to b)
  | QExceptAll (a, b) -> Printf.sprintf "(ExceptAll %s %s)" (query_to a) (query_to b)
  | QInnerJoin (p, a, b) ->
      Printf.sprintf "(Inner %s %s %s)" (pred_to p) (query_to a) (query_to b)
  | QLeftJoin (n, p, a, b) ->
      Printf.sprintf "(Left %d %s %s %s)" n (pred_to p) (query_to a) (query_to b)
  | QNamed (i, q) -> Printf.sprintf "(Named %d %s)" i (query_to q)
  | QAtom (i, n) -> Printf.sprintf "(QAtom %d %d)" i n

let dir_name = function Up -> "Up" | Down -> "Down"

(* ---- value queries ---- *)

let rec item_of = function
  | L [A "ACol"; e] -> ACol (expr_of e)
  | L [A "AConst"; A n] -> AConst (int_of_string n)
  | L [A "ACount"; e] -> ACount (expr_of e)
  | L [A "ACountD"; e] -> ACountD (expr_of e)
  | L [A "ASum"; e] -> ASum (expr_of e)
  | L [A "AMin"; e] -> AMin (expr_of e)
  | L [A "AMax"; e] -> AMax (expr_of e)
  | L [A "AAvg"; e] -> AAvg (expr_of e)
  | L [A "AVar"; e] -> AVarSamp (expr_of e)
  | L [A "AStd"; e] -> AStdSamp (expr_of e)
  | L [A "AAdd"; a; b] -> AAdd (item_of a, item_of b)
  | L [A "AMul"; a; b] -> AMul (item_of a, item_of b)
  | L [A "AMono"; A f; a] -> AMono (int_of_string f, item_of a)
  | L [A "AOpaque"; A i] -> AOpaque (int_of_string i)
  | _ -> failwith "bad select item"

let rec item_to = function
  | ACol e -> Printf.sprintf "(ACol %s)" (expr_to e)
  | AConst n -> Printf.sprintf "(AConst %d)" n
  | ACount e -> Printf.sprintf "(ACount %s)" (expr_to e)
  | ACountD e -> Printf.sprintf "(ACountD %s)" (expr_to e)
  | ASum e -> Printf.sprintf "(ASum %s)" (expr_to e)
  | AMin e -> Printf.sprintf "(AMin %s)" (expr_to e)
  | AMax e -> Printf.sprintf "(AMax %s)" (expr_to e)
  | AAvg e -> Printf.sprintf "(AAvg %s)" (expr_to e)
  | AVarSamp e -> Printf.sprintf "(AVar %s)" (expr_to e)
  | AStdSamp e -> Printf.sprintf "(AStd %s)" (expr_to e)
  | AAdd (a, b) -> Printf.sprintf "(AAdd %s %s)" (item_to a) (item_to b)
  | AMul (a, b) -> Printf.sprintf "(AMul %s %s)" (item_to a) (item_to b)
  | AMono (f, a) -> Printf.sprintf "(AMono %d %s)" f (item_to a)
  | AOpaque i -> Printf.sprintf "(AOpaque %d)" i

let items_to l = String.concat " " (List.map item_to l)

let vquery_of = function
  | L [A "VProj"; L items; q] -> VProj (List.map item_of items, query_of q)
  | L [A "VGroup"; L keys; L items; h; q] ->
      VGroup (List.map expr_of keys, List.map item_of items, pred_of h, query_of q)
  | L [A "VGlobal"; L items; h; q] -> VGlobal (List.map item_of items, pred_of h, query_of q)
  | _ -> failwith "bad value query"

let vquery_to = function
  | VProj (items, q) -> Printf.sprintf "(VProj (%s) %s)" (items_to items) (query_to q)
  | VGroup (keys, items, h, q) ->
      Printf.sprintf "(VGroup (%s) (%s) %s %s)"
        (String.concat " " (List.map expr_to keys)) (items_to items) (pred_to h) (query_to q)
  | VGlobal (items, h, q) ->
      Printf.sprintf "(VGlobal (%s) %s %s)" (items_to items) (pred_to h) (query_to q)

let rec vtop_of = function
  | L [A "VUnionAll"; a; b] -> VUnionAll (vtop_of a, vtop_of b)
  | t -> VOne (vquery_of t)

let rec vtop_to = function
  | VOne v -> vquery_to v
  | VUnionAll (a, b) -> Printf.sprintf "(VUnionAll %s %s)" (vtop_to a) (vtop_to b)

let rel_name = function
  | VLe -> "Le" | VGe -> "Ge" | VAwayZero -> "AwayZero"
  | VTowardOne -> "TowardOne" | VAwayOne -> "AwayOne"

let is_value_query = function
  | L (A ("VProj" | "VGroup" | "VGlobal" | "VUnionAll") :: _) -> true
  | _ -> false

let () =
  if Array.length Sys.argv > 1 && Sys.argv.(1) = "--rules" then begin
    List.iter (fun (n, d) -> Printf.printf "pred\t%s\t%s\n" (dir_name d) n) pred_rule_names;
    List.iter (fun (n, d) -> Printf.printf "query\t%s\t%s\n" (dir_name d) n) query_rule_names;
    List.iter (fun (n, r) -> Printf.printf "value\t%s\t%s\n" (rel_name r) n) value_rule_names
  end else
    try
      while true do
        let line = input_line stdin in
        if String.trim line <> "" then begin
          (try
             let term = parse_sexp line in
             if is_value_query term then begin
               let v = vtop_of term in
               List.iter (fun (name, (rel, (j, v'))) ->
                 Printf.printf "%s\t%s\t%d\t%s\n" (rel_name rel) name j (vtop_to v'))
                 (tmutate v);
               List.iter (fun d ->
                 List.iter (fun (name, v') ->
                   Printf.printf "%s\t%s\t%s\n" (dir_name d) name (vtop_to v'))
                   (thmutate d v)) [Up; Down]
             end
             else begin
               let q = query_of term in
               List.iter (fun d ->
                 List.iter (fun (name, q') ->
                   Printf.printf "%s\t%s\t%s\n" (dir_name d) name (query_to q'))
                   (mutate d q)) [Up; Down]
             end
           with Failure msg -> Printf.printf "ERROR\t%s\n" msg);
          print_endline "END"; flush stdout
        end
      done
    with End_of_file -> ()
