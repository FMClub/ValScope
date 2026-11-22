(** Semantics.v: bag semantics with three-valued predicates, for any SQL dialect.

    Everything that differs between DBMSs is supplied by the world [db_t]: how values
    are compared (type coercions, collations), how arithmetic works, which values
    are equal for DISTINCT and the set operations (the collation equivalence [veq]),
    how values are turned into text for LIKE / REGEXP, how characters are compared,
    and what the opaque atoms mean.  The world must satisfy a few laws:

    - [veq] is an equivalence;
    - comparisons satisfy the weakening laws ([x < y] implies [x <= y], ...);
    - every operation respects [veq]: equivalent inputs give equal truth values and
      equivalent values.  (If an operation distinguishes two values that DISTINCT
      treats as equal, the result of a query depends on which representative DISTINCT
      keeps, and SQL itself does not determine it.)

    [eval_q db ctx q] is the bag of rows returned by [q]; [eval_p db ctx p] is the
    truth value of [p] in context [ctx]. *)

From Coq Require Import List ZArith QArith String Ascii.
Import ListNotations.
From ValScope Require Import Bag Logic3 Pattern Syntax.

Definition like3 (tt : value -> option string) (ce : ascii -> ascii -> bool) (v : value) (p : lpat) : tv :=
  match tt v with None => U3 | Some s => of_bool (lmatch ce p (list_ascii_of_string s)) end.

Definition rx3 (tt : value -> option string) (ce : ascii -> ascii -> bool) (v : value) (r : rx) : tv :=
  match tt v with None => U3 | Some s => of_bool (rsearch ce r (list_ascii_of_string s)) end.

(** The numeric value of a value, used by the value-semantic layer: integers and
    rationals are numbers, NULL and text are not. *)
Definition numq (v : value) : option Q :=
  match v with VInt z => Some (inject_Z z) | VNum q => Some q | _ => None end.

