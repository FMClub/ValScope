(** Engine.v: the generic mutator, parametric in the set of rules.

    This is the "compiler" from theorems to mutators.  Given ANY lists of rules
    (Rule.v), [mut_q prs qrs d q] applies every rule of direction [d] at every
    position of [q] where the polarity analysis allows it, flipping the direction
    under NOT and in the right operand of EXCEPT, and never entering positions
    that are neither monotone nor antitone.  Each mutant is labelled with the name
    of the rule that produced it.

    [engine_sound] is proved once, for all rule sets: every mutant is above
    ([Up]) or below ([Down]) the original on every database.  Adding a rule never
    requires touching this file.

    The engine exists in two forms.  [mut_q_in] takes rules that are sound in a class
    of worlds [W] (Rule.v, [prule_in] / [qrule_in]) and is sound in that class
    ([mut_q_in_sound]).  [mut_q] takes rules that are sound in every world; it is
    [mut_q_in] for the class of all worlds ([mut_eq]), from which its soundness
    follows. *)

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

(** ---------------- the generic engine: rules sound in a class of worlds ----------------

    [W] is a class of worlds: all of them, or the worlds of one dialect.  The engine is
    the same recursion as before; its soundness is proved world by world, from the
    monotonicity of every constructor in one world (Approx.v). *)

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

Lemma dle_in_at : forall {X : Type} (le_at : db_t -> X -> X -> Prop) (W : db_t -> Prop) d x y db,
  W db -> dle (fun a b => forall db, W db -> le_at db a b) d x y -> dle (le_at db) d x y.
Proof. intros X le_at W [] x y db HW H; simpl in *; apply H; exact HW. Qed.

Definition fire_p_in {W} (rs : list (prule_in W)) (d : dir) (p : pred) : list (string * pred) :=
  flat_map (fun r => if dir_eqb (pri_dir r) d
                     then map (fun p' => (pri_name r, p')) (pri_fun r p) else []) rs.

Definition fire_q_in {W} (rs : list (qrule_in W)) (d : dir) (q : query) : list (string * query) :=
  flat_map (fun r => if dir_eqb (qri_dir r) d
                     then map (fun q' => (qri_name r, q')) (qri_fun r q) else []) rs.

Section EngineIn.
Variable W : db_t -> Prop.
Variable prs : list (prule_in W).
Variable qrs : list (qrule_in W).

Fixpoint mut_p_in (d : dir) (p : pred) {struct p} : list (string * pred) :=
  fire_p_in prs d p ++
  match p with
  | PNot a => lmap PNot (mut_p_in (flip d) a)
  | PAnd a b =>
      lmap (fun a' => PAnd a' b) (mut_p_in d a) ++ lmap (fun b' => PAnd a b') (mut_p_in d b)
  | POr a b =>
      lmap (fun a' => POr a' b) (mut_p_in d a) ++ lmap (fun b' => POr a b') (mut_p_in d b)
  | PExists q => lmap PExists (mut_q_in d q)
  | PIn e q => lmap (PIn e) (mut_q_in d q)
  | PInT es q => lmap (PInT es) (mut_q_in d q)
  | _ => []
  end
with mut_q_in (d : dir) (q : query) {struct q} : list (string * query) :=
  fire_q_in qrs d q ++
  match q with
  | QTable _ _ => []
  | QProject es a => lmap (QProject es) (mut_q_in d a)
  | QWhere p a =>
      lmap (fun p' => QWhere p' a) (mut_p_in d p) ++ lmap (QWhere p) (mut_q_in d a)
  | QDistinct a => lmap QDistinct (mut_q_in d a)
  | QUnionAll a b =>
      lmap (fun a' => QUnionAll a' b) (mut_q_in d a) ++ lmap (QUnionAll a) (mut_q_in d b)
  | QUnion a b =>
      lmap (fun a' => QUnion a' b) (mut_q_in d a) ++ lmap (QUnion a) (mut_q_in d b)
  | QIntersect a b =>
      lmap (fun a' => QIntersect a' b) (mut_q_in d a) ++ lmap (QIntersect a) (mut_q_in d b)
  | QExcept a b =>
      lmap (fun a' => QExcept a' b) (mut_q_in d a) ++ lmap (QExcept a) (mut_q_in (flip d) b)
  | QIntersectAll a b =>
      lmap (fun a' => QIntersectAll a' b) (mut_q_in d a) ++ lmap (QIntersectAll a) (mut_q_in d b)
  | QExceptAll a b =>
      lmap (fun a' => QExceptAll a' b) (mut_q_in d a) ++ lmap (QExceptAll a) (mut_q_in (flip d) b)
  | QInnerJoin p a b =>
      lmap (fun p' => QInnerJoin p' a b) (mut_p_in d p) ++
      lmap (fun a' => QInnerJoin p a' b) (mut_q_in d a) ++
      lmap (QInnerJoin p a) (mut_q_in d b)
  | QLeftJoin n p a b =>
      (* only the LEFT input is monotone; see Counter.v *)
      lmap (fun a' => QLeftJoin n p a' b) (mut_q_in d a)
  | QNamed n a => lmap (QNamed n) (mut_q_in d a)
  | QAtom _ _ => []
  end.

