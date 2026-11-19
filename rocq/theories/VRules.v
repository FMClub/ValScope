(** VRules.v: the value-semantic rules 18-26 of mutation.md as plug-ins.

    Each rule is a root rewrite of a select item plus a theorem relating the value
    of the rewritten item to the value of the original, on every group of rows.
    Data-dependent preconditions of the original rule table (sign of the value,
    below or above 1) are part of the relation instead of being assumed. *)

From Coq Require Import List String ZArith Reals Lra Lia.
Import ListNotations.
From ValScope Require Import Logic3 Syntax Semantics Value VEngine.
Local Open Scope string_scope.
Local Open Scope R_scope.

(** Rule 18: COUNT(DISTINCT c) -> COUNT(c) *)
Definition f_countd_count (a : aexpr) : list aexpr :=
  match a with ACountD e => [ACount e] | _ => [] end.

Theorem f_countd_count_sound : forall a a', In a' (f_countd_count a) ->
  forall env g, rel_holds VLe (aeval env g a) (aeval env g a').
Proof.
  intros a a' H env g. destruct a; simpl in H; try contradiction.
  destruct H as [<-|[]]. simpl. apply IZR_le. unfold zlen.
  apply Nat2Z.inj_le. apply length_nodup_le.
Qed.

Definition r_countd_count : vrule :=
  mk_vrule "COUNT-DISTINCT->COUNT" VLe f_countd_count f_countd_count_sound.

(** Rule 18 backwards: COUNT(c) -> COUNT(DISTINCT c) *)
Definition f_count_countd (a : aexpr) : list aexpr :=
  match a with ACount e => [ACountD e] | _ => [] end.

Theorem f_count_countd_sound : forall a a', In a' (f_count_countd a) ->
  forall env g, rel_holds VGe (aeval env g a) (aeval env g a').
Proof.
  intros a a' H env g. destruct a; simpl in H; try contradiction.
  destruct H as [<-|[]]. simpl. apply IZR_le. unfold zlen.
  apply Nat2Z.inj_le. apply length_nodup_le.
Qed.

Definition r_count_countd : vrule :=
  mk_vrule "COUNT->COUNT-DISTINCT" VGe f_count_countd f_count_countd_sound.

(** Rule 19: AVG(c) -> MAX(c) *)
Definition f_avg_max (a : aexpr) : list aexpr :=
  match a with AAvg e => [AMax e] | _ => [] end.

Lemma mean_le_max : forall x t, mean (x :: t) <= IZR (fold_right Z.max x t).
Proof.
  intros x t. set (l := x :: t). set (m := fold_right Z.max x t).
  assert (Hs : (zsum l <= zlen l * m)%Z).
  { apply zsum_le. intros y Hy. apply max_ge. exact Hy. }
  assert (Hn : 0 < IZR (zlen l)).
  { apply IZR_lt. unfold zlen. subst l. cbn [List.length]. rewrite Nat2Z.inj_succ. lia. }
  apply IZR_le in Hs. rewrite mult_IZR in Hs.
  unfold mean, Rdiv. apply Rmult_le_reg_r with (IZR (zlen l)); [exact Hn|].
  rewrite Rmult_assoc, Rinv_l by (apply Rgt_not_eq; exact Hn). nra.
Qed.

Theorem f_avg_max_sound : forall a a', In a' (f_avg_max a) ->
  forall env g, rel_holds VLe (aeval env g a) (aeval env g a').
Proof.
  intros a a' H env g. destruct a; simpl in H; try contradiction.
  destruct H as [<-|[]]. simpl. destruct (col e g) as [|x t]; simpl; [exact I|].
  apply mean_le_max.
Qed.

Definition r_avg_max : vrule := mk_vrule "AVG->MAX" VLe f_avg_max f_avg_max_sound.

(** Rule 20: MIN(c) -> MAX(c), and backwards MAX(c) -> MIN(c) *)
Definition f_min_max (a : aexpr) : list aexpr :=
  match a with AMin e => [AMax e] | _ => [] end.

Lemma min_le_max : forall x t, (fold_right Z.min x t <= fold_right Z.max x t)%Z.
Proof.
  intros x t. apply Z.le_trans with x.
  - apply min_le. left. reflexivity.
  - apply max_ge. left. reflexivity.
Qed.

Theorem f_min_max_sound : forall a a', In a' (f_min_max a) ->
  forall env g, rel_holds VLe (aeval env g a) (aeval env g a').
Proof.
  intros a a' H env g. destruct a; simpl in H; try contradiction.
  destruct H as [<-|[]]. simpl. destruct (col e g) as [|x t]; simpl; [exact I|].
  apply IZR_le. apply min_le_max.
Qed.

Definition r_min_max : vrule := mk_vrule "MIN->MAX" VLe f_min_max f_min_max_sound.

Definition f_max_min (a : aexpr) : list aexpr :=
  match a with AMax e => [AMin e] | _ => [] end.

Theorem f_max_min_sound : forall a a', In a' (f_max_min a) ->
  forall env g, rel_holds VGe (aeval env g a) (aeval env g a').
Proof.
  intros a a' H env g. destruct a; simpl in H; try contradiction.
  destruct H as [<-|[]]. simpl. destruct (col e g) as [|x t]; simpl; [exact I|].
  apply IZR_le. apply min_le_max.
Qed.

Definition r_max_min : vrule := mk_vrule "MAX->MIN" VGe f_max_min f_max_min_sound.

(** Rule 21: VAR_SAMP(c) -> STDDEV_SAMP(c).  The value moves toward 1. *)
Definition f_var_std (a : aexpr) : list aexpr :=
  match a with AVarSamp e => [AStdSamp e] | _ => [] end.

Theorem f_var_std_sound : forall a a', In a' (f_var_std a) ->
  forall env g, rel_holds VTowardOne (aeval env g a) (aeval env g a').
Proof.
  intros a a' H env g. destruct a; simpl in H; try contradiction.
  destruct H as [<-|[]]. simpl.
  destruct (var_samp (col e g)) as [v|] eqn:E; [|exact I].
  apply sqrt_toward_one. eapply var_samp_nonneg. exact E.
Qed.

Definition r_var_std : vrule :=
  mk_vrule "VAR_SAMP->STDDEV_SAMP" VTowardOne f_var_std f_var_std_sound.

(** Rule 22: STDDEV_SAMP(c) -> VAR_SAMP(c).  The value moves away from 1. *)
Definition f_std_var (a : aexpr) : list aexpr :=
  match a with AStdSamp e => [AVarSamp e] | _ => [] end.

Theorem f_std_var_sound : forall a a', In a' (f_std_var a) ->
  forall env g, rel_holds VAwayOne (aeval env g a) (aeval env g a').
Proof.
  intros a a' H env g. destruct a; simpl in H; try contradiction.
  destruct H as [<-|[]]. simpl.
  destruct (var_samp (col e g)) as [v|] eqn:E; [|exact I].
  apply sq_away_one. eapply var_samp_nonneg. exact E.
Qed.

Definition r_std_var : vrule :=
  mk_vrule "STDDEV_SAMP->VAR_SAMP" VAwayOne f_std_var f_std_var_sound.

(** Rule 23: SUM(c) -> SUM(c * k), k >= 1.  The sum moves away from 0. *)
Section Scale.
Variable k : Z.
Hypothesis Hk : (1 <= k)%Z.

Definition f_sum_scale (a : aexpr) : list aexpr :=
  match a with ASum e => [ASum (EMul e (EConst (VInt k)))] | _ => [] end.

Lemma away_zero_scale : forall x, rel_R VAwayZero x (x * IZR k).
Proof.
  intros x. apply IZR_le in Hk. simpl. split; intro H; nra.
Qed.

Theorem f_sum_scale_sound : forall a a', In a' (f_sum_scale a) ->
  forall env g, rel_holds VAwayZero (aeval env g a) (aeval env g a').
Proof.
  intros a a' H env g. destruct a; simpl in H; try contradiction.
  destruct H as [<-|[]]. cbn [aeval]. rewrite col_scale.
  destruct (col e g) as [|x t]; [exact I|].
  cbn [map]. cbv iota beta.
  change ((x * k)%Z :: map (fun z => (z * k)%Z) t) with (map (fun z => (z * k)%Z) (x :: t)).
  rewrite zsum_scale, mult_IZR. apply away_zero_scale.
Qed.

(** Rule 25: expr -> expr * k, k >= 1 *)
Definition f_scale (a : aexpr) : list aexpr := [AMul a (AConst k)].

Theorem f_scale_sound : forall a a', In a' (f_scale a) ->
  forall env g, rel_holds VAwayZero (aeval env g a) (aeval env g a').
Proof.
  intros a a' H env g. destruct H as [<-|[]]. simpl.
  destruct (aeval env g a) as [x|]; simpl; [|exact I]. apply away_zero_scale.
Qed.

End Scale.

Definition r_sum_scale (k : Z) (Hk : (1 <= k)%Z) : vrule :=
  mk_vrule "SUM(c)->SUM(c*k)" VAwayZero (f_sum_scale k) (f_sum_scale_sound k Hk).

Definition r_scale (k : Z) (Hk : (1 <= k)%Z) : vrule :=
  mk_vrule "expr->expr*k" VAwayZero (f_scale k) (f_scale_sound k Hk).

(** Rule 24: expr -> expr + k, k > 0 *)
Section Shift.
Variable k : Z.
Hypothesis Hk : (0 < k)%Z.

Definition f_shift (a : aexpr) : list aexpr := [AAdd a (AConst k)].

Theorem f_shift_sound : forall a a', In a' (f_shift a) ->
  forall env g, rel_holds VLe (aeval env g a) (aeval env g a').
Proof.
  intros a a' H env g. destruct H as [<-|[]]. simpl. apply IZR_lt in Hk.
  destruct (aeval env g a) as [x|]; simpl; [lra|exact I].
Qed.

(** Rule 26, first form: FUNC(a) -> FUNC(a + k) for a monotone FUNC *)
Definition f_mono_shift (a : aexpr) : list aexpr :=
  match a with AMono f x => [AMono f (AAdd x (AConst k))] | _ => [] end.

Theorem f_mono_shift_sound : forall a a', In a' (f_mono_shift a) ->
  forall env g, rel_holds VLe (aeval env g a) (aeval env g a').
Proof.
  intros a a' H env g. destruct a; simpl in H; try contradiction.
  destruct H as [<-|[]]. simpl. apply IZR_lt in Hk.
  destruct (aeval env g a) as [x|]; simpl; [|exact I]. apply mfn_mono. lra.
Qed.

End Shift.

Definition r_shift (k : Z) (Hk : (0 < k)%Z) : vrule :=
  mk_vrule "expr->expr+k" VLe (f_shift k) (f_shift_sound k Hk).

Definition r_mono_shift (k : Z) (Hk : (0 < k)%Z) : vrule :=
  mk_vrule "FUNC(a)->FUNC(a+k)" VLe (f_mono_shift k) (f_mono_shift_sound k Hk).

(** Rule 26, second form: FUNC(c) -> FUNC(c * k) for a monotone FUNC, k >= 1.
    The rule table states it for k > 0 only; it needs c >= 0 as well.  The
    argument's sign is not visible in the result, so the rule fires only when
    the argument is non-negative by construction. *)
Fixpoint nonneg (a : aexpr) : bool :=
  match a with
  | ACount _ | ACountD _ => true
  | AConst k => (0 <=? k)%Z
  | AAdd x y | AMul x y => nonneg x && nonneg y
  | _ => false
  end.

Lemma nonneg_sound : forall a, nonneg a = true ->
  forall env g x, aeval env g a = Some x -> 0 <= x.
Proof.
  induction a; simpl; intros Hn env g x H; try discriminate.
  - inversion H; subst. apply IZR_le. apply Z.leb_le. exact Hn.
  - inversion H; subst. apply IZR_le. unfold zlen. lia.
  - inversion H; subst. apply IZR_le. unfold zlen. lia.
  - apply andb_prop in Hn as [H1 H2].
    destruct (aeval env g a1) as [u|] eqn:E1; destruct (aeval env g a2) as [w|] eqn:E2;
      simpl in H; try discriminate. inversion H; subst.
    specialize (IHa1 H1 env g u E1). specialize (IHa2 H2 env g w E2). lra.
  - apply andb_prop in Hn as [H1 H2].
    destruct (aeval env g a1) as [u|] eqn:E1; destruct (aeval env g a2) as [w|] eqn:E2;
      simpl in H; try discriminate. inversion H; subst.
    specialize (IHa1 H1 env g u E1). specialize (IHa2 H2 env g w E2).
    apply Rmult_le_pos; assumption.
Qed.

Section MonoScale.
Variable k : Z.
Hypothesis Hk : (1 <= k)%Z.

Definition f_mono_scale (a : aexpr) : list aexpr :=
  match a with
  | AMono f x => if nonneg x then [AMono f (AMul x (AConst k))] else []
  | _ => []
  end.

Theorem f_mono_scale_sound : forall a a', In a' (f_mono_scale a) ->
  forall env g, rel_holds VLe (aeval env g a) (aeval env g a').
Proof.
  intros a a' H env g. destruct a; simpl in H; try contradiction.
  destruct (nonneg a) eqn:Hn; simpl in H; [|contradiction].
  destruct H as [<-|[]]. simpl. apply IZR_le in Hk.
  destruct (aeval env g a) as [x|] eqn:E; simpl; [|exact I].
  apply mfn_mono. pose proof (nonneg_sound a Hn env g x E). nra.
Qed.

End MonoScale.

Definition r_mono_scale (k : Z) (Hk : (1 <= k)%Z) : vrule :=
  mk_vrule "FUNC(c)->FUNC(c*k)" VLe (f_mono_scale k) (f_mono_scale_sound k Hk).