Record db_t := mk_world {
  tables  : nat -> list row;
  atoms   : nat -> row -> tv;            (* opaque predicates *)
  eatoms  : nat -> row -> value;         (* opaque expressions *)
  qatoms  : nat -> row -> list row;      (* opaque (possibly correlated) queries *)
  vcmp    : cmp -> value -> value -> tv;
  vadd    : value -> value -> value;
  vmul    : value -> value -> value;
  veq     : value -> value -> bool;      (* the collation equivalence *)
  to_text : value -> option string;      (* conversion for LIKE / REGEXP; None for NULL *)
  ceq     : ascii -> ascii -> bool;      (* character comparison for LIKE / REGEXP *)

  veq_refl  : forall x, veq x x = true;
  veq_sym   : forall x y, veq x y = true -> veq y x = true;
  veq_trans : forall x y z, veq x y = true -> veq y z = true -> veq x z = true;
  vcmp_weaker : forall c c' x y, cmp_weaker c c' -> tv_le (vcmp c x y) (vcmp c' x y);
  vcmp_compat : forall c x x' y y', veq x x' = true -> veq y y' = true -> vcmp c x y = vcmp c x' y';
  vadd_compat : forall x x' y y', veq x x' = true -> veq y y' = true -> veq (vadd x y) (vadd x' y') = true;
  vmul_compat : forall x x' y y', veq x x' = true -> veq y y' = true -> veq (vmul x y) (vmul x' y') = true;
  null_compat : forall x y, veq x y = true -> x = VNull -> y = VNull;
  like_compat : forall x y p, veq x y = true -> like3 to_text ceq x p = like3 to_text ceq y p;
  rx_compat   : forall x y r, veq x y = true -> rx3 to_text ceq x r = rx3 to_text ceq y r;
  atoms_compat  : forall n c c', list_eqb veq c c' = true -> atoms n c = atoms n c';
  eatoms_compat : forall n c c', list_eqb veq c c' = true -> veq (eatoms n c) (eatoms n c') = true;
  qatoms_compat : forall n c c', list_eqb veq c c' = true ->
                    bag_le (list_eqb veq) (qatoms n c) (qatoms n c');
  (** used only by rule 23 (SUM(c) -> SUM(c * k)): multiplying by an integer
      constant multiplies numbers and keeps non-numbers non-numeric *)
  vmul_num : forall v k,
               match numq (vmul v (VInt k)), numq v with
               | Some a, Some b => Qeq a (Qmult b (inject_Z k))
               | None, None => True
               | _, _ => False
               end
}.

(** Rows are equivalent when they are equivalent column by column. *)
Definition req (db : db_t) : row -> row -> bool := list_eqb (veq db).

Definition eval_expr (db : db_t) (ctx : row) : expr -> value :=
  fix go e :=
    match e with
    | EConst v => v
    | ECol i => nth i ctx VNull
    | EAdd a b => vadd db (go a) (go b)
    | EMul a b => vmul db (go a) (go b)
    | EAtom n => eatoms db n ctx
    end.

(** [x IN (v1, ..., vn)] is [x = v1 OR ... OR x = vn] in three-valued logic. *)
Definition in3 (db : db_t) (v : value) (vs : list value) : tv :=
  fold_right (fun x acc => tv_or (vcmp db CEq v x) acc) F3 vs.

(** Row comparison [(x1, ..., xn) = (y1, ..., yn)]: [x1 = y1 AND ... AND xn = yn] in
    three-valued logic (FALSE if one pair differs, else UNKNOWN if one is unknown). *)
Fixpoint roweq3 (db : db_t) (xs ys : list value) : tv :=
  match xs, ys with
  | x :: xs', y :: ys' => tv_and (vcmp db CEq x y) (roweq3 db xs' ys')
  | _, _ => T3
  end.

(** [(x1, ..., xn) IN (subquery)]: the row equals one of the rows, in three-valued logic. *)
Definition int3 (db : db_t) (xs : list value) (rows : list row) : tv :=
  fold_right (fun r acc => tv_or (roweq3 db xs r) acc) F3 rows.

Definition first_col (rows : list row) : list value :=
  map (fun r => nth 0 r VNull) rows.

(** Rows of the right input that match the left row [r1] under [P]. *)
Definition matches (P : row -> bool) (r1 : row) (rhs : list row) : list row :=
  filter P (map (fun r2 => r1 ++ r2) rhs).

Definition left_matches (P : row -> bool) (pad : nat) (r1 : row) (rhs : list row) : list row :=
  match matches P r1 rhs with
  | [] => [r1 ++ repeat VNull pad]
  | ms => ms
  end.

Fixpoint eval_q (db : db_t) (ctx : row) (q : query) : list row :=
  match q with
  | QTable n _ => tables db n
  | QAtom n _ => qatoms db n ctx
  | QNamed _ q => eval_q db ctx q
  | QProject es q =>
      map (fun r => map (eval_expr db (r ++ ctx)) es) (eval_q db ctx q)
  | QWhere p q =>
      filter (fun r => is_true (eval_p db (r ++ ctx) p)) (eval_q db ctx q)
  | QDistinct q => dedup (req db) (eval_q db ctx q)
  | QUnionAll a b => eval_q db ctx a ++ eval_q db ctx b
  | QUnion a b => union (req db) (eval_q db ctx a) (eval_q db ctx b)
  | QIntersect a b => inter (req db) (eval_q db ctx a) (eval_q db ctx b)
  | QExcept a b => exc (req db) (eval_q db ctx a) (eval_q db ctx b)
  | QIntersectAll a b => inter_all (req db) (eval_q db ctx a) (eval_q db ctx b)
  | QExceptAll a b => exc_all (req db) (eval_q db ctx a) (eval_q db ctx b)
  | QInnerJoin p a b =>
      flat_map (fun r1 =>
                  matches (fun r => is_true (eval_p db (r ++ ctx) p)) r1 (eval_q db ctx b))
               (eval_q db ctx a)
  | QLeftJoin pad p a b =>
      flat_map (fun r1 =>
                  left_matches (fun r => is_true (eval_p db (r ++ ctx) p)) pad r1
                               (eval_q db ctx b))
               (eval_q db ctx a)
  end
with eval_p (db : db_t) (ctx : row) (p : pred) : tv :=
  match p with
  | PTrue => T3
  | PFalse => F3
  | PCmp c a b => vcmp db c (eval_expr db ctx a) (eval_expr db ctx b)
  | PIsNull e => match eval_expr db ctx e with VNull => T3 | _ => F3 end
  | PNot p => tv_not (eval_p db ctx p)
  | PAnd p q => tv_and (eval_p db ctx p) (eval_p db ctx q)
  | POr p q => tv_or (eval_p db ctx p) (eval_p db ctx q)
  | PExists q => match eval_q db ctx q with [] => F3 | _ => T3 end
  | PIn e q => in3 db (eval_expr db ctx e) (first_col (eval_q db ctx q))
  | PInT es q => int3 db (map (eval_expr db ctx) es) (eval_q db ctx q)
  | PLike e pt => like3 (to_text db) (ceq db) (eval_expr db ctx e) pt
  | PRegex e r => rx3 (to_text db) (ceq db) (eval_expr db ctx e) r
  | PAtom n => atoms db n ctx
  end.

(** Approximation relations.  [q_le q1 q2]: for every world (every dialect, every
    collation, every database) and every context, every class of rows occurs in the
    result of [q1] at most as often as in the result of [q2]. *)
Definition q_le (q1 q2 : query) : Prop :=
  forall db ctx, bag_le (req db) (eval_q db ctx q1) (eval_q db ctx q2).

Definition p_le (p1 p2 : pred) : Prop :=
  forall db ctx, tv_le (eval_p db ctx p1) (eval_p db ctx p2).

(** The same relations in one world, and in a class of worlds.  A rule proved for
    every world holds in every class; a rule proved against the semantics of one
    dialect holds in the class of the worlds of that dialect ([q_le_within]). *)
Definition q_le_at (db : db_t) (q1 q2 : query) : Prop :=
  forall ctx, bag_le (req db) (eval_q db ctx q1) (eval_q db ctx q2).

Definition p_le_at (db : db_t) (p1 p2 : pred) : Prop :=
  forall ctx, tv_le (eval_p db ctx p1) (eval_p db ctx p2).

Definition q_le_within (W : db_t -> Prop) (q1 q2 : query) : Prop :=
  forall db, W db -> q_le_at db q1 q2.

Definition p_le_within (W : db_t -> Prop) (p1 p2 : pred) : Prop :=
  forall db, W db -> p_le_at db p1 p2.

(** Every world. *)
Definition all_worlds : db_t -> Prop := fun _ => True.

Lemma q_le_within_of_le : forall W q1 q2, q_le q1 q2 -> q_le_within W q1 q2.
Proof. intros W q1 q2 H db _ ctx. apply H. Qed.

Lemma p_le_within_of_le : forall W p1 p2, p_le p1 p2 -> p_le_within W p1 p2.
Proof. intros W p1 p2 H db _ ctx. apply H. Qed.

Lemma q_le_within_all : forall q1 q2, q_le_within all_worlds q1 q2 -> q_le q1 q2.
Proof. intros q1 q2 H db ctx. exact (H db I ctx). Qed.

Lemma p_le_within_all : forall p1 p2, p_le_within all_worlds p1 p2 -> p_le p1 p2.
Proof. intros p1 p2 H db ctx. exact (H db I ctx). Qed.

(** A class of worlds can only be narrowed. *)
Lemma q_le_within_weaken : forall (W W' : db_t -> Prop) q1 q2,
  (forall db, W' db -> W db) -> q_le_within W q1 q2 -> q_le_within W' q1 q2.
Proof. intros W W' q1 q2 HW H db Hdb. apply H. apply HW. exact Hdb. Qed.

Lemma p_le_within_weaken : forall (W W' : db_t -> Prop) p1 p2,
  (forall db, W' db -> W db) -> p_le_within W p1 p2 -> p_le_within W' p1 p2.
Proof. intros W W' p1 p2 HW H db Hdb. apply H. apply HW. exact Hdb. Qed.
