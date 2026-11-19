(** Semantics.v: bag semantics with three-valued predicates.

    [eval_q db ctx q] is the bag of rows returned by [q]; [eval_p db ctx p] is the
    truth value of [p] in context [ctx]. *)

From Coq Require Import List ZArith.
Import ListNotations.
From ValScope Require Import Bag Logic3 Syntax.

Definition db_t := nat -> list row.

Definition eval_expr (ctx : row) : expr -> value :=
  fix go e :=
    match e with
    | EConst v => v
    | ECol i => nth i ctx VNull
    | EAdd a b =>
        match go a, go b with
        | VInt x, VInt y => VInt (x + y)
        | _, _ => VNull
        end
    end.

Definition rdedup  := dedup  row_eq_dec.
Definition runion  := union  row_eq_dec.
Definition rinter  := inter  row_eq_dec.
Definition rexc    := exc    row_eq_dec.
Definition rle     := bag_le row_eq_dec.

(** Rows of the right input that match the left row [r1] under [P]. *)
Definition matches (P : row -> bool) (r1 : row) (rhs : list row) : list row :=
  filter P (map (fun r2 => r1 ++ r2) rhs).

Definition left_matches (P : row -> bool) (pad : nat) (r1 : row) (rhs : list row)
  : list row :=
  match matches P r1 rhs with
  | [] => [r1 ++ repeat VNull pad]
  | ms => ms
  end.

Fixpoint eval_q (db : db_t) (ctx : row) (q : query) : list row :=
  match q with
  | QTable n _ => db n
  | QProject es q =>
      map (fun r => map (eval_expr (r ++ ctx)) es) (eval_q db ctx q)
  | QWhere p q =>
      filter (fun r => is_true (eval_p db (r ++ ctx) p)) (eval_q db ctx q)
  | QDistinct q => rdedup (eval_q db ctx q)
  | QUnionAll a b => eval_q db ctx a ++ eval_q db ctx b
  | QUnion a b => runion (eval_q db ctx a) (eval_q db ctx b)
  | QIntersect a b => rinter (eval_q db ctx a) (eval_q db ctx b)
  | QExcept a b => rexc (eval_q db ctx a) (eval_q db ctx b)
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
  | PCmp c a b => cmp3 c (eval_expr ctx a) (eval_expr ctx b)
  | PIsNull e => match eval_expr ctx e with VNull => T3 | _ => F3 end
  | PNot p => tv_not (eval_p db ctx p)
  | PAnd p q => tv_and (eval_p db ctx p) (eval_p db ctx q)
  | POr p q => tv_or (eval_p db ctx p) (eval_p db ctx q)
  | PExists q => match eval_q db ctx q with [] => F3 | _ => T3 end
  end.

(** Approximation relations.  [q_le q1 q2] holds when, for every database and every
    context, the result of [q1] is included in the result of [q2]. *)
Definition q_le (q1 q2 : query) : Prop :=
  forall db ctx, rle (eval_q db ctx q1) (eval_q db ctx q2).

Definition p_le (p1 p2 : pred) : Prop :=
  forall db ctx, tv_le (eval_p db ctx p1) (eval_p db ctx p2).
