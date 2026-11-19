(** Engine.v: the generic mutator, parametric in the set of rules.

    This is the "compiler" from theorems to mutators.  Given ANY lists of rules
    (Rule.v), [mut_q prs qrs d q] applies every rule of direction [d] at every
    position of [q] where the polarity analysis allows it, flipping the direction
    under NOT and in the right operand of EXCEPT, and never entering positions
    that are neither monotone nor antitone.  Each mutant is labelled with the name
    of the rule that produced it.

    [engine_sound] is proved once, for all rule sets: every mutant is above
    ([Up]) or below ([Down]) the original on every database.  Adding a rule never
    requires touching this file. *)

From Coq Require Import List String.
Import ListNotations.
From ValScope Require Import Bag Logic3 Syntax Semantics Approx Rule.

(** Apply at the root every rule whose direction is [d]. *)
Definition fire_p (rs : list prule) (d : dir) (p : pred) : list (string * pred) :=
  flat_map (fun r => if dir_eqb (pr_dir r) d
                     then map (fun p' => (pr_name r, p')) (pr_fun r p) else []) rs.

Definition fire_q (rs : list qrule) (d : dir) (q : query) : list (string * query) :=
  flat_map (fun r => if dir_eqb (qr_dir r) d
                     then map (fun q' => (qr_name r, q')) (qr_fun r q) else []) rs.

(** Rebuild the context around a labelled mutant. *)
Definition lmap {X Y : Type} (C : X -> Y) (l : list (string * X)) : list (string * Y) :=
  map (fun z => (fst z, C (snd z))) l.

Section Engine.
Variable prs : list prule.
Variable qrs : list qrule.

Fixpoint mut_p (d : dir) (p : pred) {struct p} : list (string * pred) :=
  fire_p prs d p ++
  match p with
  | PNot a => lmap PNot (mut_p (flip d) a)
  | PAnd a b =>
      lmap (fun a' => PAnd a' b) (mut_p d a) ++ lmap (fun b' => PAnd a b') (mut_p d b)
  | POr a b =>
      lmap (fun a' => POr a' b) (mut_p d a) ++ lmap (fun b' => POr a b') (mut_p d b)
  | PExists q => lmap PExists (mut_q d q)
  | PIn e q => lmap (PIn e) (mut_q d q)
  | _ => []
  end
with mut_q (d : dir) (q : query) {struct q} : list (string * query) :=
  fire_q qrs d q ++
  match q with
  | QTable _ _ => []
  | QProject es a => lmap (QProject es) (mut_q d a)
  | QWhere p a =>
      lmap (fun p' => QWhere p' a) (mut_p d p) ++ lmap (QWhere p) (mut_q d a)
  | QDistinct a => lmap QDistinct (mut_q d a)
  | QUnionAll a b =>
      lmap (fun a' => QUnionAll a' b) (mut_q d a) ++ lmap (QUnionAll a) (mut_q d b)
  | QUnion a b =>
      lmap (fun a' => QUnion a' b) (mut_q d a) ++ lmap (QUnion a) (mut_q d b)
  | QIntersect a b =>
      lmap (fun a' => QIntersect a' b) (mut_q d a) ++ lmap (QIntersect a) (mut_q d b)
  | QExcept a b =>
      lmap (fun a' => QExcept a' b) (mut_q d a) ++ lmap (QExcept a) (mut_q (flip d) b)
  | QInnerJoin p a b =>
      lmap (fun p' => QInnerJoin p' a b) (mut_p d p) ++
      lmap (fun a' => QInnerJoin p a' b) (mut_q d a) ++
      lmap (QInnerJoin p a) (mut_q d b)
  | QLeftJoin n p a b =>
      (* only the LEFT input is monotone; see Counter.v *)
      lmap (fun a' => QLeftJoin n p a' b) (mut_q d a)
  end.

(** ---------------- soundness, for every rule set ---------------- *)

Definition okp (d : dir) (p : pred) (z : string * pred) : Prop := dle p_le d p (snd z).
Definition okq (d : dir) (q : query) (z : string * query) : Prop := dle q_le d q (snd z).