Section At.
Variable db : db_t.
Hypothesis HW : W db.

Definition okp_at (d : dir) (p : pred) (z : string * pred) : Prop := dle (p_le_at db) d p (snd z).
Definition okq_at (d : dir) (q : query) (z : string * query) : Prop := dle (q_le_at db) d q (snd z).

Lemma fire_p_in_sound : forall (rs : list (prule_in W)) d p, Forall (okp_at d p) (fire_p_in rs d p).
Proof.
  induction rs as [|r rs IH]; intros d p; simpl.
  - apply Forall_nil.
  - rewrite Forall_app; split; [|apply IH].
    destruct (dir_eqb (pri_dir r) d) eqn:E; [|apply Forall_nil].
    apply dir_eqb_eq in E. apply Forall_forall. intros z Hz.
    apply in_map_iff in Hz as [p' [<- Hin]]. unfold okp_at. simpl.
    rewrite <- E. exact (dle_in_at p_le_at W _ _ _ db HW (pri_sound r p p' Hin)).
Qed.

Lemma fire_q_in_sound : forall (rs : list (qrule_in W)) d q, Forall (okq_at d q) (fire_q_in rs d q).
Proof.
  induction rs as [|r rs IH]; intros d q; simpl.
  - apply Forall_nil.
  - rewrite Forall_app; split; [|apply IH].
    destruct (dir_eqb (qri_dir r) d) eqn:E; [|apply Forall_nil].
    apply dir_eqb_eq in E. apply Forall_forall. intros z Hz.
    apply in_map_iff in Hz as [q' [<- Hin]]. unfold okq_at. simpl.
    rewrite <- E. exact (dle_in_at q_le_at W _ _ _ db HW (qri_sound r q q' Hin)).
Qed.

Definition SP (p : pred) : Prop := forall d, Forall (okp_at d p) (mut_p_in d p).
Definition SQ (q : query) : Prop := forall d, Forall (okq_at d q) (mut_q_in d q).

Theorem engine_sound_at : (forall p, SP p) /\ (forall q, SQ q).
Proof.
  apply (pq_ind SP SQ); unfold SP, SQ, okp_at, okq_at.
  - intros d. simpl mut_p_in. rewrite Forall_app; split; [apply fire_p_in_sound|apply Forall_nil].
  - intros d. simpl mut_p_in. rewrite Forall_app; split; [apply fire_p_in_sound|apply Forall_nil].
  - intros c e1 e2 d. simpl mut_p_in. rewrite Forall_app; split; [apply fire_p_in_sound|apply Forall_nil].
  - intros e d. simpl mut_p_in. rewrite Forall_app; split; [apply fire_p_in_sound|apply Forall_nil].
  - (* PNot: antitone *)
    intros a IHa d. simpl mut_p_in. rewrite Forall_app; split; [apply fire_p_in_sound|].
    apply (fa_anti (p_le_at db) (p_le_at db) PNot); [|apply IHa].
    intros u v H. apply p_le_not_at. exact H.
  - (* PAnd *)
    intros a IHa b IHb d. simpl mut_p_in. rewrite Forall_app; split; [apply fire_p_in_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono (p_le_at db) (p_le_at db) (fun a' => PAnd a' b)); [|apply IHa].
      intros u v H. apply p_le_and_at; [exact H|apply p_le_refl_at].
    + apply (fa_mono (p_le_at db) (p_le_at db) (fun b' => PAnd a b')); [|apply IHb].
      intros u v H. apply p_le_and_at; [apply p_le_refl_at|exact H].
  - (* POr *)
    intros a IHa b IHb d. simpl mut_p_in. rewrite Forall_app; split; [apply fire_p_in_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono (p_le_at db) (p_le_at db) (fun a' => POr a' b)); [|apply IHa].
      intros u v H. apply p_le_or_at; [exact H|apply p_le_refl_at].
    + apply (fa_mono (p_le_at db) (p_le_at db) (fun b' => POr a b')); [|apply IHb].
      intros u v H. apply p_le_or_at; [apply p_le_refl_at|exact H].
  - (* PExists *)
    intros q IHq d. simpl mut_p_in. rewrite Forall_app; split; [apply fire_p_in_sound|].
    apply (fa_mono (q_le_at db) (p_le_at db) PExists); [|apply IHq].
    intros u v H. apply p_le_exists_at. exact H.
  - (* PIn: monotone in the subquery *)
    intros e q IHq d. simpl mut_p_in. rewrite Forall_app; split; [apply fire_p_in_sound|].
    apply (fa_mono (q_le_at db) (p_le_at db) (PIn e)); [|apply IHq].
    intros u v H. apply p_le_in_at. exact H.
  - (* PInT: monotone in the subquery *)
    intros es q IHq d. simpl mut_p_in. rewrite Forall_app; split; [apply fire_p_in_sound|].
    apply (fa_mono (q_le_at db) (p_le_at db) (PInT es)); [|apply IHq].
    intros u v H. apply p_le_int_at. exact H.
  - (* PLike *)
    intros e l d. simpl mut_p_in. rewrite Forall_app; split; [apply fire_p_in_sound|apply Forall_nil].
  - (* PRegex *)
    intros e r d. simpl mut_p_in. rewrite Forall_app; split; [apply fire_p_in_sound|apply Forall_nil].
  - (* PAtom *)
    intros n d. simpl mut_p_in. rewrite Forall_app; split; [apply fire_p_in_sound|apply Forall_nil].
  - (* QTable *)
    intros n k d. simpl mut_q_in. rewrite Forall_app; split; [apply fire_q_in_sound|apply Forall_nil].
  - (* QProject *)
    intros es a IHa d. simpl mut_q_in. rewrite Forall_app; split; [apply fire_q_in_sound|].
    apply (fa_mono (q_le_at db) (q_le_at db) (QProject es)); [|apply IHa].
    intros u v H. apply q_le_project_at. exact H.
  - (* QWhere *)
    intros p IHp a IHa d. simpl mut_q_in. rewrite Forall_app; split; [apply fire_q_in_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono (p_le_at db) (q_le_at db) (fun p' => QWhere p' a)); [|apply IHp].
      intros u v H. apply q_le_where_at; [exact H|apply q_le_refl_at].
    + apply (fa_mono (q_le_at db) (q_le_at db) (QWhere p)); [|apply IHa].
      intros u v H. apply q_le_where_at; [apply p_le_refl_at|exact H].
  - (* QDistinct *)
    intros a IHa d. simpl mut_q_in. rewrite Forall_app; split; [apply fire_q_in_sound|].
    apply (fa_mono (q_le_at db) (q_le_at db) QDistinct); [|apply IHa].
    intros u v H. apply q_le_distinct_at. exact H.
  - (* QUnionAll *)
    intros a IHa b IHb d. simpl mut_q_in. rewrite Forall_app; split; [apply fire_q_in_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono (q_le_at db) (q_le_at db) (fun a' => QUnionAll a' b)); [|apply IHa].
      intros u v H. apply q_le_union_all_at; [exact H|apply q_le_refl_at].
    + apply (fa_mono (q_le_at db) (q_le_at db) (QUnionAll a)); [|apply IHb].
      intros u v H. apply q_le_union_all_at; [apply q_le_refl_at|exact H].
  - (* QUnion *)
    intros a IHa b IHb d. simpl mut_q_in. rewrite Forall_app; split; [apply fire_q_in_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono (q_le_at db) (q_le_at db) (fun a' => QUnion a' b)); [|apply IHa].
      intros u v H. apply q_le_union_at; [exact H|apply q_le_refl_at].
    + apply (fa_mono (q_le_at db) (q_le_at db) (QUnion a)); [|apply IHb].
      intros u v H. apply q_le_union_at; [apply q_le_refl_at|exact H].
  - (* QIntersect *)
    intros a IHa b IHb d. simpl mut_q_in. rewrite Forall_app; split; [apply fire_q_in_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono (q_le_at db) (q_le_at db) (fun a' => QIntersect a' b)); [|apply IHa].
      intros u v H. apply q_le_intersect_at; [exact H|apply q_le_refl_at].
    + apply (fa_mono (q_le_at db) (q_le_at db) (QIntersect a)); [|apply IHb].
      intros u v H. apply q_le_intersect_at; [apply q_le_refl_at|exact H].
  - (* QExcept: the right operand is antitone *)
    intros a IHa b IHb d. simpl mut_q_in. rewrite Forall_app; split; [apply fire_q_in_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono (q_le_at db) (q_le_at db) (fun a' => QExcept a' b)); [|apply IHa].
      intros u v H. apply q_le_except_at; [exact H|apply q_le_refl_at].
    + apply (fa_anti (q_le_at db) (q_le_at db) (QExcept a)); [|apply IHb].
      intros u v H. apply q_le_except_at; [apply q_le_refl_at|exact H].
  - (* QIntersectAll: monotone in both operands *)
    intros a IHa b IHb d. simpl mut_q_in. rewrite Forall_app; split; [apply fire_q_in_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono (q_le_at db) (q_le_at db) (fun a' => QIntersectAll a' b)); [|apply IHa].
      intros u v H. apply q_le_intersect_all_at; [exact H|apply q_le_refl_at].
    + apply (fa_mono (q_le_at db) (q_le_at db) (QIntersectAll a)); [|apply IHb].
      intros u v H. apply q_le_intersect_all_at; [apply q_le_refl_at|exact H].
  - (* QExceptAll: the right operand is antitone *)
    intros a IHa b IHb d. simpl mut_q_in. rewrite Forall_app; split; [apply fire_q_in_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono (q_le_at db) (q_le_at db) (fun a' => QExceptAll a' b)); [|apply IHa].
      intros u v H. apply q_le_except_all_at; [exact H|apply q_le_refl_at].
    + apply (fa_anti (q_le_at db) (q_le_at db) (QExceptAll a)); [|apply IHb].
      intros u v H. apply q_le_except_all_at; [apply q_le_refl_at|exact H].
  - (* QInnerJoin *)
    intros p IHp a IHa b IHb d. simpl mut_q_in. rewrite Forall_app; split; [apply fire_q_in_sound|].
    rewrite Forall_app; split.
    + apply (fa_mono (p_le_at db) (q_le_at db) (fun p' => QInnerJoin p' a b)); [|apply IHp].
      intros u v H. apply q_le_inner_join_at; [exact H|apply q_le_refl_at|apply q_le_refl_at].
    + rewrite Forall_app; split.
      * apply (fa_mono (q_le_at db) (q_le_at db) (fun a' => QInnerJoin p a' b)); [|apply IHa].
        intros u v H. apply q_le_inner_join_at; [apply p_le_refl_at|exact H|apply q_le_refl_at].
      * apply (fa_mono (q_le_at db) (q_le_at db) (QInnerJoin p a)); [|apply IHb].
        intros u v H. apply q_le_inner_join_at; [apply p_le_refl_at|apply q_le_refl_at|exact H].
  - (* QLeftJoin: only the left input is entered *)
    intros n p IHp a IHa b IHb d. simpl mut_q_in. rewrite Forall_app; split; [apply fire_q_in_sound|].
    apply (fa_mono (q_le_at db) (q_le_at db) (fun a' => QLeftJoin n p a' b)); [|apply IHa].
    intros u v H. apply q_le_left_join_left_at. exact H.
  - (* QNamed *)
    intros n a IHa d. simpl mut_q_in. rewrite Forall_app; split; [apply fire_q_in_sound|].
    apply (fa_mono (q_le_at db) (q_le_at db) (QNamed n)); [|apply IHa].
    intros u v H. apply q_le_named_at. exact H.
  - (* QAtom: opaque, never entered *)
    intros n k d. simpl mut_q_in. rewrite Forall_app; split; [apply fire_q_in_sound|apply Forall_nil].
Qed.

End At.

(** Whatever the rules, a mutant labelled [Up] returns a super-bag and a mutant
    labelled [Down] a sub-bag, in every world of the class. *)
Corollary mut_q_in_sound : forall d q name q',
  In (name, q') (mut_q_in d q) -> dle (q_le_within W) d q q'.
Proof.
  intros d q name q' H.
  assert (A : forall db, W db -> dle (q_le_at db) d q q').
  { intros db HW. destruct (engine_sound_at db HW) as [_ Hq].
    exact (proj1 (Forall_forall _ _) (Hq q d) (name, q') H). }
  destruct d; simpl in *; intros db HW; exact (A db HW).
Qed.

Corollary mut_p_in_sound : forall d p name p',
  In (name, p') (mut_p_in d p) -> dle (p_le_within W) d p p'.
Proof.
  intros d p name p' H.
  assert (A : forall db, W db -> dle (p_le_at db) d p p').
  { intros db HW. destruct (engine_sound_at db HW) as [Hp _].
    exact (proj1 (Forall_forall _ _) (Hp p d) (name, p') H). }
  destruct d; simpl in *; intros db HW; exact (A db HW).
Qed.

End EngineIn.

Arguments mut_p_in {W}. Arguments mut_q_in {W}.

(** ---------------- the engine for rules sound in every world ---------------- *)

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
  | PInT es q => lmap (PInT es) (mut_q d q)
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
  | QIntersectAll a b =>
      lmap (fun a' => QIntersectAll a' b) (mut_q d a) ++ lmap (QIntersectAll a) (mut_q d b)
  | QExceptAll a b =>
      lmap (fun a' => QExceptAll a' b) (mut_q d a) ++ lmap (QExceptAll a) (mut_q (flip d) b)
  | QInnerJoin p a b =>
      lmap (fun p' => QInnerJoin p' a b) (mut_p d p) ++
      lmap (fun a' => QInnerJoin p a' b) (mut_q d a) ++
      lmap (QInnerJoin p a) (mut_q d b)
  | QLeftJoin n p a b =>
      (* only the LEFT input is monotone; see Counter.v *)
      lmap (fun a' => QLeftJoin n p a' b) (mut_q d a)
  | QNamed n a => lmap (QNamed n) (mut_q d a)
  | QAtom _ _ => []
  end.

(** It is the generic engine, in the class of all worlds. *)
Lemma fire_p_eq : forall rs d p, fire_p rs d p = fire_p_in (map (prule_at all_worlds) rs) d p.
Proof. induction rs as [|r rs IH]; intros d p; simpl; [reflexivity|]. rewrite IH. reflexivity. Qed.

Lemma fire_q_eq : forall rs d q, fire_q rs d q = fire_q_in (map (qrule_at all_worlds) rs) d q.
Proof. induction rs as [|r rs IH]; intros d q; simpl; [reflexivity|]. rewrite IH. reflexivity. Qed.

Lemma mut_eq :
  (forall p d, mut_p d p = mut_p_in (map (prule_at all_worlds) prs) (map (qrule_at all_worlds) qrs) d p) /\
  (forall q d, mut_q d q = mut_q_in (map (prule_at all_worlds) prs) (map (qrule_at all_worlds) qrs) d q).
Proof.
  apply (pq_ind
    (fun p => forall d, mut_p d p = mut_p_in (map (prule_at all_worlds) prs) (map (qrule_at all_worlds) qrs) d p)
    (fun q => forall d, mut_q d q = mut_q_in (map (prule_at all_worlds) prs) (map (qrule_at all_worlds) qrs) d q));
  intros; simpl; rewrite ?fire_p_eq, ?fire_q_eq;
  repeat match goal with H : forall d, _ = _ |- _ => rewrite H; clear H end; reflexivity.
Qed.

(** The statement used from outside: whatever the rules, a mutant labelled [Up]
    returns a super-bag and a mutant labelled [Down] a sub-bag. *)
Corollary mut_q_sound : forall d q name q',
  In (name, q') (mut_q d q) -> dle q_le d q q'.
Proof.
  intros d q name q' H. rewrite (proj2 mut_eq) in H.
  apply dle_q_within_all. exact (mut_q_in_sound _ _ _ d q name q' H).
Qed.

Corollary mut_p_sound : forall d p name p',
  In (name, p') (mut_p d p) -> dle p_le d p p'.
Proof.
  intros d p name p' H. rewrite (proj1 mut_eq) in H.
  apply dle_p_within_all. exact (mut_p_in_sound _ _ _ d p name p' H).
Qed.

Definition okp (d : dir) (p : pred) (z : string * pred) : Prop := dle p_le d p (snd z).
Definition okq (d : dir) (q : query) (z : string * query) : Prop := dle q_le d q (snd z).

Theorem engine_sound :
  (forall p d, Forall (okp d p) (mut_p d p)) /\ (forall q d, Forall (okq d q) (mut_q d q)).
Proof.
  split; intros x d; apply Forall_forall; intros [name y] H; unfold okp, okq; simpl.
  - exact (mut_p_sound d x name y H).
  - exact (mut_q_sound d x name y H).
Qed.

End Engine.
