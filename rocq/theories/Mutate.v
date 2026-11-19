(** Mutate.v: the set-semantic mutators and their soundness proof.

    [mut_q d q] lists every query obtained from [q] by ONE application of a rewrite
    rule somewhere in [q].  The direction [d] says what the mutation does to the
    result of the whole query:
    - [Up]   : the mutant returns a super-bag   ([q] is below the mutant),
    - [Down] : the mutant returns a sub-bag     (the mutant is below [q]).

    Positions are traversed with the polarity of Approx.v: below a NOT or in the
    right operand of EXCEPT the direction flips.  Positions that are neither
    monotone nor antitone (ON condition and right input of a LEFT JOIN) are never
    entered, so nothing there is ever mutated.

    [mutate_sound] proves that every generated mutant stands in the claimed
    relation to the original, for every database. *)

From Coq Require Import List.
Import ListNotations.
From ValScope Require Import Bag Logic3 Syntax Semantics Approx.

Inductive dir : Type := Up | Down.

Definition flip (d : dir) : dir := match d with Up => Down | Down => Up end.

(** [dle le d x y]: [Up] means [x] is below [y]; [Down] means [y] is below [x]. *)
Definition dle {X : Type} (le : X -> X -> Prop) (d : dir) (x y : X) : Prop :=
  match d with Up => le x y | Down => le y x end.

(** Rewrites that apply at the root of a predicate. *)
Definition base_p (d : dir) (p : pred) : list pred :=
  match d with
  | Up =>
      (match p with PTrue => [] | _ => [PTrue] end) ++
      (match p with
       | PAnd a b => [a; b]
       | PCmp CLt x y => [PCmp CLe x y; PCmp CNe x y]
       | PCmp CGt x y => [PCmp CGe x y; PCmp CNe x y]
       | PCmp CEq x y => [PCmp CLe x y; PCmp CGe x y]
       | _ => []
       end)
  | Down =>
      (match p with PFalse => [] | _ => [PFalse] end) ++
      (match p with
       | POr a b => [a; b]
       | PCmp CLe x y => [PCmp CLt x y; PCmp CEq x y]
       | PCmp CGe x y => [PCmp CGt x y; PCmp CEq x y]
       | PCmp CNe x y => [PCmp CLt x y; PCmp CGt x y]
       | _ => []
       end)
  end.

(** Rewrites that apply at the root of a query. *)
Definition base_q (d : dir) (q : query) : list query :=
  match d with
  | Up =>
      match q with
      | QDistinct a => [a]                                (* rule 1 *)
      | QUnion a b => [QUnionAll a b]                     (* rule 2 *)
      | QIntersect a b => [QUnion a b]                    (* rule 4 *)
      | QExcept a b => [a]                                (* rule 3 *)
      | QInnerJoin p a b => [QLeftJoin (arity b) p a b]   (* rule 17 *)
      | _ => []
      end
  | Down =>
      (match q with QDistinct _ => [] | _ => [QDistinct q] end) ++
      (match q with
       | QUnionAll a b => [QUnion a b]
       | QUnion a b => [QIntersect a b]
       | QLeftJoin _ p a b => [QInnerJoin p a b]
       | _ => []
       end)
  end.

Arguments base_p : simpl never.
Arguments base_q : simpl never.

Fixpoint mut_p (d : dir) (p : pred) {struct p} : list pred :=
  base_p d p ++
  match p with
  | PNot a => map PNot (mut_p (flip d) a)
  | PAnd a b =>
      map (fun a' => PAnd a' b) (mut_p d a) ++ map (fun b' => PAnd a b') (mut_p d b)
  | POr a b =>
      map (fun a' => POr a' b) (mut_p d a) ++ map (fun b' => POr a b') (mut_p d b)
  | PExists q => map PExists (mut_q d q)
  | _ => []
  end
with mut_q (d : dir) (q : query) {struct q} : list query :=
  base_q d q ++
  match q with
  | QTable _ _ => []
  | QProject es a => map (QProject es) (mut_q d a)
  | QWhere p a =>
      map (fun p' => QWhere p' a) (mut_p d p) ++ map (QWhere p) (mut_q d a)
  | QDistinct a => map QDistinct (mut_q d a)
  | QUnionAll a b =>
      map (fun a' => QUnionAll a' b) (mut_q d a) ++ map (QUnionAll a) (mut_q d b)
  | QUnion a b =>
      map (fun a' => QUnion a' b) (mut_q d a) ++ map (QUnion a) (mut_q d b)
  | QIntersect a b =>
      map (fun a' => QIntersect a' b) (mut_q d a) ++ map (QIntersect a) (mut_q d b)
  | QExcept a b =>
      map (fun a' => QExcept a' b) (mut_q d a) ++ map (QExcept a) (mut_q (flip d) b)
  | QInnerJoin p a b =>
      map (fun p' => QInnerJoin p' a b) (mut_p d p) ++
      map (fun a' => QInnerJoin p a' b) (mut_q d a) ++
      map (QInnerJoin p a) (mut_q d b)
  | QLeftJoin n p a b =>
      (* only the LEFT input is monotone; the ON condition and the right input are not *)
      map (fun a' => QLeftJoin n p a' b) (mut_q d a)
  end.

