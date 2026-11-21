(** VSet.v: INTERSECT and EXCEPT of value queries (set semantics).

    [A INTERSECT B] keeps the distinct rows of [A] that are rows of [B]; [A EXCEPT B] those
    that are not.  The result, as a set, grows with [A] (both operators), grows with [B]
    for INTERSECT and shrinks with [B] for EXCEPT.  The HAVING mutator of VHaving.v gives
    arms whose rows are a sub-list (or a super-list) of the original's, so it can be
    applied inside every operand, with the direction flipped in the right operand of
    EXCEPT.  The relation is inclusion of the sets of rows: duplicates and their order do
    not matter, and a DISTINCT or UNION inside an operand does not change the result.

    The value rules (one column grows or shrinks) have no such relation: a changed value
    can enter or leave the intersection. *)

From Coq Require Import List String Reals.
Import ListNotations.
From ValScope Require Import Bag Logic3 Pattern Syntax Semantics Rule Engine Value VEngine VHaving VUnion VDistinct.

Inductive stop : Type :=
  | SOne    : vtop -> stop
  | SInter  : stop -> stop -> stop
  | SExcept : stop -> stop -> stop.

Definition inb (l : list vrow) (x : vrow) : bool := if in_dec vrow_eq_dec x l then true else false.

Fixpoint seval (env : venv) (db : db_t) (s : stop) : list vrow :=
  match s with
  | SOne t => teval env db t
  | SInter a b => filter (inb (seval env db b)) (seval env db a)
  | SExcept a b => filter (fun x => negb (inb (seval env db b) x)) (seval env db a)
  end.

(** Inclusion of the sets of rows on every database. *)
Definition s_incl (s s' : stop) : Prop := forall env db, incl (seval env db s) (seval env db s').

Lemma incl_filter : forall (f : vrow -> bool) l l', incl l l' -> incl (filter f l) (filter f l').
Proof.
  intros f l l' H x Hx. apply filter_In in Hx as [Hx Hf]. apply filter_In. split; [apply H; exact Hx|exact Hf].
Qed.

Lemma inb_incl : forall l l' x, incl l l' -> inb l x = true -> inb l' x = true.
Proof.
  intros l l' x H. unfold inb. destruct (in_dec vrow_eq_dec x l) as [Hl|Hl]; [|discriminate].
  destruct (in_dec vrow_eq_dec x l') as [_|Hn]; [reflexivity|]. exfalso. apply Hn, H, Hl.
Qed.

Lemma incl_inter_right : forall a b b', incl b b' -> incl (filter (inb b) a) (filter (inb b') a).
Proof.
  intros a b b' H x Hx. apply filter_In in Hx as [Hx Hf]. apply filter_In.
  split; [exact Hx|exact (inb_incl _ _ _ H Hf)].
Qed.

Lemma incl_except_right : forall a b b', incl b b' ->
  incl (filter (fun x => negb (inb b' x)) a) (filter (fun x => negb (inb b x)) a).
Proof.
  intros a b b' H x Hx. apply filter_In in Hx as [Hx Hf]. apply filter_In. split; [exact Hx|].
  destruct (inb b x) eqn:E; [|reflexivity].
  rewrite (inb_incl _ _ _ H E) in Hf. discriminate.
Qed.

Section SHaving.
Variable prs : list prule.
Variable qrs : list qrule.

Fixpoint shmut (d : dir) (s : stop) : list (string * stop) :=
  match s with
  | SOne t => map (fun m => (fst m, SOne (snd m))) (thmut prs qrs d t)
  | SInter a b =>
      map (fun m => (fst m, SInter (snd m) b)) (shmut d a) ++
      map (fun m => (fst m, SInter a (snd m))) (shmut d b)
  | SExcept a b =>
      map (fun m => (fst m, SExcept (snd m) b)) (shmut d a) ++
      map (fun m => (fst m, SExcept a (snd m))) (shmut (flip d) b)
  end.

Theorem shmut_sound : forall s d name s', In (name, s') (shmut d s) -> dle s_incl d s s'.
Proof.
  induction s as [t|a IHa b IHb|a IHa b IHb]; intros d name s' H; simpl in H.
  - apply in_map_iff in H as [[n t'] [E Hin]]. simpl in E. inversion E; subst.
    pose proof (thmut_sound prs qrs d t _ _ Hin) as K.
    destruct d; simpl in *; intros env db; apply sub_incl; exact (K env db).
  - apply in_app_or in H as [H|H]; apply in_map_iff in H as [[n x] [E Hin]]; simpl in E; inversion E; subst.
    + pose proof (IHa d _ _ Hin) as Ka.
      destruct d; simpl in *; intros env db; apply incl_filter; exact (Ka env db).
    + pose proof (IHb d _ _ Hin) as Kb.
      destruct d; simpl in *; intros env db; apply incl_inter_right; exact (Kb env db).
  - apply in_app_or in H as [H|H]; apply in_map_iff in H as [[n x] [E Hin]]; simpl in E; inversion E; subst.
    + pose proof (IHa d _ _ Hin) as Ka.
      destruct d; simpl in *; intros env db; apply incl_filter; exact (Ka env db).
    + pose proof (IHb (flip d) _ _ Hin) as Kb.
      destruct d; simpl in *; intros env db; apply incl_except_right; exact (Kb env db).
Qed.

End SHaving.
