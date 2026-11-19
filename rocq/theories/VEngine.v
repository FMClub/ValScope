(** VEngine.v: plug-in interface and generic engine for value-semantic rules.

    A value rule rewrites a select item at its root and comes with a theorem:
    on every group of rows, the value of the rewritten item stands in the rule's
    value relation to the value of the original item.

    The engine applies every rule to every select item of a value query, at the
    root of the item and inside monotone contexts (addition, multiplication by a
    non-negative constant, monotone functions), where only the relations [VLe]
    and [VGe] survive.  [vmut_sound] is proved once, for all rule sets: the rows
    of the original and of the mutant correspond one to one, agree outside the
    mutated column, and are related by the rule's relation inside it. *)

From Coq Require Import List String ZArith Reals Lra.
Import ListNotations.
From ValScope Require Import Logic3 Syntax Semantics Value.

Record vrule : Type := mk_vrule {
  vr_name  : string;
  vr_rel   : vrel;
  vr_fun   : aexpr -> list aexpr;
  vr_sound : forall a a', In a' (vr_fun a) ->
             forall env g, rel_holds vr_rel (aeval env g a) (aeval env g a')
}.

(** A mutant of an item: rule name, relation, new item. *)
Definition vmutant : Type := (string * (vrel * aexpr))%type.

Definition vfire (rs : list vrule) (a : aexpr) : list vmutant :=
  flat_map (fun r => map (fun a' => (vr_name r, (vr_rel r, a'))) (vr_fun r a)) rs.

(** Keep the mutants whose relation survives a monotone context and rebuild it. *)
Definition vctx (C : aexpr -> aexpr) (l : list vmutant) : list vmutant :=
  map (fun z => (fst z, (fst (snd z), C (snd (snd z)))))
      (filter (fun z => is_mono (fst (snd z))) l).

Section VEngine.
Variable rs : list vrule.

Fixpoint mut_a (a : aexpr) : list vmutant :=
  vfire rs a ++
  match a with
  | AAdd x y => vctx (fun x' => AAdd x' y) (mut_a x) ++ vctx (fun y' => AAdd x y') (mut_a y)
  | AMul x y =>
      match y with
      | AConst k => if (0 <=? k)%Z then vctx (fun x' => AMul x' (AConst k)) (mut_a x) else []
      | _ => []
      end
  | AMono f x => vctx (AMono f) (mut_a x)
  | _ => []
  end.

Definition vok (a : aexpr) (z : vmutant) : Prop :=
  forall env g, rel_holds (fst (snd z)) (aeval env g a) (aeval env g (snd (snd z))).

Lemma vfire_sound : forall l a, Forall (vok a) (vfire l a).
Proof.
  induction l as [|r l IH]; intros a; simpl.
  - apply Forall_nil.
  - rewrite Forall_app; split; [|apply IH].
    apply Forall_forall. intros z Hz. apply in_map_iff in Hz as [a' [<- Hin]].
    unfold vok. simpl. intros env g. apply (vr_sound r). exact Hin.
Qed.

Lemma vctx_sound : forall (C : aexpr -> aexpr) x l,
  (forall r x', is_mono r = true ->
     (forall env g, rel_holds r (aeval env g x) (aeval env g x')) ->
     forall env g, rel_holds r (aeval env g (C x)) (aeval env g (C x'))) ->
  Forall (vok x) l -> Forall (vok (C x)) (vctx C l).
Proof.
  intros C x l HC H. unfold vctx. apply Forall_forall. intros z Hz.
  apply in_map_iff in Hz as [w [<- Hw]]. apply filter_In in Hw as [Hin Hm].
  unfold vok. simpl. apply HC; [exact Hm|].
  exact (proj1 (Forall_forall _ _) H w Hin).
Qed.

Theorem mut_a_sound : forall a, Forall (vok a) (mut_a a).
Proof.
  induction a; simpl mut_a; rewrite Forall_app; split; try apply vfire_sound;
    try apply Forall_nil.
  - (* AAdd *)
    rewrite Forall_app; split.
    + apply (vctx_sound (fun x' => AAdd x' a2)); [|exact IHa1].
      intros r x' Hm H env g. simpl. apply ctx_add_l; [exact Hm|apply H].
    + apply (vctx_sound (fun y' => AAdd a1 y')); [|exact IHa2].
      intros r y' Hm H env g. simpl. apply ctx_add_r; [exact Hm|apply H].
  - (* AMul by a non-negative constant *)
    destruct a2; try apply Forall_nil.
    destruct (0 <=? z)%Z eqn:E; [|apply Forall_nil]. apply Z.leb_le in E.
    apply (vctx_sound (fun x' => AMul x' (AConst z))); [|exact IHa1].
    intros r x' Hm H env g. simpl. apply ctx_mul_const; [exact Hm|exact E|apply H].
  - (* AMono *)
    apply (vctx_sound (AMono n)); [|exact IHa].
    intros r x' Hm H env g. simpl. specialize (H env g).
    destruct r; try discriminate;
      destruct (aeval env g a), (aeval env g x'); simpl in *; try tauto;
      apply mfn_mono; exact H.
Qed.

(** ---------------- value queries ---------------- *)

(** All ways to single out one element of a list. *)
Fixpoint splits {X : Type} (l : list X) : list (list X * X * list X) :=
  match l with
  | [] => []
  | x :: t => ([], x, t) :: map (fun s => (x :: fst (fst s), snd (fst s), snd s)) (splits t)
  end.

Lemma splits_spec : forall {X : Type} (l : list X) pre x post,
  In (pre, x, post) (splits l) -> l = (pre ++ x :: post)%list.
Proof.
  induction l as [|y t IH]; intros pre x post H; simpl in H; [contradiction|].
  destruct H as [H|H].
  - inversion H; subst. reflexivity.
  - apply in_map_iff in H as [[[p a] q] [E Hin]]. simpl in E. inversion E; subst.
    simpl. f_equal. apply IH. exact Hin.
Qed.

(** A mutant of a value query: rule name, relation, mutated column, new query. *)
Definition qmutant : Type := (string * (vrel * (nat * vquery)))%type.

Definition vmut (v : vquery) : list qmutant :=
  flat_map (fun s =>
      let pre := fst (fst s) in let a := snd (fst s) in let post := snd s in
      map (fun m => (fst m, (fst (snd m), (List.length pre, with_items v (pre ++ snd (snd m) :: post)%list))))
          (mut_a a))
    (splits (vitems v)).

Theorem vmut_sound : forall v name r j v',
  In (name, (r, (j, v'))) (vmut v) ->
  forall env db, Forall2 (row_rel r j) (veval env db v) (veval env db v').
Proof.
  intros v name r j v' H env db. unfold vmut in H.
  apply in_flat_map in H as [[[pre a] post] [Hs Hm]]. simpl in Hm.
  apply in_map_iff in Hm as [[n [r0 a']] [E Hin]]. simpl in E. inversion E; subst. clear E.
  apply splits_spec in Hs.
  pose proof (proj1 (Forall_forall _ _) (mut_a_sound a) _ Hin) as Hok.
  unfold vok in Hok. simpl in Hok.
  unfold veval. rewrite vgroups_with_items, vitems_with_items, Hs.
  induction (vgroups db v) as [|g gs IH]; simpl; constructor; [|exact IH].
  exists (map (aeval env g) pre), (aeval env g a), (aeval env g a'), (map (aeval env g) post).
  rewrite !map_app. simpl. repeat split; try reflexivity.
  - apply map_length.
  - apply Hok.
Qed.

End VEngine.