Lemma fire_p_sound : forall rs d p, Forall (okp d p) (fire_p rs d p).
Proof.
  induction rs as [|r rs IH]; intros d p; simpl.
  - apply Forall_nil.
  - rewrite Forall_app; split; [|apply IH].
    destruct (dir_eqb (pr_dir r) d) eqn:E; [|apply Forall_nil].
    apply dir_eqb_eq in E. apply Forall_forall. intros z Hz.
    apply in_map_iff in Hz as [p' [<- Hin]]. unfold okp. simpl.
    rewrite <- E. apply (pr_sound r). exact Hin.
Qed.

Lemma fire_q_sound : forall rs d q, Forall (okq d q) (fire_q rs d q).
Proof.
  induction rs as [|r rs IH]; intros d q; simpl.
  - apply Forall_nil.
  - rewrite Forall_app; split; [|apply IH].
    destruct (dir_eqb (qr_dir r) d) eqn:E; [|apply Forall_nil].
    apply dir_eqb_eq in E. apply Forall_forall. intros z Hz.
    apply in_map_iff in Hz as [q' [<- Hin]]. unfold okq. simpl.
    rewrite <- E. apply (qr_sound r). exact Hin.
Qed.

Lemma fa_mono : forall {X Y : Type} (le_X : X -> X -> Prop) (le_Y : Y -> Y -> Prop)
  (C : X -> Y) d x (l : list (string * X)),
  (forall a b, le_X a b -> le_Y (C a) (C b)) ->
  Forall (fun z => dle le_X d x (snd z)) l ->
  Forall (fun z => dle le_Y d (C x) (snd z)) (lmap C l).
Proof.
  intros X Y le_X le_Y C d x l Hm H. unfold lmap.
  induction H; simpl; [apply Forall_nil|apply Forall_cons].
  - simpl. destruct d; simpl in *; apply Hm; assumption.
  - assumption.
Qed.

Lemma fa_anti : forall {X Y : Type} (le_X : X -> X -> Prop) (le_Y : Y -> Y -> Prop)
  (C : X -> Y) d x (l : list (string * X)),
  (forall a b, le_X a b -> le_Y (C b) (C a)) ->
  Forall (fun z => dle le_X (flip d) x (snd z)) l ->
  Forall (fun z => dle le_Y d (C x) (snd z)) (lmap C l).
Proof.
  intros X Y le_X le_Y C d x l Hm H. unfold lmap.
  induction H; simpl; [apply Forall_nil|apply Forall_cons].
  - simpl. destruct d; simpl in *; apply Hm; assumption.
  - assumption.
Qed.

Definition SP (p : pred) : Prop := forall d, Forall (okp d p) (mut_p d p).
Definition SQ (q : query) : Prop := forall d, Forall (okq d q) (mut_q d q).

Theorem engine_sound : (forall p, SP p) /\ (forall q, SQ q).
Proof.
  apply (pq_ind SP SQ); unfold SP, SQ, okp, okq.
  - intros d. simpl mut_p. rewrite Forall_app; split; [apply fire_p_sound|apply Forall_nil].
  - intros d. simpl mut_p. rewrite Forall_app; split; [apply fire_p_sound|apply Forall_nil].
  - intros c e1 e2 d. simpl mut_p. rewrite Forall_app; split; [apply fire_p_sound|apply Forall_nil].
  - intros e d. simpl mut_p. rewrite Forall_app; split; [apply fire_p_sound|apply Forall_nil].
  - (* PNot: antitone *)
    intros a IHa d. simpl mut_p. rewrite Forall_app; split; [apply fire_p_sound|].
    apply (fa_anti p_le p_le PNot); [|apply IHa].
    intros u v H. apply p_le_not. exact H.
  - (* PAnd *)
    intros a IHa b IHb d. simpl mut_p. rewrite Forall_app; split; [apply fire_p_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono p_le p_le (fun a' => PAnd a' b)); [|apply IHa].
      intros u v H. apply p_le_and; [exact H|apply p_le_refl].
    + apply (fa_mono p_le p_le (fun b' => PAnd a b')); [|apply IHb].
      intros u v H. apply p_le_and; [apply p_le_refl|exact H].
  - (* POr *)
    intros a IHa b IHb d. simpl mut_p. rewrite Forall_app; split; [apply fire_p_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono p_le p_le (fun a' => POr a' b)); [|apply IHa].
      intros u v H. apply p_le_or; [exact H|apply p_le_refl].
    + apply (fa_mono p_le p_le (fun b' => POr a b')); [|apply IHb].
      intros u v H. apply p_le_or; [apply p_le_refl|exact H].
  - (* PExists *)
    intros q IHq d. simpl mut_p. rewrite Forall_app; split; [apply fire_p_sound|].
    apply (fa_mono q_le p_le PExists); [|apply IHq].
    intros u v H. apply p_le_exists. exact H.
  - (* PIn: monotone in the subquery *)
    intros e q IHq d. simpl mut_p. rewrite Forall_app; split; [apply fire_p_sound|].
    apply (fa_mono q_le p_le (PIn e)); [|apply IHq].
    intros u v H. apply p_le_in. exact H.
  - (* PAtom *)
    intros n d. simpl mut_p. rewrite Forall_app; split; [apply fire_p_sound|apply Forall_nil].
  - (* QTable *)
    intros n k d. simpl mut_q. rewrite Forall_app; split; [apply fire_q_sound|apply Forall_nil].
  - (* QProject *)
    intros es a IHa d. simpl mut_q. rewrite Forall_app; split; [apply fire_q_sound|].
    apply (fa_mono q_le q_le (QProject es)); [|apply IHa].
    intros u v H. apply q_le_project. exact H.
  - (* QWhere *)
    intros p IHp a IHa d. simpl mut_q. rewrite Forall_app; split; [apply fire_q_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono p_le q_le (fun p' => QWhere p' a)); [|apply IHp].
      intros u v H. apply q_le_where; [exact H|apply q_le_refl].
    + apply (fa_mono q_le q_le (QWhere p)); [|apply IHa].
      intros u v H. apply q_le_where; [apply p_le_refl|exact H].
  - (* QDistinct *)
    intros a IHa d. simpl mut_q. rewrite Forall_app; split; [apply fire_q_sound|].
    apply (fa_mono q_le q_le QDistinct); [|apply IHa].
    intros u v H. apply q_le_distinct. exact H.
  - (* QUnionAll *)
    intros a IHa b IHb d. simpl mut_q. rewrite Forall_app; split; [apply fire_q_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono q_le q_le (fun a' => QUnionAll a' b)); [|apply IHa].
      intros u v H. apply q_le_union_all; [exact H|apply q_le_refl].
    + apply (fa_mono q_le q_le (QUnionAll a)); [|apply IHb].
      intros u v H. apply q_le_union_all; [apply q_le_refl|exact H].
  - (* QUnion *)
    intros a IHa b IHb d. simpl mut_q. rewrite Forall_app; split; [apply fire_q_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono q_le q_le (fun a' => QUnion a' b)); [|apply IHa].
      intros u v H. apply q_le_union; [exact H|apply q_le_refl].
    + apply (fa_mono q_le q_le (QUnion a)); [|apply IHb].
      intros u v H. apply q_le_union; [apply q_le_refl|exact H].
  - (* QIntersect *)
    intros a IHa b IHb d. simpl mut_q. rewrite Forall_app; split; [apply fire_q_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono q_le q_le (fun a' => QIntersect a' b)); [|apply IHa].
      intros u v H. apply q_le_intersect; [exact H|apply q_le_refl].
    + apply (fa_mono q_le q_le (QIntersect a)); [|apply IHb].
      intros u v H. apply q_le_intersect; [apply q_le_refl|exact H].
  - (* QExcept: the right operand is antitone *)
    intros a IHa b IHb d. simpl mut_q. rewrite Forall_app; split; [apply fire_q_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono q_le q_le (fun a' => QExcept a' b)); [|apply IHa].
      intros u v H. apply q_le_except; [exact H|apply q_le_refl].
    + apply (fa_anti q_le q_le (QExcept a)); [|apply IHb].
      intros u v H. apply q_le_except; [apply q_le_refl|exact H].
  - (* QInnerJoin *)
    intros p IHp a IHa b IHb d. simpl mut_q. rewrite Forall_app; split; [apply fire_q_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono p_le q_le (fun p' => QInnerJoin p' a b)); [|apply IHp].
      intros u v H. apply q_le_inner_join; [exact H|apply q_le_refl|apply q_le_refl].
    + rewrite Forall_app; split.
      * apply (fa_mono q_le q_le (fun a' => QInnerJoin p a' b)); [|apply IHa].
        intros u v H. apply q_le_inner_join; [apply p_le_refl|exact H|apply q_le_refl].
      * apply (fa_mono q_le q_le (QInnerJoin p a)); [|apply IHb].
        intros u v H. apply q_le_inner_join; [apply p_le_refl|apply q_le_refl|exact H].
  - (* QLeftJoin: only the left input is entered *)
    intros n p IHp a IHa b IHb d. simpl mut_q. rewrite Forall_app; split; [apply fire_q_sound|].
    apply (fa_mono q_le q_le (fun a' => QLeftJoin n p a' b)); [|apply IHa].
    intros u v H. apply q_le_left_join_left. exact H.
Qed.

(** The statement used from outside: whatever the rules, a mutant labelled [Up]
    returns a super-bag and a mutant labelled [Down] a sub-bag. *)
Corollary mut_q_sound : forall d q name q',
  In (name, q') (mut_q d q) -> dle q_le d q q'.
Proof.
  intros d q name q' H. destruct engine_sound as [_ Hq].
  exact (proj1 (Forall_forall _ _) (Hq q d) (name, q') H).
Qed.

Corollary mut_p_sound : forall d p name p',
  In (name, p') (mut_p d p) -> dle p_le d p p'.
Proof.
  intros d p name p' H. destruct engine_sound as [Hp _].
  exact (proj1 (Forall_forall _ _) (Hp p d) (name, p') H).
Qed.

End Engine.
