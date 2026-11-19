(** Rule.v: a mutation rule is a rewrite function packaged with its theorem.

    A rule can only be built by supplying a proof that every query (or predicate)
    it produces is above ([Up]) or below ([Down]) its input, on every database.
    This is the plug-in interface of the framework: proving the theorem is the
    only thing a new rule has to do.  Traversal, polarity and the soundness of the
    resulting mutator are provided once and for all by Engine.v. *)

From Coq Require Import List String.
Import ListNotations.
From ValScope Require Import Bag Logic3 Syntax Semantics Approx.

Inductive dir : Type := Up | Down.

Definition flip (d : dir) : dir := match d with Up => Down | Down => Up end.

Definition dir_eqb (a b : dir) : bool :=
  match a, b with Up, Up | Down, Down => true | _, _ => false end.

Lemma dir_eqb_eq : forall a b, dir_eqb a b = true -> a = b.
Proof. intros [] []; simpl; intro H; try reflexivity; discriminate. Qed.

(** [dle le d x y]: with [Up], [x] is below [y]; with [Down], [y] is below [x]. *)
Definition dle {X : Type} (le : X -> X -> Prop) (d : dir) (x y : X) : Prop :=
  match d with Up => le x y | Down => le y x end.

(** A rule on predicates.  [pr_fun p] lists the rewrites of [p] at its root
    (the empty list when the rule does not match). *)
Record prule : Type := mk_prule {
  pr_name  : string;
  pr_dir   : dir;
  pr_fun   : pred -> list pred;
  pr_sound : forall p p', In p' (pr_fun p) -> dle p_le pr_dir p p'
}.

(** A rule on queries. *)
Record qrule : Type := mk_qrule {
  qr_name  : string;
  qr_dir   : dir;
  qr_fun   : query -> list query;
  qr_sound : forall q q', In q' (qr_fun q) -> dle q_le qr_dir q q'
}.
