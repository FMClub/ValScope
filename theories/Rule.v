(** Rule.v: a mutation rule is a rewrite function packaged with its theorem.

    A rule can only be built by supplying a proof that every query (or predicate)
    it produces is above ([Up]) or below ([Down]) its input, on every database.
    This is the plug-in interface of the framework: proving the theorem is the
    only thing a new rule has to do.  Traversal, polarity and the soundness of the
    resulting mutator are provided once and for all by Engine.v. *)

From Coq Require Import List String.
Import ListNotations.
From ValScope Require Import Bag Logic3 Pattern Syntax Semantics Approx.

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

(** ---------------- rules sound in a class of worlds ----------------

    [prule] and [qrule] above are sound in every world.  A rule proved against the
    semantics of one dialect is sound in the worlds of that dialect only: it is a
    [prule_in W] or a [qrule_in W], where [W] is that class of worlds.  The generic
    engine of Engine.v takes rules of this form, so the two kinds can be mixed. *)

Lemma dle_p_within : forall W d p p', dle p_le d p p' -> dle (p_le_within W) d p p'.
Proof. intros W [] p p' H; simpl in *; apply p_le_within_of_le; exact H. Qed.

Lemma dle_q_within : forall W d q q', dle q_le d q q' -> dle (q_le_within W) d q q'.
Proof. intros W [] q q' H; simpl in *; apply q_le_within_of_le; exact H. Qed.

Lemma dle_p_within_all : forall d p p', dle (p_le_within all_worlds) d p p' -> dle p_le d p p'.
Proof. intros [] p p' H; simpl in *; apply p_le_within_all; exact H. Qed.

Lemma dle_q_within_all : forall d q q', dle (q_le_within all_worlds) d q q' -> dle q_le d q q'.
Proof. intros [] q q' H; simpl in *; apply q_le_within_all; exact H. Qed.

Record prule_in (W : db_t -> Prop) : Type := mk_prule_in {
  pri_name  : string;
  pri_dir   : dir;
  pri_fun   : pred -> list pred;
  pri_sound : forall p p', In p' (pri_fun p) -> dle (p_le_within W) pri_dir p p'
}.

Record qrule_in (W : db_t -> Prop) : Type := mk_qrule_in {
  qri_name  : string;
  qri_dir   : dir;
  qri_fun   : query -> list query;
  qri_sound : forall q q', In q' (qri_fun q) -> dle (q_le_within W) qri_dir q q'
}.

Arguments pri_name {W}. Arguments pri_dir {W}. Arguments pri_fun {W}. Arguments pri_sound {W}.
Arguments qri_name {W}. Arguments qri_dir {W}. Arguments qri_fun {W}. Arguments qri_sound {W}.

(** A rule sound in every world, used in a class of worlds. *)
Definition prule_at (W : db_t -> Prop) (r : prule) : prule_in W :=
  mk_prule_in W (pr_name r) (pr_dir r) (pr_fun r)
    (fun p p' H => dle_p_within W _ _ _ (pr_sound r p p' H)).

Definition qrule_at (W : db_t -> Prop) (r : qrule) : qrule_in W :=
  mk_qrule_in W (qr_name r) (qr_dir r) (qr_fun r)
    (fun q q' H => dle_q_within W _ _ _ (qr_sound r q q' H)).
