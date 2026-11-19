(** Syntax.v: the SQL fragment the mutators work on.

    Columns are addressed by position in a context row: [ECol i] reads column [i] of
    (current row ++ outer rows), so correlated subqueries are expressed by indexes
    that point past the columns of the subquery's own row.

    Anything the mutators do not analyse is an opaque atom whose meaning is given by
    the world (Semantics.v): an expression ([EAtom]), a predicate ([PAtom]) or a query
    ([QAtom]).  Atoms are carried through mutations unchanged.  The theorems hold for
    every interpretation of the atoms that respects the collation of the world. *)

From Coq Require Import List.
Import ListNotations.
From ValScope Require Import Logic3 Pattern.

Inductive expr : Type :=
  | EConst : value -> expr
  | ECol   : nat -> expr
  | EAdd   : expr -> expr -> expr
  | EMul   : expr -> expr -> expr
  | EAtom  : nat -> expr.                (* opaque expression *)

Inductive pred : Type :=
  | PTrue   : pred
  | PFalse  : pred
  | PCmp    : cmp -> expr -> expr -> pred
  | PIsNull : expr -> pred
  | PNot    : pred -> pred
  | PAnd    : pred -> pred -> pred
  | POr     : pred -> pred -> pred
  | PExists : query -> pred
  | PIn     : expr -> query -> pred      (* e IN (subquery); the subquery has one column *)
  | PLike   : expr -> lpat -> pred       (* e LIKE pattern *)
  | PRegex  : expr -> rx -> pred         (* e REGEXP pattern *)
  | PAtom   : nat -> pred                (* opaque predicate *)
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
  | QNamed     : nat -> query -> query      (* a named subquery: derived table or CTE body *)
  | QAtom      : nat -> nat -> query        (* opaque query (id, arity), may be correlated *)
  .

Scheme pred_ind2  := Induction for pred  Sort Prop
  with query_ind2 := Induction for query Sort Prop.
Combined Scheme pq_ind from pred_ind2, query_ind2.

(** Number of output columns; used only to pad the NULL row of a LEFT JOIN. *)
Fixpoint arity (q : query) : nat :=
  match q with
  | QTable _ n | QAtom _ n => n
  | QProject es _ => length es
  | QWhere _ q | QDistinct q | QNamed _ q => arity q
  | QUnionAll a _ | QUnion a _ | QIntersect a _ | QExcept a _ => arity a
  | QInnerJoin _ a b | QLeftJoin _ _ a b => arity a + arity b
  end.