(** ---------------- soundness ---------------- *)

Lemma fa_map_mono : forall {X Y : Type} (le_X : X -> X -> Prop) (le_Y : Y -> Y -> Prop)
  (C : X -> Y) d x l,
  (forall a b, le_X a b -> le_Y (C a) (C b)) ->
  Forall (dle le_X d x) l -> Forall (dle le_Y d (C x)) (map C l).
Proof.
  intros X Y le_X le_Y C d x l Hm H. induction H; simpl; constructor.
  - destruct d; simpl in *; apply Hm; assumption.
  - assumption.
Qed.

Lemma fa_map_anti : forall {X Y : Type} (le_X : X -> X -> Prop) (le_Y : Y -> Y -> Prop)
  (C : X -> Y) d x l,
  (forall a b, le_X a b -> le_Y (C b) (C a)) ->
  Forall (dle le_X (flip d) x) l -> Forall (dle le_Y d (C x)) (map C l).
Proof.
  intros X Y le_X le_Y C d x l Hm H. induction H; simpl; constructor.
  - destruct d; simpl in *; apply Hm; assumption.
  - assumption.
Qed.

Ltac solve_p :=
  first [ apply p_le_true | apply p_le_false | apply p_le_and_l | apply p_le_and_r
        | apply p_le_or_l | apply p_le_or_r
        | (apply p_le_cmp; constructor) ].

(** Split [Forall P [a; b; ...]] into one goal per element, solved by [tac]. *)
Ltac fa_solve tac :=
  match goal with
  | |- Forall _ [] => apply Forall_nil
  | |- Forall _ (_ :: _) => apply Forall_cons; [ tac | fa_solve tac ]
  end.

Lemma base_p_sound : forall d p, Forall (dle p_le d p) (base_p d p).
Proof.
  intros d p. unfold base_p. destruct d; destruct p; try (destruct c);
    simpl; fa_solve solve_p.
Qed.

Ltac solve_q :=
  first [ apply q_le_distinct_base | apply q_le_union_base | apply q_le_inter_base
        | apply q_le_except_base | apply q_le_inner_left ].

Lemma base_q_sound : forall d q, Forall (dle q_le d q) (base_q d q).
Proof.
  intros d q. unfold base_q. destruct d; destruct q; simpl; fa_solve solve_q.
Qed.

Definition SP (p : pred) : Prop := forall d, Forall (dle p_le d p) (mut_p d p).
Definition SQ (q : query) : Prop := forall d, Forall (dle q_le d q) (mut_q d q).

