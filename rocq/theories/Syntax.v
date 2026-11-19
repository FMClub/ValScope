(** Syntax.v: the SQL fragment that ValScope's set-semantic mutators work on.

    Columns are addressed by position in a context row.  A predicate or query is
    evaluated in a context row: [ECol i] reads column [i] of (current row ++ outer
    contexts), so correlated subqueries are expressed by indexes that point past the
    columns of the subquery's own row. *)

From Coq Require Import List.
Import ListNotations.
From ValScope Require Import Logic3.

Inductive expr : Type :=
  | EConst : value -> expr
  | ECol   : nat -> expr
  | EAdd   : expr -> expr -> expr.

Inductive pred : Type :=
  | PTrue   : pred
  | PFalse  : pred
  | PCmp    : cmp -> expr -> expr -> pred
  | PIsNull : expr -> pred
  | PNot    : pred -> pred
  | PAnd    : pred -> pred -> pred
  | POr     : pred -> pred -> pred
  | PExists : query -> pred
  | PAtom   : nat -> pred          (* opaque predicate, interpreted by the world *)
with query : Type :=
  | QTable     : nat -> nat -> query                (* table id, arity *)
  | QProject   : list expr -> query -> query
  | QWhere     : pred -> query -> query
  | QDistinct  : query -> query
  | QUnionAll  : query -> query -> query
  | QUnion     : query -> query -> query
  | QIntersect : query -> query -> query
  | QExcept    : query -> query -> query
  | QInnerJoin : pred -> query -> query -> query
  | QLeftJoin  : nat -> pred -> query -> query -> query  (* padding width, ON, left, right *)
  .

Scheme pred_ind2  := Induction for pred  Sort Prop
  with query_ind2 := Induction for query Sort Prop.
Combined Scheme pq_ind from pred_ind2, query_ind2.

(** Number of output columns; used only to pad the NULL row of a LEFT JOIN. *)
Fixpoint arity (q : query) : nat :=
  match q with
  | QTable _ n => n
  | QProject es _ => length es
  | QWhere _ q | QDistinct q => arity q
  | QUnionAll a _ | QUnion a _ | QIntersect a _ | QExcept a _ => arity a
  | QInnerJoin _ a b | QLeftJoin _ _ a b => arity a + arity b
  end.