Theorem mutate_sound : (forall p, SP p) /\ (forall q, SQ q).
Proof.
  apply (pq_ind SP SQ); unfold SP, SQ.
  - (* PTrue *) intros d. simpl mut_p. rewrite Forall_app; split; [apply base_p_sound|apply Forall_nil].
  - (* PFalse *) intros d. simpl mut_p. rewrite Forall_app; split; [apply base_p_sound|apply Forall_nil].
  - (* PCmp *) intros c e1 e2 d. simpl mut_p. rewrite Forall_app; split; [apply base_p_sound|apply Forall_nil].
  - (* PIsNull *) intros e d. simpl mut_p. rewrite Forall_app; split; [apply base_p_sound|apply Forall_nil].
  - (* PNot *)
    intros a IHa d. simpl mut_p. rewrite Forall_app; split; [apply base_p_sound|].
    apply (fa_map_anti p_le p_le PNot).
    + intros u v H. apply p_le_not. exact H.
    + apply IHa.
  - (* PAnd *)
    intros a IHa b IHb d. simpl mut_p. rewrite Forall_app; split; [apply base_p_sound|].
    rewrite Forall_app; split.
    + apply (fa_map_mono p_le p_le (fun a' => PAnd a' b)).
      * intros u v H. apply p_le_and; [exact H|apply p_le_refl].
      * apply IHa.
    + apply (fa_map_mono p_le p_le (fun b' => PAnd a b')).
      * intros u v H. apply p_le_and; [apply p_le_refl|exact H].
      * apply IHb.
  - (* POr *)
    intros a IHa b IHb d. simpl mut_p. rewrite Forall_app; split; [apply base_p_sound|].
    rewrite Forall_app; split.
    + apply (fa_map_mono p_le p_le (fun a' => POr a' b)).
      * intros u v H. apply p_le_or; [exact H|apply p_le_refl].
      * apply IHa.
    + apply (fa_map_mono p_le p_le (fun b' => POr a b')).
      * intros u v H. apply p_le_or; [apply p_le_refl|exact H].
      * apply IHb.
  - (* PExists *)
    intros q IHq d. simpl mut_p. rewrite Forall_app; split; [apply base_p_sound|].
    apply (fa_map_mono q_le p_le PExists).
    + intros u v H. apply p_le_exists. exact H.
    + apply IHq.
  - (* QTable *) intros n k d. simpl mut_q. rewrite Forall_app; split; [apply base_q_sound|apply Forall_nil].
  - (* QProject *)
    intros es a IHa d. simpl mut_q. rewrite Forall_app; split; [apply base_q_sound|].
    apply (fa_map_mono q_le q_le (QProject es)).
    + intros u v H. apply q_le_project. exact H.
    + apply IHa.
  - (* QWhere *)
    intros p IHp a IHa d. simpl mut_q. rewrite Forall_app; split; [apply base_q_sound|].
    rewrite Forall_app; split.
    + apply (fa_map_mono p_le q_le (fun p' => QWhere p' a)).
      * intros u v H. apply q_le_where; [exact H|apply q_le_refl].
      * apply IHp.
    + apply (fa_map_mono q_le q_le (QWhere p)).
      * intros u v H. apply q_le_where; [apply p_le_refl|exact H].
      * apply IHa.
  - (* QDistinct *)
    intros a IHa d. simpl mut_q. rewrite Forall_app; split; [apply base_q_sound|].
    apply (fa_map_mono q_le q_le QDistinct).
    + intros u v H. apply q_le_distinct. exact H.
    + apply IHa.
  - (* QUnionAll *)
    intros a IHa b IHb d. simpl mut_q. rewrite Forall_app; split; [apply base_q_sound|].
    rewrite Forall_app; split.
    + apply (fa_map_mono q_le q_le (fun a' => QUnionAll a' b)).
      * intros u v H. apply q_le_union_all; [exact H|apply q_le_refl].
      * apply IHa.
    + apply (fa_map_mono q_le q_le (QUnionAll a)).
      * intros u v H. apply q_le_union_all; [apply q_le_refl|exact H].
      * apply IHb.
  - (* QUnion *)
    intros a IHa b IHb d. simpl mut_q. rewrite Forall_app; split; [apply base_q_sound|].
    rewrite Forall_app; split.
    + apply (fa_map_mono q_le q_le (fun a' => QUnion a' b)).
      * intros u v H. apply q_le_union; [exact H|apply q_le_refl].
      * apply IHa.
    + apply (fa_map_mono q_le q_le (QUnion a)).
      * intros u v H. apply q_le_union; [apply q_le_refl|exact H].
      * apply IHb.
  - (* QIntersect *)
    intros a IHa b IHb d. simpl mut_q. rewrite Forall_app; split; [apply base_q_sound|].
    rewrite Forall_app; split.
    + apply (fa_map_mono q_le q_le (fun a' => QIntersect a' b)).
      * intros u v H. apply q_le_intersect; [exact H|apply q_le_refl].
      * apply IHa.
    + apply (fa_map_mono q_le q_le (QIntersect a)).
      * intros u v H. apply q_le_intersect; [apply q_le_refl|exact H].
      * apply IHb.
  - (* QExcept: antitone in the right operand *)
    intros a IHa b IHb d. simpl mut_q. rewrite Forall_app; split; [apply base_q_sound|].
    rewrite Forall_app; split.
    + apply (fa_map_mono q_le q_le (fun a' => QExcept a' b)).
      * intros u v H. apply q_le_except; [exact H|apply q_le_refl].
      * apply IHa.
    + apply (fa_map_anti q_le q_le (QExcept a)).
      * intros u v H. apply q_le_except; [apply q_le_refl|exact H].
      * apply IHb.
  - (* QInnerJoin *)
    intros p IHp a IHa b IHb d. simpl mut_q. rewrite Forall_app; split; [apply base_q_sound|].
    rewrite Forall_app; split.
    + apply (fa_map_mono p_le q_le (fun p' => QInnerJoin p' a b)).
      * intros u v H. apply q_le_inner_join; [exact H|apply q_le_refl|apply q_le_refl].
      * apply IHp.
    + rewrite Forall_app; split.
      * apply (fa_map_mono q_le q_le (fun a' => QInnerJoin p a' b)).
        -- intros u v H. apply q_le_inner_join; [apply p_le_refl|exact H|apply q_le_refl].
        -- apply IHa.
      * apply (fa_map_mono q_le q_le (QInnerJoin p a)).
        -- intros u v H. apply q_le_inner_join; [apply p_le_refl|apply q_le_refl|exact H].
        -- apply IHb.
  - (* QLeftJoin: only the left input is entered *)
    intros n p IHp a IHa b IHb d. simpl mut_q. rewrite Forall_app; split; [apply base_q_sound|].
    apply (fa_map_mono q_le q_le (fun a' => QLeftJoin n p a' b)).
    + intros u v H. apply q_le_left_join_left. exact H.
    + apply IHa.
Qed.

(** The two statements that are used from outside. *)
Corollary mut_q_sound : forall d q q',
  In q' (mut_q d q) -> dle q_le d q q'.
Proof.
  intros d q q' H. destruct mutate_sound as [_ Hq].
  exact (proj1 (Forall_forall _ _) (Hq q d) q' H).
Qed.

Corollary mut_p_sound : forall d p p',
  In p' (mut_p d p) -> dle p_le d p p'.
Proof.
  intros d p p' H. destruct mutate_sound as [Hp _].
  exact (proj1 (Forall_forall _ _) (Hp p d) p' H).
Qed.

Print Assumptions mutate_sound.
